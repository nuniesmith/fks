# Pre-publish audit (Phase 2 of `SPLIT_PLAN.md`)

> **Historical (2026-05).** The publish run has since executed — current
> published versions are `rustrade-framework` 0.4.x, `indicators-ta` 0.2.x,
> `exchange-apiws` 0.9.0, `jflow-core` 0.1.0 (see `CLAUDE.md` / TODO). The
> `spawner` open question resolved itself: it moved to its **own repo**
> (`fks-spawner`, fks #196) and ships as a Docker image, not a crate. Kept
> as the record of the pre-publish state; the per-crate paths below no
> longer exist in this tree.
>
> Last refreshed 2026-05-12 with `cargo package --no-verify --allow-dirty`
> results.
>
> **What this is:** a per-crate inventory of what's blocking each
> crates.io publish, plus the recommended execution order and the
> chicken-and-egg gotcha that defines that order.
>
> **What this is NOT:** an execution log. Nothing is published here.

---

## TL;DR

| Crate | Cargo.toml metadata | `cargo package` | Blocker |
|---|---|---|---|
| `indicators-ta` | ✅ | ✅ packages cleanly (69 files) | none — publishable today |
| `exchange-apiws` | ✅ | ✅ packages cleanly (31 files) | none — publishable today |
| `rustrade-core` | ✅ | ✅ packages cleanly (14 files) | none — publishable today |
| `rustrade-supervisor` | ✅ | ✅ packages cleanly (11 files) | none — publishable today |
| `rustrade-risk` | ✅ | ⛔ can't dry-run | waits on `rustrade-core` being live |
| `rustrade-backtest` | ✅ | ⛔ can't dry-run | waits on `rustrade-core` |
| `rustrade-notify` | ✅ | ⛔ can't dry-run | waits on `rustrade-core` + `rustrade-supervisor` |
| `rustrade-kucoin` | ✅ | ⛔ can't dry-run | waits on `rustrade-core` + `exchange-apiws` |
| `rustrade` (facade) | ✅ | ⛔ can't dry-run | waits on every `rustrade-*` sibling |
| `spawner` | ❌ | not attempted | rename, license, repository, keywords, categories, edition — see below |

**Four crates are immediately publishable** (top half). The downstream
rustrade crates cannot even `cargo package --no-verify` until their
upstream siblings hit crates.io — this is the chicken-and-egg covered
below.

---

## The chicken-and-egg

`cargo package --no-verify --allow-dirty` still fetches the crates.io
index to resolve dependency declarations. Five of the rustrade crates
fail this check:

```
rustrade-risk:     no matching package named `rustrade-core` found
rustrade-backtest: no matching package named `rustrade-core` found
rustrade-notify:   no matching package named `rustrade-core` found
rustrade-kucoin:   no matching package named `rustrade-core` found
rustrade (facade): no matching package named `rustrade-core` found
```

**There's no way around this short of a private registry.** Publishing
is inherently a one-way trip past `rustrade-core` — once it goes live
with version 0.1.0, downstream crates can finally dry-run and publish.

**Implication for the execution PR:** if a metadata typo in
`rustrade-core` 0.1.0 ships, the fix is to publish 0.1.1 — not to yank.
Get the metadata right before the first publish.

---

## Recommended execution (dependency order)

```bash
# Step 1 — leaves with zero internal deps
cd crates/indicators-ta
cargo publish --dry-run && cargo publish

cd crates/exchange-apiws
cargo publish --dry-run && cargo publish

# Step 2 — rustrade-core (root of the rustrade dep graph)
cd crates/rustrade/crates/rustrade-core
cargo publish --dry-run && cargo publish

# Wait ~1 minute for the index to update, then continue with siblings:

cd ../rustrade-supervisor    && cargo publish --dry-run && cargo publish
cd ../rustrade-risk          && cargo publish --dry-run && cargo publish
cd ../rustrade-backtest      && cargo publish --dry-run && cargo publish
cd ../rustrade-notify        && cargo publish --dry-run && cargo publish

# Step 3 — kucoin (after exchange-apiws is live)
cd ../rustrade-kucoin        && cargo publish --dry-run && cargo publish

# Step 4 — facade (after every sibling)
cd ../rustrade               && cargo publish --dry-run && cargo publish
```

Each `cargo publish` call needs `CARGO_REGISTRY_TOKEN` (via
`~/.cargo/credentials.toml` or env). One-time setup if not already done.

---

## Per-crate status

### `indicators-ta` v0.1.3 — ✅ READY

- All metadata fields populated (`description`, `license = "MIT"`,
  `repository = "https://github.com/nuniesmith/indicators-ta"`,
  `documentation = "https://docs.rs/indicators-ta"`, `readme`,
  `keywords`, `categories`).
- Standalone workspace (`[workspace]` at top of Cargo.toml, fixed in PR #22).
- Zero path deps.
- `LICENSE` + `README.md` files present at the crate root.
- `cargo package --no-verify --allow-dirty` succeeds — 69 files, 136 KiB compressed.

**One caveat:** version `0.1.3` suggests prior uploads. Verify ownership
on crates.io before publishing (`cargo search indicators-ta`).

### `exchange-apiws` v0.1.10 — ✅ READY

Same shape as indicators-ta. Standalone workspace, all metadata,
LICENSE + README present, packages cleanly (31 files, 80 KiB). Version
`0.1.10` similarly suggests prior uploads.

### `rustrade-core` v0.1.0 — ✅ READY

Inherits `version`, `license`, `repository`, `authors`, `edition`,
`rust-version` from `crates/rustrade/Cargo.toml`'s `[workspace.package]`.
Adds per-crate `description`, `readme`, `keywords`, `categories`.

After PR #26 added per-crate `LICENSE` and `README.md`:
- `cargo package --no-verify --allow-dirty` succeeds — 14 files, 15 KiB.

### `rustrade-supervisor` v0.1.0 — ✅ READY

Same shape as rustrade-core. Crucially, this crate's `[dependencies]`
use **explicit version pins** (not `workspace = true`) so external
workspaces — including `crates/janus/bin/janus/` today and crates.io
consumers tomorrow — can path-dep it without mirroring its transitive
deps. `cargo package` succeeds — 11 files, 21 KiB.

### `rustrade-risk` v0.1.0 — 🟡 BLOCKED on upstream

Metadata complete after PR #26. Can't `cargo package --no-verify` yet
because cargo can't resolve `rustrade-core = { path = "../rustrade-core",
version = "0.1.0" }` — that `version` must exist on crates.io.

**Will publish cleanly once `rustrade-core` is live.**

### `rustrade-backtest` v0.1.0 — 🟡 BLOCKED on upstream

Same as rustrade-risk. Blocked on `rustrade-core` being live.

### `rustrade-notify` v0.1.0 — 🟡 BLOCKED on upstream

Same. Also depends on `rustrade-supervisor`, so technically blocked on both.

### `rustrade-kucoin` v0.1.0 — 🟡 BLOCKED on upstreams

Depends on `rustrade-core` AND `exchange-apiws`. Publishable after
both are live.

### `rustrade` (facade) v0.1.0 — 🟡 BLOCKED on every sibling

The facade re-exports `rustrade-core`, `rustrade-supervisor`,
`rustrade-risk`, `rustrade-backtest`, `rustrade-notify`, `rustrade-kucoin`.
Must be the LAST publish in the rustrade family.

### `spawner` v0.1.0 — 🟥 NOT READY

Missing nearly every field crates.io requires:

- ❌ `license` not set
- ❌ `repository` not set
- ❌ `documentation` not set
- ❌ `readme` not set
- ❌ `keywords` not set
- ❌ `categories` not set
- ❌ `LICENSE` file at `crates/spawner/` missing
- ❌ `edition = "2021"` (other publishable crates are on `2024`)
- ❌ **`name = "spawner"` is almost certainly taken** on crates.io.
  Rename candidates: `fks-spawner`, `bot-spawner`, `docker-bot-spawner`.

**Recommendation:** defer publishing `spawner` to crates.io. It's
primarily a Docker-image-shipped service; crates.io makes sense only
if downstream users want it as a library. If keeping for library use,
treat the cleanup as a separate PR.

---

## Tarball-content cleanup (optional, before publish)

The 69-file `indicators-ta` and 31-file `exchange-apiws` tarballs
include files that don't help downstream consumers:

- `.github/workflows/*` — repo workflow files
- `.zed/settings.json` — editor preferences
- `CLAUDE.md`, `TODO.md` — assistant + dev workflow notes
- `scripts/*` — dev helpers

Nothing here breaks anything, but it bloats the download. Optional
follow-up before first publish, per crate:

```toml
[package]
exclude = [
    ".zed",
    ".github",
    "CLAUDE.md",
    "TODO.md",
    "scripts/",
]
```

The four rustrade-* crates that package today (rustrade-core,
rustrade-supervisor, rustrade-risk, rustrade-backtest if it ever
packages, etc.) are already lean — 11–14 files each — and don't need
this.

---

## Open questions

1. **Should `spawner` publish to crates.io at all?** It's a binary-only service
   consumed as a Docker image. If yes, decide the renamed package name.

2. **`indicators-ta` 0.1.3 and `exchange-apiws` 0.1.10** — were these previously
   published by you? Run `cargo search` to confirm. If they're someone else's, the
   crate name claim is gone and we need new names.

3. **`rustrade-kucoin` publish position.** Confirmed after `exchange-apiws`.
   The path dep `exchange-apiws = { path = "../../../exchange-apiws",
   version = "0.1.10" }` resolves via the published version at publish time.

4. **First publish PR scope.** Single PR that publishes everything sequentially,
   or one PR per crate? Per-crate is safer (each PR is reversible-ish via
   patch-bump if a typo gets through) but more PR noise. Single coordinated
   PR is faster but a typo on crate 3 of 9 strands crates 1+2 already live.

---

## What lands in the actual publish PR

This audit + the polish PR (#26) get the metadata right. The actual
publish PR is:

1. Run the dependency-ordered commands above with `cargo publish`
2. Optionally add `[package].exclude` to slim tarballs for
   indicators-ta + exchange-apiws first
3. Open the docs.rs build for each crate (automatic on publish)
4. Set up `docs.rs/badge.svg` and `crates.io/badge.svg` links in the
   workspace README

Nothing in the rustrade repo's code needs to change for this. The
exception is `spawner` which needs the metadata cleanup before it
becomes publishable.
