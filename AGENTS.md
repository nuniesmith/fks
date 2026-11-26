# AGENTS.md — fks

The operational / orchestration root of the FKS trading platform: Docker compose topology, nginx and monitoring config, DB bootstrap, proto, deployment tooling. It **consumes** the reusable pieces (rustrade, janus, indicators-ta, exchange-apiws, fks-web, fks-spawner) from their own repos / crates.io — it does not contain them.

## Start here

- **`CLAUDE.md` in this repo is the detailed, canonical instruction file** — service map, repo map, consumption direction, conventions. Read it first; this file only adds cross-cutting rules.
- Shared context for every agent working with Jordan: `soul.md` and `memory.md` (especially §5) in the [agents repo](https://github.com/nuniesmith/agents).
- When working in a sub-directory, read its own `CLAUDE.md` first.

## Rules that outrank convenience

- **This repo is public.** Every secret, strategy and piece of trading IP lives outside it, in the private `fks-state` layer and encrypted snapshots. Never push governance or account detail here.
- **Never `docker volume prune` on oryx** — it would take the FKS volumes and `lifeos_db_data` with it.
- A green workflow is not evidence. After any deploy, verify the **service** on the box (image tag, migrations, readiness, real row counts), not the checkmark.
- A PR is "ready" only when its own CI is green on its own head, with current main merged in.
- The live crypto bot runs inside this platform (`fks-bot-crypto-regime`). Real-money rules from the crypto repo's AGENTS.md apply to anything that touches it: no duplicate bots on one Kraken account, no shell calls to Kraken private endpoints with the live key.
