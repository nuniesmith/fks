# janus-bridge

Milestone 1 of the Janus↔crypto integration: a daily **logged** regime
assessment. Read-only/advisory — it never touches the bot and never posts
anywhere.

## What it does

1. Every 5 minutes, polls Janus's `RegimeBridgeService.GetCurrentRegime`
   (`fks_janus:50052`) and appends a raw sample to
   `samples-<YYYY-MM-DD>.jsonl` in the `janus-bridge-data` volume. Each
   sample also records the bot's own `regime_bull` flags from
   `state.json` -- a read-only mount of the LIVE bot's data directory
   (`CRYPTO_BOT_STATE_DIR`, default the standalone's
   `/home/actions/oryx/data/crypto-bot`), read at
   `JANUS_BRIDGE_BOT_STATE=/bot-state/paper/state.json`. Until 2026-10-15 it
   mounted the spawner volume `fks-bot-state-crypto-regime` at a path where
   no `state.json` existed, so no sample carried the bot's flags.
2. At the close of each 00:05→00:05 UTC window (aligned to the bot's daily
   regime read), aggregates the window's samples and appends one JSONL
   assessment line per pair plus a window summary to `assessment.jsonl`.

## The predeclared rule (approved 2026-10-12)

- Janus daily call per pair: **Bullish** iff Bullish-side
  (STRONG_BULLISH, BULLISH) time-share ≥ **60%**, **Bearish** iff
  Bearish-side (STRONG_BEARISH, BEARISH) ≥ 60%, else **"no clear call"**
  (excluded from the agreement rate, never forced).
- Agreement = Janus call matches the bot's `regime_bull` flag for the day.
- Success: all 6 pairs logged for 7 consecutive days; an agreement-rate
  summary is first evidence only — no edge claims.

## Files (in the `janus-bridge-data` volume)

- `samples-<day>.jsonl` — raw 5-minute polls (one JSON object per line).
- `assessment.jsonl` — one `assessment` object per pair per day, plus a
  `summary` object per day with calls and the rolling 7-day agreement rate.
- `finalized.txt` — windows already aggregated (crash-safe restarts).

Inspect on oryx, e.g.:

```sh
docker run --rm -v fks_janus-bridge-data:/data alpine tail -n 20 /data/assessment.jsonl
```

## Configuration (compose env, all optional)

| Var | Default | Meaning |
|---|---|---|
| `JANUS_BRIDGE_GRPC` | `fks_janus:50052` | Regime bridge endpoint |
| `JANUS_BRIDGE_SAMPLE_SECS` | `300` | Poll cadence |
| `JANUS_BRIDGE_CALL_THRESHOLD` | `0.60` | Directional time-share for a daily call |
| `JANUS_BRIDGE_WINDOW_MINUTE` | `5` | UTC window boundary minute |
