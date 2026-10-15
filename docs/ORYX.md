# FKS on oryx — runbook

Deploys the full FKS stack on the oryx host (`100.113.72.63`) as one compose
deployment: `docker-compose.oryx.yml`. The FKS webui is exposed at
**fks.7gram.xyz** (princess proxies → oryx:80).

## Services

| Group | Services |
|---|---|
| Data stores | postgres (`janus_db` + `fks_db`), redis, questdb, qdrant |
| Brain + factory | janus, fks_bot_spawner (host **:8091** — oryx:8090 belongs to the standalone crypto bot) |
| Front door | nginx on host **:80**, webui (dashboard) |
| Observability | prometheus, grafana (`/grafana/`), loki, promtail, jaeger, alertmanager + discord bridge, 4 exporters |
| Misc | docs (mkdocs), deadman (watchdog; idles if `DEADMAN_PING_URL` empty) |
| Sync | botsync (one-shot, runs on every `up`) |

Excluded: profile-gated services (`crypto-demo`, `advisor`, `orb-briefing`,
`rithmic-connector` — need the private `fks-state` sibling or are demo-only).

## Fresh bootstrap

Prereqs on the machine: Docker + compose plugin, Tailscale, `getent group docker`.

```bash
git clone https://github.com/nuniesmith/fks.git && cd fks
cp .env.example .env   # then fill secrets (or let the deploy workflow do it)
docker volume create prometheus_data grafana_data alertmanager_data  # one-time
docker compose -f docker-compose.oryx.yml up -d --build
```

That's it. Postgres init scripts create both DBs + the spawner schema; janus
waits on all four data stores; botsync upserts `bots/*.yaml` into the spawner
and respawns `autostart: true` bots. Reboots are handled by the spawner's
`boot_reconcile` — no human needed.

## Ports (host)

nginx `:80` (front door) · spawner `:8091` · webui `:3001` · grafana `:3000` ·
janus `:7000/:7001` REST, `:9051` gRPC, `:9092` metrics · postgres `:5432` ·
redis `:6379` · questdb `:9000/:9009/:8812` · qdrant `:6333/:6334` ·
prometheus `:9090` · alertmanager `:9093` · loki `:3100` · jaeger `:16686`.
All except nginx bind `127.0.0.1`; remote access is via Tailscale.

**Before first deploy:** verify nothing else listens on oryx:80.

## Volumes

Auto-created named volumes: `postgres_data`, `redis_data`, `questdb_data`,
`qdrant_data`, `optimizer_data`, `janus_checkpoints`, `prometheus_sd`,
`loki_data`, `promtail_positions`. Pre-created (external):
`prometheus_data`, `grafana_data`, `alertmanager_data`. Per-bot state:
`fks-bot-state-{bot_id}` at `/var/lib/fks-bot`, created by the spawner.

## Adding a bot

1. Drop a YAML file in `bots/` (see `bots/crypto-regime.yaml` for the shape).
2. `docker compose -f docker-compose.oryx.yml up -d` — botsync picks it up.
   (Or `POST /configs` on the spawner directly.)

Bot definitions are the source of truth: versioned in git, easy to save and
restore. Secrets are **never** in the YAML — declare `secrets: [name]` and the
spawner injects them from its encrypted store at spawn time.

## Crypto bot cutover (phase 2)

> **PAUSED 2026-10-15 — `crypto-regime` is disabled (`autostart: false`).**
> Step 2 below never happened: the spawner-managed bot and the standalone
> `crypto-bot-live` both traded the same Kraken account from 10-11 to 10-15,
> and both invested the 2026-10-14 USDC deposit (an extra ~$18 of BTC). The
> standalone (oryx repo, `crypto.7gram.xyz`, Discord reports) is the live
> trader. To disable the managed bot for good: Stop it in the FKS web UI
> (Bots page), which closes its run so `boot_reconcile` won't bring it back
> after a reboot; `autostart: false` keeps botsync from respawning it.
>
> Before resuming, the managed bot needs a Discord webhook: its
> `CRYPTO_DISCORD_WEBHOOK_URL` is `""` and botsync passes no webhook into
> its templating, so it reports to nobody. Then run the steps below IN
> ORDER, and point janus-bridge's `CRYPTO_BOT_STATE_DIR` at the managed bot's
> state.

The spawner-managed `crypto-regime` bot runs **live**. Cutover rule: **never
two live bots on one Kraken account.**

1. Deploy the stack; confirm the spawner-managed bot starts (Discord startup
   post in #crypto, regime reads correct, spawner `/health` green).
2. Stop the standalone `crypto-bot-live` container.
3. Verify the managed bot trades: positions managed, reports land in #crypto.
4. **Wednesday 5pm EST checkpoint:** Jordan adds $50 — confirm the bot
   handles the deposit correctly.
5. Only then retire the standalone container (keep it stopped-but-deployed
   until step 4 as instant rollback).

Note: spawned bots get no host ports, so `crypto.7gram.xyz` (:8090) goes dark
on cutover. The FKS webui covers bot status/control; the forecast calculator
needs a new home (spawner port-mapping feature or a separate tiny service).

## Troubleshooting

- `botsync` exits non-zero → `docker logs fks_botsync`; it never blocks the rest.
- Spawner rejects a spawn → check `ALLOWED_BOT_IMAGE_PREFIX` allows the image
  (`ghcr.io/nuniesmith/` for the crypto image) and `kraken` creds are in the
  secret store (`POST /secrets`).
- Janus won't start → all four data stores must be healthy first (`depends_on`).
- After host reboot, bots missing → spawner `boot_reconcile` respawns bots
  whose last `bot_runs` row is still open; check the spawner logs.
- `docker compose -f docker-compose.oryx.yml ps` / `logs <service>` for status.
