//! Order execution helpers — thin wrappers around `exchange_apiws` REST calls.
//!
//! All actual HTTP logic lives in `exchange_apiws`. This module provides
//! convenience functions that accept `BotSettings` so call sites stay clean.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use crate::BotSettings;
use crate::bot::state::BotState;
use crate::error::{BotError, Result};
use exchange_apiws::rest::orders::OrderResponse;
use exchange_apiws::{KuCoinClient, OrderType, Side};
use tokio::sync::{Mutex, oneshot};
use tracing::{info, warn};

/// Pending fill signals shared between the order executor and the private WS task.
/// Keyed by order-id; the WS task pops and fires on a confirmed fill so
/// `poll_for_fill` can return immediately instead of waiting for the next REST tick.
///
/// This is the single canonical definition — `main.rs` and `strategy.rs`
/// re-export it via `use kucoin::bot::execute::FillSignals`.
pub type FillSignals = Arc<Mutex<HashMap<String, oneshot::Sender<()>>>>;

// ── Limit-order fill constants ────────────────────────────────────────────────

/// How often to poll the exchange to check if a limit order filled.
const FILL_POLL_INTERVAL: Duration = Duration::from_secs(2);

/// After this duration the limit order is presumed unfilled and is cancelled,
/// then a market order is placed as a fallback.
const FILL_POLL_TIMEOUT: Duration = Duration::from_secs(30);

/// Open a new position (market order by default; limit with fill confirmation).
///
/// For limit orders `price` is the limit price sent to the exchange.
/// The function polls for a fill with `FILL_POLL_INTERVAL` ticks, but
/// returns immediately if the private WS task fires a fill signal first.
/// If the order is not filled within `FILL_POLL_TIMEOUT` it is cancelled
/// and a market order is placed as a fallback, so the caller can rely on
/// the position being open when this returns `Ok`.
///
/// `contracts` should come from `sizing::contracts_for_signal`.
///
/// `fill_signals` is the shared map: a `oneshot::Sender` is inserted here
/// (keyed by order-id) and popped by the private WS task on confirmed fill.
pub async fn open_position(
    client: &KuCoinClient,
    side: Side,
    contracts: u32,
    price: f64,
    settings: &BotSettings,
    fill_signals: FillSignals,
) -> Result<OrderResponse> {
    info!(
        symbol    = %settings.symbol,
        side      = ?side,
        contracts = contracts,
        leverage  = settings.leverage,
        price,
        "opening position",
    );

    let order_type = if settings.use_market_orders {
        OrderType::Market
    } else {
        OrderType::Limit
    };

    let limit_price = if order_type == OrderType::Limit {
        Some(price)
    } else {
        None
    };

    let resp = client
        .place_order(
            &settings.symbol,
            side,
            contracts,
            settings.leverage,
            order_type,
            limit_price,
            None,  // time_in_force — default GTC
            false, // reduce_only
            None,  // stp
        )
        .await
        .map_err(BotError::Exchange)?;

    // Market orders are accepted synchronously; only limit orders need
    // fill confirmation.
    if order_type == OrderType::Limit {
        // Register a oneshot sender so the private WS task can signal us
        // the moment it sees the OrderUpdate(filled) event, making REST
        // polling a pure fallback timeout rather than the primary signal.
        let (ws_tx, ws_rx) = oneshot::channel::<()>();
        fill_signals
            .lock()
            .await
            .insert(resp.order_id.clone(), ws_tx);

        let filled = poll_for_fill(client, &resp.order_id, &settings.symbol, ws_rx).await?;

        // Always clean up the map entry regardless of outcome — either the
        // WS task already popped it (on fill) or we timed out and need to
        // prevent a stale sender from accumulating.
        fill_signals.lock().await.remove(&resp.order_id);
        if !filled {
            // Cancel the stale resting limit.  Log a warning if the cancel
            // itself fails — the limit may still be live, so the market
            // fallback could briefly double the position; KuCoin STP and
            // reduce-only semantics should prevent a runaway, but we surface
            // the error so the operator can investigate.
            warn!(
                symbol   = %settings.symbol,
                order_id = %resp.order_id,
                timeout  = ?FILL_POLL_TIMEOUT,
                "limit order unfilled — cancelling and falling back to market",
            );
            if let Err(e) = client.cancel_all_orders(&settings.symbol).await {
                warn!(
                    symbol   = %settings.symbol,
                    order_id = %resp.order_id,
                    err      = %e,
                    "cancel_all_orders failed before market fallback — orphaned limit order possible",
                );
            }

            // Brief pause so the cancel propagates on the exchange side
            // before we place the market order.
            tokio::time::sleep(Duration::from_millis(500)).await;

            let mkt = client
                .place_order(
                    &settings.symbol,
                    side,
                    contracts,
                    settings.leverage,
                    OrderType::Market,
                    None,
                    None,
                    false,
                    None,
                )
                .await
                .map_err(BotError::Exchange)?;

            info!(
                symbol   = %settings.symbol,
                order_id = %mkt.order_id,
                "market fallback order placed",
            );
            return Ok(mkt);
        }
        info!(symbol = %settings.symbol, order_id = %resp.order_id, "limit order filled");
    }

    Ok(resp)
}

/// Poll `GET /api/v1/orders/{orderId}` until the order fills or the deadline.
///
/// `ws_signal` is a oneshot receiver wired from the private WebSocket task.
/// When the WS `OrderUpdate(filled)` event arrives the sender is fired and
/// this function returns `Ok(true)` immediately without waiting for the next
/// REST tick. REST polling is the fallback for when the WS feed is lagging or
/// disconnected.
///
/// Returns `Ok(true)` if the order filled (`filled_size >= size`, or
/// `is_active()` returned `false` after placement — done/cancelled).
/// Returns `Ok(false)` if the timeout elapsed (caller should cancel + retry as
/// market), or `Err` on a hard API failure.
async fn poll_for_fill(
    client: &KuCoinClient,
    order_id: &str,
    symbol: &str,
    ws_signal: oneshot::Receiver<()>,
) -> Result<bool> {
    let deadline = tokio::time::Instant::now() + FILL_POLL_TIMEOUT;
    // Pin the receiver so we can poll it repeatedly inside select!.
    tokio::pin!(ws_signal);

    loop {
        tokio::select! {
            // Primary path: WS fill notification.
            // The private WS task fires this oneshot the moment it sees an
            // OrderUpdate with status == "filled" for this order_id.
            // Returning here skips the REST round-trip entirely.
            _ = &mut ws_signal => {
                info!(symbol, order_id, "WS fill signal received — confirmed without REST poll");
                return Ok(true);
            }

            // Fallback path: REST poll interval.
            // Fires every FILL_POLL_INTERVAL when the WS signal has not arrived.
            () = tokio::time::sleep(FILL_POLL_INTERVAL) => {}
        }

        if tokio::time::Instant::now() >= deadline {
            warn!(symbol, order_id, "limit-order fill poll timed out");
            return Ok(false);
        }

        match tokio::time::timeout(FILL_POLL_INTERVAL, client.get_order(order_id)).await {
            Err(_elapsed) => {
                // REST call timed out — don't count this as an error, just
                // let the outer deadline check decide whether to give up.
            }
            Ok(Ok(detail)) if detail.is_filled() => {
                // All contracts matched — position is open.
                return Ok(true);
            }
            Ok(Ok(detail)) if !detail.is_active() => {
                // Order is done but not fully filled — externally cancelled.
                warn!(
                    symbol, order_id,
                    filled_size = ?detail.filled_size,
                    size        = detail.size,
                    "limit order cancelled externally before fill",
                );
                return Ok(false);
            }
            Ok(Ok(_)) => {} // still resting — keep polling
            Ok(Err(e)) => {
                // Hard error (auth failure, network partition) — propagate so
                // the candle-poll task can log it and skip this candle rather
                // than silently opening on stale state.
                return Err(BotError::Exchange(e));
            }
        }
    }
}

/// Close an open position with a reduce-only market order.
///
/// `current_qty` is the signed position size from `BotState::position.0`.
pub async fn close_position(
    client: &KuCoinClient,
    symbol: &str,
    current_qty: i32,
    leverage: u32,
) -> Result<OrderResponse> {
    info!(symbol, current_qty, "closing position");
    client
        .close_position(symbol, current_qty, leverage)
        .await
        .map_err(BotError::Exchange)
}

/// Place an exchange-enforced stop-market order for an open position.
///
/// This stop survives a process crash because it lives on the exchange, unlike
/// a software stop that disappears when the bot exits. It must be cancelled
/// explicitly before the position is closed or flipped.
///
/// `stop_side` is the opposite of the open position (Sell to stop a long,
/// Buy to stop a short). `stop_price` should be computed from ATR:
///
/// ```text
/// long  stop = entry_price − stop_atr_mult × ATR
/// short stop = entry_price + stop_atr_mult × ATR
/// ```
///
/// Failure is non-fatal: the position is open regardless. The error is
/// logged as a warning so the operator can investigate, but trading
/// continues — the software circuit-breaker provides a secondary safety net.
///
/// # Exchange-crate dependency
/// Requires `KuCoinClient::place_stop_order` exposed by `exchange-apiws`
/// (maps to `POST /api/v1/stopOrders` on the KuCoin Futures REST API).
pub async fn place_hard_stop(
    client: &KuCoinClient,
    symbol: &str,
    stop_side: Side,
    contracts: u32,
    stop_price: f64,
    leverage: u32,
) {
    match client
        .place_stop_order(
            symbol, stop_side, contracts, leverage, stop_price, "", None, true,
        )
        .await
    {
        Ok(resp) => info!(
            symbol,
            order_id = %resp.order_id,
            stop_price,
            "hard stop placed",
        ),
        Err(e) => warn!(
            symbol,
            err = %e,
            stop_price,
            "place_stop_order failed — position has no exchange-enforced hard stop; \
             circuit-breaker is the sole safety net until next candle",
        ),
    }
}

/// Cancel all open orders for a symbol (e.g., on shutdown or breaker trip).
pub async fn cancel_all(client: &KuCoinClient, symbol: &str) -> Result<serde_json::Value> {
    client
        .cancel_all_orders(symbol)
        .await
        .map_err(BotError::Exchange)
}

/// Cancel all open *stop* orders for a symbol.
///
/// KuCoin Futures stop/take-profit orders live on a separate endpoint from
/// regular limit orders (`/api/v1/stopOrders` vs `/api/v1/orders`), so
/// `cancel_all` above will not touch them.
///
/// This is a best-effort call: failure is logged as a warning rather than
/// propagated, because the bot can still trade safely with orphaned stops —
/// the stops will either fill at their price or expire; they won't open new
/// positions. The caller decides whether to treat the error as fatal.
///
/// # Exchange-crate dependency
/// Requires `KuCoinClient::cancel_all_stop_orders(symbol)` to be exposed by
/// `exchange-apiws` (maps to `DELETE /api/v1/stopOrders?symbol=…`).
pub async fn cancel_all_stop_orders(client: &KuCoinClient, symbol: &str) {
    match client.cancel_all_stop_orders(symbol).await {
        Ok(_) => info!(symbol, "orphaned stop orders cleared"),
        Err(e) => warn!(
            symbol,
            err = %e,
            "cancel_all_stop_orders failed — orphaned stops may persist; \
             they will fill or expire naturally but could interfere with new entries"
        ),
    }
}

// ── Startup reconciliation ────────────────────────────────────────────────────

/// Outcome of a startup reconciliation for one symbol.
#[derive(Debug)]
pub enum ReconcileOutcome {
    /// No open position found — bot starts flat.
    Flat,
    /// An open position was found and adopted into state.
    PositionAdopted { qty: i32, entry_price: Option<f64> },
}

/// Reconcile `state` against the live exchange on startup.
///
/// This is the crash-safety step. Without it, a restarted bot assumes it is flat
/// and may open a second position on top of an existing one.
///
/// Behaviour:
/// - Fetches the live position for `symbol` and the USDT account balance.
/// - If the position is flat, nothing changes — logs and returns.
/// - If a position is open, it is adopted: `state.position`, `state.entry_price`,
///   `state.last_signal`, and `state.balance` are all set from the exchange data.
///   The SAR logic will then treat this as an existing position and respect
///   `min_hold_candles` / the circuit breaker before acting on it.
///
/// Only call this in live mode. In sim mode the exchange has no record of
/// simulated trades, so the call would always return flat and zero balance.
pub async fn reconcile_startup(
    client: &KuCoinClient,
    state: &mut BotState,
) -> Result<ReconcileOutcome> {
    let symbol = state.settings.symbol.clone();

    // ── Balance ───────────────────────────────────────────────────────────────
    match client.get_balance("USDT").await {
        Ok(bal) => {
            state.balance = bal;
            info!(symbol, balance = bal, "startup: balance synced");
        }
        Err(e) => {
            // Non-fatal — position sync is what matters for safety.
            warn!(symbol, err = %e, "startup: balance fetch failed — balance left at 0");
        }
    }

    // ── Position ──────────────────────────────────────────────────────────────
    let pos_info = client.get_position(&symbol).await?;

    // Cancel any stop/take-profit orders left over from before a crash,
    // regardless of whether we are flat or have an open position.
    // Duplicate stops stacked on restart would fire at stale prices and
    // potentially over-hedge or interfere with new entries.
    info!(symbol, "startup: cancelling any orphaned stop orders");
    cancel_all_stop_orders(client, &symbol).await;

    if pos_info.is_flat() {
        info!(symbol, "startup: no open position — starting flat");
        return Ok(ReconcileOutcome::Flat);
    }

    // Adopt the live position into bot state.
    state.sync_position(&pos_info);

    // Restore `last_signal` from position direction so the SAR flip logic
    // does not immediately re-enter on the first candle.
    state.last_signal = if pos_info.current_qty > 0 { 1 } else { -1 };

    let entry = pos_info.avg_entry_price;
    let direction = if pos_info.current_qty > 0 {
        "LONG"
    } else {
        "SHORT"
    };

    warn!(
        symbol,
        qty       = pos_info.current_qty,
        direction,
        entry_price = ?entry,
        "startup: open position adopted — bot resuming existing trade",
    );

    Ok(ReconcileOutcome::PositionAdopted {
        qty: pos_info.current_qty,
        entry_price: entry,
    })
}