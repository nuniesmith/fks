// =============================================================================
// positions.rs — read-only positions book fed by the Rithmic PnL plant.
//
// DOCTRINE (non-negotiable): READ-ONLY. This module opens ONLY the PnL plant
// (`RithmicPnlPlant`) to *observe* positions and account P&L. It NEVER imports
// or opens `RithmicOrderPlant`; there is no order-entry path here. See the
// crate CLAUDE.md "no autonomous execution" and connector.rs doctrine header.
//
// Two halves:
//   * `PositionSnapshot` / `PositionsBook` — feature-independent, serde-friendly
//     state the /positions endpoint reads. Compiles with or without live-connect.
//   * `run_pnl` + `map_*` — the live PnL subscription + the pure mapping from the
//     vendor crate's protobuf updates into `PositionSnapshot`. Behind
//     `live-connect` because they reference `rithmic_rs` types. The mapping is
//     pure and unit-tested (default builds include the feature).
// =============================================================================

use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

/// A single open futures position, as last reported by Rithmic. Serialised by
/// the `/positions` endpoint. All monetary/qty fields are best-effort: Rithmic
/// sends many of them as optional strings, so absent values become 0.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct PositionSnapshot {
    /// Instrument symbol (e.g. `ESU6`). Namespaced `rithmic:` upstream in the UI.
    pub symbol: String,
    /// Exchange the instrument trades on (e.g. `CME`).
    pub exchange: String,
    /// Product code (e.g. `ES`).
    pub product_code: String,
    /// Signed net position quantity (>0 long, <0 short).
    pub net_quantity: i32,
    /// `long` / `short` / `flat`, derived from `net_quantity`.
    pub direction: &'static str,
    /// Average open fill price for the position.
    pub avg_open_price: f64,
    /// Open-position P&L (mark-to-market on the open quantity).
    pub open_pnl: f64,
    /// Day P&L (realised + unrealised for the session).
    pub day_pnl: f64,
    /// Filled buy quantity for the session.
    pub buy_qty: i32,
    /// Filled sell quantity for the session.
    pub sell_qty: i32,
    /// Open-position quantity (absolute).
    pub open_quantity: i32,
    /// Owning account id.
    pub account_id: String,
}

/// Account-level P&L summary (optional; populated from AccountPnLPositionUpdate).
#[derive(Debug, Clone, Default, PartialEq, serde::Serialize)]
pub struct AccountSummary {
    /// Account id this summary belongs to.
    pub account_id: String,
    /// Net position quantity across the account.
    pub net_quantity: i32,
    /// Open-position P&L across the account.
    pub open_pnl: f64,
    /// Day P&L across the account.
    pub day_pnl: f64,
    /// Account balance, if reported.
    pub account_balance: f64,
}

/// The observable positions snapshot returned by `GET /positions`.
#[derive(Debug, Clone, serde::Serialize)]
pub struct PositionsView {
    /// Owning account id (empty until a position/account update arrives).
    pub account: String,
    /// Number of currently-open positions.
    pub count: usize,
    /// The open positions, ordered by symbol.
    pub positions: Vec<PositionSnapshot>,
    /// Account-level P&L summary, if one has been received.
    pub account_summary: Option<AccountSummary>,
    /// Always true — this book is fed by the read-only PnL plant.
    pub read_only: bool,
    /// Always false — the order plant is never opened (doctrine invariant).
    pub order_plant_open: bool,
}

/// Shared, thread-safe book of open positions. Cheap to clone (Arc inside): the
/// PnL task holds one clone and mutates it; the HTTP server holds another and
/// reads it. Keyed by symbol; a position going flat is removed.
#[derive(Debug, Clone, Default)]
pub struct PositionsBook {
    inner: Arc<Mutex<BookInner>>,
}

#[derive(Debug, Default)]
struct BookInner {
    positions: BTreeMap<String, PositionSnapshot>,
    account: Option<AccountSummary>,
}

impl PositionsBook {
    /// A fresh, empty book.
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert/update a position. A flat position (net 0 and no open qty) is
    /// removed instead — the book tracks *open* positions only.
    pub fn upsert(&self, snap: PositionSnapshot) {
        let mut inner = self.inner.lock().expect("positions book poisoned");
        if snap.net_quantity == 0 && snap.open_quantity == 0 {
            inner.positions.remove(&snap.symbol);
        } else {
            inner.positions.insert(snap.symbol.clone(), snap);
        }
    }

    /// Record the latest account-level P&L summary.
    pub fn set_account(&self, summary: AccountSummary) {
        let mut inner = self.inner.lock().expect("positions book poisoned");
        inner.account = Some(summary);
    }

    /// Number of open positions currently tracked.
    pub fn len(&self) -> usize {
        self.inner
            .lock()
            .expect("positions book poisoned")
            .positions
            .len()
    }

    /// Whether the book has no open positions.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Render an observable view for the `/positions` endpoint.
    pub fn view(&self) -> PositionsView {
        let inner = self.inner.lock().expect("positions book poisoned");
        let positions: Vec<PositionSnapshot> = inner.positions.values().cloned().collect();
        // Prefer the account summary's id; fall back to any position's account.
        let account = inner
            .account
            .as_ref()
            .map(|a| a.account_id.clone())
            .or_else(|| positions.first().map(|p| p.account_id.clone()))
            .unwrap_or_default();
        PositionsView {
            account,
            count: positions.len(),
            positions,
            account_summary: inner.account.clone(),
            read_only: true,
            order_plant_open: false,
        }
    }
}

/// Direction label from a signed net quantity.
pub fn direction_of(net_quantity: i32) -> &'static str {
    if net_quantity > 0 {
        "long"
    } else if net_quantity < 0 {
        "short"
    } else {
        "flat"
    }
}

/// Parse an optional Rithmic string-encoded number into an f64 (0.0 on
/// absent/garbage). Rithmic sends several P&L fields as strings.
pub fn parse_opt_f64(s: &Option<String>) -> f64 {
    s.as_deref()
        .map(str::trim)
        .and_then(|v| v.parse::<f64>().ok())
        .unwrap_or(0.0)
}

// ── Live PnL subscription (behind live-connect) ──────────────────────────────

/// Map a Rithmic per-instrument P&L update into a [`PositionSnapshot`].
///
/// Returns `None` when the update carries no symbol (nothing we can key on).
/// Pure — unit-tested without any network.
#[cfg(feature = "live-connect")]
pub fn map_instrument_update(
    u: &rithmic_rs::rti::InstrumentPnLPositionUpdate,
) -> Option<PositionSnapshot> {
    let symbol = u.symbol.clone().filter(|s| !s.is_empty())?;
    let net_quantity = u.net_quantity.unwrap_or(0);
    Some(PositionSnapshot {
        symbol,
        exchange: u.exchange.clone().unwrap_or_default(),
        product_code: u.product_code.clone().unwrap_or_default(),
        net_quantity,
        direction: direction_of(net_quantity),
        avg_open_price: u.avg_open_fill_price.unwrap_or(0.0),
        open_pnl: parse_opt_f64(&u.open_position_pnl),
        day_pnl: u.day_pnl.unwrap_or(0.0),
        buy_qty: u.buy_qty.unwrap_or(0),
        sell_qty: u.sell_qty.unwrap_or(0),
        open_quantity: u.open_position_quantity.unwrap_or(0),
        account_id: u.account_id.clone().unwrap_or_default(),
    })
}

/// Map a Rithmic account-level P&L update into an [`AccountSummary`].
#[cfg(feature = "live-connect")]
pub fn map_account_update(a: &rithmic_rs::rti::AccountPnLPositionUpdate) -> AccountSummary {
    AccountSummary {
        account_id: a.account_id.clone().unwrap_or_default(),
        net_quantity: a.net_quantity.unwrap_or(0),
        open_pnl: parse_opt_f64(&a.open_position_pnl),
        day_pnl: parse_opt_f64(&a.day_pnl),
        account_balance: parse_opt_f64(&a.account_balance),
    }
}

/// Run the read-only PnL subscription until the stream closes. Opens the PnL
/// plant, logs in, pulls a position snapshot, subscribes to live updates, and
/// feeds every position/account update into `book`.
///
/// This is a secondary reader within the connector's `Ready` state: it runs only
/// when the account triple (account_id/fcm_id/ib_id) is configured. Market data
/// (the ticker plant) runs independently of it.
#[cfg(feature = "live-connect")]
pub async fn run_pnl(
    rr_config: rithmic_rs::RithmicConfig,
    account: rithmic_rs::RithmicAccount,
    book: PositionsBook,
) -> anyhow::Result<()> {
    use rithmic_rs::{ConnectStrategy, RithmicPnlPlant, rti::messages::RithmicMessage};
    use tokio::sync::broadcast::error::RecvError;
    use tracing::{info, warn};

    let plant = RithmicPnlPlant::connect(&rr_config, ConnectStrategy::Retry)
        .await
        .map_err(|e| anyhow::anyhow!("pnl plant connect failed: {e}"))?;
    let handle = plant.get_handle(&account);

    handle
        .login()
        .await
        .map_err(|e| anyhow::anyhow!("pnl plant login failed: {e}"))?;
    info!(account = %account.account_id, "logged in to Rithmic PnL plant (read-only)");

    // Pull a one-off snapshot, then subscribe to live updates. Snapshot rows and
    // subscription updates both arrive on `subscription_receiver` as
    // Instrument/Account PnL messages, so the loop below handles them uniformly.
    if let Err(e) = handle.pnl_position_snapshots().await {
        warn!(error = %e, "pnl position snapshot request failed (continuing with live updates)");
    }
    handle
        .subscribe_pnl_updates()
        .await
        .map_err(|e| anyhow::anyhow!("pnl subscribe failed: {e}"))?;
    info!("subscribed to Rithmic PnL updates (read-only)");

    let mut receiver = handle.subscription_receiver.resubscribe();
    loop {
        match receiver.recv().await {
            Ok(resp) => {
                if let Some(err) = &resp.error {
                    if err.is_connection_issue() {
                        warn!(error = %err, "connection issue on PnL stream — stopping loop");
                        break;
                    }
                    continue;
                }
                match resp.message {
                    RithmicMessage::InstrumentPnLPositionUpdate(u) => {
                        if let Some(snap) = map_instrument_update(&u) {
                            info!(
                                symbol = %snap.symbol,
                                net = snap.net_quantity,
                                dir = snap.direction,
                                "position update"
                            );
                            book.upsert(snap);
                        }
                    }
                    RithmicMessage::AccountPnLPositionUpdate(a) => {
                        book.set_account(map_account_update(&a));
                    }
                    _ => {}
                }
            }
            Err(RecvError::Lagged(n)) => {
                warn!(
                    skipped = n,
                    "PnL subscription lagged — some updates dropped"
                );
            }
            Err(RecvError::Closed) => {
                warn!("PnL subscription channel closed — stopping loop");
                break;
            }
        }
    }

    let _ = handle.disconnect().await;
    info!("pnl plant disconnected");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn direction_from_net_quantity() {
        assert_eq!(direction_of(3), "long");
        assert_eq!(direction_of(-2), "short");
        assert_eq!(direction_of(0), "flat");
    }

    #[test]
    fn parse_opt_f64_is_lenient() {
        assert_eq!(parse_opt_f64(&Some("123.5".to_string())), 123.5);
        assert_eq!(parse_opt_f64(&Some(" -4.0 ".to_string())), -4.0);
        assert_eq!(parse_opt_f64(&Some("".to_string())), 0.0);
        assert_eq!(parse_opt_f64(&Some("n/a".to_string())), 0.0);
        assert_eq!(parse_opt_f64(&None), 0.0);
    }

    fn sample(symbol: &str, net: i32, open_qty: i32) -> PositionSnapshot {
        PositionSnapshot {
            symbol: symbol.to_string(),
            exchange: "CME".to_string(),
            product_code: "ES".to_string(),
            net_quantity: net,
            direction: direction_of(net),
            avg_open_price: 5000.0,
            open_pnl: 12.5,
            day_pnl: 20.0,
            buy_qty: 1,
            sell_qty: 0,
            open_quantity: open_qty,
            account_id: "ACCT1".to_string(),
        }
    }

    #[test]
    fn book_upserts_and_orders_by_symbol() {
        let book = PositionsBook::new();
        book.upsert(sample("MNQU6", 1, 1));
        book.upsert(sample("ESU6", 2, 2));
        let view = book.view();
        assert_eq!(view.count, 2);
        // BTreeMap → deterministic symbol order.
        assert_eq!(view.positions[0].symbol, "ESU6");
        assert_eq!(view.positions[1].symbol, "MNQU6");
        assert_eq!(view.account, "ACCT1");
        assert!(view.read_only);
        assert!(!view.order_plant_open);
    }

    #[test]
    fn book_updates_existing_symbol_in_place() {
        let book = PositionsBook::new();
        book.upsert(sample("ESU6", 1, 1));
        book.upsert(sample("ESU6", 3, 3));
        let view = book.view();
        assert_eq!(view.count, 1);
        assert_eq!(view.positions[0].net_quantity, 3);
    }

    #[test]
    fn book_removes_position_when_flat() {
        let book = PositionsBook::new();
        book.upsert(sample("ESU6", 2, 2));
        assert_eq!(book.len(), 1);
        // Net 0 + no open qty ⇒ closed ⇒ removed.
        book.upsert(sample("ESU6", 0, 0));
        assert!(book.is_empty());
        assert_eq!(book.view().count, 0);
    }

    #[test]
    fn account_summary_populates_view_and_account_id() {
        let book = PositionsBook::new();
        book.set_account(AccountSummary {
            account_id: "ACCT9".to_string(),
            net_quantity: 1,
            open_pnl: 5.0,
            day_pnl: 7.5,
            account_balance: 10_000.0,
        });
        let view = book.view();
        assert_eq!(view.account, "ACCT9");
        assert_eq!(view.account_summary.unwrap().account_balance, 10_000.0);
    }

    // ── live-connect: pure mapping from the vendor protobuf types ────────────
    #[cfg(feature = "live-connect")]
    #[test]
    fn map_instrument_update_extracts_position() {
        let u = rithmic_rs::rti::InstrumentPnLPositionUpdate {
            symbol: Some("ESU6".to_string()),
            exchange: Some("CME".to_string()),
            product_code: Some("ES".to_string()),
            net_quantity: Some(-2),
            avg_open_fill_price: Some(5012.25),
            open_position_pnl: Some("-37.50".to_string()),
            day_pnl: Some(-40.0),
            buy_qty: Some(0),
            sell_qty: Some(2),
            open_position_quantity: Some(2),
            account_id: Some("ACCT1".to_string()),
            ..Default::default()
        };

        let snap = map_instrument_update(&u).expect("has symbol → maps");
        assert_eq!(snap.symbol, "ESU6");
        assert_eq!(snap.net_quantity, -2);
        assert_eq!(snap.direction, "short");
        assert_eq!(snap.avg_open_price, 5012.25);
        assert_eq!(snap.open_pnl, -37.50);
        assert_eq!(snap.day_pnl, -40.0);
        assert_eq!(snap.open_quantity, 2);
        assert_eq!(snap.account_id, "ACCT1");
    }

    #[cfg(feature = "live-connect")]
    #[test]
    fn map_instrument_update_without_symbol_is_none() {
        let u = rithmic_rs::rti::InstrumentPnLPositionUpdate::default();
        assert!(map_instrument_update(&u).is_none());
    }

    #[cfg(feature = "live-connect")]
    #[test]
    fn map_account_update_extracts_summary() {
        let a = rithmic_rs::rti::AccountPnLPositionUpdate {
            account_id: Some("ACCT1".to_string()),
            net_quantity: Some(1),
            open_position_pnl: Some("15.0".to_string()),
            day_pnl: Some("22.5".to_string()),
            account_balance: Some("52000.00".to_string()),
            ..Default::default()
        };

        let s = map_account_update(&a);
        assert_eq!(s.account_id, "ACCT1");
        assert_eq!(s.net_quantity, 1);
        assert_eq!(s.open_pnl, 15.0);
        assert_eq!(s.day_pnl, 22.5);
        assert_eq!(s.account_balance, 52000.0);
    }
}
