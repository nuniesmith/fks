/**
 * FKS Bot Spawner API Client
 *
 * Wraps the spawner's HTTP surface so route components don't have to
 * know the URL structure. We use the `/api/spawner/*` passthrough
 * route exclusively (not the `/api/bots/*` rewrite route) because:
 *
 *   - The `/api/bots/` rewrites collapse paths into `/container/<id>/<...>`
 *     which would mis-route `/api/bots/runs` → `/container/runs` (404).
 *   - The passthrough is a single `^/api/spawner/(.*)$ → /$1` rule, so
 *     every spawner route maps trivially.
 *
 *   browser                            → fks_bot_spawner:8090
 *   ─────────────────────────────────────────────────────────
 *   GET    /api/spawner/health            → /health
 *   GET    /api/spawner/containers        → /containers
 *   GET    /api/spawner/container/<id>    → /container/<id>
 *   POST   /api/spawner/spawn             → /spawn
 *   POST   /api/spawner/container/<id>/stop / restart  → ...
 *   DELETE /api/spawner/container/<id>    → /container/<id>
 *   GET    /api/spawner/container/<id>/logs            → SSE
 *   GET    /api/spawner/runs?limit=N      → /runs (db feature only)
 *
 * The vite dev server proxies `/api/spawner` → `http://fks_bot_spawner:8090/`
 * with the same rewrite as the production nginx config.
 */
import { api } from "./client";
import type {
  ActionResponse,
  ConfigsResponse,
  ContainerInfo,
  ContainersResponse,
  HealthResponse,
  RunsResponse,
  SaveConfigRequest,
  SpawnRequest,
  SpawnResponse,
} from "$lib/types/spawner";

/** Base path — matches the nginx + vite proxy passthrough rewrites. */
const BASE = "/api/spawner";

export const spawner = {
  // ── Health & inventory ────────────────────────────────────────────────

  health: () => api.get<HealthResponse>(`${BASE}/health`),

  list: () => api.get<ContainersResponse>(`${BASE}/containers`),

  inspect: (id: string) => api.get<ContainerInfo>(`${BASE}/container/${id}`),

  // ── Lifecycle actions ──────────────────────────────────────────────────

  spawn: (req: SpawnRequest) => api.post<SpawnResponse>(`${BASE}/spawn`, req),

  stop: (id: string) =>
    api.post<ActionResponse>(`${BASE}/container/${id}/stop`),

  restart: (id: string) =>
    api.post<ActionResponse>(`${BASE}/container/${id}/restart`),

  remove: (id: string) => api.delete<ActionResponse>(`${BASE}/container/${id}`),

  // ── History ────────────────────────────────────────────────────────────

  /**
   * Recent run history. The spawner returns `db_enabled: false` (and an
   * empty array) when Postgres isn't configured — callers should check
   * the flag before showing a "no data" message instead of an error.
   */
  runs: (limit = 50) => api.get<RunsResponse>(`${BASE}/runs?limit=${limit}`),

  // ── Saved spawn configs (db feature) ───────────────────────────────────

  /** List active saved spawn configs. `db_enabled:false` ⇒ empty array. */
  listConfigs: () => api.get<ConfigsResponse>(`${BASE}/configs`),

  /** Save (UPSERT by name) a reusable spawn config. */
  saveConfig: (req: SaveConfigRequest) =>
    api.post<{ ok: boolean; id?: string; name?: string }>(`${BASE}/configs`, req),

  /** Soft-delete a saved config by name. */
  deleteConfig: (name: string) =>
    api.delete<{ ok: boolean; name?: string }>(
      `${BASE}/configs/${encodeURIComponent(name)}`,
    ),

  // ── SSE log stream ─────────────────────────────────────────────────────

  /**
   * Open a Server-Sent Events stream of container logs. Caller is
   * responsible for closing the returned EventSource. Each event has
   * type `"log"` with `data` set to the log line (already trimmed).
   *
   * @param id   Short or full container ID.
   * @param tail Number of historical lines to send before tailing live
   *             output. Default 100 (matches the spawner default).
   */
  openLogStream: (id: string, tail = 100): EventSource => {
    const url = `${BASE}/container/${id}/logs?tail=${tail}`;
    return new EventSource(url);
  },
};
