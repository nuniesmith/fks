#!/usr/bin/env python3
"""
fks_overnight_analyzer.py
═══════════════════════════════════════════════════════════════════════════════
Overnight multi-repo analysis for the nuniesmith/fks ecosystem.

Crawls every repo in the FKS ecosystem via the GitHub API, routes each file
through xAI Grok (optionally via the rustcode LLM proxy), and synthesises
per-category, per-repo, and cross-repo summaries into a timestamped Markdown
report + a JSON task file compatible with rustcode's async task agent.

Rolling cache is stored under .rustcode/analyzer/ (inside the fks repo clone
or a path set via --cache-dir / FKS_CACHE_DIR). Files whose GitHub blob SHA
hasn't changed since the last run are served from cache — no LLM call needed.

ECOSYSTEM
─────────
  nuniesmith/fks          Unified monorepo — Janus (Rust) + Ruby (Python) +
                          infrastructure, monitoring, proto, scripts, docs
  nuniesmith/janus        Standalone Janus source mirror (src-code only)
  nuniesmith/ruby         Standalone Ruby source mirror  (src-code only)
  nuniesmith/rustcode     AI coding assistant & LLM backend — this script's
                          backend: OpenAI-compatible proxy, RAG, task agent
  nuniesmith/fks-web      Web frontend (src-code only)
  nuniesmith/fks-kotlin   KMP mobile monitoring app (src-code only)

USAGE
─────
  # Single repo (default: fks)
  python fks_overnight_analyzer.py

  # All repos overnight sweep (uses rolling cache automatically)
  python fks_overnight_analyzer.py --all-repos

  # Specific repos
  python fks_overnight_analyzer.py --repos nuniesmith/fks nuniesmith/rustcode

  # Route through local rustcode proxy instead of hitting xAI directly
  export RUSTCODE_URL="http://localhost:3500"
  python fks_overnight_analyzer.py --all-repos

  # Force full re-analysis (ignore cache)
  python fks_overnight_analyzer.py --no-cache

  # Clear cache for a specific repo then re-run
  python fks_overnight_analyzer.py --clear-cache nuniesmith/fks

  # Show cache stats
  python fks_overnight_analyzer.py --cache-info

  # Prune old run archives (keep last 30)
  python fks_overnight_analyzer.py --prune-cache

  # Dry run / resume
  python fks_overnight_analyzer.py --dry-run
  python fks_overnight_analyzer.py --resume

ENVIRONMENT VARIABLES
──────────────────────
  XAI_API_KEY       xAI API key  (required unless routing via rustcode)
  RUSTCODE_URL      rustcode base URL — routes LLM calls through the proxy
                    e.g. http://localhost:3500  (skips XAI_API_KEY requirement)
  RUSTCODE_API_KEY  Bearer token for rustcode auth (RC_PROXY_API_KEYS)
  GITHUB_TOKEN      GitHub PAT   (optional, raises rate limit to 5 000/hr)
  XAI_MODEL         Override model (default: grok-4)
                    Use grok-3-mini-fast-beta for faster/cheaper bulk sweeps.
                    DO NOT use grok-4.20-multi-agent-0309 — that model requires
                    the xAI Enterprise multi-agent endpoint, not /v1/chat/completions.
  FKS_CACHE_DIR     Path to rolling cache dir
                    (default: auto-detect fks clone, else ~/.fks-analyzer-cache)
  CONCURRENCY       Parallel API calls per repo (default: 4)
  MAX_FILE_BYTES    Skip files larger than this (default: 150 000)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Cache manager lives alongside this script
try:
    from fks_cache_manager import CacheManager
except ImportError:
    CacheManager = None  # type: ignore[assignment,misc]

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_API    = "https://api.github.com"
XAI_API_URL   = "https://api.x.ai/v1/chat/completions"
# grok-4.20-multi-agent-0309 requires the xAI Enterprise multi-agent endpoint
# and is NOT compatible with /v1/chat/completions — use grok-4 (flagship) or
# grok-3-mini-fast-beta (cheaper/faster) for bulk per-file analysis.
DEFAULT_MODEL = os.getenv("XAI_MODEL", "grok-4")

# rustcode proxy — when set, all LLM calls go through it instead of xAI directly
RUSTCODE_URL     = os.getenv("RUSTCODE_URL", "").rstrip("/")
RUSTCODE_API_KEY = os.getenv("RUSTCODE_API_KEY", "")

MAX_FILE_BYTES  = int(os.getenv("MAX_FILE_BYTES", 150_000))
CONCURRENCY     = int(os.getenv("CONCURRENCY", 4))
RETRY_ATTEMPTS  = 4
RETRY_BACKOFF   = 2.0
REQUEST_TIMEOUT = 180

# ─────────────────────────────────────────────────────────────────────────────
# Cache directory resolution
# ─────────────────────────────────────────────────────────────────────────────

def resolve_cache_dir(cli_cache_dir: str = "") -> Path:
    """
    Resolve the rolling cache directory in priority order:
      1. --cache-dir CLI argument
      2. FKS_CACHE_DIR environment variable
      3. Auto-detect: look for a local fks clone via common paths
      4. Fallback: ~/.fks-analyzer-cache/

    The canonical location is <fks_repo_root>/.rustcode/analyzer/
    which keeps the cache alongside rustcode's own .rustcode/ cache.
    """
    if cli_cache_dir:
        return Path(cli_cache_dir).expanduser().resolve()

    env_dir = os.getenv("FKS_CACHE_DIR", "")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    candidates = [
        Path.cwd() / ".rustcode" / "analyzer",
        Path.cwd().parent / "fks" / ".rustcode" / "analyzer",
        Path.home() / "fks" / ".rustcode" / "analyzer",
        Path.home() / "repos" / "fks" / ".rustcode" / "analyzer",
        Path.home() / "dev" / "fks" / ".rustcode" / "analyzer",
        Path.home() / "projects" / "fks" / ".rustcode" / "analyzer",
        Path.home() / "code" / "fks" / ".rustcode" / "analyzer",
    ]
    for c in candidates:
        repo_root = c.parent.parent
        if (repo_root / "Cargo.toml").exists() and (repo_root / "run.sh").exists():
            return c

    return Path.home() / ".fks-analyzer-cache"

# ─────────────────────────────────────────────────────────────────────────────
# Repo Profiles
# ─────────────────────────────────────────────────────────────────────────────
# Each repo entry describes its role in the ecosystem, its on-disk layout,
# and any repo-specific categorisation hints used when building prompts.

REPO_PROFILES: dict[str, dict] = {
    "nuniesmith/fks": {
        "label":   "FKS — Unified Monorepo",
        "role":    (
            "Main platform monorepo. Merges Janus (Rust sub-millisecond trading engine) "
            "and Ruby (Python ML/data services) into one repo alongside all infrastructure, "
            "monitoring, proto definitions, scripts, and docs."
        ),
        "type":    "monorepo",
        "branch":  "main",
        "layout":  """
src/janus/              — Rust trading engine (Janus)
  bin/                  — Binary entry points: janus, backtest-cli
  lib/                  — Core libraries: janus-core, janus-api, janus-ltn
  crates/               — Feature crates: indicators, risk, backtest,
                          strategies, optimizer, exchanges, bybit-client,
                          questdb-writer, memory (Qdrant)
  services/             — Service crates: forward (live), backward (persist),
                          data (DataServiceProvider), execution, cns (health)
  neuromorphic/         — Brain-region modules: amygdala (risk/kill-switch),
                          hippocampus (memory), cerebellum (timing),
                          prefrontal (decisions), basal_ganglia (reward),
                          thalamus (routing), hypothalamus (homeostasis),
                          visual_cortex (GAF/CNN)
src/ruby/               — Python ML & data services (Ruby)
  src/lib/analysis/     — Market analysis: ICT/SMC, wave, volume, regime (HMM)
  src/lib/core/         — Database, Redis, config
  src/lib/indicators/   — Technical indicators
  src/lib/integrations/ — Massive, Rithmic, Kraken, Binance, Bybit
  src/lib/model/        — CNN inference (DiffGAF-LSTM, 3-tier)
  src/lib/services/     — FastAPI apps: data, engine, web, trainer, charting
  src/lib/trading/      — ORB, signals, journal
  src/lib/utils/        — Helpers
  src/entrypoints/      — Docker service entrypoints
  models/               — Trained ML model artifacts
src/proto/              — fks-proto Rust crate (protobuf build integration)
src/sql/                — SQL schemas + migrations (janus_db + fks_db)
proto/fks/              — .proto definitions: common, janus, execution
infrastructure/
  compose/              — Docker Compose overrides (prod, trainer)
  docker/base/rust/     — Rust multi-stage build image
  docker/services/      — Per-service Dockerfiles
  configs/              — Service runtime configs
  monitoring/           — Prometheus rules, Grafana dashboards,
                          Alertmanager, Loki
scripts/                — Deployment, testing, operations
docs/                   — Platform documentation (mkdocs)
models/                 — Shared model artifacts
Cargo.toml              — Rust workspace root (50+ crates)
pyproject.toml          — Python project root (Ruby)
docker-compose.yml      — Unified compose (20 services: 12 core + 8 monitoring)
run.sh                  — Main management script
""",
        "services": [
            "fks_janus (Rust engine, :7000 HTTP / :9051 gRPC)",
            "fks_data  (FastAPI REST+SSE, :8050)",
            "fks_engine (ML pipeline, Redis interface)",
            "fks_web   (HTMX dashboard, :8080)",
            "fks_charting (TradingView, :8003)",
            "fks_trainer (GPU CNN, :8200, profile=training)",
            "fks_postgres (janus_db + fks_db, :5432)",
            "fks_redis (:6379)",
            "fks_questdb (:9000/:9009)",
            "fks_qdrant (:6333/:6334)",
            "fks_prometheus (:9090)",
            "fks_grafana (:3000)",
            "fks_nginx (:80/:443)",
        ],
    },

    "nuniesmith/janus": {
        "label":  "Janus — Rust Trading Engine (standalone mirror)",
        "role":   (
            "Standalone source mirror of the Janus Rust engine. "
            "Production code lives in nuniesmith/fks under src/janus/. "
            "This repo contains src-code only — no docker, no infra."
        ),
        "type":   "src_only",
        "branch": "main",
        "layout": "src/ — Rust source only. Mirrors fks/src/janus/.",
    },

    "nuniesmith/ruby": {
        "label":  "Ruby — Python ML & Data Services (standalone mirror)",
        "role":   (
            "Standalone source mirror of the Ruby Python services. "
            "Production code lives in nuniesmith/fks under src/ruby/. "
            "This repo contains src-code only — no docker, no infra."
        ),
        "type":   "src_only",
        "branch": "main",
        "layout": "src/ — Python source only. Mirrors fks/src/ruby/.",
    },

    "nuniesmith/rustcode": {
        "label":  "Rustcode — AI Coding Assistant & LLM Backend",
        "role":   (
            "General-purpose Rust backend that powers the overnight analyzer itself. "
            "Provides an OpenAI-compatible LLM proxy (Grok primary, Ollama optional), "
            "repository indexing + RAG, semantic code search, automated code auditing, "
            "and an async task agent. "
            "Requests to /v1/chat/completions are classified by ModelRouter and routed to "
            "Grok (default) or local Ollama depending on prompt type. "
            "Task files dropped in tasks/ are auto-executed: scaffold → test → PR → merge "
            "or flag for manual review. Runs as fks_rustcode container alongside FKS."
        ),
        "type":   "src_only",
        "branch": "main",
        "layout": """
src/            — Rust source (~81K lines, 80 public modules)
  main.rs       — Entry point
  router/       — ModelRouter: classify_prompt_async() → Grok | Ollama
  proxy/        — OpenAI-compatible /v1/chat/completions endpoint
  rag/          — Repository indexing, embeddings, vector search
  audit/        — Code audit pipeline (POST /api/v1/audit)
  tasks/        — Async task agent: JSON task file watcher + executor
  todo/         — TODO/STUB/FIXME scanner + planner
  github/       — Webhook receiver, PR automation
  db/           — 34 Postgres tables via 20 SQL migrations
sql/            — SQL migration files
.rustcode/      — Per-repo cache: manifest, tree, todos, symbols, context, embeddings
""",
        "api_endpoints": [
            "POST /v1/chat/completions  — OpenAI-compatible LLM proxy",
            "GET  /v1/models",
            "POST /api/v1/repos         — Index a repository",
            "POST /api/v1/repos/:id/sync",
            "POST /api/v1/search        — Semantic code search",
            "POST /api/v1/audit         — Code audit pipeline",
            "GET  /api/v1/audit/:id",
            "POST /api/v1/documents     — Document indexing",
            "POST /api/v1/todo/scan     — TODO scanner",
            "POST /api/v1/todo/plan     — TODO planner",
            "POST /api/github/webhook   — GitHub webhook receiver",
            "GET  /healthz  GET /metrics",
        ],
    },

    "nuniesmith/fks-web": {
        "label":  "FKS Web — Frontend",
        "role":   (
            "Web frontend for the FKS trading platform. "
            "Source-code only repo."
        ),
        "type":   "src_only",
        "branch": "main",
        "layout": "src/ — Web source only.",
    },

    "nuniesmith/fks-kotlin": {
        "label":  "FKS Kotlin — Mobile Monitoring App (KMP)",
        "role":   (
            "Kotlin Multiplatform mobile app for monitoring the FKS trading platform "
            "remotely. Planned feature per the fks roadmap. Source-code only."
        ),
        "type":   "src_only",
        "branch": "main",
        "layout": "src/ — Kotlin Multiplatform source only.",
    },
}

# All repos in recommended analysis order
ALL_REPOS = [
    "nuniesmith/fks",
    "nuniesmith/rustcode",
    "nuniesmith/janus",
    "nuniesmith/ruby",
    "nuniesmith/fks-web",
    "nuniesmith/fks-kotlin",
]

# Short ecosystem context injected into every system prompt
ECOSYSTEM_CONTEXT = """
FKS Ecosystem — nuniesmith
──────────────────────────
• fks           Unified monorepo: Janus (Rust engine) + Ruby (Python ML/data) +
                infrastructure (20 Docker services), monitoring, proto, docs
• rustcode      Rust AI backend powering this analysis: LLM proxy (Grok/Ollama),
                RAG, semantic search, code audit, async task agent
• janus         Standalone Janus source mirror (src-code only)
• ruby          Standalone Ruby source mirror (src-code only)
• fks-web       Web frontend (src-code only)
• fks-kotlin    KMP mobile monitoring app (src-code only)

Key integration points:
  Janus ↔ Ruby   DataServiceProvider (HTTP) + Redis pub/sub
  Analyzer ↔ rustcode  /v1/chat/completions proxy + task file pipeline
  All repos       Indexed in rustcode RAG (.rustcode/ per-repo cache)
"""


# ─────────────────────────────────────────────────────────────────────────────
# File Categorisation
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES: dict[str, dict] = {

    # ── FKS monorepo-specific categories (checked first for nuniesmith/fks) ──

    "janus_neuromorphic": {
        "label": "🧠 Janus — Neuromorphic Brain Modules",
        "match": lambda p: "neuromorphic" in p and p.endswith(".rs"),
        "prompt_focus": (
            "These are brain-region modules (amygdala/risk, hippocampus/memory, "
            "cerebellum/timing, prefrontal/decisions, basal_ganglia/reward, "
            "thalamus/routing, hypothalamus/homeostasis, visual_cortex/GAF). "
            "Focus on: module isolation, signal contracts, async safety, "
            "circuit-breaker correctness in amygdala, kill-switch reachability, "
            "memory consolidation correctness, and inter-region coupling risks."
        ),
    },
    "janus_services": {
        "label": "⚙️  Janus — Service Crates (forward/backward/data/execution/cns)",
        "match": lambda p: (
            p.startswith("src/janus/services/") and p.endswith(".rs")
        ),
        "prompt_focus": (
            "Service crates: forward (live trading), backward (persistence), "
            "data (DataServiceProvider + PythonDataClient — fetches from Ruby via HTTP), "
            "execution, cns (Central Nervous System health monitoring). "
            "Focus on: DataServiceProvider retry/fallback chain (Ruby → QuestDB → Binance), "
            "WebSocket reconnect logic, async task lifecycle, error propagation, "
            "and health check completeness."
        ),
    },
    "janus_core_libs": {
        "label": "🦀 Janus — Core Libraries (janus-core/api/ltn)",
        "match": lambda p: (
            p.startswith("src/janus/lib/") and p.endswith(".rs")
        ),
        "prompt_focus": (
            "Core libraries: janus-core (types, config, signal bus), "
            "janus-api (HTTP handlers/routes), janus-ltn (Logic Tensor Network). "
            "Focus on: public API surface, trait design, configuration validation, "
            "signal bus backpressure, LTN integration correctness, and security "
            "(auth, input validation on API routes)."
        ),
    },
    "janus_crates": {
        "label": "📦 Janus — Feature Crates (indicators/risk/backtest/strategies/etc.)",
        "match": lambda p: (
            p.startswith("src/janus/crates/") and p.endswith(".rs")
        ),
        "prompt_focus": (
            "Feature crates: indicators (EMA, RSI, ATR, Bollinger), risk, "
            "backtest (Temporal Fortress — zero-lookahead enforcement), "
            "strategies, optimizer (walk-forward), exchanges, bybit-client, "
            "questdb-writer, memory (Qdrant). "
            "Focus on: indicator accuracy, Temporal Fortress lookahead prevention, "
            "risk parameter correctness, exchange abstraction leaks, "
            "and Qdrant vector dimension consistency."
        ),
    },
    "ruby_services": {
        "label": "🐍 Ruby — FastAPI Service Entrypoints (data/engine/web/trainer/charting)",
        "match": lambda p: (
            (p.startswith("src/ruby/src/lib/services/") or
             p.startswith("src/ruby/src/entrypoints/")) and p.endswith(".py")
        ),
        "prompt_focus": (
            "FastAPI apps: data (REST+SSE, execution gate, broker integration), "
            "engine (ML pipeline, regime detection HMM, risk scoring, Redis interface), "
            "web (HTMX dashboard, proxies to data), trainer (3-tier CNN GPU retraining), "
            "charting (TradingView Lightweight Charts). "
            "Focus on: execution gate safety (REAL_ORDERS_ENABLED guard), "
            "SSE backpressure, Redis pub/sub error handling, "
            "async task isolation in trainer, and route auth coverage."
        ),
    },
    "ruby_lib": {
        "label": "🐍 Ruby — Core Python Libraries",
        "match": lambda p: (
            p.startswith("src/ruby/src/lib/") and p.endswith(".py")
        ),
        "prompt_focus": (
            "Core packages: analysis (ICT/SMC, wave, volume profile, regime HMM), "
            "core (DB, Redis, config), indicators, "
            "integrations (Massive/CME, Rithmic-async, Kraken, Binance, Bybit), "
            "model (DiffGAF-LSTM, CNN inference), trading (ORB, signals, journal), utils. "
            "Focus on: ICT pattern accuracy, HMM regime stability, "
            "Rithmic async_rithmic client correctness, data fallback chain, "
            "ML model input shape validation, and Redis connection pool hygiene."
        ),
    },
    "ruby_models": {
        "label": "🤖 Ruby — ML Model Artifacts & Training",
        "match": lambda p: (
            "models/" in p and any(p.endswith(e) for e in [".py", ".json", ".yaml", ".yml"])
        ),
        "prompt_focus": (
            "ML model artifacts and training configs. "
            "Focus on: model versioning, input/output schema documentation, "
            "training reproducibility, model loading error handling, "
            "and GPU/CPU fallback in inference."
        ),
    },
    "rustcode_src": {
        "label": "🤖 Rustcode — AI Backend Source",
        "match": lambda p: p.startswith("src/") and p.endswith(".rs"),
        "prompt_focus": (
            "Rustcode is the LLM proxy + RAG + code audit + async task agent backend. "
            "Focus on: ModelRouter classification accuracy, RAG chunk quality, "
            "task agent safety (preventing malicious task files from running arbitrary code), "
            "auth enforcement (RC_PROXY_API_KEYS), Ollama fallback correctness, "
            "GitHub PR automation safety, and Postgres connection pool sizing."
        ),
    },
    "rustcode_sql": {
        "label": "🗄️  Rustcode — SQL Migrations (34 tables)",
        "match": lambda p: p.startswith("sql/") or (p.endswith(".sql") and "migration" in p.lower()),
        "prompt_focus": (
            "34 Postgres tables across 20 migrations. "
            "Focus on: index coverage on hot query paths, migration idempotency, "
            "foreign key consistency, missing NOT NULL constraints, "
            "and row-level security where appropriate."
        ),
    },
    "kotlin": {
        "label": "📱 Kotlin — KMP Mobile App (fks-kotlin)",
        "match": lambda p: p.endswith(".kt") or p.endswith(".kts"),
        "prompt_focus": (
            "Kotlin Multiplatform mobile monitoring app for FKS. "
            "Focus on: shared vs platform-specific code split, "
            "network layer (calls to fks data API), state management, "
            "error handling on flaky mobile connections, "
            "and credential storage security."
        ),
    },

    # ── Generic categories (used as fallback / for simpler repos) ────────────

    "rust_core": {
        "label":   "🦀 Rust — Core Source (src/)",
        "match":   lambda p: p.startswith("src/") and p.endswith(".rs"),
        "prompt_focus": (
            "Focus on: API surface, error handling, unsafe blocks, async patterns, "
            "trait design, lifetime correctness, DB interaction, LLM integration, "
            "and security concerns (SQL injection, SSRF, secret leakage)."
        ),
    },
    "rust_tests": {
        "label":   "🧪 Rust — Tests & Examples",
        "match":   lambda p: (p.startswith("tests/") or p.startswith("examples/")) and p.endswith(".rs"),
        "prompt_focus": (
            "Focus on: coverage gaps, test isolation, use of fixtures/mocks, "
            "integration vs unit test balance, and flakiness risks."
        ),
    },
    "cargo": {
        "label":   "⚙️  Cargo — Workspace & Crate Manifests",
        "match":   lambda p: p.endswith("Cargo.toml") or p == "Cargo.lock",
        "prompt_focus": (
            "Focus on: dependency versions, yanked or security-flagged crates, "
            "workspace coherence, feature flag hygiene, and build profiles. "
            "The fks workspace has 50+ crates — check for version drift between members."
        ),
    },
    "docker": {
        "label":   "🐳 Docker — Dockerfiles & Compose",
        "match":   lambda p: (
            "dockerfile" in p.lower()
            or "docker-compose" in p.lower()
            or p.lower().endswith("compose.yml")
            or p.lower().endswith("compose.yaml")
        ),
        "prompt_focus": (
            "FKS runs 20 Docker services. "
            "Focus on: base image pinning (fks uses rust multi-stage + python-base shared layer), "
            "layer efficiency, secrets in ENV, health checks, non-root user, "
            "multi-stage builds, service dependency ordering, and resource limits. "
            "Check that infrastructure/docker/services/ Dockerfiles align with "
            "docker-compose.yml service definitions."
        ),
    },
    "infrastructure": {
        "label":   "🏗️  Infrastructure — Terraform / Helm / K8s",
        "match":   lambda p: any(x in p.lower() for x in [
            "terraform", ".tf", "helm", "k8s", "kubernetes", "manifests/", "charts/"
        ]),
        "prompt_focus": (
            "Focus on: IAM least-privilege, network policies, secret management, "
            "resource limits, idempotency, and state backend security."
        ),
    },
    "observability": {
        "label":   "📊 Observability — Prometheus / Grafana / Alertmanager / Loki",
        "match":   lambda p: any(x in p.lower() for x in [
            "prometheus", "grafana", "alertmanager", "loki", "alert_rules",
            "recording_rules", "datasource", "dashboard"
        ]),
        "prompt_focus": (
            "FKS monitoring stack: Prometheus, Grafana (Janus + Ruby dashboards), "
            "Alertmanager, Loki. "
            "Focus on: alert coverage (latency, errors, saturation, traffic — RED method), "
            "janus-specific metrics (neuromorphic brain health, signal quality, "
            "execution latency, drawdown), ruby-specific metrics (data freshness, "
            "CNN inference latency, regime detection), label cardinality, "
            "dead-man's-switch alert, and Loki log query correctness."
        ),
    },
    "python": {
        "label":   "🐍 Python — Scripts / Config",
        "match":   lambda p: (
            p.endswith(".py")
            or p == "pyproject.toml"
            or p == "setup.cfg"
            or p == "requirements.txt"
            or p.startswith("scripts/")
        ),
        "prompt_focus": (
            "Focus on: dependency pinning, type hints, error handling, "
            "security (subprocess, eval, pickle), and async correctness."
        ),
    },
    "docs": {
        "label":   "📚 Docs — README / CLAUDE / TODO / mkdocs",
        "match":   lambda p: any(x in p.upper() for x in [
            "README", "CLAUDE", "TODO", "CHANGELOG", "CONTRIBUTING"
        ]) or p.lower() in ["mkdocs.yml", "mkdocs.yaml"] or p.endswith(".md"),
        "prompt_focus": (
            "Focus on: accuracy vs actual code, missing sections, onboarding clarity, "
            "TODO items that should become tracked issues, and stale information. "
            "Check todo.md for items that should be rustcode task files."
        ),
    },
    "proto_buf": {
        "label":   "🔌 Protobuf / Buf",
        "match":   lambda p: p.endswith(".proto") or "buf.yaml" in p or "buf.gen.yaml" in p,
        "prompt_focus": (
            "FKS uses protobuf for Janus gRPC (:9051). Proto packages: common, janus, execution. "
            "Focus on: breaking-change risk, field numbering gaps, deprecated fields, "
            "buf lint/breaking config strictness, and generated code freshness in src/proto/."
        ),
    },
    "ci_cd": {
        "label":   "🔄 CI/CD — GitHub Actions / Scripts",
        "match":   lambda p: (
            p.startswith(".github/")
            or p.endswith(".sh")
            or "makefile" in p.lower()
            or "justfile" in p.lower()
        ),
        "prompt_focus": (
            "FKS CI/CD is currently transitioning (main pipeline disabled in .github/disabled/). "
            "Active: paper-trading-test.yml, ssl-renew.yml, labeler.yml. "
            "Focus on: secret exposure in logs, pinned action versions, "
            "least-privilege tokens, Tailscale VPN usage, and re-enablement readiness "
            "for the planned Rust + Python parallel pipeline."
        ),
    },
    "config": {
        "label":   "🔧 Config — YAML / TOML / ENV / JSON",
        "match":   lambda p: (
            p.endswith((".yml", ".yaml", ".toml", ".json", ".env", ".env.example"))
            and not any(already(p) for already in [
                lambda x: x.endswith("Cargo.toml"),
                lambda x: "prometheus" in x.lower(),
                lambda x: "grafana" in x.lower(),
                lambda x: "alertmanager" in x.lower(),
                lambda x: "loki" in x.lower(),
                lambda x: "docker" in x.lower() or "compose" in x.lower(),
                lambda x: "buf" in x.lower(),
                lambda x: x.startswith(".github/"),
            ])
        ),
        "prompt_focus": (
            "Focus on: hardcoded secrets, overly permissive settings, "
            "environment-parity issues (dev vs prod vs trainer profiles), "
            "and missing required fields. "
            "FKS uses a generated .env with auto-generated passwords — "
            "ensure .env.example documents every variable used by all 20 services."
        ),
    },
    "other": {
        "label":   "📁 Other Files",
        "match":   lambda p: True,
        "prompt_focus": "Review this file for any notable issues or patterns.",
    },
}

# Category resolution order per repo type.
# For fks monorepo we check the fine-grained janus/ruby categories first.
# For rustcode we check rustcode-specific categories first.
# For standalone mirrors and simple repos we use the generic order.

CATEGORY_ORDER_FKS = [
    "janus_neuromorphic", "janus_services", "janus_core_libs", "janus_crates",
    "ruby_services", "ruby_lib", "ruby_models",
    "cargo", "docker", "observability", "proto_buf", "ci_cd",
    "docs", "config", "infrastructure", "python", "other",
]

CATEGORY_ORDER_RUSTCODE = [
    "rustcode_src", "rustcode_sql",
    "cargo", "ci_cd", "docs", "config", "other",
]

CATEGORY_ORDER_KOTLIN = [
    "kotlin", "ci_cd", "docs", "config", "other",
]

CATEGORY_ORDER_GENERIC = [
    "rust_core", "rust_tests", "cargo",
    "docker", "infrastructure", "observability", "python",
    "docs", "proto_buf", "ci_cd", "config", "other",
]


def get_category_order(repo: str) -> list[str]:
    if repo == "nuniesmith/fks":
        return CATEGORY_ORDER_FKS
    if repo == "nuniesmith/rustcode":
        return CATEGORY_ORDER_RUSTCODE
    if repo == "nuniesmith/fks-kotlin":
        return CATEGORY_ORDER_KOTLIN
    return CATEGORY_ORDER_GENERIC


def categorise(path: str, repo: str) -> str:
    for key in get_category_order(repo):
        if CATEGORIES[key]["match"](path):
            return key
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
# GitHub API helpers
# ─────────────────────────────────────────────────────────────────────────────

async def github_get(client: httpx.AsyncClient, url: str, token: str | None) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def fetch_tree(client: httpx.AsyncClient, repo: str, branch: str, token: str | None) -> list[dict]:
    url = f"{GITHUB_API}/repos/{repo}/git/trees/{branch}?recursive=1"
    data = await github_get(client, url, token)
    if data.get("truncated"):
        print("⚠️  WARNING: GitHub tree is truncated — some files may be missing.")
    return [item for item in data.get("tree", []) if item["type"] == "blob"]


async def fetch_file(client: httpx.AsyncClient, repo: str, path: str, token: str | None) -> str | None:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    try:
        data = await github_get(client, url, token)
    except httpx.HTTPStatusError as e:
        print(f"    ⚠  GitHub {e.response.status_code} fetching {path}")
        return None
    if isinstance(data, list):
        return None
    size = data.get("size", 0)
    if size > MAX_FILE_BYTES:
        print(f"    ⏩ Skipping {path} — {size:,} bytes exceeds limit")
        return None
    encoding = data.get("encoding", "")
    content  = data.get("content", "")
    if encoding == "base64":
        try:
            raw = b64decode(content.replace("\n", ""))
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None
    return content or None


# ─────────────────────────────────────────────────────────────────────────────
# LLM API helpers — supports direct xAI OR rustcode proxy
# ─────────────────────────────────────────────────────────────────────────────

def get_llm_url() -> str:
    """Return the LLM endpoint — rustcode proxy if configured, else xAI directly."""
    if RUSTCODE_URL:
        return f"{RUSTCODE_URL}/v1/chat/completions"
    return XAI_API_URL


def get_llm_headers(api_key: str) -> dict[str, str]:
    """Return auth headers for whichever backend is active."""
    key = RUSTCODE_API_KEY if RUSTCODE_URL else api_key
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }


async def call_llm(
    client: httpx.AsyncClient,
    api_key: str,
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> tuple[str, dict]:
    """Call the LLM (via rustcode proxy or xAI directly) with retry/backoff."""
    payload = {
        "model":                model,
        "messages":             messages,
        # Grok-4 is a reasoning model → uses max_completion_tokens.
        # Older models (grok-3-*) also accept this key, so it's safe for all.
        "max_completion_tokens": max_tokens,
        "temperature":          temperature,
    }
    headers = get_llm_headers(api_key)
    url     = get_llm_url()

    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                wait = RETRY_BACKOFF ** (attempt + 2)
                print(f"    ⏳ Rate limited — waiting {wait:.0f}s …")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data    = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage   = data.get("usage", {})
            # rustcode proxy injects x_ra_metadata — log it if present
            meta = data.get("x_ra_metadata")
            if meta:
                rc_answered = meta.get("answered_by", "?")
                rc_chunks   = meta.get("rag_chunks_used", 0)
                print(f"    📡 rustcode: answered_by={rc_answered} rag_chunks={rc_chunks}")
            return content, usage
        except (httpx.TimeoutException, httpx.ReadError) as e:
            wait = RETRY_BACKOFF ** (attempt + 1)
            print(f"    ↩  Timeout/read error ({e}) — retry {attempt+1}/{RETRY_ATTEMPTS} in {wait}s")
            await asyncio.sleep(wait)
        except httpx.HTTPStatusError as e:
            print(f"    ✗  HTTP {e.response.status_code}: {e.response.text[:200]}")
            raise

    raise RuntimeError(f"LLM API failed after {RETRY_ATTEMPTS} attempts")


# ─────────────────────────────────────────────────────────────────────────────
# Per-file analysis prompts
# ─────────────────────────────────────────────────────────────────────────────

def _repo_context_block(repo: str) -> str:
    profile = REPO_PROFILES.get(repo, {})
    label   = profile.get("label", repo)
    role    = profile.get("role", "")
    layout  = profile.get("layout", "")
    return f"""
REPO CONTEXT
─────────────
Repository : {repo}  ({label})
Role       : {role}
Layout     :
{layout}

ECOSYSTEM
─────────
{ECOSYSTEM_CONTEXT}
""".strip()


FILE_SYSTEM_PROMPT_TMPL = """\
You are a senior software architect and security engineer performing a thorough \
overnight code review for the nuniesmith FKS trading platform ecosystem. \
Be precise, actionable, and well-structured. Do not pad your response.

When you find issues, rate them:
  🔴 CRITICAL — must be fixed before next session (flag for manual review)
  🟠 HIGH     — fix this session (auto-task candidate)
  🟡 MEDIUM   — schedule this sprint
  🟢 LOW      — nice to have

At the end of every review include a ## Task Candidates section with a JSON array
of objects in rustcode task-agent format for any HIGH or CRITICAL issues found:
  {{ "description": "...", "steps": ["step1", "step2"], "labels": ["auto-pr"] }}
Add "manual-review" to labels for CRITICAL issues.

{repo_context}
"""


def build_file_prompt(path: str, content: str, focus: str, repo: str) -> list[dict]:
    system = FILE_SYSTEM_PROMPT_TMPL.format(repo_context=_repo_context_block(repo))
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": f"""\
## File Review Request

**Repo:** `{repo}`
**Path:** `{path}`

**Review Focus:** {focus}

**File Content:**
```
{content[:MAX_FILE_BYTES]}
```

Please provide:
1. **Summary** — one-paragraph description of what this file does in the FKS ecosystem
2. **Scores** — rate each 1–10: Quality · Security · Maintainability · Completeness
3. **Issues** — numbered list of concrete problems (severity: 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW)
4. **Improvements** — top 3–5 actionable suggestions
5. **Prep Notes** — anything worth flagging before tomorrow's development session
6. **Task Candidates** — JSON array of rustcode task objects for HIGH/CRITICAL issues
"""},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Category synthesis prompts
# ─────────────────────────────────────────────────────────────────────────────

SYNTHESIS_SYSTEM_PROMPT = """\
You are a principal engineer synthesising multiple per-file reviews into a \
category-level architectural report for the FKS trading platform. Be concise but comprehensive.

{ecosystem}
""".format(ecosystem=ECOSYSTEM_CONTEXT)


def build_synthesis_prompt(category_label: str, file_summaries: list[dict], repo: str) -> list[dict]:
    profile = REPO_PROFILES.get(repo, {})
    repo_label = profile.get("label", repo)
    summaries_text = "\n\n---\n\n".join(
        f"### `{s['path']}`\n{s['review']}" for s in file_summaries
    )
    return [
        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user",   "content": f"""\
## Category Synthesis: {category_label}
## Repo: {repo} ({repo_label})

Individual file reviews below. Synthesise into a single category report covering:

1. **Category Overview** — overall state of this area
2. **Cross-File Patterns** — recurring issues or anti-patterns
3. **Top 5 Priority Actions** — ordered by risk/impact, with rustcode task JSON snippets
4. **Green Flags** — what's working well
5. **Readiness Score** — 1–10 overall readiness for the next sprint
6. **Aggregated Task Candidates** — consolidated JSON array of all HIGH/CRITICAL task objects

---

{summaries_text}
"""},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo executive summary prompt
# ─────────────────────────────────────────────────────────────────────────────

REPO_EXEC_SYSTEM_PROMPT = """\
You are a principal engineer writing a repo-level overnight executive summary. \
Be opinionated, prioritise ruthlessly, and make every word count.

{ecosystem}
""".format(ecosystem=ECOSYSTEM_CONTEXT)


def build_repo_exec_prompt(repo: str, category_reports: list[dict], stats: dict) -> list[dict]:
    profile    = REPO_PROFILES.get(repo, {})
    repo_label = profile.get("label", repo)
    role       = profile.get("role", "")
    reports_text = "\n\n---\n\n".join(
        f"## {r['label']}\n{r['synthesis']}" for r in category_reports
    )
    return [
        {"role": "system", "content": REPO_EXEC_SYSTEM_PROMPT},
        {"role": "user",   "content": f"""\
## {repo} — Overnight Repo Analysis Executive Summary
**Label:** {repo_label}
**Role:** {role}
**Stats:** {stats['files_analysed']} files across {stats['categories']} categories.

---

{reports_text}

---

Executive Summary covering:

1. **Repo Health Score** (1–10) with one-sentence justification
2. **Top 3 Critical Issues** requiring immediate attention
3. **Architecture Assessment** — design soundness and main risks
4. **Security Posture** — top concerns (auth, secrets, injection, SSRF)
5. **Tomorrow's Battle Plan** — 5–8 specific ordered tasks
6. **Positive Highlights** — what's already solid
7. **Consolidated Task JSON** — final rustcode-format task array for this repo
"""},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Cross-repo ecosystem synthesis prompt
# ─────────────────────────────────────────────────────────────────────────────

CROSS_REPO_SYSTEM_PROMPT = """\
You are a CTO-level reviewer writing an overnight cross-repo executive summary \
for the full nuniesmith FKS trading platform ecosystem. \
Be opinionated, prioritise ruthlessly, and focus on cross-cutting concerns.

{ecosystem}
""".format(ecosystem=ECOSYSTEM_CONTEXT)


def build_cross_repo_prompt(repo_summaries: list[dict], global_stats: dict) -> list[dict]:
    summaries_text = "\n\n---\n\n".join(
        f"## {r['repo']} — {r['label']}\n{r['exec_summary']}" for r in repo_summaries
    )
    return [
        {"role": "system", "content": CROSS_REPO_SYSTEM_PROMPT},
        {"role": "user",   "content": f"""\
## FKS Ecosystem — Overnight Cross-Repo Analysis

**Repos analysed:** {global_stats['repos_analysed']}
**Total files:** {global_stats['total_files']}
**Completed:** {global_stats['timestamp']} UTC

---

{summaries_text}

---

Cross-Repo Executive Summary covering:

1. **Overall Ecosystem Health Score** (1–10)
2. **Critical Cross-Repo Risks** — issues that span multiple repos
   (e.g. rustcode ↔ fks API contract drift, janus ↔ ruby DataServiceProvider breakage,
    proto breaking changes, shared secret rotation, schema drift)
3. **Integration Integrity** — are all 6 repos consistent with each other?
4. **Automation Readiness** — how ready is the stack for the rustcode task agent to
   handle 90–95% of coding automatically? What gaps remain?
5. **Security Posture** — ecosystem-wide verdict
6. **Top 10 Ecosystem Tasks** — prioritised across all repos, in rustcode task format
7. **Manual Review Flags** — tasks too risky for auto-execution (CRITICAL issues)
8. **Positive Highlights** — what's already excellent
"""},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Task JSON generation
# ─────────────────────────────────────────────────────────────────────────────

def extract_task_candidates(review_text: str, repo: str, path: str) -> list[dict]:
    """Extract rustcode task JSON objects from a file review."""
    tasks: list[dict] = []
    # Find the Task Candidates section
    match = re.search(
        r"##\s*Task Candidates\s*\n(.*?)(?=\n##|\Z)",
        review_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return tasks

    # Try to find a JSON array in that section
    json_match = re.search(r"\[.*?\]", match.group(1), re.DOTALL)
    if not json_match:
        return tasks

    try:
        raw_tasks = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return tasks

    for t in raw_tasks:
        if not isinstance(t, dict) or "description" not in t:
            continue
        task = {
            "id":          str(uuid.uuid4())[:8],
            "repo":        repo,
            "source_file": path,
            "description": t.get("description", ""),
            "steps":       t.get("steps", []),
            "branch":      "fix/" + re.sub(r"[^a-z0-9]+", "-", t.get("description", "task")[:40].lower()).strip("-"),
            "labels":      t.get("labels", ["auto-pr"]),
        }
        tasks.append(task)

    return tasks


def build_task_file(all_tasks: list[dict], repo_summaries: list[dict], stats: dict, output_dir: Path) -> Path:
    """Write a rustcode-compatible tasks JSON file."""
    task_file = output_dir / f"fks_tasks_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    # Split into auto and manual
    auto_tasks   = [t for t in all_tasks if "manual-review" not in t.get("labels", [])]
    manual_tasks = [t for t in all_tasks if "manual-review" in t.get("labels", [])]

    payload = {
        "generated_at":  stats.get("timestamp", ""),
        "repos_analysed": [r["repo"] for r in repo_summaries],
        "summary": {
            "total_tasks":  len(all_tasks),
            "auto_tasks":   len(auto_tasks),
            "manual_tasks": len(manual_tasks),
        },
        "auto_tasks":   auto_tasks,
        "manual_tasks": manual_tasks,
    }

    task_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return task_file


# ─────────────────────────────────────────────────────────────────────────────
# Progress / state management
# ─────────────────────────────────────────────────────────────────────────────

def load_state(state_file: Path) -> dict:
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"completed": {}, "skipped": [], "token_usage": {}}


def save_state(state_file: Path, state: dict) -> None:
    state_file.write_text(json.dumps(state, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Report builder
# ─────────────────────────────────────────────────────────────────────────────

def build_repo_report(
    repo: str,
    branch: str,
    model: str,
    all_results: dict[str, list[dict]],
    syntheses: dict[str, str],
    exec_summary: str,
    stats: dict,
    delta: dict | None = None,
) -> str:
    profile    = REPO_PROFILES.get(repo, {})
    repo_label = profile.get("label", repo)
    now = stats["timestamp"]
    cat_order = get_category_order(repo)
    cached = stats.get("files_from_cache", 0)
    new_llm = stats.get("files_new_llm", stats["files_analysed"])

    lines = [
        f"# 🔍 {repo} — Overnight Analysis",
        f"",
        f"> **Repo:** `{repo}` ({repo_label})",
        f"> **Branch:** `{branch}` · **Model:** `{model}`  ",
        f"> **Generated:** {now} UTC  ",
        f"> **Files:** {stats['files_analysed']} analysed · {cached} from cache · "
        f"{new_llm} new LLM calls · {stats['files_skipped']} skipped  ",
        f"> **Tokens:** {stats['total_tokens']:,} · **Est. cost:** ${stats['est_cost_usd']:.4f}",
        f"",
        "---",
        "",
        "## 📋 Table of Contents",
        "",
        "- [Executive Summary](#executive-summary)",
    ]

    for key in cat_order:
        if key in all_results and all_results[key]:
            label  = CATEGORIES[key]["label"]
            anchor = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
            lines.append(f"- [{label}](#{anchor})")

    if delta:
        ds = delta["stats"]
        lines += ["", "---", "", "## 📊 Delta Since Last Run", ""]
        last = delta.get("last_run", "never")
        lines.append(f"> Previous run: **{last}**  ")
        lines.append(f"> LLM calls saved by cache: **{ds['llm_calls_saved']}** files")
        lines += [""]
        if delta["new_files"]:
            lines += [f"**🆕 New files ({len(delta['new_files'])}):**"]
            lines += [f"- `{p}`" for p in delta["new_files"][:30]]
            if len(delta["new_files"]) > 30:
                lines.append(f"- … and {len(delta['new_files']) - 30} more")
            lines += [""]
        if delta["modified"]:
            lines += [f"**✏️ Modified ({len(delta['modified'])}):**"]
            lines += [f"- `{p}`" for p in delta["modified"][:30]]
            if len(delta["modified"]) > 30:
                lines.append(f"- … and {len(delta['modified']) - 30} more")
            lines += [""]
        if delta["deleted"]:
            lines += [f"**🗑 Deleted ({len(delta['deleted'])}):**"]
            lines += [f"- `{p}`" for p in delta["deleted"][:20]]
            lines += [""]

    lines += ["", "---", "", "## Executive Summary", "", exec_summary, "", "---", ""]

    for key in cat_order:
        results = all_results.get(key, [])
        if not results:
            continue
        cat   = CATEGORIES[key]
        label = cat["label"]

        lines += [f"## {label}", ""]

        if key in syntheses:
            lines += ["### 🔄 Category Synthesis", "", syntheses[key], "", "<details>", "<summary>Individual File Reviews</summary>", ""]

        for item in results:
            path   = item["path"]
            review = item["review"]
            tokens = item.get("tokens", {})
            lines += [
                f"### `{path}`", "",
                review, "",
                f"*Tokens — prompt: {tokens.get('prompt_tokens', '?')} · "
                f"completion: {tokens.get('completion_tokens', '?')}*",
                "",
            ]

        if key in syntheses:
            lines += ["</details>", ""]

        lines += ["---", ""]

    lines += [
        "## 📊 Run Statistics", "",
        "| Metric | Value |", "|---|---|",
        f"| Repo | `{repo}` |",
        f"| Branch | `{branch}` |",
        f"| Model | `{model}` |",
        f"| LLM Backend | {'rustcode proxy @ ' + RUSTCODE_URL if RUSTCODE_URL else 'xAI direct'} |",
        f"| Files analysed | {stats['files_analysed']} |",
        f"| Files from rolling cache | {stats.get('files_from_cache', 0)} |",
        f"| New LLM calls | {stats.get('files_new_llm', '?')} |",
        f"| Files skipped | {stats['files_skipped']} |",
        f"| Total tokens | {stats['total_tokens']:,} |",
        f"| Est. cost (USD) | ${stats['est_cost_usd']:.4f} |",
        f"| Run duration | {stats['duration_mins']:.1f} min |",
        f"| Completed at | {now} UTC |",
        "",
    ]

    return "\n".join(lines)


def build_cross_repo_report(
    cross_summary: str,
    repo_summaries: list[dict],
    task_file: Path | None,
    global_stats: dict,
) -> str:
    now = global_stats["timestamp"]
    lines = [
        "# 🌐 FKS Ecosystem — Overnight Cross-Repo Report",
        "",
        f"> **Repos:** {', '.join(r['repo'] for r in repo_summaries)}  ",
        f"> **Total files:** {global_stats['total_files']} · "
        f"**Total tokens:** {global_stats['total_tokens']:,} · "
        f"**Est. cost:** ${global_stats['est_cost_usd']:.4f}  ",
        f"> **Generated:** {now} UTC",
        "",
        "---",
        "",
        "## 🌐 Cross-Repo Executive Summary",
        "",
        cross_summary,
        "",
        "---",
        "",
    ]

    if task_file:
        lines += [
            "## 📋 Generated Task File",
            "",
            f"Rustcode task agent input: `{task_file.name}`  ",
            "Drop this file into the rustcode `tasks/` directory to begin automated execution.",
            "",
            "---",
            "",
        ]

    lines += ["## 📊 Per-Repo Summaries", ""]
    for r in repo_summaries:
        lines += [f"### {r['repo']} — {r['label']}", "", r["exec_summary"], "", "---", ""]

    lines += [
        "## 📊 Global Run Statistics", "",
        "| Metric | Value |", "|---|---|",
        f"| Repos | {global_stats['repos_analysed']} |",
        f"| Total files | {global_stats['total_files']} |",
        f"| Total tokens | {global_stats['total_tokens']:,} |",
        f"| Est. cost | ${global_stats['est_cost_usd']:.4f} |",
        f"| Duration | {global_stats['duration_mins']:.1f} min |",
        f"| Completed | {now} UTC |",
        "",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Per-file analysis orchestrator
# ─────────────────────────────────────────────────────────────────────────────

SKIP_PATTERNS = [
    r"\.lock$", r"^target/", r"^\.git/", r"node_modules/",
    r"\.(png|jpg|jpeg|gif|ico|svg|woff|ttf|eot|otf|mp4|webm|zip|tar|gz|bin|so|dylib|exe|bin)$",
    r"^dist/", r"^build/", r"^\.rustcode/embeddings",
]
_SKIP_RE = re.compile("|".join(SKIP_PATTERNS), re.IGNORECASE)


async def analyse_file(
    llm_client:   httpx.AsyncClient,
    gh_client:    httpx.AsyncClient,
    sem:          asyncio.Semaphore,
    repo:         str,
    blob:         dict,              # full blob dict from GitHub tree API (has .sha)
    gh_token:     str | None,
    api_key:      str,
    model:        str,
    state:        dict,
    cache:        "CacheManager | None" = None,
) -> dict | None:
    """Fetch + analyse one file. Checks rolling cache before hitting the LLM."""
    path      = blob["path"]
    blob_sha  = blob.get("sha", "")
    cache_key = blob.get("_cache_key", "")

    # ── Resume / in-run state cache (fastest path) ────────────────────────────
    if path in state["completed"]:
        print(f"  ↩  {path}  [run-state]")
        return state["completed"][path]

    # ── Rolling cache (cross-run, blob SHA keyed) ─────────────────────────────
    if cache and cache_key and not state.get("_no_cache"):
        cached = cache.get_file_review(cache_key)
        if cached:
            cat_label = CATEGORIES.get(cached.get("category", "other"), {}).get("label", "")
            print(f"  💾 {path}  [cache hit — {cat_label}]")
            state["completed"][path] = cached
            return cached

    async with sem:
        content = await fetch_file(gh_client, repo, path, gh_token)
        if content is None:
            state["skipped"].append(path)
            return None

        cat_key_cat = categorise(path, repo)
        focus       = CATEGORIES[cat_key_cat]["prompt_focus"]
        # Annotate blob so analyse_repo can commit category to cache index
        blob["_category"] = cat_key_cat

        print(f"  🔍 {path}  [{CATEGORIES[cat_key_cat]['label']}]")

        messages = build_file_prompt(path, content, focus, repo)
        review, usage = await call_llm(llm_client, api_key, messages, model)

        result = {
            "path":      path,
            "blob_sha":  blob_sha,
            "cache_key": cache_key,
            "category":  cat_key_cat,
            "review":    review,
            "tokens":    usage,
            "tasks":     extract_task_candidates(review, repo, path),
        }

        # Persist to rolling cache
        if cache and cache_key:
            cache.save_file_review(cache_key, result)

        state["completed"][path] = result
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Single-repo analysis
# ─────────────────────────────────────────────────────────────────────────────

async def analyse_repo(
    llm_client: httpx.AsyncClient,
    gh_client:  httpx.AsyncClient,
    repo:       str,
    branch:     str,
    api_key:    str,
    model:      str,
    gh_token:   str | None,
    output_dir: Path,
    args:       argparse.Namespace,
    cache:      "CacheManager | None" = None,
) -> dict:
    """Run the full analysis pipeline for one repo. Returns a summary dict."""
    profile    = REPO_PROFILES.get(repo, {})
    repo_label = profile.get("label", repo)
    cat_order  = get_category_order(repo)
    run_ts     = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    state_file  = output_dir / f"state_{repo.replace('/', '_')}.json"
    report_file = output_dir / f"report_{repo.replace('/', '_')}_{run_ts}.md"
    state = load_state(state_file) if args.resume else {"completed": {}, "skipped": [], "token_usage": {}}
    if getattr(args, "no_cache", False):
        state["_no_cache"] = True

    start_time = time.monotonic()
    backend = "rustcode @ " + RUSTCODE_URL if RUSTCODE_URL else "xAI direct"
    cache_note = "disabled (--no-cache)" if getattr(args, "no_cache", False) else (
        str(cache.root) if cache else "not available"
    )
    last_run = cache.last_run_ts(repo) if cache else "—"

    print(f"\n{'═'*60}")
    print(f"  Repo     : {repo}")
    print(f"  Label    : {repo_label}")
    print(f"  Branch   : {branch}")
    print(f"  Model    : {model}")
    print(f"  Backend  : {backend}")
    print(f"  Cache    : {cache_note}")
    print(f"  Last run : {last_run or 'first run'}")
    print(f"{'═'*60}\n")

    # 1. Fetch file tree
    print(f"📂 Fetching file tree for {repo} @ {branch} …")
    try:
        tree = await fetch_tree(gh_client, repo, branch, gh_token)
    except httpx.HTTPStatusError as e:
        print(f"  ✗  Could not fetch {repo}: HTTP {e.response.status_code}")
        return {"repo": repo, "label": repo_label, "exec_summary": f"ERROR: {e}", "error": True}

    all_blobs = [b for b in tree if not _SKIP_RE.search(b["path"])]
    print(f"   Found {len(tree)} total, {len(all_blobs)} after filtering.\n")

    # 2. Delta — split blobs into changed (need LLM) vs cached (reuse)
    if cache and not getattr(args, "no_cache", False):
        changed_blobs, cached_results = cache.diff_tree(repo, all_blobs, model)
        delta = cache.build_delta_report(repo, all_blobs, changed_blobs, cached_results, run_ts)
        cache.save_delta(delta, run_ts)
        ds = delta["stats"]
        print(f"📊 Delta vs last run:")
        print(f"   🆕 New files    : {ds['new']}")
        print(f"   ✏️  Modified     : {ds['modified']}")
        print(f"   🗑  Deleted      : {ds['deleted']}")
        print(f"   💾 Unchanged    : {ds['unchanged']}  (LLM calls saved: {ds['llm_calls_saved']})")
        print()
    else:
        changed_blobs  = all_blobs
        cached_results = []
        delta          = None

    if args.dry_run:
        for cat_key in cat_order:
            cat_files = [b["path"] for b in all_blobs if categorise(b["path"], repo) == cat_key]
            if cat_files:
                print(f"\n{CATEGORIES[cat_key]['label']} ({len(cat_files)} files)")
                for p in cat_files:
                    marker = "💾" if p in {r["path"] for r in cached_results} else "🔍"
                    print(f"  {marker} {p}")
        print(f"\n[DRY RUN] {len(changed_blobs)} files would call LLM, "
              f"{len(cached_results)} served from cache.")
        return {"repo": repo, "label": repo_label, "exec_summary": "[DRY RUN]", "error": False}

    # 3. Analyse changed files concurrently
    sem   = asyncio.Semaphore(CONCURRENCY)
    tasks = [
        analyse_file(llm_client, gh_client, sem, repo, blob,
                     gh_token, api_key, model, state, cache)
        for blob in changed_blobs
    ]

    print(f"🚀 Launching {len(tasks)} LLM tasks + {len(cached_results)} from cache "
          f"(concurrency={CONCURRENCY}) …\n")

    new_results: list[dict] = []
    BATCH_SIZE = 20

    for i in range(0, len(tasks), BATCH_SIZE):
        batch_r = await asyncio.gather(*tasks[i:i+BATCH_SIZE], return_exceptions=True)
        for r in batch_r:
            if isinstance(r, Exception):
                print(f"  ✗  Task error: {r}")
            elif r is not None:
                new_results.append(r)
        save_state(state_file, state)
        done = min(i + BATCH_SIZE, len(tasks))
        print(f"\n  ✓  Progress: {done}/{len(tasks)} — state saved.\n")

    # Merge new + cached results
    results: list[dict] = new_results + cached_results

    # 4. Group by category
    all_results: dict[str, list[dict]] = {k: [] for k in cat_order}
    all_task_candidates: list[dict] = []
    for r in results:
        if r:
            all_results[r["category"]].append(r)
            all_task_candidates.extend(r.get("tasks", []))

    # 5. Category syntheses (with cache)
    print("\n🧩 Synthesising category reports …\n")
    syntheses: dict[str, str] = {}
    for cat_key in cat_order:
        items = all_results[cat_key]
        if not items:
            continue
        if len(items) < 2:
            syntheses[cat_key] = items[0]["review"]
            continue

        label      = CATEGORIES[cat_key]["label"]
        blob_shas  = [i.get("blob_sha", i["path"]) for i in items]

        # Check synthesis cache
        if cache and not getattr(args, "no_cache", False):
            cached_syn = cache.get_synthesis(blob_shas, model)
            if cached_syn:
                print(f"  💾 {label} — synthesis cache hit")
                syntheses[cat_key] = cached_syn
                continue

        print(f"  🔄 {label} ({len(items)} files) …")
        messages  = build_synthesis_prompt(label, items, repo)
        synthesis, _ = await call_llm(llm_client, api_key, messages, model, max_tokens=6000, temperature=0.15)
        syntheses[cat_key] = synthesis

        if cache:
            cache.save_synthesis(blob_shas, model, synthesis)

    # 6. Repo executive summary (never cached — always fresh)
    total_tokens = sum(
        (r.get("tokens", {}).get("total_tokens", 0) or 0) for r in new_results if r
    )
    est_cost = total_tokens / 1_000_000 * 4.0
    duration = (time.monotonic() - start_time) / 60
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    stats = {
        "files_analysed":     len(results),
        "files_from_cache":   len(cached_results),
        "files_new_llm":      len(new_results),
        "files_skipped":      len(state["skipped"]),
        "categories":         sum(1 for v in all_results.values() if v),
        "total_tokens":       total_tokens,
        "est_cost_usd":       est_cost,
        "duration_mins":      duration,
        "timestamp":          timestamp,
        "llm_calls_saved":    len(cached_results),
    }

    print(f"\n📝 Building executive summary for {repo} …\n")
    category_reports = [
        {"label": CATEGORIES[k]["label"], "synthesis": syntheses.get(k, "")}
        for k in cat_order if all_results.get(k)
    ]
    exec_msgs    = build_repo_exec_prompt(repo, category_reports, stats)
    exec_summary, _ = await call_llm(llm_client, api_key, exec_msgs, model, max_tokens=8000, temperature=0.1)

    # 7. Write per-repo report (includes delta section)
    report = build_repo_report(
        repo, branch, model, all_results, syntheses, exec_summary, stats,
        delta=delta,
    )
    report_file.write_text(report, encoding="utf-8")
    state_file.unlink(missing_ok=True)

    # 8. Commit this run to the rolling cache index
    if cache and not getattr(args, "no_cache", False):
        cache.commit_repo_run(repo, branch, all_blobs, model, run_ts)
        cache.flush()

    print(f"  ✓  Report   : {report_file}")
    print(f"  ✓  LLM calls: {len(new_results)} new  |  {len(cached_results)} from cache")
    print(f"  ✓  Tasks    : {len(all_task_candidates)} ({sum(1 for t in all_task_candidates if 'manual-review' in t.get('labels', []))} manual review)")

    return {
        "repo":            repo,
        "label":           repo_label,
        "exec_summary":    exec_summary,
        "task_candidates": all_task_candidates,
        "stats":           stats,
        "report_file":     str(report_file),
        "delta":           delta,
        "error":           False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    api_key  = os.getenv("XAI_API_KEY") or ""
    gh_token = os.getenv("GITHUB_TOKEN")
    model    = args.model

    # ── Auth validation ───────────────────────────────────────────────────────
    if not RUSTCODE_URL and not api_key and not args.dry_run \
            and not getattr(args, "cache_info", False) \
            and not getattr(args, "prune_cache", False):
        print("✗  Set XAI_API_KEY (direct xAI) or RUSTCODE_URL (rustcode proxy).")
        sys.exit(1)

    if RUSTCODE_URL:
        print(f"ℹ  LLM backend: rustcode proxy @ {RUSTCODE_URL}")
        if not RUSTCODE_API_KEY:
            print("⚠  RUSTCODE_API_KEY not set — auth may fail if RC_PROXY_API_KEYS is configured.")
    else:
        print("ℹ  LLM backend: xAI direct")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Rolling cache init ────────────────────────────────────────────────────
    cache: "CacheManager | None" = None
    if CacheManager is not None and not getattr(args, "no_cache", False):
        cache_dir = resolve_cache_dir(getattr(args, "cache_dir", ""))
        cache = CacheManager(cache_dir)
        cache.load()
        print(f"ℹ  Cache: {cache_dir}")
    elif CacheManager is None:
        print("⚠  fks_cache_manager.py not found — running without rolling cache.")
    else:
        print("ℹ  Rolling cache disabled (--no-cache).")

    # ── Cache-only commands ───────────────────────────────────────────────────
    if getattr(args, "cache_info", False):
        if cache:
            repos_arg = getattr(args, "repos", None) or ([args.repo] if args.repo != "nuniesmith/fks" or not args.all_repos else ALL_REPOS)
            print("\n📦 Rolling cache info:\n")
            for r in repos_arg:
                cache.print_summary(r)
            print()
            cs = cache.cache_stats()
            print(f"  Total cached reviews : {cs['total_reviews']}")
            print(f"  Total syntheses      : {cs['total_syntheses']}")
            print(f"  Total archived runs  : {cs['total_runs']}")
            print(f"  Cache size on disk   : {cs['disk_mb']} MB")
        else:
            print("No cache available.")
        return

    if getattr(args, "prune_cache", False):
        if cache:
            removed = cache.prune(keep_runs=30)
            cache.flush()
            print(f"✔  Pruned cache: {removed['runs']} old runs, "
                  f"{removed['reviews']} orphaned reviews removed.")
        return

    if getattr(args, "clear_cache", None):
        if cache:
            for repo in args.clear_cache:
                cache.clear_repo(repo)
            cache.flush()
            print("✔  Cache cleared. Next run will do a full re-analysis for those repos.")
        return

    # ── Determine repos ───────────────────────────────────────────────────────
    if getattr(args, "all_repos", False):
        repos = ALL_REPOS
    elif getattr(args, "repos", None):
        repos = args.repos
    else:
        repos = [args.repo]

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"\n╔{'═'*58}╗")
    print(f"║   nuniesmith/fks — Overnight Ecosystem Analyzer{'':9}║")
    print(f"╠{'═'*58}╣")
    print(f"║  Repos   : {', '.join(r.split('/')[1] for r in repos):<47}║")
    print(f"║  Model   : {model:<47}║")
    print(f"║  Output  : {str(output_dir):<47}║")
    cache_label = str(cache.root) if cache else "disabled"
    print(f"║  Cache   : {cache_label:<47}║")
    print(f"╚{'═'*58}╝\n")

    start_time = time.monotonic()
    limits  = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=30)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as gh_client, \
               httpx.AsyncClient(limits=limits, timeout=timeout) as llm_client:

        repo_summaries:      list[dict] = []
        all_task_candidates: list[dict] = []
        report_paths:        list[Path] = []

        for repo in repos:
            profile = REPO_PROFILES.get(repo, {})
            branch  = args.branch or profile.get("branch", "main")

            summary = await analyse_repo(
                llm_client, gh_client, repo, branch,
                api_key, model, gh_token, output_dir, args,
                cache=cache,
            )
            repo_summaries.append(summary)
            all_task_candidates.extend(summary.get("task_candidates", []))
            if summary.get("report_file"):
                report_paths.append(Path(summary["report_file"]))

        if args.dry_run:
            return

        # ── Cross-repo stats ──────────────────────────────────────────────────
        total_cached = sum(
            s.get("stats", {}).get("files_from_cache", 0) for s in repo_summaries
        )
        global_stats = {
            "repos_analysed":    len(repo_summaries),
            "total_files":       sum(s.get("stats", {}).get("files_analysed", 0) for s in repo_summaries),
            "total_tokens":      sum(s.get("stats", {}).get("total_tokens", 0)   for s in repo_summaries),
            "est_cost_usd":      sum(s.get("stats", {}).get("est_cost_usd", 0.0) for s in repo_summaries),
            "total_llm_saved":   total_cached,
            "duration_mins":     (time.monotonic() - start_time) / 60,
            "timestamp":         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

        # ── Task file ─────────────────────────────────────────────────────────
        task_file = None
        if all_task_candidates:
            print(f"\n📋 Writing task file ({len(all_task_candidates)} tasks) …")
            task_file = build_task_file(all_task_candidates, repo_summaries, global_stats, output_dir)
            print(f"  ✓  {task_file}")

        # ── Cross-repo synthesis ──────────────────────────────────────────────
        cross_summary = ""
        if len(repo_summaries) > 1:
            valid = [s for s in repo_summaries if not s.get("error")]
            if valid:
                print("\n🌐 Running cross-repo ecosystem synthesis …")
                cross_msgs    = build_cross_repo_prompt(valid, global_stats)
                cross_summary, _ = await call_llm(
                    llm_client, api_key, cross_msgs, model,
                    max_tokens=10000, temperature=0.1,
                )

        # ── Master report ─────────────────────────────────────────────────────
        master_file   = output_dir / f"fks_ecosystem_report_{run_ts}.md"
        master_report = build_cross_repo_report(cross_summary, repo_summaries, task_file, global_stats)
        master_file.write_text(master_report, encoding="utf-8")

        # ── Archive run in cache ──────────────────────────────────────────────
        if cache:
            run_dir = cache.archive_run(run_ts, report_paths, task_file, master_file)
            print(f"\n📦 Run archived → {run_dir}")
            prune_result = cache.prune(keep_runs=30)
            if prune_result["runs"] > 0:
                print(f"   🗑  Pruned {prune_result['runs']} old run archive(s)")
            cache.flush()

        # ── Final banner ──────────────────────────────────────────────────────
        auto_tasks   = sum(1 for t in all_task_candidates if "manual-review" not in t.get("labels", []))
        manual_tasks = sum(1 for t in all_task_candidates if "manual-review"     in t.get("labels", []))

        cache_saved_str = f"{global_stats['total_llm_saved']} files served from cache"

        print(f"""
╔{'═'*58}╗
║                ✅  Analysis Complete!{'':21}║
╠{'═'*58}╣
║  Repos         : {global_stats['repos_analysed']:<40}║
║  Files         : {global_stats['total_files']:<40}║
║  Cache hits    : {global_stats['total_llm_saved']:<40}║
║  Tokens        : {global_stats['total_tokens']:<40,}║
║  Cost          : ${global_stats['est_cost_usd']:<39.4f}║
║  Duration      : {global_stats['duration_mins']:<38.1f} min║
║  Auto tasks    : {auto_tasks:<40}║
║  Manual review : {manual_tasks:<40}║
║  Master report : {str(master_file):<40}║
╚{'═'*58}╝
""")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Overnight multi-repo analysis for nuniesmith/fks ecosystem via xAI Grok (or rustcode proxy)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Repo selection ────────────────────────────────────────────────────────
    pg = p.add_argument_group("Repo selection")
    pg.add_argument("--repo",      default="nuniesmith/fks",
                    help="Single GitHub repo (owner/name). Default: nuniesmith/fks")
    pg.add_argument("--repos",     nargs="+",
                    help="Explicit list of repos to analyse")
    pg.add_argument("--all-repos", action="store_true",
                    help="Analyse all 6 FKS ecosystem repos")
    pg.add_argument("--branch",    default="",
                    help="Branch override (default: per-repo profile, usually main)")

    # ── Run options ───────────────────────────────────────────────────────────
    rg = p.add_argument_group("Run options")
    rg.add_argument("--model",       default=DEFAULT_MODEL,  help="LLM model ID")
    rg.add_argument("--output",      default="reports/",     help="Output directory for reports")
    rg.add_argument("--resume",      action="store_true",    help="Resume a previous interrupted run")
    rg.add_argument("--dry-run",     action="store_true",    help="List files + cache status, no LLM calls")
    rg.add_argument("--concurrency", type=int, default=CONCURRENCY,
                    help=f"Parallel LLM requests per repo (default: {CONCURRENCY})")

    # ── Rolling cache options ─────────────────────────────────────────────────
    cg = p.add_argument_group("Rolling cache  (stored in .rustcode/analyzer/)")
    cg.add_argument("--cache-dir",    default="",
                    help="Override cache directory path (default: auto-detect fks repo clone)")
    cg.add_argument("--no-cache",     action="store_true",
                    help="Ignore rolling cache — force full re-analysis for all files")
    cg.add_argument("--cache-info",   action="store_true",
                    help="Print cache statistics and exit")
    cg.add_argument("--clear-cache",  nargs="+", metavar="REPO",
                    help="Clear cached data for the given repo(s) and exit "
                         "(e.g. --clear-cache nuniesmith/fks nuniesmith/rustcode)")
    cg.add_argument("--prune-cache",  action="store_true",
                    help="Remove old run archives (keep last 30) and orphaned review files, then exit")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    globals()["CONCURRENCY"] = args.concurrency
    asyncio.run(run(args))
