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

> Status: **live + restore-verified** (2026-07-12). Snapshots made before the
> 2026-07-12 fixes captured the DB dumps but silently skipped every file —
> re-`export` if your latest snapshot predates that.

## What's in a snapshot

Driven by `state.manifest` (copy `state.manifest.example` → `state.manifest`,
which is gitignored). Defaults:

| Category | Examples |
|---|---|
| Secrets & TLS | `.env`, `infrastructure/certs/` |
| Strategy configs (the edge) | the sibling bot repos' tuned configs — `../fks-state/bots/crypto-futures/…`, `../fks-spawner/bots/spot-portfolio/…` |
| Live state | journals, open-position JSON (also sibling-repo paths) |
| Model weights | `models/*.bin`, `*.safetensors` |
| DB tables (runtime secret store + account state) | `ruby_db:exchange_secrets`, `janus_db:api_keys` |

This *repopulates the secret store you already have* — the spawner's
`exchange_secrets` table and janus's Fernet-`api_keys` table — rather than
inventing a new one.

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
