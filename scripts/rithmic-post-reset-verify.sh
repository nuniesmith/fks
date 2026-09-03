#!/usr/bin/env bash
# =============================================================================
# rithmic-post-reset-verify.sh — prove a freshly-reset prop account is being
# read correctly, BEFORE trading it.
#
# WHY THIS EXISTS. On 2026-08-31 the platform showed roughly $4,500 of
# headroom while about $170 actually remained, and the evaluation was lost. The
# cause was the broker's `min_account_balance`: it reports the STATIC starting
# floor and never trails, so as equity rose the displayed floor stayed at
# 145,500 while the real trailing floor had climbed to ~150,175. We now compute
# the floor ourselves from a monotonic high-water mark.
#
# That fix introduces its own failure mode, and this script exists for it:
#
#   `high_water` is held IN MEMORY and only ever ratchets UP (`.max(equity)`).
#   A process that survives an account reset carries the OLD account's peak.
#   Restart-to-reseed is therefore load-bearing, and it is invisible — a
#   connector that kept running looks completely healthy while computing a
#   floor of 150,175 against a fresh 150,000 account. That is a -175 headroom
#   on an untouched account, or, if the numbers happen to land the other way,
#   a floor that is too LOW and permits a real breach.
#
# So this asserts the arithmetic rather than trusting the screen:
#
#   high_water           == starting equity      (nothing carried over)
#   computed_min_balance == equity - trailing_dd (the floor is where it should be)
#   headroom             == trailing_dd          (a full budget, untouched)
#   account              == the CONFIGURED id    (not the previous account's)
#
# Run it after every reset, and after any connector restart that follows one.
#
# Read-only: it performs GETs against the connector's own status endpoints and
# a SELECT against QuestDB. It never posts, and it never touches /kill.
#
# Usage:  scripts/rithmic-post-reset-verify.sh
# Env:    RITHMIC_STATUS_HOST (default 127.0.0.1:9094)
#         QUESTDB_URL         (default http://127.0.0.1:9000)
#         FKS_ENV_FILE        (default ./.env)
# Exit:   0 all checks passed · 1 a check failed · 2 could not run a check
# =============================================================================
set -uo pipefail

HOST="${RITHMIC_STATUS_HOST:-127.0.0.1:9094}"
QDB="${QUESTDB_URL:-http://127.0.0.1:9000}"
ENVF="${FKS_ENV_FILE:-.env}"
TIMEOUT=5

pass=0; fail=0; skip=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }
warn() { printf '  \033[33mSKIP\033[0m  %s\n' "$1"; skip=$((skip+1)); }

envval() { grep -oP "(?<=^$1=).*" "$ENVF" 2>/dev/null | head -1; }

WANT_ACCT="$(envval RITHMIC_ACCOUNT_ID)"
WANT_EQ="$(envval RITHMIC_STARTING_EQUITY)"
WANT_DD="$(envval RITHMIC_TRAILING_DD)"

echo "Rithmic post-reset verification"
echo "  configured account : ${WANT_ACCT:-<unset>}"
echo "  starting equity    : ${WANT_EQ:-<unset>}"
echo "  trailing drawdown  : ${WANT_DD:-<unset>}"
echo

# ── 1. the connector is up and its session is connected ─────────────────────
status="$(curl -sS -m "$TIMEOUT" "http://$HOST/status" 2>/dev/null)"
if [[ -z "$status" ]]; then
    bad "connector unreachable at $HOST — start it with: docker compose --profile rithmic up -d rithmic-connector"
    echo; echo "  $pass passed, $fail failed, $skip skipped"; exit 1
fi
# Parsed, not grepped: `"connected":true` and `"connected": true` are the same
# JSON and a substring match silently fails on one of them — a health check
# that reports "not connected" for a perfectly connected session is worse than
# no check, because it is the one you learn to ignore.
conn="$(python3 -c "
import json,sys
try: print(json.load(sys.stdin).get('connected'))
except Exception: print('unparseable')
" <<<"$status")"
case "$conn" in
    True)  ok "connector reachable and session connected" ;;
    False) bad "connector is up but NOT connected — check credentials and gateway" ;;
    *)     bad "/status did not report a 'connected' field (got: $conn)" ;;
esac

# ── 2. the PnL reader is attached to the CONFIGURED account ─────────────────
# Market data can flow perfectly while this is wrong; that split is exactly
# what went unnoticed for a full session on 2026-08-31.
pos="$(curl -sS -m "$TIMEOUT" "http://$HOST/positions" 2>/dev/null)"
if [[ -z "$pos" ]]; then
    bad "/positions returned nothing — the PnL reader is not running"
else
    got_acct="$(python3 -c "import json,sys;print(json.load(sys.stdin).get('account',''))" <<<"$pos" 2>/dev/null)"
    if [[ -z "$got_acct" ]]; then
        warn "no account on /positions yet — the reader attaches on the first account update; re-run in a minute"
    elif [[ -n "$WANT_ACCT" && "$got_acct" != "$WANT_ACCT" ]]; then
        bad "account MISMATCH: reader has '$got_acct', .env says '$WANT_ACCT' — a stale RITHMIC_ACCOUNT_ID reads the wrong (or a dead) account"
    else
        ok "PnL reader attached to $got_acct"
    fi
fi

# ── 3. the trailing floor seeded from THIS account, not the last one ────────
risk="$(python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(9)
r=d.get('risk')
if not r: sys.exit(8)
print(json.dumps(r))
" <<<"$pos" 2>/dev/null)"
rc=$?
if [[ $rc -eq 8 || -z "$risk" ]]; then
    warn "no risk state yet — it seeds on the first equity update; re-run in a minute"
elif [[ $rc -ne 0 ]]; then
    warn "could not parse /positions"
else
    read -r seeded hw cmb head dd disagree < <(python3 -c "
import json,sys
r=json.loads(sys.argv[1])
print(r['seeded'], r['high_water'], r['computed_min_balance'], r['headroom'], r['trailing_dd'], r['floor_disagreement'])
" "$risk")

    [[ "$seeded" == "True" ]] && ok "risk state seeded" || bad "risk state NOT seeded — the floor is not yet authoritative and must not be traded against"

    # THE CHECK THIS SCRIPT EXISTS FOR. On a freshly reset account the
    # high-water mark must equal the starting equity. Anything higher is the
    # previous account's peak surviving in memory.
    if [[ -n "$WANT_EQ" ]] && python3 -c "import sys;sys.exit(0 if abs($hw-$WANT_EQ)<0.01 else 1)"; then
        ok "high_water = $hw (equals starting equity — nothing carried over)"
    else
        bad "high_water = $hw but starting equity is $WANT_EQ — THE PREVIOUS ACCOUNT'S PEAK SURVIVED THE RESET. Restart the connector: docker compose --profile rithmic restart rithmic-connector"
    fi

    if [[ -n "$WANT_EQ" && -n "$WANT_DD" ]] && python3 -c "import sys;sys.exit(0 if abs($cmb-($WANT_EQ-$WANT_DD))<0.01 else 1)"; then
        ok "computed_min_balance = $cmb (= $WANT_EQ - $WANT_DD)"
    else
        bad "computed_min_balance = $cmb, expected $(python3 -c "print($WANT_EQ-$WANT_DD)" 2>/dev/null)"
    fi

    if [[ -n "$WANT_DD" ]] && python3 -c "import sys;sys.exit(0 if abs($head-$WANT_DD)<0.01 else 1)"; then
        ok "headroom = $head (full budget, untouched)"
    else
        bad "headroom = $head, expected a full $WANT_DD on an untraded account"
    fi

    # Informational, not a failure: on day one the broker's static floor and
    # ours agree, so this is ~0. It GROWS as equity rises and the broker's
    # figure stays put — that growth is the 2026-08-31 bug made visible, and
    # seeing it here is the system working, not breaking.
    printf '  \033[36mINFO\033[0m  floor_disagreement = %s (broker minus ours; grows as equity rises — expected)\n' "$disagree"
fi

# ── 4. bars are actually landing ────────────────────────────────────────────
q='select count() from candles_futures where timestamp > dateadd('"'"'m'"'"', -15, now())'
bars="$(curl -sS -m "$TIMEOUT" -G "$QDB/exec" --data-urlencode "query=$q" 2>/dev/null \
        | python3 -c "import json,sys;print(json.load(sys.stdin)['dataset'][0][0])" 2>/dev/null)"
if [[ -z "$bars" ]]; then
    warn "could not query QuestDB at $QDB"
elif [[ "$bars" -gt 0 ]]; then
    ok "$bars bar(s) written to candles_futures in the last 15 minutes"
else
    bad "no bars in candles_futures for 15 minutes — the feed is not flowing (note: expected outside RTH)"
fi

echo
echo "  $pass passed, $fail failed, $skip skipped"
[[ $fail -eq 0 ]] || exit 1
[[ $skip -eq 0 ]] || exit 2
exit 0
