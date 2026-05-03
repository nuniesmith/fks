"""
fks_cache_manager.py
═══════════════════════════════════════════════════════════════════════════════
Rolling cache for the FKS overnight analyzer.

Stored under:  <fks_repo>/.rustcode/analyzer/
               (or any path set via --cache-dir / FKS_CACHE_DIR)

Directory layout
────────────────
.rustcode/analyzer/
├── index.json                  Master index — per-repo run history + file SHAs
├── file_reviews/               Content-addressable per-file reviews
│   └── <cache_key>.json        Key = sha256(repo + blob_sha + model)[:16]
├── syntheses/                  Category synthesis cache
│   └── <cache_key>.json        Key = sha256(sorted blob_shas in category)[:16]
├── runs/                       Historical run archives
│   └── YYYYMMDD_HHMMSS/
│       ├── ecosystem_report.md
│       ├── tasks.json
│       └── per_repo/
│           └── <repo_slug>.md
└── delta/                      Per-run delta reports (what changed vs last run)
    └── YYYYMMDD_HHMMSS.json

Cache hit rules
───────────────
  File review  : blob_sha unchanged AND same model  →  reuse, skip LLM call
  Synthesis    : ALL blob_shas in category unchanged AND same model  →  reuse
  Exec summary : Never cached (always re-generated — it's cheap and should
                 reflect any new cross-file findings even if files unchanged)

index.json schema
─────────────────
{
  "schema_version": 2,
  "created_at": "<ISO>",
  "last_updated": "<ISO>",
  "repos": {
    "nuniesmith/fks": {
      "branch": "main",
      "last_full_run": "<ISO>",
      "last_commit_sha": "<sha>",       # tip SHA at last run (informational)
      "run_history": ["<ISO>", ...],    # timestamps of all runs
      "file_index": {
        "<path>": {
          "blob_sha":   "<sha>",        # GitHub blob SHA
          "cache_key":  "<key>",        # sha256(repo+blob_sha+model)[:16]
          "last_seen":  "<ISO>",
          "category":   "<cat_key>"
        }
      }
    }
  }
}
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_cache_key(repo: str, blob_sha: str, model: str) -> str:
    """Stable 16-char hex key for a specific file version + model combo."""
    raw = f"{repo}\x00{blob_sha}\x00{model}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _synthesis_cache_key(blob_shas: list[str], model: str) -> str:
    """Stable 16-char hex key for a category synthesis (order-independent)."""
    sorted_shas = sorted(blob_shas)
    raw = model + "\x00" + "\x00".join(sorted_shas)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _slug(repo: str) -> str:
    return repo.replace("/", "_")


# ─────────────────────────────────────────────────────────────────────────────
# CacheManager
# ─────────────────────────────────────────────────────────────────────────────

class CacheManager:
    """
    Manages the rolling cache in .rustcode/analyzer/.

    Usage
    ─────
    cache = CacheManager(Path("/path/to/fks/.rustcode/analyzer"))
    cache.load()

    # Check what changed before analysis
    changed, cached_results = cache.diff_tree("nuniesmith/fks", current_tree, model)

    # Retrieve a cached file review
    result = cache.get_file_review(cache_key)

    # Store a new file review
    cache.save_file_review(cache_key, result_dict)

    # After analysis: update the index
    cache.commit_repo_run("nuniesmith/fks", "main", current_tree, model, run_ts)

    # Archive the run outputs
    cache.archive_run(run_ts, report_paths, task_file)

    cache.flush()
    """

    def __init__(self, cache_dir: Path) -> None:
        self.root          = cache_dir
        self.index_file    = cache_dir / "index.json"
        self.reviews_dir   = cache_dir / "file_reviews"
        self.syntheses_dir = cache_dir / "syntheses"
        self.runs_dir      = cache_dir / "runs"
        self.delta_dir     = cache_dir / "delta"

        self._index: dict[str, Any] = {}
        self._loaded = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load (or initialise) the cache index from disk."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.reviews_dir.mkdir(exist_ok=True)
        self.syntheses_dir.mkdir(exist_ok=True)
        self.runs_dir.mkdir(exist_ok=True)
        self.delta_dir.mkdir(exist_ok=True)

        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
                if data.get("schema_version") != SCHEMA_VERSION:
                    print(f"  ⚠  Cache schema v{data.get('schema_version')} → migrating to v{SCHEMA_VERSION}")
                    data = self._migrate(data)
                self._index = data
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"  ⚠  Cache index corrupt ({exc}) — starting fresh.")
                self._index = self._empty_index()
        else:
            self._index = self._empty_index()

        self._loaded = True

    def flush(self) -> None:
        """Write the index back to disk."""
        assert self._loaded, "Call load() before flush()"
        self._index["last_updated"] = _now()
        self.index_file.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _empty_index(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "created_at":     _now(),
            "last_updated":   _now(),
            "repos":          {},
        }

    def _migrate(self, old: dict) -> dict:
        """Best-effort migration from older schema versions."""
        fresh = self._empty_index()
        # v1 → v2: file_index values were flat dicts without 'category'
        for repo, rdata in old.get("repos", {}).items():
            fresh["repos"][repo] = rdata
            for path, fdata in rdata.get("file_index", {}).items():
                fdata.setdefault("category", "other")
        return fresh

    # ── Repo index access ─────────────────────────────────────────────────────

    def _repo_entry(self, repo: str) -> dict:
        if repo not in self._index["repos"]:
            self._index["repos"][repo] = {
                "branch":          "",
                "last_full_run":   "",
                "last_commit_sha": "",
                "run_history":     [],
                "file_index":      {},
            }
        return self._index["repos"][repo]

    def last_run_ts(self, repo: str) -> str:
        """Return ISO timestamp of last full run, or empty string."""
        return self._repo_entry(repo).get("last_full_run", "")

    def run_history(self, repo: str) -> list[str]:
        return self._repo_entry(repo).get("run_history", [])

    # ── Delta / diff ──────────────────────────────────────────────────────────

    def diff_tree(
        self,
        repo:         str,
        current_tree: list[dict],    # blobs from GitHub tree API
        model:        str,
    ) -> tuple[list[dict], list[dict]]:
        """
        Compare current GitHub tree against the cached file index.

        Returns
        ───────
        changed_blobs   : blobs whose blob_sha differs or are new — need LLM analysis
        cached_results  : list of cached result dicts for unchanged blobs
        """
        entry      = self._repo_entry(repo)
        file_index = entry.get("file_index", {})

        changed: list[dict]        = []
        cached:  list[dict]        = []

        for blob in current_tree:
            path     = blob["path"]
            blob_sha = blob.get("sha", "")

            if path not in file_index:
                # New file — must analyse
                blob["_cache_key"] = _file_cache_key(repo, blob_sha, model)
                changed.append(blob)
                continue

            stored = file_index[path]

            if stored.get("blob_sha") != blob_sha:
                # Content changed — must re-analyse
                blob["_cache_key"] = _file_cache_key(repo, blob_sha, model)
                changed.append(blob)
                continue

            # SHA matches → try to load cached review
            cache_key  = stored.get("cache_key") or _file_cache_key(repo, blob_sha, model)
            cached_rev = self.get_file_review(cache_key)
            if cached_rev is None:
                # Cache entry lost (e.g. file deleted manually) — re-analyse
                blob["_cache_key"] = _file_cache_key(repo, blob_sha, model)
                changed.append(blob)
            else:
                blob["_cache_key"] = cache_key
                cached.append(cached_rev)

        return changed, cached

    def build_delta_report(
        self,
        repo:         str,
        current_tree: list[dict],
        changed:      list[dict],
        cached:       list[dict],
        run_ts:       str,
    ) -> dict:
        """Build a human+machine readable delta summary for this run."""
        entry      = self._repo_entry(repo)
        file_index = entry.get("file_index", {})
        current_paths = {b["path"] for b in current_tree}
        cached_paths  = set(file_index.keys())

        new_files     = [b["path"] for b in changed if b["path"] not in cached_paths]
        modified      = [b["path"] for b in changed if b["path"] in cached_paths]
        deleted       = list(cached_paths - current_paths)
        unchanged     = [r["path"] for r in cached]

        delta = {
            "run_ts":       run_ts,
            "repo":         repo,
            "last_run":     entry.get("last_full_run", "never"),
            "new_files":    new_files,
            "modified":     modified,
            "deleted":      deleted,
            "unchanged":    unchanged,
            "stats": {
                "total":     len(current_tree),
                "new":       len(new_files),
                "modified":  len(modified),
                "deleted":   len(deleted),
                "unchanged": len(unchanged),
                "llm_calls_saved": len(unchanged),
            },
        }
        return delta

    def save_delta(self, delta: dict, run_ts: str) -> None:
        delta_file = self.delta_dir / f"{run_ts}.json"
        delta_file.write_text(json.dumps(delta, indent=2), encoding="utf-8")

    # ── File review cache ─────────────────────────────────────────────────────

    def get_file_review(self, cache_key: str) -> dict | None:
        """Return cached result dict or None."""
        f = self.reviews_dir / f"{cache_key}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save_file_review(self, cache_key: str, result: dict) -> None:
        """Persist a file analysis result."""
        f = self.reviews_dir / f"{cache_key}.json"
        f.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Synthesis cache ───────────────────────────────────────────────────────

    def get_synthesis(self, blob_shas: list[str], model: str) -> str | None:
        """Return cached synthesis text or None."""
        if not blob_shas:
            return None
        key = _synthesis_cache_key(blob_shas, model)
        f   = self.syntheses_dir / f"{key}.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                return data.get("synthesis")
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save_synthesis(self, blob_shas: list[str], model: str, synthesis: str) -> None:
        key = _synthesis_cache_key(blob_shas, model)
        f   = self.syntheses_dir / f"{key}.json"
        f.write_text(
            json.dumps({"synthesis": synthesis, "cached_at": _now()}, indent=2),
            encoding="utf-8",
        )

    # ── Commit run to index ───────────────────────────────────────────────────

    def commit_repo_run(
        self,
        repo:         str,
        branch:       str,
        current_tree: list[dict],
        model:        str,
        run_ts:       str,
        tip_sha:      str = "",
    ) -> None:
        """
        Update the file index for a repo after a completed run.
        Marks every blob in current_tree with its SHA and cache key.
        """
        entry = self._repo_entry(repo)
        entry["branch"]          = branch
        entry["last_full_run"]   = run_ts
        entry["last_commit_sha"] = tip_sha

        history = entry.setdefault("run_history", [])
        if run_ts not in history:
            history.append(run_ts)
        # Keep last 50 run timestamps
        entry["run_history"] = history[-50:]

        new_index: dict[str, dict] = {}
        for blob in current_tree:
            path     = blob["path"]
            blob_sha = blob.get("sha", "")
            cache_key = blob.get("_cache_key") or _file_cache_key(repo, blob_sha, model)
            category  = blob.get("_category", "other")
            new_index[path] = {
                "blob_sha":  blob_sha,
                "cache_key": cache_key,
                "last_seen": run_ts,
                "category":  category,
            }

        entry["file_index"] = new_index

    # ── Run archiving ─────────────────────────────────────────────────────────

    def archive_run(
        self,
        run_ts:       str,
        report_paths: list[Path],    # per-repo .md files
        task_file:    Path | None,
        master_file:  Path | None,
    ) -> Path:
        """
        Copy this run's outputs into runs/<run_ts>/ for historical reference.
        Returns the run directory.
        """
        run_dir     = self.runs_dir / run_ts
        per_repo_dir = run_dir / "per_repo"
        run_dir.mkdir(parents=True, exist_ok=True)
        per_repo_dir.mkdir(exist_ok=True)

        for rp in report_paths:
            if rp.exists():
                shutil.copy2(rp, per_repo_dir / rp.name)

        if task_file and task_file.exists():
            shutil.copy2(task_file, run_dir / task_file.name)

        if master_file and master_file.exists():
            shutil.copy2(master_file, run_dir / master_file.name)

        return run_dir

    # ── Stats / reporting ─────────────────────────────────────────────────────

    def cache_stats(self, repo: str | None = None) -> dict:
        """Return cache statistics for display."""
        review_count    = len(list(self.reviews_dir.glob("*.json")))
        synthesis_count = len(list(self.syntheses_dir.glob("*.json")))
        run_count       = len(list(self.runs_dir.iterdir())) if self.runs_dir.exists() else 0

        stats: dict[str, Any] = {
            "root":             str(self.root),
            "total_reviews":    review_count,
            "total_syntheses":  synthesis_count,
            "total_runs":       run_count,
            "disk_mb":          self._dir_size_mb(self.root),
        }

        if repo:
            entry = self._repo_entry(repo)
            stats["repo"]          = repo
            stats["last_run"]      = entry.get("last_full_run", "never")
            stats["indexed_files"] = len(entry.get("file_index", {}))
            stats["run_count"]     = len(entry.get("run_history", []))

        return stats

    def _dir_size_mb(self, path: Path) -> float:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return round(total / 1_048_576, 2)

    def print_summary(self, repo: str | None = None) -> None:
        s = self.cache_stats(repo)
        print(f"  📦 Cache: {s['root']}")
        print(f"     Reviews  : {s['total_reviews']}")
        print(f"     Syntheses: {s['total_syntheses']}")
        print(f"     Runs     : {s['total_runs']}")
        print(f"     Size     : {s['disk_mb']} MB")
        if repo:
            print(f"     [{repo}] last run  : {s['last_run']}")
            print(f"     [{repo}] indexed   : {s['indexed_files']} files")

    # ── Maintenance ───────────────────────────────────────────────────────────

    def prune(self, keep_runs: int = 30) -> dict:
        """
        Garbage-collect:
          • Old run archives beyond keep_runs
          • Orphaned review/synthesis files no longer referenced by any repo index

        Returns a dict describing what was removed.
        """
        removed = {"runs": 0, "reviews": 0, "syntheses": 0}

        # 1. Prune old run archives
        run_dirs = sorted(self.runs_dir.iterdir()) if self.runs_dir.exists() else []
        for old_run in run_dirs[:-keep_runs]:
            shutil.rmtree(old_run, ignore_errors=True)
            removed["runs"] += 1

        # 2. Collect all live cache keys from the index
        live_keys: set[str] = set()
        for repo_data in self._index.get("repos", {}).values():
            for fdata in repo_data.get("file_index", {}).values():
                if "cache_key" in fdata:
                    live_keys.add(fdata["cache_key"])

        # 3. Remove review files not in live_keys
        for f in self.reviews_dir.glob("*.json"):
            if f.stem not in live_keys:
                f.unlink(missing_ok=True)
                removed["reviews"] += 1

        # Note: syntheses are not tracked in the index (derived keys),
        # so we keep all of them — they're small.

        return removed

    def clear_repo(self, repo: str) -> None:
        """Remove all cached data for a specific repo (forces full re-analysis)."""
        entry = self._repo_entry(repo)
        file_keys = {fdata["cache_key"] for fdata in entry.get("file_index", {}).values()}
        for key in file_keys:
            f = self.reviews_dir / f"{key}.json"
            f.unlink(missing_ok=True)
        self._index["repos"].pop(repo, None)
        print(f"  🗑  Cleared cache for {repo} ({len(file_keys)} reviews removed).")
