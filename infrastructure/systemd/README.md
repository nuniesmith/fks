# systemd user units

Host-side timers the platform depends on. **These were untracked until
2026-08-22** — they existed only in `~/.config/systemd/user/` on `oryx`, so a
host rebuild would have silently lost them and nothing would have said so.
That is the same failure family as an unmonitored monitor: the thing that
watches disappears quietly and the gap looks identical to "all clear".

| unit | what it does | if it stops |
|---|---|---|
| `fks-state-backup` | daily encrypted snapshot → age → push to the private repo | `StateBackupNotReachingRemote` fires (the metric is `absent()`-guarded) |
| `fks-digest-deadman` | every 10 min, publishes next-due/last-send gauges for **orb-briefing and advisor** | `DiscordDigestProbeNotRunning` fires after 1h |
| `fks-questdb-integrity` | hourly, publishes candle-table DEDUP/WAL state | `QuestDbIntegrityProbeNotRunning` fires after 3h |

Both alerts treat a **missing** metric as failing, so a stopped timer is loud
rather than silent. That property is deliberate and load-bearing — do not
"simplify" either expression by dropping its `absent()` clause.

## Install / restore on a fresh host

```bash
install -d ~/.config/systemd/user
cp infrastructure/systemd/*.service infrastructure/systemd/*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fks-state-backup.timer fks-digest-deadman.timer fks-questdb-integrity.timer
loginctl enable-linger "$USER"      # so user timers run without an active login
systemctl --user list-timers --no-pager
```

`enable-linger` matters: without it these stop when the last session ends,
which on a headless box means "after the next SSH disconnect".

## The textfile collector these depend on

Both write Prometheus metrics into `$FKS_TEXTFILE_DIR`
(`/home/jordan/.local/share/node_exporter/textfile`), read by node_exporter's
textfile collector. **The collector flag is baked at container-create time** —
`--collector.textfile.directory` plus the read-only mount, both in
`docker-compose.yml`. Editing `.env` alone does nothing; the container must be
recreated. Getting this half-done is exactly what left
`fks_state_backup_push_ok` absent for weeks while the emitter shipped fine.

Note also that the units carry `Environment=FKS_TEXTFILE_DIR=...` explicitly:
only `docker compose` reads `.env`, a plain shell script run by systemd does
not, so the variable has to be set on the unit.
