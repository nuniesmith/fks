//! `kucoin` binary entry point.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;

use anyhow::Context;
use clap::Parser;
use tokio::sync::{Mutex, RwLock, Semaphore, mpsc, watch};
use tokio::task::JoinHandle;
use tracing::{error, info, warn};
use tracing_subscriber::Layer as _;
use tracing_subscriber::layer::SubscriberExt as _;
use tracing_subscriber::util::SubscriberInitExt as _;

use exchange_apiws::KucoinEnv;
use exchange_apiws::actors::{DataMessage, ExchangeConnector, TradeSide};
use exchange_apiws::ws::{KucoinConnector, WsRunnerConfig, run_feed};
use kucoin::BotSettings;
use kucoin::bot::{
    candle_poller,
    circuit_breaker::CircuitBreaker,
    execute::{self, FillSignals},
    pnl::PnlTracker,
    state::BotState,
    strategy::{self, SymbolIndicators},
};
use kucoin::config::RuntimeConfig;
use kucoin::notify::{discord::DiscordNotifier, redis_store::RedisStore};
use kucoin::settings::ParamOverrides;
use kucoin::types::{BotFill, BotOrder};
use kucoin::{Credentials, KuCoinClient};

// ── CLI ───────────────────────────────────────────────────────────────────────

#[derive(Parser, Debug)]
#[command(name = "kucoin", about = "KuCoin Futures SAR trading bot")]
struct Args {
    #[arg(long, conflicts_with = "live")]
    sim: bool,
    #[arg(long, conflicts_with = "sim")]
    live: bool,
    #[arg(long, value_delimiter = ',', default_value = "XBTUSDTM")]
    symbols: Vec<String>,
    #[arg(long, default_value_t = 20)]
    poll_secs: u64,
}

type PriceMap = Arc<RwLock<HashMap<String, f64>>>;

struct SymbolContext {
    indicators: SymbolIndicators,
    state: BotState,
    pnl: PnlTracker,
    breaker: CircuitBreaker,
    /// Open time of the last fully-closed candle we processed, in milliseconds
    /// since the UNIX epoch. Stored as `i64` (same type as `Candle::time`) to
    /// avoid the precision loss that comes from dividing by 1000 into an `f64`.
    last_candle_ts_ms: i64,
    /// UTC day number (days since UNIX epoch) recorded at the last session
    /// reset.  Compared against the current day on each candle poll so the
    /// drawdown cap and session PnL are cleared exactly once per calendar day
    /// at 00:00 UTC, without requiring a bot restart.
    last_session_day: u64,
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    // ── Log directory ─────────────────────────────────────────────────────────
    // Docker volume mounts ./logs → /app/logs, but also works for local runs.
    std::fs::create_dir_all("logs").ok();

    // ── File appenders ────────────────────────────────────────────────────────
    // bot.log  — rolling daily, all bot events (mirroring stdout).
    let bot_appender = tracing_appender::rolling::daily("logs", "bot.log");
    let (bot_writer, _bot_guard) = tracing_appender::non_blocking(bot_appender);

    // pnl.log  — single file, only trade / session PnL events.
    let pnl_appender = tracing_appender::rolling::never("logs", "pnl.log");
    let (pnl_writer, _pnl_guard) = tracing_appender::non_blocking(pnl_appender);

    // ── Subscriber layers ─────────────────────────────────────────────────────
    let mk_filter = || {
        tracing_subscriber::EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| "kucoin=info,warn".into())
    };

    // Only route events whose tracing target starts with "pnl" to pnl.log.
    let pnl_only = tracing_subscriber::filter::filter_fn(|meta| meta.target().starts_with("pnl"));

    tracing_subscriber::registry()
        .with(
            // Layer 1: stdout — existing colour/text behaviour.
            tracing_subscriber::fmt::layer().with_filter(mk_filter()),
        )
        .with(
            // Layer 2: logs/bot.YYYY-MM-DD — full bot log, no ANSI codes.
            tracing_subscriber::fmt::layer()
                .with_writer(bot_writer)
                .with_ansi(false)
                .with_filter(mk_filter()),
        )
        .with(
            // Layer 3: logs/pnl.log — only target="pnl" events.
            tracing_subscriber::fmt::layer()
                .with_writer(pnl_writer)
                .with_ansi(false)
                .with_filter(pnl_only),
        )
        .init();

    run(args).await
    // _bot_guard and _pnl_guard are dropped here, flushing both writers.
}

#[allow(clippy::too_many_lines)]
async fn run(args: Args) -> anyhow::Result<()> {
    let cfg = RuntimeConfig::from_env().context("loading RuntimeConfig")?;

    let sim_mode = if args.live {
        false
    } else if args.sim {
        true
    } else {
        std::env::var("BOT_MODE")
            .map(|v| v.to_lowercase() != "live")
            .unwrap_or(true)
    };

    info!(
        mode    = if sim_mode { "SIM" } else { "LIVE" },
        symbols = ?args.symbols,
        "kucoin starting",
    );

    let creds = if sim_mode {
        Credentials::new(
            std::env::var("KC_KEY").unwrap_or_default(),
            std::env::var("KC_SECRET").unwrap_or_default(),
            std::env::var("KC_PASSPHRASE").unwrap_or_default(),
        )
    } else {
        Credentials::new(
            std::env::var("KC_KEY").context("KC_KEY not set")?,
            std::env::var("KC_SECRET").context("KC_SECRET not set")?,
            std::env::var("KC_PASSPHRASE").context("KC_PASSPHRASE not set")?,
        )
    };

    let client = Arc::new(KuCoinClient::new(creds, cfg.env)?);

    let discord: Option<Arc<DiscordNotifier>> = if cfg.discord_enabled {
        cfg.discord_webhook.as_ref().map(|url| {
            Arc::new(DiscordNotifier::new(
                url.clone(),
                true,
                cfg.discord_notify_signal,
                cfg.discord_notify_fill,
                cfg.discord_notify_error,
            ))
        })
    } else {
        None
    };

    if let Some(d) = &discord {
        let _ = d
            .notify_bot_started(env!("CARGO_PKG_VERSION"), sim_mode)
            .await;
    }

    let prices: PriceMap = Arc::new(RwLock::new(HashMap::new()));
    let mut contexts: HashMap<String, Arc<Mutex<SymbolContext>>> = HashMap::new();

    for sym in &args.symbols {
        let mut settings = BotSettings::by_symbol(sym);

        let params_path = format!("data/best_params_{sym}.json");
        let fallback_path = "data/best_params.json";
        for path in [params_path.as_str(), fallback_path] {
            if std::path::Path::new(path).exists() {
                match apply_best_params(path, &mut settings) {
                    Ok(true) => {
                        info!(symbol = %sym, path, "best params applied");
                        break;
                    }
                    Ok(false) => warn!(symbol = %sym, path, "best params score too low — skipped"),
                    Err(e) => warn!(symbol = %sym, path, err = %e, "best params load failed"),
                }
            }
        }

        info!(symbol = %sym, bars = settings.history_candles, "loading history");
        let history = candle_poller::fetch_history(&client, &settings)
            .await
            .with_context(|| format!("fetch_history failed for {sym}"))?;

        let mut inds = SymbolIndicators::new(&settings);
        inds.warm_up(&history);

        let last_candle_ts_ms = history.last().map_or(0, |c| c.time);

        info!(symbol = %sym, bars = history.len(), "warm-up complete");

        if let Some(c) = history.last() {
            prices.write().await.insert(sym.clone(), c.close);
        }

        // Wrap settings in Arc — BotState (and its clones in the hot candle path)
        // hold only a reference-count bump, not a full copy of all fields.
        let arc_settings = Arc::new(settings);
        let mut state = BotState::new(Arc::clone(&arc_settings));
        let breaker = CircuitBreaker::new(&arc_settings);
        let session_limit = arc_settings.session_loss_limit_usdt;

        // ── Startup reconciliation (live mode only) ───────────────────────────
        // Sync actual position and balance from the exchange before any trading
        // logic runs. Without this, a crash-and-restart would leave the bot
        // believing it is flat and potentially double-entering a position.
        if !sim_mode {
            match execute::reconcile_startup(&client, &mut state).await {
                Ok(outcome) => {
                    info!(symbol = %sym, ?outcome, "startup reconciliation complete");

                    // If we adopted an existing position, the cancel_all_stop_orders
                    // call inside reconcile_startup wiped out any pre-existing hard
                    // stop on the exchange. We now own a position with no protective
                    // stop — re-place one immediately using the warmed-up ATR. The
                    // software stop in execute_sar would catch a runaway on the next
                    // candle, but that widens the unprotected window unnecessarily.
                    if let execute::ReconcileOutcome::PositionAdopted { qty, entry_price } = outcome
                    {
                        let atr = inds.ind.atr.unwrap_or(0.0);
                        let stop_mult = arc_settings.stop_atr_mult;
                        if let Some(entry) = entry_price
                            && atr > 0.0
                            && stop_mult > 0.0
                        {
                            let stop_distance = stop_mult * atr;
                            let (stop_side, stop_price) = if qty > 0 {
                                (exchange_apiws::Side::Sell, entry - stop_distance)
                            } else {
                                (exchange_apiws::Side::Buy, entry + stop_distance)
                            };
                            info!(
                                symbol = %sym,
                                qty,
                                entry,
                                atr,
                                stop_price,
                                "startup: replacing hard stop on adopted position",
                            );
                            execute::place_hard_stop(
                                &client,
                                sym,
                                stop_side,
                                qty.unsigned_abs(),
                                stop_price,
                                arc_settings.leverage,
                            )
                            .await;
                        } else {
                            warn!(
                                symbol = %sym,
                                qty,
                                entry_price = ?entry_price,
                                atr,
                                stop_mult,
                                "startup: cannot replace hard stop on adopted position \
                                 (missing entry price, ATR not warm, or stop_atr_mult=0); \
                                 software stop will protect on next candle",
                            );
                        }
                    }
                }
                Err(e) => {
                    // Abort startup — trading on stale position state is unsafe.
                    return Err(anyhow::Error::from(e)).with_context(|| {
                        format!("startup reconciliation failed for {sym} — cannot safely continue")
                    });
                }
            }
        }

        contexts.insert(
            sym.clone(),
            Arc::new(Mutex::new(SymbolContext {
                indicators: inds,
                state,
                pnl: PnlTracker::new(sym).with_session_limit(session_limit),
                breaker,
                last_candle_ts_ms,
                last_session_day: utc_day_number(),
            })),
        );
    }

    let mut redis_map: HashMap<String, Arc<RedisStore>> = HashMap::new();
    for sym in &args.symbols {
        let store = Arc::new(RedisStore::new(
            &cfg.redis_url,
            None,
            &format!("sar:{sym}:"),
        ));
        store.connect().await;
        if store.is_connected().await {
            info!(symbol = %sym, "Redis connected");
        } else {
            warn!(symbol = %sym, "Redis unavailable — in-memory fallback");
        }
        // Start the background reconnect loop so a dropped Redis connection
        // is automatically healed without requiring a bot restart.
        Arc::clone(&store).spawn_reconnect_loop();
        redis_map.insert(sym.clone(), store);
    }

    let mut fill_signals_map: HashMap<String, FillSignals> = HashMap::new();
    for sym in &args.symbols {
        fill_signals_map.insert(sym.clone(), Arc::new(Mutex::new(HashMap::new())));
    }

    let mut handles: Vec<JoinHandle<()>> = Vec::new();

    // Shared rate-limiter: all symbol candle-poll tasks share the same KuCoin
    // REST rate-limit bucket. A 1-permit semaphore serialises their fetches so
    // no two symbols hit the exchange simultaneously.  With the default 20-s
    // poll interval and fast REST responses this adds negligible latency while
    // preventing request races under heavy multi-symbol load.
    let candle_limiter = Arc::new(Semaphore::new(1));

    for (sym_idx, sym) in args.symbols.iter().enumerate() {
        // Stagger candle-poll task start times so symbols don't all fire REST
        // calls at the same instant even if they slip their sleep by a few ms.
        // Each symbol is offset by (index × poll_secs / n_symbols) seconds.
        let n = args.symbols.len().max(1);
        let stagger_secs = (sym_idx as u64 * args.poll_secs) / n as u64;

        let (ctx, cli, pmap, dis, s, ps, limiter, fs) = (
            Arc::clone(
                contexts
                    .get(sym)
                    .expect("symbol context missing — this is a bug"),
            ),
            Arc::clone(&client),
            Arc::clone(&prices),
            discord.clone(),
            sym.clone(),
            args.poll_secs,
            Arc::clone(&candle_limiter),
            Arc::clone(
                fill_signals_map
                    .get(sym)
                    .expect("fill_signals missing — this is a bug"),
            ),
        );
        handles.push(tokio::spawn(async move {
            candle_poll_task(
                ctx,
                cli,
                pmap,
                dis,
                s,
                ps,
                sim_mode,
                stagger_secs,
                limiter,
                fs,
            )
            .await;
        }));

        let (ctx, redis, cli, s) = (
            Arc::clone(
                contexts
                    .get(sym)
                    .expect("symbol context missing — this is a bug"),
            ),
            Arc::clone(
                redis_map
                    .get(sym)
                    .expect("redis store missing — this is a bug"),
            ),
            Arc::clone(&client),
            sym.clone(),
        );
        handles.push(tokio::spawn(async move {
            heartbeat_task(ctx, redis, cli, s, sim_mode).await;
        }));

        // Hot-reload task: watches for updated Optuna params on disk and
        // rebuilds indicators without requiring a bot restart.
        let (ctx, cli, s) = (
            Arc::clone(
                contexts
                    .get(sym)
                    .expect("symbol context missing — this is a bug"),
            ),
            Arc::clone(&client),
            sym.clone(),
        );
        handles.push(tokio::spawn(async move {
            param_watch_task(ctx, cli, s).await;
        }));
    }

    // ── Private WebSocket feed (live mode only) ───────────────────────────────
    // Subscribes to balance and per-symbol position events so ctx.state.balance
    // and ctx.state.position are updated in real-time on every fill, instead of
    // waiting up to heartbeat_interval_sec (30 s) for the next polling cycle.
    if !sim_mode {
        let (cli, syms, ctxs, env, dis, fs_map) = (
            Arc::clone(&client),
            args.symbols.clone(),
            contexts.clone(),
            cfg.env,
            discord.clone(),
            fill_signals_map.clone(),
        );
        handles.push(tokio::spawn(async move {
            private_ws_task(cli, syms, ctxs, env, dis, fs_map).await;
        }));
    }

    {
        let (syms, cli, pmap, env, dis) = (
            args.symbols.clone(),
            Arc::clone(&client),
            Arc::clone(&prices),
            cfg.env,
            discord.clone(),
        );
        handles.push(tokio::spawn(async move {
            ws_ticker_task(cli, syms, pmap, env, dis).await;
        }));
    }

    // On Unix, Docker sends SIGTERM on `docker stop` (then SIGKILL after the
    // grace period). `ctrl_c()` only catches SIGINT, so without this select
    // the position-close loop and Discord "bot stopped" notification would
    // never run in production containers.
    #[cfg(unix)]
    {
        use tokio::signal::unix::{SignalKind, signal};
        let mut sigterm =
            signal(SignalKind::terminate()).context("failed to install SIGTERM handler")?;
        tokio::select! {
            result = tokio::signal::ctrl_c() => {
                result.context("failed to install Ctrl-C handler")?;
            }
            _ = sigterm.recv() => {
                info!("received SIGTERM");
            }
        }
    }
    #[cfg(not(unix))]
    tokio::signal::ctrl_c()
        .await
        .context("failed to install Ctrl-C handler")?;

    info!("shutdown — aborting tasks");
    for h in &handles {
        h.abort();
    }
    for h in handles {
        let _ = h.await;
    }

    // Close any open positions in live mode before exiting.
    // Extract the fields we need then drop the lock before the async call.
    if !sim_mode {
        for sym in &args.symbols {
            let close_args = {
                let ctx = contexts[sym].lock().await;
                if ctx.state.position.is_flat() {
                    None
                } else {
                    Some((ctx.state.position.0, ctx.state.settings.leverage))
                }
            };
            if let Some((qty, leverage)) = close_args {
                // Cancel any resting limit or stop orders first so a
                // reduce-only market close doesn't race with an open order
                // and briefly over-hedge or take an unexpected fill.
                info!(symbol = %sym, "shutdown: cancelling open orders");
                execute::cancel_all_stop_orders(&client, sym).await;
                let _ = execute::cancel_all(&client, sym).await;

                info!(symbol = %sym, "shutdown: closing open position");
                if let Err(e) = execute::close_position(&client, sym, qty, leverage).await {
                    error!(
                        symbol = %sym,
                        err    = %e,
                        "shutdown: close_position failed — position may remain open on the exchange",
                    );
                }
            }
        }
    }

    for sym in &args.symbols {
        contexts[sym].lock().await.pnl.log_summary();
    }

    if let Some(d) = &discord {
        let _ = d.notify_bot_stopped("Ctrl-C").await;
    }

    info!("shutdown complete");
    Ok(())
}

// ── Candle poll task ──────────────────────────────────────────────────────────

#[allow(clippy::significant_drop_tightening, clippy::too_many_arguments)]
async fn candle_poll_task(
    ctx: Arc<Mutex<SymbolContext>>,
    client: Arc<KuCoinClient>,
    prices: PriceMap,
    discord: Option<Arc<DiscordNotifier>>,
    symbol: String,
    poll_secs: u64,
    sim_mode: bool,
    stagger_secs: u64,
    rate_limiter: Arc<Semaphore>,
    fill_signals: FillSignals,
) {
    info!(symbol, poll_secs, stagger_secs, "candle poll task started");

    // Spread the initial wakeups across symbols so they don't all fire REST
    // calls at exactly the same moment.
    if stagger_secs > 0 {
        tokio::time::sleep(Duration::from_secs(stagger_secs)).await;
    }

    loop {
        tokio::time::sleep(Duration::from_secs(poll_secs)).await;

        let (last_ts_ms, settings) = {
            let ctx = ctx.lock().await;
            // Arc::clone is O(1) — no heap allocation, just a refcount bump.
            (ctx.last_candle_ts_ms, Arc::clone(&ctx.state.settings))
        };

        let now_ms = unix_now_ms();
        let gran_ms = settings.rest_kline_type.parse::<i64>().unwrap_or_else(|_| {
            warn!(
                symbol,
                kline_type = %settings.rest_kline_type,
                "rest_kline_type is non-numeric — defaulting to 1-minute granularity"
            );
            1
        }) * 60_000; // minutes → milliseconds

        // A zero granularity makes close_ts_ms == open_ts_ms, which causes
        // every historical candle to pass the "too recent" guard and be skipped.
        // This is a configuration error; abort the task rather than silently
        // producing incorrect behaviour.
        if gran_ms == 0 {
            error!(
                symbol,
                kline_type = %settings.rest_kline_type,
                "rest_kline_type resolved to 0 minutes — cannot compute candle \
                 close time; aborting candle poll task"
            );
            return;
        }

        // Acquire the shared rate-limit permit before hitting the exchange.
        // Released automatically when `permit` is dropped at end of scope.
        let permit = rate_limiter.acquire().await.expect("semaphore closed");

        let candles = match candle_poller::fetch_recent(&client, &settings, 5).await {
            Ok(v) => v,
            Err(e) => {
                warn!(symbol, err = %e, "candle fetch failed");
                continue;
            }
        };

        // Release permit immediately after the fetch — don't hold it during
        // the CPU-bound indicator math or the async order execution.
        drop(permit);

        // ── Daily session reset (00:00 UTC) ───────────────────────────────────
        // The drawdown cap and session PnL are scoped to a calendar day.
        // Check once per poll cycle — cheap integer comparison, no I/O.
        //
        // Requires `PnlTracker::reset_session(&mut self)` in pnl.rs:
        //   pub fn reset_session(&mut self) {
        //       self.session_net_pnl = 0.0;
        //       self.session_halted  = false;
        //   }
        {
            let today = utc_day_number();
            let mut ctx_g = ctx.lock().await;
            if today > ctx_g.last_session_day {
                ctx_g.pnl.reset_session();
                ctx_g.last_session_day = today;
                info!(
                    symbol,
                    "daily session reset — drawdown cap and session PnL cleared"
                );
            }
        }

        let mut new_count = 0usize;
        let mut latest_close: Option<f64> = None;

        for candle in &candles {
            let open_ts_ms = candle.time;
            let close_ts_ms = open_ts_ms + gran_ms;

            if open_ts_ms <= last_ts_ms {
                continue;
            }
            if close_ts_ms > now_ms - 5_000 {
                continue;
            }

            latest_close = Some(candle.close);

            // ── Phase 1: sync indicator update + signal planning (lock held) ──
            //
            // All CPU-bound indicator math happens here. The mutex is released
            // before any network I/O so the heartbeat task is never blocked by
            // an in-flight order.
            let (plan, mut state_snap, mut pnl_snap, mut breaker_snap) = {
                let mut ctx_g = ctx.lock().await;
                let c = &mut *ctx_g;
                let plan = c
                    .indicators
                    .plan_candle(candle, &mut c.state, &mut c.breaker);
                let state_snap = c.state.clone();
                let pnl_snap = c.pnl.clone();
                let breaker_snap = c.breaker.clone();
                (plan, state_snap, pnl_snap, breaker_snap)
                // mutex released here
            };

            // ── Phase 2: order execution (lock-free) ──────────────────────────
            let dis_ref = discord.as_deref();
            let exec_result = strategy::SymbolIndicators::execute_plan(
                &plan,
                &mut state_snap,
                &mut pnl_snap,
                &mut breaker_snap,
                &client,
                sim_mode,
                dis_ref,
                Arc::clone(&fill_signals),
            )
            .await;

            // ── Phase 3: write updated state back (lock held briefly) ─────────
            //
            // IMPORTANT: In live mode we do NOT write `state_snap.position` or
            // `state_snap.entry_price` back here.  Between Phase 1 and now the
            // private WS task may have received a `PositionChange` event with
            // the authoritative post-fill position from the exchange.  A full
            // `c.state = state_snap` would overwrite that update with a stale
            // local snapshot, causing the bot to believe it is flat when it is
            // not (or vice versa) and potentially doubling into a position.
            //
            // In sim mode there is no WS task, so the candle task owns all
            // position state and a full swap is correct.
            {
                let mut ctx_g = ctx.lock().await;
                let c = &mut *ctx_g;
                c.pnl = pnl_snap;
                c.breaker = breaker_snap;
                // Re-apply the current settings to the just-written-back
                // breaker and pnl tracker. If `param_watch_task` ran a
                // hot-reload between the Phase-1 snapshot and now, the
                // snapshot we just wrote back may carry the *old* params;
                // re-deriving here ensures the new ones take effect on the
                // next candle without waiting for the param-watch task to
                // fire again.
                c.breaker.update_params(&c.state.settings);
                c.pnl
                    .set_session_loss_limit(c.state.settings.session_loss_limit_usdt);
                c.last_candle_ts_ms = open_ts_ms;
                // Signal/hold tracking is always owned by the candle task.
                c.state.last_signal = state_snap.last_signal;
                c.state.bars_since_entry = state_snap.bars_since_entry;
                if sim_mode {
                    // Sim: no WS task — candle task fully owns position state.
                    c.state.position = state_snap.position;
                    c.state.entry_price = state_snap.entry_price;
                    c.state.balance = state_snap.balance;
                }
            }

            if let Err(e) = exec_result {
                error!(symbol, err = %e, "process_candle error");
                if let Some(d) = &discord {
                    let _ = d
                        .notify_error("process_candle", &e.to_string(), &symbol)
                        .await;
                }
            }

            new_count += 1;
        }

        // Update the shared price map once with the latest close — outside
        // the candle loop to avoid taking the write lock on every catch-up bar.
        if let Some(price) = latest_close {
            prices.write().await.insert(symbol.clone(), price);
        }

        if new_count > 1 {
            warn!(symbol, new_count, "caught up missed candles");
        }
    }
}

// ── Heartbeat task ────────────────────────────────────────────────────────────

async fn heartbeat_task(
    ctx: Arc<Mutex<SymbolContext>>,
    redis: Arc<RedisStore>,
    client: Arc<KuCoinClient>,
    symbol: String,
    sim_mode: bool,
) {
    info!(symbol, "heartbeat task started");
    loop {
        // Re-read the interval on every iteration so a hot-reloaded
        // settings change is picked up without restarting the bot.
        let interval_secs = ctx.lock().await.state.settings.heartbeat_interval_sec;
        tokio::time::sleep(Duration::from_secs(interval_secs)).await;

        // ── Refresh live balance (live mode only) ─────────────────────────────
        if !sim_mode {
            match client.get_balance("USDT").await {
                Ok(bal) => ctx.lock().await.state.balance = bal,
                Err(e) => warn!(symbol, err = %e, "heartbeat: balance refresh failed"),
            }
        }

        let status = {
            let ctx = ctx.lock().await;
            let balance = if sim_mode {
                ctx.state.settings.sim_balance
            } else {
                ctx.state.balance
            };
            serde_json::json!({
                "symbol":       symbol,
                "position":     ctx.state.position.0,
                "balance":      balance,
                "trades":       ctx.pnl.trade_count,
                "net_pnl":      ctx.pnl.net_pnl(),
                "breaker_open": ctx.breaker.is_tripped(),
                "bars_held":    ctx.state.bars_since_entry,
            })
        };
        redis.heartbeat(&status).await;
    }
}

// ── WebSocket ticker task ─────────────────────────────────────────────────────

/// Drives a public ticker feed for all `symbols` using the `exchange-apiws`
/// runner, which handles TLS, application-level pings, and exponential-backoff
/// reconnection internally.
///
/// When `run_feed` exhausts its reconnect budget (token likely expired or
/// the server endpoint changed), this task re-negotiates a fresh token and
/// restarts the feed from scratch.
async fn ws_ticker_task(
    client: Arc<KuCoinClient>,
    symbols: Vec<String>,
    prices: PriceMap,
    env: KucoinEnv,
    discord: Option<Arc<DiscordNotifier>>,
) {
    // Delay between full token re-negotiation cycles (after run_feed gives up).
    // 5 s is enough for KuCoin to issue a new token — the old 30 s just meant
    // the bot ran blind for half a minute after a hard exhaustion.
    const RENEG_DELAY: Duration = Duration::from_secs(5);

    info!(?symbols, "WS ticker task started");

    // Counts how many times the feed has been fully re-negotiated in this
    // process lifetime.  Used to surface persistent connectivity problems.
    let mut reneg_count: u32 = 0;

    loop {
        // ── Step 1: negotiate a fresh token ──────────────────────────────────
        let token = match client.get_ws_token_public().await {
            Ok(t) => t,
            Err(e) => {
                warn!(err = %e, delay = ?RENEG_DELAY, "WS token fetch failed — retrying");
                tokio::time::sleep(RENEG_DELAY).await;
                continue;
            }
        };

        // ── Step 2: build connector + subscriptions ───────────────────────────
        let conn = match KucoinConnector::new(&token, env) {
            Ok(c) => Arc::new(c),
            Err(e) => {
                warn!(err = %e, "WS connector build failed — retrying");
                tokio::time::sleep(RENEG_DELAY).await;
                continue;
            }
        };

        let subs: Vec<String> = symbols
            .iter()
            .filter_map(|sym| conn.ticker_subscription(sym))
            .collect();

        info!(
            n_subs = subs.len(),
            ping_interval_secs = conn.ping_interval_secs,
            "WS connecting",
        );

        // ── Step 3: launch run_feed ───────────────────────────────────────────
        let (tx, mut rx) = mpsc::channel::<DataMessage>(1024);
        let (_shutdown_tx, shutdown_rx) = watch::channel(false);
        // Holding _shutdown_tx keeps the channel open. When this loop
        // iteration ends (reconnect), _shutdown_tx is dropped, which closes
        // the channel and causes run_feed's shutdown_rx.changed() to resolve,
        // stopping the feed cleanly before we reconnect.

        let config = WsRunnerConfig::from_ping_interval(conn.ping_interval_secs);
        let ws_url = conn.ws_url().to_string();

        tokio::spawn(run_feed(ws_url, subs, conn, tx, config, shutdown_rx));

        // ── Step 4: consume ticker messages until the feed dies ───────────────
        while let Some(msg) = rx.recv().await {
            let DataMessage::Ticker(t) = msg else {
                continue;
            };

            // Prefer best-bid as the live price; fall back to last-trade price.
            let price = if t.best_bid > 0.0 {
                t.best_bid
            } else {
                t.price
            };

            if !t.symbol.is_empty() && price > 0.0 {
                prices.write().await.insert(t.symbol, price);
            }
        }

        // rx closed → run_feed exhausted its reconnect budget.
        reneg_count += 1;
        warn!(
            delay = ?RENEG_DELAY,
            reneg_count,
            "WS feed terminated — re-negotiating token",
        );
        // Escalate after repeated full exhaustions in the same process run —
        // this indicates a persistent network or exchange issue rather than a
        // normal token rotation.
        if reneg_count >= 3 {
            warn!(
                reneg_count,
                "WS ticker has re-negotiated 3+ times — check network or KuCoin status",
            );
        }
        if let Some(d) = &discord {
            let _ = d
                .notify_error(
                    "ws_ticker",
                    "public WS ticker feed terminated — re-negotiating token",
                    "all",
                )
                .await;
        }
        tokio::time::sleep(RENEG_DELAY).await;
    }
}

// ── Private WebSocket feed task ───────────────────────────────────────────────

/// Subscribes to the private KuCoin futures feed and keeps `ctx.state.balance`
/// and `ctx.state.position` in sync with exchange-side events in real time.
///
/// On each fill or margin movement the exchange pushes a `BalanceUpdate` or
/// `PositionChange` message. This task applies those events directly to the
/// relevant `SymbolContext` so the heartbeat polling interval no longer limits
/// how quickly the bot sees its own account changes.
///
/// The token re-negotiation loop mirrors `ws_ticker_task`: when `run_feed`
/// exhausts its reconnect budget a fresh private token is obtained and the
/// feed restarts from scratch.
#[allow(clippy::too_many_lines)]
async fn private_ws_task(
    client: Arc<KuCoinClient>,
    symbols: Vec<String>,
    contexts: HashMap<String, Arc<Mutex<SymbolContext>>>,
    env: KucoinEnv,
    discord: Option<Arc<DiscordNotifier>>,
    fill_signals_map: HashMap<String, FillSignals>,
) {
    const RENEG_DELAY: Duration = Duration::from_secs(5);
    info!(?symbols, "private WS task started");

    let mut reneg_count: u32 = 0;

    loop {
        // ── Step 1: negotiate a fresh private token ───────────────────────────
        let token = match client.get_ws_token_private().await {
            Ok(t) => t,
            Err(e) => {
                warn!(err = %e, delay = ?RENEG_DELAY, "private WS token fetch failed — retrying");
                tokio::time::sleep(RENEG_DELAY).await;
                continue;
            }
        };

        // ── Step 2: build connector + subscriptions ───────────────────────────
        let conn = match KucoinConnector::new(&token, env) {
            Ok(c) => Arc::new(c),
            Err(e) => {
                warn!(err = %e, "private WS connector build failed — retrying");
                tokio::time::sleep(RENEG_DELAY).await;
                continue;
            }
        };

        let mut subs: Vec<String> = Vec::new();
        if let Some(s) = conn.balance_subscription() {
            subs.push(s);
        }
        // Real-time fill and status events for all placed orders.
        if let Some(s) = conn.order_updates_subscription() {
            subs.push(s);
        }
        for sym in &symbols {
            if let Some(s) = conn.position_subscription(sym) {
                subs.push(s);
            }
        }

        info!(
            n_subs = subs.len(),
            ping_interval_secs = conn.ping_interval_secs,
            "private WS connecting",
        );

        // ── Step 3: launch run_feed ───────────────────────────────────────────
        let (tx, mut rx) = mpsc::channel::<DataMessage>(256);
        let (_shutdown_tx, shutdown_rx) = watch::channel(false);
        let config = WsRunnerConfig::from_ping_interval(conn.ping_interval_secs);
        let ws_url = conn.ws_url().to_string();

        tokio::spawn(run_feed(ws_url, subs, conn, tx, config, shutdown_rx));

        // ── Step 4: apply private-feed events to context state ────────────────
        while let Some(msg) = rx.recv().await {
            match msg {
                DataMessage::BalanceUpdate(b) if b.currency == "USDT" => {
                    // All symbols share the same USDT margin account.
                    for ctx in contexts.values() {
                        ctx.lock().await.state.balance = b.available_balance;
                    }
                    tracing::debug!(
                        balance = b.available_balance,
                        event   = %b.event,
                        "private WS: balance updated",
                    );
                }
                DataMessage::PositionChange(p) => {
                    if let Some(ctx) = contexts.get(&p.symbol) {
                        let mut g = ctx.lock().await;
                        g.state.position = kucoin::types::Position(p.current_qty);
                        g.state.unrealised_pnl = p.unrealised_pnl;
                        if p.current_qty != 0 && p.avg_entry_price != 0.0 {
                            g.state.entry_price = Some(p.avg_entry_price);
                        } else if p.current_qty == 0 {
                            // Position closed (possibly externally) — reset entry.
                            g.state.entry_price = None;
                        }
                        drop(g);
                        tracing::debug!(
                            symbol = %p.symbol,
                            qty    = p.current_qty,
                            reason = %p.change_reason,
                            "private WS: position updated",
                        );
                    }
                }
                DataMessage::OrderUpdate(o) => {
                    let is_filled = o.status == "filled";
                    let is_partial = o.status == "partialFilled";

                    tracing::info!(
                        symbol    = %o.symbol,
                        order_id  = %o.order_id,
                        status    = %o.status,
                        side      = ?o.side,
                        filled    = o.filled_size,
                        remaining = o.remaining_size,
                        fee       = o.fee,
                        "private WS: order update",
                    );

                    // Fire the fill signal so any waiting poll_for_fill returns immediately.
                    if is_filled && let Some(fs) = fill_signals_map.get(&o.symbol) {
                        let tx = fs.lock().await.remove(&o.order_id);
                        if let Some(tx) = tx {
                            let _ = tx.send(());
                        }
                    }

                    if (is_filled || is_partial)
                        && let Some(ctx) = contexts.get(&o.symbol)
                    {
                        // ── Phase A: work that needs the lock ─────────────────
                        // Emit the PnL log line (cheap — just a tracing call),
                        // then snapshot the data needed for Discord *before*
                        // dropping the guard.  Holding the lock across an async
                        // network call would stall the heartbeat and candle-poll
                        // tasks for every symbol while Discord responds.
                        let should_notify = {
                            let _g = ctx.lock().await;

                            if is_filled {
                                tracing::info!(
                                    target: "pnl",
                                    symbol   = %o.symbol,
                                    order_id = %o.order_id,
                                    side     = ?o.side,
                                    filled   = o.filled_size,
                                    fee_usdt = format!("{:.4}", o.fee),
                                    "WS fill confirmed",
                                );
                            }

                            discord
                                .as_ref()
                                .map(|d| d.notify_on_fill())
                                .unwrap_or(false)
                            // _g dropped here — lock released before any I/O
                        };

                        // ── Phase B: Discord notify (lock-free) ───────────────
                        if should_notify {
                            if let Some(d) = &discord {
                                let side_str = match o.side {
                                    TradeSide::Buy => "buy",
                                    TradeSide::Sell => "sell",
                                }
                                .to_string();
                                let bot_order = BotOrder {
                                    id: o.order_id.clone(),
                                    symbol: o.symbol.clone(),
                                    side: side_str.clone(),
                                    price: o.price,
                                    size: o.filled_size,
                                };
                                let bot_fill = BotFill {
                                    symbol: o.symbol.clone(),
                                    order_id: o.order_id.clone(),
                                    side: side_str,
                                    price: o.price,
                                    quantity: f64::from(o.filled_size),
                                    fee: o.fee,
                                    fee_currency: "USDT".to_string(),
                                };
                                let _ = d.notify_order_filled(&bot_order, &bot_fill, None).await;
                            }
                        }

                        // ── Phase C: brief write-back (lock held minimally) ───
                        // If fully filled and the position is now flat,
                        // clear entry_price.  PositionChange will follow
                        // shortly with the authoritative update.
                        if is_filled {
                            let mut g = ctx.lock().await;
                            if g.state.position.is_flat() {
                                g.state.entry_price = None;
                            }
                        }
                    }
                }
                // Trade, Ticker, OrderBook, InstrumentEvent, AdvancedOrderUpdate,
                // and non-USDT BalanceUpdate events are not consumed by this task.
                _ => {}
            }
        }

        // rx closed → run_feed exhausted its reconnect budget.
        reneg_count += 1;
        warn!(
            delay = ?RENEG_DELAY,
            reneg_count,
            "private WS feed terminated — re-negotiating token",
        );
        if reneg_count >= 3 {
            warn!(
                reneg_count,
                "private WS has re-negotiated 3+ times — check network or KuCoin status",
            );
        }
        if let Some(d) = &discord {
            let _ = d
                .notify_error(
                    "private_ws",
                    "private WS feed terminated — re-negotiating token",
                    "all",
                )
                .await;
        }
        tokio::time::sleep(RENEG_DELAY).await;
    }
}

/// Watches `data/best_params_<symbol>.json` (falling back to
/// `data/best_params.json`) for changes and hot-reloads params + indicators
/// without requiring a bot restart.
///
/// On each tick the task compares the file's mtime against the last-seen
/// value. If the file changed it:
/// 1. Parses the new params into a fresh `BotSettings`.
/// 2. Fetches a full history window (same as startup) so indicators can be
///    re-warmed from a clean slate — avoids indicator state drift from a
///    window-size change.
/// 3. Rebuilds `SymbolIndicators` with the new settings.
/// 4. Holds the context mutex briefly to atomically swap settings +
///    indicators + `last_candle_ts`.
///
/// The candle-poll task will continue on the new settings from the very next
/// tick. Any candles between the history fetch and the swap are picked up by
/// the poll task on its next iteration because `last_candle_ts` is set to
/// the last bar in the freshly fetched history.
async fn param_watch_task(
    ctx: Arc<Mutex<SymbolContext>>,
    client: Arc<KuCoinClient>,
    symbol: String,
) {
    const FALLBACK: &str = "data/best_params.json";

    // Read the configured interval once at startup.
    // `0` is documented as "disable" — return early so the task does nothing
    // rather than silently defaulting to 300 s and running anyway.
    let interval_secs = ctx.lock().await.state.settings.param_watch_interval_sec;
    if interval_secs == 0 {
        info!(
            symbol,
            "param hot-reload disabled (param_watch_interval_sec=0)"
        );
        return;
    }

    let params_path = format!("data/best_params_{symbol}.json");

    let mut last_mtime: Option<std::time::SystemTime> = None;

    info!(symbol, interval_secs, "param watch task started");

    loop {
        tokio::time::sleep(Duration::from_secs(interval_secs)).await;

        // Determine which params file to watch.
        let path: String = if std::path::Path::new(&params_path).exists() {
            params_path.clone()
        } else if std::path::Path::new(FALLBACK).exists() {
            FALLBACK.to_string()
        } else {
            continue; // no params file yet — skip silently
        };

        let mtime = std::fs::metadata(&path).and_then(|m| m.modified()).ok();

        if mtime == last_mtime {
            continue; // file unchanged
        }

        // Build updated settings: start from the current settings so fields
        // absent from the JSON file keep their existing tuned values.
        let new_settings = {
            let mut tmp = (*ctx.lock().await.state.settings).clone();
            match apply_best_params(&path, &mut tmp) {
                Ok(true) => tmp,
                Ok(false) => {
                    warn!(symbol, path, "hot-reload: score below minimum — skipped");
                    // Advance mtime so we don't log this every interval.
                    last_mtime = mtime;
                    continue;
                }
                Err(e) => {
                    warn!(symbol, path, err = %e, "hot-reload: parse error — retrying next cycle");
                    continue; // don't advance mtime; retry when timer fires
                }
            }
        };

        // Fetch fresh history for indicator re-warm. Done *outside* the mutex
        // so the candle-poll and heartbeat tasks are never blocked by I/O.
        info!(
            symbol,
            path, "hot-reload: fetching history for indicator rebuild"
        );
        let history = match candle_poller::fetch_history(&client, &new_settings).await {
            Ok(h) => h,
            Err(e) => {
                warn!(
                    symbol,
                    err = %e,
                    "hot-reload: history fetch failed — retrying next cycle"
                );
                continue;
            }
        };

        // Rebuild indicators and warm them from the fresh history.
        let mut new_inds = strategy::SymbolIndicators::new(&new_settings);
        new_inds.warm_up(&history);

        // Atomically swap settings + indicators + breaker params + session
        // limit + timestamp under the lock.  The lock is only held for a
        // handful of field assignments — no I/O inside.
        //
        // Order matters: read the new fields out of `new_settings` and apply
        // them to the existing `breaker` and `pnl` BEFORE moving `new_settings`
        // into the Arc, so we don't fight the borrow checker over `g`.
        {
            let mut g = ctx.lock().await;
            // Pick up changes to breaker_loss_limit / breaker_window_sec /
            // breaker_cooldown_sec without clearing the rolling-window loss
            // history or any active trip.
            g.breaker.update_params(&new_settings);
            // Pick up changes to session_loss_limit_usdt without clearing an
            // already-tripped session halt (only the daily rollover does that).
            g.pnl
                .set_session_loss_limit(new_settings.session_loss_limit_usdt);
            g.state.settings = Arc::new(new_settings);
            g.indicators = new_inds;
            // Reset the candle cursor to the last bar in the new history so
            // the poll task picks up any candles that arrived during the rebuild.
            g.last_candle_ts_ms = history.last().map_or(0, |c| c.time);
        }

        last_mtime = mtime;
        info!(
            symbol,
            path, "hot-reload: params + indicators updated successfully"
        );
    }
}

// ── Best-params loader ────────────────────────────────────────────────────────

fn apply_best_params(path: &str, settings: &mut BotSettings) -> anyhow::Result<bool> {
    const MIN_SCORE: f64 = 0.0; // reject any strategy with a negative backtest score

    let raw = std::fs::read_to_string(path).with_context(|| format!("reading {path}"))?;
    let parsed: serde_json::Value =
        serde_json::from_str(&raw).with_context(|| format!("parsing {path}"))?;

    let score = parsed.get("score").and_then(serde_json::Value::as_f64);
    match score {
        None => {
            // No "score" field — treat as unconditional apply (e.g. params
            // from a grid-search tool that doesn't emit a score).
            tracing::warn!(
                path,
                "params file has no 'score' field — applying unconditionally"
            );
        }
        Some(s) if s < MIN_SCORE => return Ok(false),
        Some(_) => {}
    }

    if let Some(params) = parsed.get("params") {
        let overrides: ParamOverrides = serde_json::from_value(params.clone())
            .with_context(|| format!("deserializing params from {path}"))?;
        settings.apply_overrides(&overrides);
    }

    Ok(true)
}

// ── Utilities ─────────────────────────────────────────────────────────────────

/// Returns the current time as milliseconds since the UNIX epoch.
///
/// Stored as `i64` to match `Candle::time` exactly — no f64 precision loss,
/// no division-by-1000 rounding errors.
///
/// # Panics
/// Panics if the system clock reports a time before the UNIX epoch. This is
/// a configuration error (containerised environment without a real-time clock)
/// and should never happen in normal operation.
fn unix_now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("system clock is before the UNIX epoch")
        .as_millis() as i64
}

/// Returns the current UTC day number (whole days since the UNIX epoch).
///
/// Rolls over at 00:00 UTC. Used by the candle-poll task to detect when a
/// new calendar day has started and trigger the daily session reset (clearing
/// the drawdown cap and session PnL without requiring a bot restart).
fn utc_day_number() -> u64 {
    unix_now_ms() as u64 / (24 * 60 * 60 * 1_000)
}
