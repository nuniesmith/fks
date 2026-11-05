# Private state: backup & import

`fks` is a **public** orchestrator. Everything sensitive — secrets, TLS
certs, the runtime secret store, tuned strategy configs, live trading state, and
model weights — lives **outside** the repo, in an encrypted, versioned snapshot
stored in a **private** repo (`nuniesmith/fks-state`). The public repo ships only
templates (`.env.example`, `state.manifest.example`) and the tool below.

`scripts/fks-state.sh` is that tool.

```
./scripts/fks-state.sh init      one-time: make an age key + clone fks-state
./scripts/fks-state.sh status    show what will be backed up (no secret values)
./scripts/fks-state.sh export    snapshot → age-encrypt → upload as a release
./scripts/fks-state.sh import    fetch latest → decrypt → restore in place
./scripts/fks-state.sh list      list snapshots (releases and git)
```

## Where snapshots live (since 2026-11-05)

Each new snapshot is a **private GitHub release** in `nuniesmith/fks-state`,
tagged `snapshot-<UTC stamp>`, with the encrypted tarball as its one asset.
`export` checks that GitHub holds the same number of bytes it sent, and
deletes the release again if not, so no empty release ever counts as a kept
snapshot. The newest 3 are also cached in `~/.local/share/fks-state-releases`
for a restore without the network (same disk, so not a backup).

Until then every snapshot was **committed** under `snapshots/`. Git keeps
every version forever, so the repo reached 1.57 GB on GitHub (+~10 MB a
night), and single snapshots came within a few MB of git's hard 100 MiB
per-file limit, which already broke the push once (2026-08-07). A release
asset may be 2 GiB, and releases can be deleted one at a time.

**Retention (releases only):** after each verified upload, keep the newest
`FKS_STATE_KEEP_DAILY` (30) plus the newest snapshot of every calendar month,
forever; delete the rest. Tags that aren't `snapshot-<stamp>` are never
touched. The rule is pinned by `scripts/testing/fks-state-prune-plan.test.sh`.

**The git snapshots are never pruned or rewritten.** They are the only copy of
the platform before the 2026-10-17 volume wipe (July–September: the Gate-A
evidence, the funding bot, Janus). `import` still reads them by name, e.g.
`import --dry-run 20260920T120128Z`. `FKS_STATE_STORE=git` brings back the
old export.

## How it works

- **One [age](https://github.com/FiloSottile/age) keypair is the root secret.**
  `init` generates `~/.config/fks/age.key` (the private identity) and records the
  public recipient in `~/.config/fks/recipients.txt`. The private key decrypts
  every snapshot — **back it up out of band** (password manager / paper /
  hardware). It is the one thing not recoverable from a backup.
- **`export`** reads `state.manifest`, copies the listed files, dumps the listed
  database tables (`pg_dump --data-only` *inside* the postgres container — no host
  `pg_dump` needed), tars it, **age-encrypts** to your recipient(s), and uploads
  it as a release (above). The private repo is just encrypted transport — if
  it leaked, the contents stay sealed to your key.
- **Sibling repos are first-class.** Manifest paths may reach *above* the fks
  checkout (`../fks-state/...`, `../fks-spawner/...`); the snapshot is anchored
  at the **parent directory** of the checkout, so sibling files round-trip
  instead of silently escaping the archive. File lines also accept an optional
  `file:` prefix (symmetric with `db:`).
- **`import`** fetches the latest snapshot (the newest release, else the
  newest cached copy, else git's latest), decrypts it with your key, and
  restores the files **under that same parent directory** (fks paths and `../`
  siblings land back where they came from) + replays the DB dumps via `psql`
  **with user triggers off** (`session_replication_role = replica`). Before
  2026-11-05 the replay ran through the ladder's guards, and one of them
  (`edge_experiments_after_hypothesis`) names `edge_hypotheses` without a
  schema while `pg_dump` clears `search_path`, so every ladder verdict was
  silently dropped from a restore. It prompts before overwriting; `--dry-run`
  previews without touching anything.
- **A DB restore needs the schema first.** The dumps are data-only: restore
  onto a database the `fks-postgres` image's initdb (or `fks-migrate`) has
  built. Janus creates its own tables when it starts, so start Janus before
  importing `janus_db`, or its rows have nowhere to go.
- The tool **never prints secret values** — only paths, sizes, and counts.

> **DB rename (2026-07-21):** the spawner database was renamed `ruby_db` → `fks_db`
> (env var name `RUBY_DB` retained). Snapshots taken **before 2026-07-21** contain
> `db/ruby_db.sql` payloads keyed to the old database name — restoring one onto a
> `fks_db` instance needs a manual rename hop (restore into a `ruby_db` first, then
> `ALTER DATABASE ruby_db RENAME TO fks_db`, or rewrite the dump's target). New
> snapshots write `db/fks_db.sql`.

> Status: **live + restore-verified** (2026-07-12). Snapshots made before the
> 2026-07-12 fixes captured the DB dumps but silently skipped every file —
> re-`export` if your latest snapshot predates that.

> **Export fix (2026-07-23):** the DB dump loop drained its own stdin (`docker
> compose exec -T` inside a `while read` consumed the manifest), so only the
> **first** `db:` line (`exchange_secrets`) was ever dumped — every other
> table (funding risk/ledger, webui auth/audit, janus `api_keys`) was silently
> absent. Fixed in `fks-state.sh` (union all tables per db, `pg_dump` with
> `</dev/null`). **Any snapshot taken before 2026-07-23 is DB-incomplete —
> re-`export` and confirm every `db/*.sql` payload is present.**

## What's in a snapshot

Coverage is **whatever `state.manifest` lists — nothing more**. Copy
`state.manifest.example` → `state.manifest` (gitignored) and keep it in step with
the schema: a snapshot only captures the files/tables named in it, silently, so
an unlisted table or cert is simply absent from DR with no error. Don't assume
"full coverage" — audit the manifest against the live schema when either changes.

The `state.manifest.example` defaults capture:

| Category | Examples |
|---|---|
| Secrets & TLS | `.env`, `.env.secrets`, `infrastructure/certs/` |
| Strategy configs (the edge) | the sibling bot repos' tuned configs — `../fks-state/bots/crypto-futures/…`, `../fks-spawner/bots/spot-portfolio/…` |
| Live state | journals, open-position JSON (also sibling-repo paths) |
| Model weights | `models/*.bin`, `*.safetensors`, `*.pt`, `*.onnx` |
| DB — secret store | `fks_db:exchange_secrets`, `janus_db:api_keys,api_key_audit` |
| DB — funding bot | `fks_db:framework_risk_state,funding_kill_switch` (LIVE risk state — the SessionPnl/CircuitBreaker halt + kill sentinel), `funding_open_trades,funding_paper_records` (open positions + paper PnL ledger) |
| DB — WebUI auth & audit | `fks_db:webui_users,webui_sessions,webui_auth_audit,webui_invites,webui_alert_acks`, `fks_db:notification_log` |

This *repopulates the state you already have* — the spawner's `exchange_secrets`
table, janus's Fernet-`api_keys` table, the funding bot's risk/ledger tables, and
the webui auth tables — rather than inventing a new one.

> **A --data-only restore needs the table's schema to already exist** on the
> target (it replays `COPY`/`INSERT`, not `CREATE`). Every table listed above is
> backed by a `src/sql/spawner/` migration baked into the postgres image
> (`014_funding_state.sql` added the funding tables + the scoped `fks_funding`
> role for exactly this reason — review H1/H3), so a fresh-host bootstrap creates
> them before `import` loads the data. Only list a table here once its CREATE
> lives in `src/sql/`.

### Restore notes (what each table brings back)

- **`framework_risk_state` / `funding_kill_switch`** — the funding bot's live
  halt state. Restoring them means a bot that had **tripped its circuit breaker
  or been manually killed comes back HALTED**, as it should. Omitting them (the
  pre-H3 gap) silently re-armed a halted strategy with a cleared loss window.
- **`webui_users`** — restores the **admin account**. Without it a restore boots
  to **bootstrap mode**: fks-web reseeds a CSPRNG admin (password printed to the
  log) when the users table is empty, so you are never locked out — but the
  original operators, their roles, and the pending invites are **gone**.
- **`webui_auth_audit` / `notification_log`** — append-only forensic ledgers
  ("did the crash-page send at 3am?"). Excluding them loses the audit trail for
  the very incident a restore is consulted about.

## On oryx (2026-10-27)

FKS runs from the deploy checkout `/home/actions/fks`, owned by `actions`; the
backup runs as `jordan` from `~/github/fks`. Three consequences:

- **The manifest lives outside both checkouts:** `~/.config/fks/state.manifest`,
  passed as `FKS_STATE_MANIFEST` by `fks-state-backup.service`. It was rebuilt
  from the live schema on 2026-10-27; the 2026-09 list still named the retired
  spot bot's volume and had never covered the live trader's
  (`fks-bot-state-crypto-regime`). Audit it whenever the schema or the bots
  change: every table listed for a database goes into one `pg_dump`, so a
  table that does not exist drops that database's whole dump.
- **The DB dumps reach the live Postgres** because compose names the project
  after the folder (`fks`), so `docker compose exec postgres` from
  `~/github/fks` finds the live container. No access to the deploy's `.env` is
  needed for that.
- **The deploy's `.env` is not in the snapshot** (it is `actions`-only, mode
  600). It holds `SPAWNER_SECRETS_KEY`, which decrypts `exchange_secrets` and
  `notification_channels`. After a restore onto a fresh deploy, re-enter the
  Kraken key and the webhooks in Settings; everything else the deploy
  regenerates.

The metric (`fks_state_backup_push_ok`, which `StateBackupNotReachingRemote`
reads) is written to `/var/lib/node_exporter/textfile`, the folder the fks
compose mounts into node-exporter. That folder is root-owned on a fresh box;
until `sudo chown jordan /var/lib/node_exporter/textfile`, the backup still
runs and pushes, but the metric is skipped and the alert stays up.

Not covered by this snapshot: the recorded data lake (`/srv/fks-lake`, GBs a
day), which needs its own offsite copy.

## First-time setup

```bash
# 0. install age once:  sudo apt install age   (or a static binary from the releases)
# 1. create the private repo (once):  gh repo create nuniesmith/fks-state --private
./scripts/fks-state.sh init       # makes your key, clones fks-state, seeds state.manifest
$EDITOR state.manifest            # tune to your deployment
./scripts/fks-state.sh status     # sanity-check what will be captured
./scripts/fks-state.sh export "first snapshot"
```

On a fresh box (disaster recovery): install age, **restore your `age.key`**, then
`git clone …/fks && cd fks && ./scripts/fks-state.sh import` → the stack
is ready to bring up.

## Security notes

- `state.manifest`, `*.age`, and the age key paths are gitignored — only the
  `.example` template and the tool are tracked.
- Release snapshots are pruned by the retention rule above; git snapshots are
  history and stay. Rotating exchange keys? Re-`export` after rotation.
- The age key is your single point of failure **and** the single thing that keeps
  the whole platform private. Treat it like a seed phrase.
