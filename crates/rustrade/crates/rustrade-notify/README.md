# rustrade-notify

Webhook-style notifications as supervised `TradingService`s for the
[rustrade](https://github.com/nuniesmith/rustrade) trading-bot framework.

Trading bots want lifecycle telemetry — "bot started", periodic
heartbeats, "circuit breaker tripped" — somewhere humans actually see
(Discord, Slack, PagerDuty). This crate provides the pipes; notification
*policy* (which events to send, with what content) is bot-specific and
lives outside the framework.

```toml
[dependencies]
rustrade-notify = "0.1"
```

## What's in this crate

- **The `Notifier` trait** — one method, `async fn notify(&self, msg: &str)`.
  Implement it for any transport.
- **`DiscordNotifier`** (feature `discord`, default-on) — POSTs `{ "content": "..." }`
  to a Discord webhook URL.
- **`WebhookHeartbeatService`** — a `TradingService` that posts a fixed
  string on a fixed interval. Failures during the run loop are logged and
  swallowed so a transient outage doesn't tear down the supervisor tree.
- **`InMemoryNotifier`** — test-only impl that records every message.

## Quick start (Discord heartbeat)

```rust,ignore
use std::sync::Arc;
use std::time::Duration;
use rustrade_notify::{DiscordNotifier, WebhookHeartbeatService};

let notifier = Arc::new(DiscordNotifier::new(std::env::var("DISCORD_WEBHOOK")?)?);
let heartbeat = WebhookHeartbeatService::new(
    "my-bot-heartbeat",
    notifier,
    Duration::from_secs(300),
    ":heartbeat: my-bot is alive".to_string(),
);
bot.supervisor().spawn_service(Box::new(heartbeat));
```

## Features

- `discord` (default-on) — pulls in `reqwest` + `serde` for the Discord
  client. Test-only consumers can `default-features = false` and use just
  `InMemoryNotifier`.

See the [workspace README](https://github.com/nuniesmith/rustrade) for how
this slots into the full framework.

## License

MIT — see `LICENSE`.
