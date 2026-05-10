# FKS Split Plan

> Operational blueprint for cracking `fks-full` into multiple repos.
> Nothing in this document moves code today — it's a checklist so the
> moves, when they happen, land cleanly on the first try.
>
> **Last updated:** 2026-05-10

---

## End-state vision

`fks-full` becomes a **private orchestration repo** — the place that runs
production, holds secrets, defines the deployment topology, and houses my
**actual trading strategies** (the parts I don't open-source).

Everything reusable lives in its own public repo and is consumed from
crates.io / PyPI / npm.

```
                        ┌────────────────────────────────────┐
                        │       fks-full  (PRIVATE)          │
                        │                                    │
                        │  docker-compose.yml                │
                        │  infrastructure/  (Dockerfiles)    │
                        │  proto/           (protobuf defs)  │
                        │  scripts/         (run.sh, ops)    │
                        │  strategies/      (private brains) │
                        │  .env / secrets                    │
                        └────┬───────────────────────────────┘
                             │ consumes
       ┌─────────────────────┼─────────────────────┬──────────────┐
       ▼                     ▼                     ▼              ▼
  ┌─────────┐         ┌─────────┐           ┌──────────┐    ┌─────────┐
  │rustrade │         │  janus  │           │indicators│    │exchange │
  │(public) │         │ (public │           │   -ta    │    │ -apiws  │
  │crates.io│         │ or priv)│           │(public)  │    │(public) │
  └─────────┘         └─────────┘           └──────────┘    └─────────┘
       │                                                          │
       └──────────────────────────┬───────────────────────────────┘
                                  │ consumed by spawned bot containers
                                  ▼
                            ┌──────────┐
                            │ spawner  │  ◄── separate published crate
                            │ (public) │      manages bot lifecycles
                            └──────────┘
                                  │
                                  │ Python side:
                                  ▼
                            ┌──────────┐
                            │  ruby    │  ◄── data pipeline + ML
                            │ (public  │      lives in nuniesmith/ruby
                            │  or priv)│
                            └──────────┘

                            ┌──────────┐
                            │ fks-web  │  ◄── SvelteKit dashboard
                            │ (public) │      lives in nuniesmith/fks-web
                            └──────────┘
```

---

## Repo map (target)

| Future repo                            | Visibility | Today's path                | First release plan |
|----------------------------------------|------------|------------------------------|--------------------|
| `nuniesmith/rustrade`                  | public     | `crates/rustrade/`           | Publish `rustrade-{core,supervisor,risk,backtest,notify}` + facade `rustrade` to crates.io |
| `nuniesmith/indicators-ta`             | public     | `crates/indicators-ta/`      | Publish to crates.io |
| `nuniesmith/exchange-apiws`            | public     | `crates/exchange-apiws/`     | Publish to crates.io |
| `nuniesmith/spawner`                   | public     | `crates/spawner/`            | Publish; produces both a binary image and a re-usable library |
| `nuniesmith/janus`                     | TBD (probably private) | `crates/janus/`  | Will be carved up per `JANUS_EXTRACTION_PLAN.md` — public siblings ship via crates.io, the brain stays private |
| `nuniesmith/ruby`                      | TBD        | `src/ruby/`                  | Python package; deployed as the `nuniesmith/fks:ruby` Docker image |
| `nuniesmith/fks-web`                   | public     | `src/web/`                   | Dockerized SvelteKit app |
| `nuniesmith/fks-full` (this repo)      | **private** | — (we're already here)      | Docker compose + secrets + strategies only |

### What stays in `fks-full` post-split

- `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.trainer.yml`
- `infrastructure/` — Dockerfiles, configs (nginx, prometheus, grafana, …), Kubernetes manifests, Tailscale certs
- `proto/` — shared `.proto` definitions (source of truth)
- `src/proto/` — `fks-proto` Rust crate (consumed by rustrade, janus, spawner)
- `scripts/` — operational scripts (`run.sh` and friends)
- `.env.example`, `mkdocs.yml`, `LICENSE`, `README.md`, `CLAUDE.md`, `TODO.md`
- `docs/` — runbooks + architecture notes for the production deployment
- (new) `strategies/` — the actual private trading logic the rest of the world doesn't see

### What leaves `fks-full`

Eventually empty (each becomes a `*_REF` build arg pointing at the external repo):
- `crates/rustrade/`
- `crates/indicators-ta/`
- `crates/exchange-apiws/`
- `crates/spawner/`
- `crates/janus/`
- `src/ruby/`
- `src/web/`

---

## Removal candidates (now, not later)

> The "less surface area" pass before the splits, to keep both this repo
> and each future repo small and focused.

### `crates/rustcode/` — REMOVE

Status: workspace currently broken (32 errors from incomplete `TaskExecutor`
work). The Claude/Zed CLI + Claude API path covers the same need today
without the operational overhead. Bring it back later as its own repo if
the assistant story changes.

**To remove:** the whole `crates/rustcode/` directory, plus:
- `infrastructure/docker/services/rustcode/`
- `rustcode` + `fks_ollama` + `fks_ollama_init` + `openclaw` + `openclaw_cli` + `promptfoo` entries in `docker-compose.yml` *(already removed in the working tree as of 2026-05-10)*
- `infrastructure/config/openclaw/`, `infrastructure/promptfoo/`
- the `/api/code/*` location blocks in `infrastructure/config/nginx/conf.d/*.conf`
- `RC_*` and `OPENCLAW_*` env vars in `.env.example`

### `infrastructure/docker/services/openclaw{,_cli}/` — REMOVE

Same reasoning as rustcode. The Discord bridge can be rebuilt against
alertmanager-discord which we keep.

### `crates/kucoin/` (legacy bot) — REMOVE

The pre-rustrade KuCoin bot. Replaced by `rustrade::Bot` + the
`rustrade-kucoin` adapter + `crates/rustrade/examples/kucoin-v2/`. The
legacy code under `crates/kucoin/` adds no functionality the rustrade
stack doesn't already provide.

**Keep:**
- `crates/rustrade/crates/rustrade-kucoin/` (the published adapter)
- `crates/rustrade/examples/kucoin-v2/` (reference impl)
- `crates/rustrade/examples/kucoin-stub-bot/` (test scaffolding)

### Quick win when removing all of the above

Once `rustcode + openclaw + ollama + promptfoo + kucoin (legacy)` are
gone, the docker-compose container count drops from ~23 → ~15. Easier
to reason about, faster to bring up, fewer secrets in `.env`.

---

## Per-future-repo doc requirements

Each future-external directory needs **README.md + CLAUDE.md + TODO.md**
*before* the split so the new repo isn't born blind.

| Path                       | README | CLAUDE | TODO | Notes |
|----------------------------|:------:|:------:|:----:|-------|
| `crates/rustrade/`         | ✅     | added in this PR | added in this PR | also has CONTRIBUTING.md, NEXT_STEPS.md |
| `crates/janus/`            | ✅     | added in this PR | ✅   | also has JANUS_EXTRACTION_PLAN.md |
| `crates/indicators-ta/`    | ✅     | added in this PR | added in this PR | |
| `crates/exchange-apiws/`   | ✅     | added in this PR | added in this PR | |
| `crates/spawner/`          | ✅     | added in this PR | added in this PR | recently moved from `src/spawner/` |
| `src/ruby/`                | ✅     | added in this PR | ✅   | |
| `src/web/`                 | ✅     | added in this PR | ✅   | |

The new CLAUDE.md files follow the same structure as the root one
(overview → stack → build commands → conventions → gotchas) but are
self-contained — readable without any context from `fks-full`.

---

## Sequencing — when to actually split

### Phase 0 — *we are here* (this PR)
- [x] Write `SPLIT_PLAN.md` (this file).
- [x] Land per-sub-codebase `CLAUDE.md` and `TODO.md`.
- [x] Update root `CLAUDE.md` / `TODO.md` / `README.md` to reflect the
      direction and drop dead scope (rustcode, openclaw).
- [ ] Decide: rustcode + openclaw removal in a follow-up PR (one focused
      PR that deletes everything in one go).

### Phase 1 — Tidy in-place
1. Land the in-progress reorganization (currently uncommitted in working
   tree): `src/spawner/` → `crates/spawner/`, `src/kucoin/` → `crates/kucoin/`,
   sql tree co-located with owners, `JANUS_EXTRACTION_PLAN.md` →
   `crates/janus/JANUS_EXTRACTION_PLAN.md`.
2. Fix root `Cargo.toml` workspace members to point at the new paths
   (currently broken; `cargo check --workspace` fails because
   `src/spawner/Cargo.toml` no longer exists).
3. Remove `crates/rustcode/`, `crates/kucoin/`, `infrastructure/docker/services/{rustcode,openclaw,openclaw_cli,promptfoo}/`,
   and the matching nginx + env-var entries.
4. CI: confirm every remaining workspace's `cargo check` + `cargo test` pass.

### Phase 2 — Publish the small, safe ones
- `indicators-ta` → crates.io
- `exchange-apiws` → crates.io
- `spawner` → crates.io (binary crate; image becomes `nuniesmith/spawner` on Docker Hub)
- `rustrade-{core,supervisor,risk,backtest,notify}` → crates.io
- `rustrade-kucoin` → crates.io
- `rustrade` (facade) → crates.io

Each one becomes its own repo; the crates.io publish is the moment of
truth that proves it's standalone.

### Phase 3 — Move dependents to consume the published crates
- Update `crates/janus/`'s Cargo.tomls: `rustrade-supervisor = "x.y"` (crates.io) instead of `path = "../../../rustrade/..."`.
- Verify nothing in `fks-full` still uses a local path dep for the
  published crates.

### Phase 4 — Move janus + ruby + web to their own repos
- `crates/janus/` → `github.com/nuniesmith/janus` (or `janus-private`)
  — see `JANUS_EXTRACTION_PLAN.md` for the per-sub-crate destination.
- `src/ruby/` → `github.com/nuniesmith/ruby`. The Dockerfile in
  `infrastructure/docker/services/data/Dockerfile` becomes a
  `git clone --branch ${RUBY_REF:-main}` build.
- `src/web/` → `github.com/nuniesmith/fks-web`. Same Dockerfile pattern.

### Phase 5 — `fks-full` is the private orchestrator
- Repo flips `private`.
- New top-level `strategies/` directory for the actual trading IP.
- All crate deps in `Cargo.toml` (if any remain) point at crates.io.
- All service images either `git clone` external repos or pull pre-built
  images from a private registry.

---

## Risks / open decisions

- **Janus visibility.** The JANUS_EXTRACTION_PLAN already splits janus
  into public siblings + private brain. Decide whether the whole janus
  repo is private (simpler) or split into two repos at the GitHub
  level (cleaner public story). Recommendation: split — the public
  siblings have value on crates.io.
- **rustrade-kucoin's home.** Lives inside the rustrade workspace
  today. Could publish from there, or extract to its own
  `rustrade-kucoin` repo if it grows beyond ~500 LOC. Publish from
  rustrade for v0.1; extract later if needed.
- **Crate naming for the public siblings of janus.** Open question
  from `JANUS_EXTRACTION_PLAN.md` — `-ta` suffix vs `trading-` prefix
  vs `rustrade-` prefix. Pick a convention before Phase 2 publishing.
- **`crates/janus/JANUS_EXTRACTION_PLAN.md` location.** Currently
  moved (uncommitted) from repo root. Keep it inside `crates/janus/`
  so it travels with the janus repo when extracted.

---

## Validation checklist before each move

For every directory that becomes its own repo:

- [ ] `cargo check --workspace` (or `npm run check`, or `pytest`) passes from inside the directory.
- [ ] `README.md` is self-contained — no references to `fks-full` paths.
- [ ] `CLAUDE.md` describes everything an AI assistant needs to know to work in the repo without context from elsewhere.
- [ ] `TODO.md` only lists work that belongs in this repo.
- [ ] Every dep is either crates.io / PyPI / npm, OR a path dep that the new repo can satisfy locally.
- [ ] CI config (when added in the new repo) actually runs the tests.
- [ ] License + repo URL in `Cargo.toml` / `package.json` / `pyproject.toml` updated.
- [ ] The current `fks-full` Dockerfile that consumed the code gets a `git clone --branch ${REPO_REF:-main}` step.
