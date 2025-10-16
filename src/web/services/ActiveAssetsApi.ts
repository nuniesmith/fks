import { config } from './config'
import { buildAuthHeaders, authFetch } from './authToken'

// Ensure API base always includes /api prefix expected by FastAPI routers
function resolveApiBase(): string {
  const base = (config.apiBaseUrl || (import.meta as any).env?.VITE_API_URL || '/api').replace(/\/$/, '')
  if (base.endsWith('/api')) return base
  // If user supplied root host (e.g. https://localhost), append /api
  return `${base}/api`
}
const API_BASE = resolveApiBase()

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  try {
    return await authFetch<T>(url, { ...init, headers: buildAuthHeaders({ 'Content-Type': 'application/json', ...(init?.headers || {}) }) })
  } catch (err:any) {
    // Deduplicate noisy 404s for active-assets endpoint during development
    if (/\/active-assets(\/|$)/.test(path) && /404/.test(err?.message || '')) {
      try {
        const key = 'fks.logged.active_assets_api_404'
        if (typeof sessionStorage === 'undefined' || !sessionStorage.getItem(key)) {
          console.warn(`[ActiveAssetsApi] 404 for ${url} (service absent?)`)
          if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(key, '1')
        }
      } catch {}
    }
    throw err;
  }
}

export type ActiveAsset = {
  id: number
  source: string
  symbol: string
  // Optional metadata for richer asset classification. Backend may ignore these.
  asset_type?: string | null
  exchange?: string | null
  intervals: string[]
  years?: number | null
  full_history?: boolean
  enabled: boolean
  created_at?: string
  updated_at?: string
  progress?: Array<{ interval: string; last_cursor?: string; target_start?: string | null; target_end?: string; last_rows?: number; last_run?: string }>
}

export async function listActiveAssets(): Promise<{ items: ActiveAsset[]; count: number }> {
  return http('/active-assets')
}

export async function addActiveAsset(payload: { source: string; symbol: string; intervals: string[]; years?: number; full_history?: boolean; asset_type?: string; exchange?: string }): Promise<{ id: number; ok: boolean }> {
  return http('/active-assets', { method: 'POST', body: JSON.stringify(payload) })
}

export async function removeActiveAsset(id: number): Promise<{ ok: boolean }> {
  return http(`/active-assets/${id}`, { method: 'DELETE' })
}

export async function setActiveAssetEnabled(id: number, enable: boolean): Promise<{ ok: boolean }> {
  return http(`/active-assets/${id}/enable?enable=${enable ? 'true' : 'false'}`, { method: 'POST' })
}

export async function startBackfillScheduler(): Promise<{ ok: boolean }> {
  return http('/active-assets/scheduler/start', { method: 'POST' })
}

export async function stopBackfillScheduler(): Promise<{ ok: boolean }> {
  return http('/active-assets/scheduler/stop', { method: 'POST' })
}
