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
./scripts/fks-state.sh export    snapshot → age-encrypt → commit+push
./scripts/fks-state.sh import    pull latest → decrypt → restore in place
./scripts/fks-state.sh list      list snapshots
```

## How it works

- **One [age](https://github.com/FiloSottile/age) keypair is the root secret.**
  `init` generates `~/.config/fks/age.key` (the private identity) and records the
  public recipient in `~/.config/fks/recipients.txt`. The private key decrypts
  every snapshot — **back it up out of band** (password manager / paper /
  hardware). It is the one thing not recoverable from a backup.
- **`export`** reads `state.manifest`, copies the listed files, dumps the listed
  database tables (`pg_dump --data-only` *inside* the postgres container — no host
  `pg_dump` needed), tars it, **age-encrypts** to your recipient(s), and commits
  the result to `fks-state/snapshots/fks-state-<UTC>.tar.gz.age`. The push
  **rebases on the remote first**, so a code merge landing on `fks-state` between
  snapshots can't break the backup. The private repo is just encrypted
  transport — if it leaked, the contents stay sealed to your key.
- **Sibling repos are first-class.** Manifest paths may reach *above* the fks
  checkout (`../fks-state/...`, `../fks-spawner/...`); the snapshot is anchored
  at the **parent directory** of the checkout, so sibling files round-trip
  instead of silently escaping the archive. File lines also accept an optional
  `file:` prefix (symmetric with `db:`).
- **`import`** pulls the latest snapshot, decrypts it with your key, and restores
  the files **under that same parent directory** (fks paths and `../` siblings
  land back where they came from) + replays the DB dumps via `psql`. It prompts
  before overwriting; `--dry-run` previews without touching anything.
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
- Snapshots are append-only history in `fks-state`; prune old ones there if size
  grows. Rotating exchange keys? Re-`export` after rotation.
- The age key is your single point of failure **and** the single thing that keeps
  the whole platform private. Treat it like a seed phrase.
