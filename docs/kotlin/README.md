# Kotlin / KMP Documentation

> **Status (July 2025):** KMP work is being restructured. Weekly progress sprints (Weeks 3–5) are paused with no Week 6+ planned under the old cadence. The new plan is tracked in the master [`todo.md`](../../todo.md) under **P1 — KOTLIN: KMP App Restructure & Tailscale Auth**.

---

## What's here

| Path | Description |
|------|-------------|
| `KMP_ARCHITECTURE.md` | High-level KMP architecture & module layout |
| `KMP_IMPLEMENTATION_SUMMARY.md` | Summary of what has been implemented so far |
| `PHASE_1_IMPLEMENTATION.md` | Phase 1 implementation details |
| `PHASE_1_QUICK_START.md` | Quick-start guide for Phase 1 |
| `MOCK_DATA_MODE.md` | Mock data mode for offline / demo development |
| `PERSISTENCE_INTEGRATION_GUIDE.md` | SQLDelight persistence integration guide |
| `QUICK_REFERENCE.md` | Quick reference for common tasks |
| `WEEK3_SUMMARY.md` | Week 3 sprint summary |
| `WEEK4_PLAN.md` / `WEEK4_SUMMARY.md` | Week 4 plan & summary |
| `WEEK5_*.md` | Week 5 plan, progress, session summaries, and next steps |
| `guides/` | Build & test quick-reference guides |
| `ui/` | UI implementation docs (settings, health page, Discord, web build) |

## Current restructuring

The weekly sprint format (Weeks 3–5) produced useful implementation work but is now superseded by a milestone-based plan:

1. **KT-A — Structural Cleanup:** Deduplicate `src/kotlin/` (proto, composeApp, templates).
2. **KT-B — Tailscale Authentication:** OAuth login flow per platform (Android, iOS, desktop).
3. **KT-C — Match WebUI Look & Feel:** Port the terminal dark theme to Compose UI.
4. **KT-D — Core Functionality:** SSE client, dashboard views, push notifications.

The weekly progress docs are kept as-is — they contain valuable implementation details, architectural decisions, and known issues that feed into the restructured plan.