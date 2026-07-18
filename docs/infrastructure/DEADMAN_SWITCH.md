# External Dead-Man's Switch

**The problem:** every alert this platform can send — Prometheus rules,
Alertmanager, the Discord bridge, even the bots' own webhook pushes — runs on
oryx. If oryx loses power, its disk, its network, or the Docker daemon, the
platform's last act is *silence*, not a page. Until this switch exists,
"no alerts" and "total outage" are the same signal.

**The fix:** invert the direction. The `deadman` compose service sends a tiny
GET heartbeat to a **hosted** dead-man check every 60 s
(`scripts/monitoring/deadman-ping.sh`). The hosted check — not anything on
oryx — pages when the heartbeat **stops**. It is the only alert in the stack
that works when the box is off.

## Setup (one time, ~10 minutes)

1. **Create a free check.** [healthchecks.io](https://healthchecks.io) free
   tier is plenty (20 checks); [Dead Man's Snitch](https://deadmanssnitch.com)
   or any equivalent works the same way. Create one check named e.g.
   `oryx-heartbeat`.
2. **Tune the schedule.** Recommended: **Period = 2 min, Grace = 5 min**.
   The pinger fires every 60 s, so a page means ~7 consecutive minutes of
   missed heartbeats — tolerant of a brief ISP blip, fast enough to matter.
3. **Wire the alert.** In the check's integrations, add delivery that does
   NOT depend on oryx or on you watching Discord: email at minimum; the
   healthchecks.io mobile app / SMS / Pushover if you want a real page.
   (Pointing it at a Discord webhook also works and is still valid here —
   Discord's servers are off-box.)
4. **Set the URL in `.env` on oryx** (this file is never committed):

   ```bash
   DEADMAN_PING_URL=https://hc-ping.com/<your-check-uuid>
   ```

   Treat the URL as a secret — the UUID in the path is the only
   authentication the check has. The pinger script never logs it.
5. **Start the service** (next deploy picks it up automatically; to start it
   alone): `docker compose up -d deadman`. With `DEADMAN_PING_URL` unset the
   container stays up but idles — fresh checkouts need no setup and nothing
   thrashes.

## What a page means

A dead-man page means **oryx, or its path to the internet, is DOWN** — the
one failure mode no on-box alert can ever report. Concretely, one of:

- host power loss / hardware or disk failure / kernel panic
- the home ISP or LAN is down
- the Docker daemon died (which also means the entire live stack died)
- the `deadman` container itself was stopped and not restarted
  (`restart: unless-stopped` — a plain `docker stop` sticks)
- least likely: the hosted check provider is having an outage

Triage order: can you reach the box (Tailscale/SSH)? → if yes,
`docker ps | grep fks_deadman` and `docker logs fks_deadman` (the script logs
state transitions only, never the URL); if no, it's power/ISP/hardware — go
look at the machine. Remember the Gate-A context: the paper funding bot and
janus run on this box; a real outage here pauses the measurement window.

## Design notes

- **Pure observer.** No `depends_on`, no ports, no reads from any other
  service — it must never block or be blocked by the rest of the stack.
- **Heartbeat, not status.** The GET carries no payload and no secrets in
  logs; it asserts exactly one bit: "this box is alive and can reach the
  internet". Armed-path/service-level alerting stays with Prometheus rules —
  do not overload the dead-man with meaning beyond host liveness.
- **Failure handling:** curl failures are logged on state transitions only
  and the loop keeps retrying forever; the hosted check turning red IS the
  alert, the local log line is just for triage afterwards.
