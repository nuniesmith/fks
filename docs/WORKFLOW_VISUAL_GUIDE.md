# GitHub Actions Dynamic Workflow - Visual Guide

## 📊 Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          GitHub Event Triggers                           │
├─────────────────┬──────────────────┬──────────────────┬─────────────────┤
│   Push to       │   Pull Request   │   Version Tag    │    Manual       │
│   main/develop  │   to main/dev    │   (v*)           │    Trigger      │
└────────┬────────┴────────┬─────────┴────────┬─────────┴────────┬────────┘
         │                 │                  │                  │
         ▼                 ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          notify-start                                   │
│                    (Discord notification)                               │
└────────┬──────────────────────────────────────────────────────┬────────┘
         │                                                       │
         ▼                                                       ▼
┌────────────────────┐                                 ┌────────────────────┐
│    label-pr        │                                 │                    │
│  (Auto-labeling)   │                                 │   (Other jobs      │
│                    │                                 │    continue)       │
│  Outputs:          │                                 │                    │
│  • all-labels      │                                 └────────────────────┘
│  • new-labels      │
│                    │
│  Special Actions:  │
│  • Framework warn  │
│  • Breaking warn   │
└────────┬───────────┘
         │
         ├──────────────────┬──────────────────┬──────────────────┐
         ▼                  ▼                  ▼                  ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│     test       │ │     lint       │ │   security     │ │                │
│                │ │                │ │                │ │                │
│ Matrix:        │ │ Conditional:   │ │ Conditional:   │ │                │
│ ├─ Py 3.10 U   │ │ Skip if docs   │ │ Always if      │ │                │
│ ├─ Py 3.11 U   │ │ only           │ │ 'security'     │ │                │
│ ├─ Py 3.12 U   │ │                │ │ label          │ │                │
│ ├─ Py 3.13 U*  │ │ Tools:         │ │                │ │                │
│ └─ Py 3.13 W   │ │ • ruff         │ │ Tools:         │ │                │
│                │ │ • black        │ │ • bandit       │ │                │
│ *slow tests    │ │ • isort        │ │ • safety       │ │                │
│ *coverage      │ │ • mypy         │ │                │ │                │
└────────┬───────┘ └────────┬───────┘ └────────┬───────┘ └────────┬───────┘
         │                  │                  │                  │
         └──────────────────┴──────────────────┴──────────────────┘
                                      │
                                      ▼
                            ┌────────────────────┐
                            │      docker        │
                            │                    │
                            │  Conditional:      │
                            │  • Skip if WIP     │
                            │  • Skip if docs    │
                            │  • Tests passed    │
                            │                    │
                            │  Outputs:          │
                            │  • Versioned tags  │
                            │  • Branch tags     │
                            │  • SHA tags        │
                            │  • Latest (main)   │
                            └─────────┬──────────┘
                                      │
                        ┌─────────────┴─────────────┐
                        │                           │
                        ▼                           ▼
              ┌───────────────────┐       ┌────────────────────┐
              │  create-release   │       │    update-dns      │
              │                   │       │                    │
              │  Trigger:         │       │  Trigger:          │
              │  • Tag v*         │       │  • Push to main    │
              │                   │       │  • Push to develop │
              │  Actions:         │       │                    │
              │  • Generate notes │       │  Actions:          │
              │  • Create release │       │  • Update A record │
              │  • Publish        │       │  • Verify DNS      │
              └─────────┬─────────┘       └─────────┬──────────┘
                        │                           │
                        └───────────┬───────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │  notify-completion   │
                        │                      │
                        │  • Overall status    │
                        │  • Job results table │
                        │  • Discord summary   │
                        └──────────────────────┘
```

## 🏷️ Label Decision Tree

```
PR Created/Updated
     │
     ├─ Changed files scanned
     │
     ├─ docs/** or *.md?
     │  └─ YES → Label: documentation
     │           Effect: Skip lint job
     │
     ├─ src/framework/**?
     │  └─ YES → Label: framework + breaking
     │           Effect: ⚠️ Critical review warning
     │
     ├─ requirements.txt or .env?
     │  └─ YES → Label: security + dependencies
     │           Effect: Enhanced security scan
     │
     ├─ tests/**?
     │  └─ YES → Label: tests
     │           Effect: Ensure coverage
     │
     ├─ docker/** or Dockerfile?
     │  └─ YES → Label: docker
     │           Effect: Force Docker build
     │
     ├─ Draft PR?
     │  └─ YES → Label: wip
     │           Effect: Skip Docker + deployment
     │
     └─ Labels applied → Notify Discord
```

## 🧪 Test Matrix Flow

```
test job triggered
     │
     ├─ Strategy: Matrix
     │
     ├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
     │             │             │             │             │             │
     v             v             v             v             v             v
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Py 3.10 │  │ Py 3.11 │  │ Py 3.12 │  │ Py 3.13 │  │ Py 3.13 │
│ Ubuntu  │  │ Ubuntu  │  │ Ubuntu  │  │ Ubuntu  │  │ Windows │
│         │  │         │  │         │  │         │  │         │
│ Unit    │  │ Unit    │  │ Unit    │  │ Unit    │  │ Unit    │
│ Integ   │  │ Integ   │  │ Integ   │  │ Integ   │  │ Integ   │
│         │  │         │  │         │  │ Slow ✓  │  │         │
│         │  │         │  │         │  │ Cov ✓   │  │         │
└─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
     │             │             │             │             │
     └─────────────┴─────────────┴─────────────┴─────────────┘
                                  │
                                  v
                         Parallel Execution
                         (5 jobs at once)
                                  │
                                  v
                         All results combined
```

## 🚀 Release Flow

```
Developer                     GitHub Actions                    Docker Hub / GitHub

git tag -a v1.2.3                   │                                 │
git push origin v1.2.3              │                                 │
     │                              │                                 │
     └─────────────────────────────>│                                 │
                                    │                                 │
                          Tag detected (v*)                           │
                                    │                                 │
                          Run full test suite                         │
                                    │                                 │
                          Tests pass ✓                                │
                                    │                                 │
                          Build Docker images ───────────────────────>│
                                    │                          • v1.2.3
                                    │                          • v1.2
                          Extract version                      • v1
                          (v1.2.3 → 1.2.3)                    • latest
                                    │                                 │
                          Get previous tag                            │
                          (v1.2.2)                                    │
                                    │                                 │
                          Generate changelog                          │
                          (commits since v1.2.2)                      │
                                    │                                 │
                          Create GitHub Release                       │
                          • Title: Release v1.2.3                     │
                          • Body: Changelog + Docker tags             │
                          • Assets: (optional)                        │
                                    │                                 │
                          Notify Discord ────────────────────────────>│
                          "🎉 New Release: v1.2.3"            User sees notification
```

## 🔀 Conditional Logic Examples

### Example 1: Docs-only PR

```
PR #123: "Update README"
Changed files: README.md, docs/API.md
     │
     v
label-pr → Labels applied: [documentation]
     │
     ├─ test job   → Runs (no skip condition)
     ├─ lint job   → SKIPPED (docs-only)
     ├─ security   → Runs (on push)
     ├─ docker     → SKIPPED (not in PR labels)
     └─ update-dns → SKIPPED (PR, not push)
```

### Example 2: Framework change PR

```
PR #124: "Refactor circuit breaker"
Changed files: src/framework/middleware/circuit_breaker.py
     │
     v
label-pr → Labels applied: [framework, breaking, code]
     │
     └─ ⚠️ Warning added to PR:
        "Framework layer modified! Requires Phase 9D analysis"
     │
     ├─ test job   → Runs FULL matrix
     ├─ lint job   → Runs
     ├─ security   → Runs
     ├─ docker     → Runs (tests passed + code label)
     └─ update-dns → SKIPPED (PR, not push)
```

### Example 3: WIP PR

```
PR #125: "WIP: New feature"
Draft: true
Changed files: src/trading/signals/generator.py
     │
     v
label-pr → Labels applied: [wip, trading, code]
     │
     ├─ test job   → Runs (no skip)
     ├─ lint job   → Runs
     ├─ security   → Runs
     ├─ docker     → SKIPPED (wip label)
     └─ update-dns → SKIPPED (PR + wip)
```

### Example 4: Security fix

```
PR #126: "CVE-2024-1234: Update dependency"
Changed files: requirements.txt, src/authentication/utils.py
     │
     v
label-pr → Labels applied: [security, dependencies, code]
     │
     ├─ test job   → Runs FULL matrix
     ├─ lint job   → Runs
     ├─ security   → ENHANCED SCAN (security label)
     ├─ docker     → Runs (tests passed)
     └─ update-dns → SKIPPED (PR, not push)
```

## 📈 Performance Comparison

### Old Pipeline (Static)

```
Push to main → All jobs run sequentially
     │
     ├─ test (single version)      [8 min]
     ├─ lint                        [3 min]
     ├─ security                    [4 min]
     ├─ docker                      [5 min]
     └─ update-dns                  [2 min]
                                    ─────────
                              Total: 22 minutes
```

### New Pipeline (Dynamic)

#### Scenario A: Code change

```
Push to main → Smart parallel execution
     │
     ├─ test (matrix, parallel)     [10 min] ─┐
     ├─ lint (parallel)              [3 min] ─┤─ Parallel
     └─ security (parallel)          [4 min] ─┘
            │
            ├─ docker                [5 min]
            └─ update-dns            [2 min]
                                    ─────────
                              Total: 20 minutes
                              (Matrix adds jobs but parallel execution saves time)
```

#### Scenario B: Docs-only

```
PR with docs → Optimized execution
     │
     ├─ test (matrix, parallel)     [10 min]
     ├─ lint                         SKIPPED
     └─ security                     SKIPPED
                                    ─────────
                              Total: 10 minutes (55% savings)
```

#### Scenario C: WIP PR

```
Draft PR → Minimal execution
     │
     ├─ test (fast)                  [10 min]
     ├─ lint                         [3 min]
     ├─ security                     [4 min]
     ├─ docker                       SKIPPED
     └─ update-dns                   SKIPPED
                                    ─────────
                              Total: 17 minutes (23% savings)
```

## 🎯 Decision Matrix

| Condition | test | lint | security | docker | dns | release |
|-----------|------|------|----------|--------|-----|---------|
| Push main | ✓ | ✓ | ✓ | ✓ | ✓ | - |
| Push tag v* | ✓ | ✓ | ✓ | ✓ | - | ✓ |
| PR (code) | ✓ | ✓ | ✓ | ✓* | - | - |
| PR (docs) | ✓ | - | - | - | - | - |
| PR (WIP) | ✓ | ✓ | ✓ | - | - | - |
| PR (security) | ✓ | ✓ | ✓✓ | ✓* | - | - |
| Manual trigger | ✓** | ✓ | ✓ | ✓ | ✓*** | - |

Legend:
- ✓ = Runs
- - = Skipped
- ✓* = Runs if tests pass
- ✓✓ = Enhanced scan
- ✓** = Optional skip via input
- ✓*** = Based on environment input

---

**Visual guide created for FKS Trading Platform**  
Covers all dynamic workflow behaviors and decision flows
