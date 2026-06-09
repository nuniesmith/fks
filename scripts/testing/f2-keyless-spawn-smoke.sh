#!/usr/bin/env bash
#
# F2 — Keyless paper-bot spawn smoke test
# =======================================
# Exercises the keyless end-to-end path that the WebUI /bots page drives:
#
#   spawner  POST /spawn  (crypto-demo · paper · synthetic · mock)
#     → bot connects to the janus brain over HTTP (DEMO_BRAIN=janus)
#     → synthetic candles → indicators-ta features → janus signal + risk (:8080)
#     → rustrade risk gate → MockExchange  (PAPER — no real orders)
#
# No exchange API keys and no real orders (DEMO_EXCHANGE=mock). This is the
# script form of WEBUI_BUILDOUT_PLAN.md Phase F2; the manual UI walkthrough is in
# F2-KEYLESS-SPAWN-RUNBOOK.md (same dir).
#
# Prereqs:
#   - the stack is up:        ./run.sh all   (or: docker compose --profile demo up)
#   - the bot image is built: fks-bot-crypto-demo:latest
#   - curl + jq on PATH
#   - NGINX_INTERNAL_TOKEN (env or .env) — the spawner's X-Internal-Token
#
# Usage:
#   NGINX_INTERNAL_TOKEN=… scripts/testing/f2-keyless-spawn-smoke.sh \
#       [--brain janus|ema-cross] [--timeout 60] [--keep]
#
#   --brain    DEMO_BRAIN (default janus; ema-cross = local, no janus needed)
#   --timeout  seconds to wait for 'running' (default 60)
#   --keep     leave the bot running afterwards (default: remove it)
#
set -euo pipefail

SPAWNER_URL="${SPAWNER_URL:-http://127.0.0.1:8090}"
JANUS_URL="${JANUS_URL:-http://127.0.0.1:8080}"
IMAGE="${F2_IMAGE:-fks-bot-crypto-demo:latest}"
BRAIN="janus"
TIMEOUT=60
KEEP=0

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Pull the internal token from .env when it isn't already in the environment.
TOKEN="${NGINX_INTERNAL_TOKEN:-}"
if [[ -z "$TOKEN" && -f "$REPO_ROOT/.env" ]]; then
  TOKEN="$(grep -E '^NGINX_INTERNAL_TOKEN=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)"
  TOKEN="${TOKEN%\"}"; TOKEN="${TOKEN#\"}"
  TOKEN="${TOKEN%\'}"; TOKEN="${TOKEN#\'}"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --brain)   BRAIN="${2:?}"; shift 2 ;;
    --timeout) TIMEOUT="${2:?}"; shift 2 ;;
    --keep)    KEEP=1; shift ;;
    -h|--help) sed -n '2,33p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[36m▸ %s\033[0m\n' "$*"; }
ok()  { printf '\033[32m✓ %s\033[0m\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v curl >/dev/null || die "curl is required"
command -v jq   >/dev/null || die "jq is required"

auth=()
if [[ -n "$TOKEN" ]]; then auth=(-H "X-Internal-Token: $TOKEN"); fi

# 1) spawner reachable + healthy
say "Checking spawner at $SPAWNER_URL …"
curl -fsS "${auth[@]}" "$SPAWNER_URL/health" | jq -e '.status == "ok"' >/dev/null \
  || die "spawner /health not ok — is the stack up and the token correct?"
ok "spawner healthy"

# 2) spawn the keyless paper bot (exactly the compose crypto-demo env)
bot_id="f2-smoke-$(date +%s)"
say "Spawning $IMAGE as $bot_id (paper · synthetic · mock · brain=$BRAIN) …"
spawn_body="$(jq -n --arg img "$IMAGE" --arg id "$bot_id" --arg brain "$BRAIN" '{
  image: $img, bot_id: $id, mode: "paper",
  env: {
    DEMO_BRAIN: $brain, DEMO_SOURCE: "synthetic", DEMO_EXCHANGE: "mock",
    JANUS_HTTP_URL: "http://fks_janus:8080",
    DEMO_SYMBOLS: "XBTUSDTM,ETHUSDTM,SOLUSDTM",
    RUST_LOG: "info,crypto_demo=debug"
  }
}')"
cid="$(curl -fsS "${auth[@]}" -H 'content-type: application/json' \
  -X POST "$SPAWNER_URL/spawn" -d "$spawn_body" | jq -r '.container_id')" \
  || die "spawn request failed"
[[ -n "$cid" && "$cid" != "null" ]] || die "spawn returned no container_id"
ok "spawned container $cid"

cleanup() {
  if [[ "$KEEP" -eq 0 ]]; then
    say "Removing container $cid …"
    curl -fsS "${auth[@]}" -X DELETE "$SPAWNER_URL/container/$cid" >/dev/null 2>&1 || true
  else
    say "Leaving container $cid running (--keep)"
  fi
}
trap cleanup EXIT

# 3) wait for 'running'
say "Waiting up to ${TIMEOUT}s for the bot to reach 'running' …"
deadline=$(( $(date +%s) + TIMEOUT ))
state=""
while [[ "$(date +%s)" -lt "$deadline" ]]; do
  state="$(curl -fsS "${auth[@]}" "$SPAWNER_URL/containers" 2>/dev/null \
    | jq -r --arg id "$cid" \
        '.containers[] | select(.id == $id or (.id_full | startswith($id))) | .state' \
    | head -1 || true)"
  [[ "$state" == "running" ]] && break
  sleep 2
done
[[ "$state" == "running" ]] || die "bot did not reach 'running' (state=${state:-unknown})"
ok "bot is running"

# 4) tail ~20s of logs; assert the keyless/paper path
say "Tailing logs (~20s) to confirm the janus-brain + paper path …"
logs="$(curl -fsS -N --max-time 22 "${auth[@]}" \
  "$SPAWNER_URL/container/$cid/logs?tail=200" 2>/dev/null || true)"
echo "$logs" | tail -20 | sed 's/^/    /'

# PAPER SAFETY: the bot must stay on MockExchange — never a live order path.
if echo "$logs" | grep -Eiq 'live order|placing real|DEMO_EXCHANGE=(kucoin|kraken)'; then
  die "PAPER SAFETY: logs hint at a non-mock order path — aborting"
fi
ok "no live-order path in logs (paper / mock)"

if echo "$logs" | grep -Eiq 'janus|signal|brain'; then
  ok "bot is talking to the janus brain / emitting signals"
else
  say "no janus/signal lines in the first window — try a longer --timeout"
fi

# 5) janus-side signals (best-effort, doesn't fail the test)
if curl -fsS --max-time 5 "$JANUS_URL/api/dashboard/signals/summary" >/tmp/f2-signals.json 2>/dev/null; then
  n="$(jq -r '.recent_signals | length' /tmp/f2-signals.json 2>/dev/null || echo 0)"
  ok "janus dashboard reachable — recent_signals=$n"
fi

ok "F2 keyless spawn smoke test passed"
