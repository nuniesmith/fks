#!/bin/sh
# =============================================================================
# deadman-ping.sh — external dead-man's-switch heartbeat
# =============================================================================
# Sends a plain GET to ${DEADMAN_PING_URL} (a hosted dead-man check, e.g.
# healthchecks.io) every ${DEADMAN_INTERVAL_SECS:-60}s. The hosted check pages
# when the pings STOP — covering the one failure mode no on-box alert can
# report: oryx (or its power / disk / network / docker daemon) is down
# entirely. Today "no alerts" and "total outage" are the same signal; this
# script is what makes them different.
#
# Runs as the `deadman` compose service (pure observer: no depends_on, no
# ports, the only volume is this script). Also runnable standalone or from a
# host cron if the container path is ever unavailable.
#
# Behaviour:
#   - DEADMAN_PING_URL unset/empty  -> logs one line, then idles forever
#     (keeps the container up so `restart: unless-stopped` doesn't thrash).
#     This is the "silently disabled" state — safe default for fresh checkouts.
#   - curl failure                  -> logged on state TRANSITIONS only (ok->fail,
#     fail->ok), loop continues. A transient blip never kills the pinger.
#   - The URL is NEVER logged: the healthchecks.io path contains the check's
#     secret UUID. curl runs with stderr discarded for the same reason; only
#     the numeric curl exit code is logged.
#
# Setup + what a page means: docs/infrastructure/DEADMAN_SWITCH.md
# =============================================================================

set -u

log() {
    printf '%s deadman: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1"
}

# Interruptible sleep: `sleep` runs in the background and we `wait` on it, so
# a `docker stop` (SIGTERM) is handled immediately instead of after up to a
# full interval (a foreground `sleep` would block signal delivery in sh).
snooze() {
    sleep "$1" &
    wait $! || true
}

trap 'log "stop signal received - exiting"; exit 0' INT TERM

interval="${DEADMAN_INTERVAL_SECS:-60}"
case "$interval" in
    '' | *[!0-9]*)
        log "invalid DEADMAN_INTERVAL_SECS ('${interval}') - falling back to 60"
        interval=60
        ;;
esac

if [ -z "${DEADMAN_PING_URL:-}" ]; then
    log "DEADMAN_PING_URL not set - dead-man pinger disabled, idling"
    while :; do snooze 3600; done
fi

log "started - GET heartbeat every ${interval}s (URL withheld from logs)"

state=""
while :; do
    # -f: HTTP >= 400 is a failure; -s + 2>/dev/null: nothing curl prints can
    # leak the URL/UUID; -o /dev/null: response body discarded (no payload
    # either direction beyond the GET itself); -m 10: never wedge the loop.
    if curl -fs -m 10 -o /dev/null "$DEADMAN_PING_URL" 2>/dev/null; then
        [ "$state" = ok ] || log "heartbeat OK"
        state=ok
    else
        rc=$?
        [ "$state" = fail ] || log "heartbeat FAILED (curl exit ${rc}) - retrying every ${interval}s"
        state=fail
    fi
    snooze "$interval"
done
