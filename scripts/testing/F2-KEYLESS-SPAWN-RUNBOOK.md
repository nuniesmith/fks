# F2 — Keyless paper-bot spawn (end-to-end) runbook

> WebUI buildout plan **Phase F2**: *spawn a paper crypto bot end-to-end from the
> UI on the keyless path.* This runbook covers both the **manual UI walkthrough**
> and the **automated smoke test** (`f2-keyless-spawn-smoke.sh`).

## What "keyless" means here

The whole path runs with **no exchange API keys and no real orders**:

```
spawner POST /spawn (crypto-demo · paper · synthetic · mock)
  → bot connects to the janus brain over HTTP   (DEMO_BRAIN=janus)
  → synthetic candles → indicators-ta features → janus signal + risk (:8080)
  → rustrade risk gate → MockExchange            (PAPER — never a live order)
```

`DEMO_SOURCE=synthetic` means no exchange feed/creds are needed; `DEMO_EXCHANGE=mock`
keeps it paper. Real exchange keys (entered on `/settings`) only unlock the
authenticated order path, which stays behind the manual execution gate — they are
**not** involved here.

## Prerequisites

- Stack up: `./run.sh all` (or `docker compose --profile demo up -d janus`), so
  **janus** (`:8080`), **spawner** (`:8090`), postgres, questdb, redis are running.
- Bot image built: `fks-bot-crypto-demo:latest`
  (`docker compose --profile demo build crypto-demo`).
- `NGINX_INTERNAL_TOKEN` known (it's in `.env`; the spawner validates it as
  `X-Internal-Token`).

## A. Manual UI walkthrough (`/bots`)

1. Open the dashboard → **Bots** tab (`/bots`).
2. In **Spawn Bot**, click the **Crypto Demo · janus brain** preset. It pre-fills
   the verified keyless config (image `fks-bot-crypto-demo:latest`, mode `paper`,
   `DEMO_BRAIN=janus`, `DEMO_SOURCE=synthetic`, `DEMO_EXCHANGE=mock`,
   `JANUS_HTTP_URL`, `DEMO_SYMBOLS`, `RUST_LOG`). No keys, no edits required.
3. Click **▶ Spawn**. A `fks-bot-…` container appears in **Running containers**
   and flips to `running`; the row shows live **CPU% / memory / uptime**.
4. Click the row's **Logs** button → the SSE viewer streams the bot's output.
   Expect: synthetic candles → feature build → janus signal/risk calls → MockExchange
   paper fills. **No real-order lines.**
5. Cross-check the brain side: **Janus AI** (`/janus-ai`) → *Live Signals*, or
   **Signals** (`/signals`) — recent signals should tick as the bot drives janus.
6. Stop/remove from the row's **Stop** / **✕** when done. *(Optional: save the
   form as a named config via "Save config".)*

**Pass =** the bot spawns keyless, reaches `running`, streams logs, drives janus
signals, and never touches a live order path.

## B. Automated smoke test

```bash
NGINX_INTERNAL_TOKEN=<token> scripts/testing/f2-keyless-spawn-smoke.sh
# options: --brain janus|ema-cross   --timeout 60   --keep
```

It performs the same checks over the spawner HTTP API: `/health` → `POST /spawn`
(the exact keyless env) → poll `/containers` for `running` → tail `/container/{id}/logs`
~20s, asserting **no live-order path** (paper safety) and best-effort janus/signal
activity → query janus `/api/dashboard/signals/summary` → remove the container
(unless `--keep`). Non-zero exit on any hard failure.

> Use `--brain ema-cross` to validate the spawn + container lifecycle without
> requiring a healthy janus (the bot then runs a local EMA-cross brain).
