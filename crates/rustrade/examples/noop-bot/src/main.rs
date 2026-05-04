//! Minimal end-to-end rustrade example.
//!
//! Wires a `NoopBrain` (always returns `Decision::hold()`) and a
//! `MockExchange` (no real API calls) into a [`rustrade::Bot`], publishes
//! a few synthetic events into the market bus, then triggers a graceful
//! shutdown after ~3 seconds.
//!
//! Run with: `cargo run -p noop-bot`
//!
//! What this proves:
//!   1. `Bot::new` wires brains + exchange + supervisor without panicking.
//!   2. The execution service subscribes to the bus and processes events.
//!   3. Graceful shutdown drains all spawned tasks within the timeout.

use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use chrono::Utc;
use rustrade::{
    Bot, BotConfig, Brain, Decision, ExchangeClient, MarketDataEvent, Order, Position, Result,
    SupervisorConfig, Symbol, Tick,
};

// ── NoopBrain ────────────────────────────────────────────────────────────────

struct NoopBrain;

#[async_trait]
impl Brain for NoopBrain {
    fn name(&self) -> &str {
        "noop"
    }

    async fn on_event(&self, event: &MarketDataEvent, _position: &Position) -> Result<Decision> {
        tracing::debug!(symbol = %event.symbol(), "noop brain saw event");
        Ok(Decision::hold())
    }
}

// ── MockExchange ─────────────────────────────────────────────────────────────

struct MockExchange;

#[async_trait]
impl ExchangeClient for MockExchange {
    fn name(&self) -> &str {
        "mock"
    }

    async fn place_order(&self, _order: &Order) -> Result<String> {
        Ok("mock-order-id".to_string())
    }

    async fn cancel_all(&self, _symbol: &str) -> Result<usize> {
        Ok(0)
    }

    async fn close_position(&self, _symbol: &str, _position: &Position) -> Result<String> {
        Ok("mock-close-id".to_string())
    }

    async fn get_position(&self, _symbol: &str) -> Result<Position> {
        Ok(Position::FLAT)
    }

    async fn get_balance(&self, _currency: &str) -> Result<f64> {
        Ok(10_000.0)
    }
}

// ── main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    rustrade::logging::init();

    let exchange: Arc<dyn ExchangeClient> = Arc::new(MockExchange);
    let brains: Vec<Arc<dyn Brain>> = vec![Arc::new(NoopBrain)];

    let config = BotConfig::new("noop-bot")
        .with_supervisor(
            SupervisorConfig::default()
                .without_signal_handler()
                .with_shutdown_timeout(Duration::from_secs(2)),
        )
        .with_session_symbol("BTCUSDT");

    let bot = Bot::new(config, exchange, brains);
    let bus = bot.market_bus().clone();
    let supervisor_cancel = bot.supervisor().cancel_token().clone();

    // Publish a few synthetic ticks, then trigger shutdown.
    let publisher = tokio::spawn(async move {
        for i in 0..5 {
            tokio::time::sleep(Duration::from_millis(200)).await;
            let tick = Tick {
                symbol: "BTCUSDT".to_string(),
                timestamp: Utc::now(),
                bid: rustrade::Price(50_000.0 + i as f64),
                ask: rustrade::Price(50_001.0 + i as f64),
                bid_size: rustrade::Volume(1.0),
                ask_size: rustrade::Volume(1.0),
                last_price: Some(rustrade::Price(50_000.5 + i as f64)),
                last_size: Some(rustrade::Volume(0.1)),
            };
            let n = bus.publish(MarketDataEvent::Ticker {
                exchange: "mock".into(),
                symbol: Symbol::from("BTCUSDT"),
                tick,
            });
            tracing::info!(iter = i, subscribers = n, "published ticker");
        }

        tokio::time::sleep(Duration::from_secs(1)).await;
        tracing::info!("publisher done — triggering shutdown");
        supervisor_cancel.cancel();
    });

    bot.run_until_shutdown().await?;
    publisher.await?;

    tracing::info!("noop-bot exited cleanly");
    Ok(())
}
