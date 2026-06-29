# Go-public checklist (fks-full)

The plan flips `fks-full` from private to **public** as the open orchestrator,
with every secret/strategy/state moved into the encrypted `fks-state` backup
(see [`STATE_BACKUP.md`](STATE_BACKUP.md)). Work top-to-bottom; the flip is the
last, one-way step.

## 1. Externalize the private surface  *(the keystone)*
- [ ] `age` installed; `./scripts/fks-state.sh init` run (your age key exists and is **backed up out of band**).
- [ ] `state.manifest` reviewed — `./scripts/fks-state.sh status` shows every secret/config/state path + DB table.
- [ ] `./scripts/fks-state.sh export` produced a snapshot in `fks-state`; `import --dry-run` round-trips it.
- [ ] On a scratch checkout, `import` reproduces a runnable stack (proves recovery works **before** you need it).

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
- [ ] `fks-web` carries the canonical app; `fks-full`'s web build set to `WEB_REPO`/`WEB_REF` git-clone; `src/web` removed.

## 5. Decide the repo name
- [ ] Keep `fks-full` public, **or** rename → `fks` for a clean public name and archive the drifted `fks` scaffold. *(your call)*

## 6. Flip  *(one-way — do this last)*
```bash
gh repo edit nuniesmith/fks-full --visibility public --accept-visibility-change-consequences
```
- [ ] Immediately after: **rotate every exchange/API key** that was ever in the live `.env`. Going public is the moment to assume the old keys are burned, even though they were never committed — cheap insurance. Re-`export` the state after rotation.

## Already done
- The 4 libraries (rustrade / indicators-ta / exchange-apiws / janus) are public + on crates.io, MIT, secret-free.
- `fks-full` history is clean of committed secrets (blob + high-signal content scan).
- The `fks-state` private repo + the backup/import tooling exist (PR with `scripts/fks-state.sh`).
