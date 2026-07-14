# Go-public checklist (fks)

> **The flip happened** — `nuniesmith/fks` is **public**. This checklist is
> kept as the record + for the stragglers still open below (`src/web` removal,
> the post-flip key rotation).

The plan flips `fks` from private to **public** as the open orchestrator,
with every secret/strategy/state moved into the encrypted `fks-state` backup
(see [`STATE_BACKUP.md`](STATE_BACKUP.md)). Work top-to-bottom; the flip is the
last, one-way step.

## 1. Externalize the private surface  *(the keystone)*
- [x] `age` installed; `./scripts/fks-state.sh init` run (your age key exists and is **backed up out of band**). *(live on the prod host)*
- [x] `state.manifest` reviewed — `./scripts/fks-state.sh status` shows every secret/config/state path + DB table. *(after #203 fixed the silent file-skip, status shows the real capture set)*
- [x] `./scripts/fks-state.sh export` produced a snapshot in `fks-state`; `import --dry-run` round-trips it. *(snapshots push to fks-state; export auto-rebases first, #206)*
- [x] `import` restore-verified 2026-07-12 — the snapshot round-trips to a restorable state (proved **after** the #203 payload-path fix; earlier snapshots restored nothing).

## 2. Confirm nothing private is tracked
- [ ] `git ls-files | grep -iE '\.env$|\.key$|\.pem$|secret|cred'` → only `.example`/templates. *(verified clean 2026-06-29)*
- [ ] No secret ever in history: `git rev-list --all --objects | grep -iE '(^|/)(\.env|.*\.key|.*\.pem)$'` → empty. *(verified clean)*
- [ ] **gitleaks** content scan (the proper gate — install: `go install github.com/gitleaks/gitleaks/v8@latest`):
      `gitleaks detect --source . --log-opts="--all"` → 0 findings. The committed `.gitleaks.toml` allowlists the two known test fixtures (`sk-1234…`, `super_secret_password_123`).

## 3. Scrub internal references *(cosmetic, but do it)*
- [ ] **Tailscale hostname** `desktop.tailfef10.ts.net` → genericized in `README.md` + `crates/spawner/README.md`. *(done in this PR)*
- [ ] Internal service defaults `*.internal` in `infrastructure/config/{production,staging}/config.toml` — these are `${VAR:-default}` placeholders (no secrets/IPs). Optional: neutralize to `example.com` for a cleaner public read. Low priority.
- [ ] `.env.example` carries **no real values** (it's a template — confirm). *(verified)*

## 4. Web split done (Phase C)
- [ ] `fks-web` carries the canonical app ✅ and the web build defaults to the `WEB_REPO`/`WEB_REF` git-clone ✅ — **`src/web` removal still pending** (it survives as a dev fallback).

## 5. Decide the repo name
- [x] Kept `fks`.

## 6. Flip  *(one-way — do this last)*
```bash
gh repo edit nuniesmith/fks --visibility public --accept-visibility-change-consequences
```
- [x] **Flipped — the repo is public.**
- [ ] **Rotate every exchange/API key** that was ever in the live `.env`. Going public is the moment to assume the old keys are burned, even though they were never committed — cheap insurance. Re-`export` the state after rotation. *(Still open — parked by the operator; the old keys remain active.)*

## Already done
- The 4 libraries (rustrade / indicators-ta / exchange-apiws / janus) are public + on crates.io, MIT, secret-free.
- `fks` history is clean of committed secrets (blob + high-signal content scan).
- The `fks-state` private repo + the backup/import tooling exist (PR with `scripts/fks-state.sh`).
