/**
 * FKS Bot Spawner — Shared Types
 *
 * Mirror of the Rust types in `src/spawner/src/models.rs` and
 * `src/spawner/src/db.rs`. Keep these in sync with the Rust definitions
 * — the spawner exposes JSON over HTTP at `/api/bots/*` (via nginx) or
 * `/api/spawner/*` (passthrough), so any field rename on either side
 * needs to be reflected here.
 */

// ─── Container info ──────────────────────────────────────────────────────

/** Bot mode label — informational, stored as a container label. */
export type BotMode = "paper" | "live" | "backtest" | "optimise" | "train";

/** A bot container as returned by `GET /containers` and `GET /container/:id`. */
export interface ContainerInfo {
  /** Short Docker container ID (12 chars). */
  id: string;
  /** Full 64-char container ID. */
  id_full: string;
  /** Container name — typically `fks-bot-<bot_id>`. */
  name: string;
  /** Image, e.g. `fks-bot-arbitrage:latest`. */
  image: string;
  /** Human-readable status string from Docker (e.g. "Up 5 minutes"). */
  status: string;
  /** Lifecycle state (e.g. "running", "exited", "dead"). */
  state: string;
  /** Bot identifier from the `fks.bot_id` label. */
  bot_id: string;
  /** Mode from the `fks.mode` label. */
  mode: string;
  /** ISO-8601 timestamp; null if unknown. */
  created_at: string | null;
  /** ISO-8601 timestamp; null if not yet started. */
  started_at: string | null;
  /** ISO-8601 timestamp; null if still running. */
  finished_at: string | null;
  /** All container labels (includes the `fks.*` ones plus user-supplied). */
  labels: Record<string, string>;
  /** Last sampled CPU % (per-core, optional — not always populated). */
  cpu_percent: number | null;
  /** Last sampled memory in bytes. */
  memory_bytes: number | null;
}

/** Wrapper returned by `GET /containers`. */
export interface ContainersResponse {
  containers: ContainerInfo[];
  total: number;
  running: number;
}

// ─── Spawn ────────────────────────────────────────────────────────────────

/** Request body for `POST /spawn`. */
export interface SpawnRequest {
  /** Docker image — must start with the spawner's `ALLOWED_IMAGE_PREFIX`. */
  image: string;
  /** Optional bot id; auto-generated UUID when omitted. */
  bot_id?: string;
  /** Defaults to `"paper"`. */
  mode?: BotMode | string;
  env?: Record<string, string>;
  labels?: Record<string, string>;
  /** Fractional cores. */
  cpu_limit?: number;
  /** Megabytes. */
  memory_limit_mb?: number;
  cmd?: string[];
  entrypoint?: string[];
}

/** Response body for `POST /spawn` (HTTP 201). */
export interface SpawnResponse {
  container_id: string;
  container_name: string;
  bot_id: string;
  image: string;
  mode: string;
  /** ISO-8601 timestamp. */
  started_at: string;
}

// ─── Action / health ──────────────────────────────────────────────────────

/** Generic ack body for stop/restart/remove. */
export interface ActionResponse {
  ok: boolean;
  container_id: string;
  action: string;
  message: string;
}

/** `GET /health` response. */
export interface HealthResponse {
  status: "ok";
  service: "fks-bot-spawner";
  version: string;
  running_bots: number;
  max_bots: number;
}

// ─── Run history (db feature) ────────────────────────────────────────────

/** A single row from the `bot_runs` table. */
export interface BotRun {
  id: string;
  container_id: string;
  container_name: string | null;
  image: string;
  mode: string;
  /** spawning | running | stopping | stopped | error | pruned */
  status: string;
  started_at: string;
  stopped_at: string | null;
  runtime_secs: number | null;
  error_message: string | null;
}

/** `GET /runs?limit=N` wrapper. When `db_enabled=false` the array is empty. */
export interface RunsResponse {
  runs: BotRun[];
  total: number;
  db_enabled: boolean;
}

// ─── Errors ──────────────────────────────────────────────────────────────

/** Error envelope used by all 4xx/5xx responses. */
export interface SpawnerErrorBody {
  error: string;
  detail?: string;
}
