// Lightweight client for the FKS Data API
import { config } from './config';
import { buildAuthHeaders, authFetch } from './authToken';
export type SourceInfo = {
  id: string
  name: string
  type: string
  description?: string
  requires_auth?: boolean
  supports_live?: boolean
  intervals?: string[]
  asset_types?: string[]
}

export type ListSourcesResponse = {
  sources: Record<string, SourceInfo>
  count: number
}

export type MarketDataJsonResponse = {
  symbol: string
  source: string
  interval: string
  count: number
  total: number
  next_page_token?: string | null
  columns: string[]
  data: Array<Record<string, unknown>>
}

export type SymbolListResponse = {
  symbols: Array<{
    symbol: string
    name?: string
    exchange?: string
    asset_type?: string
  }>
  count: number
  total?: number
}

// Use the configured API base URL which may be "/api" or a full URL ending in "/api"
const API_BASE = (config.apiBaseUrl || (import.meta as any).env?.VITE_API_URL || '/api').replace(/\/$/, '')
// Data API is exposed from the Core API under the "/data" prefix (the API base already includes "/api").
const DATA_API_BASE = API_BASE
async function http<T>(path: string, init?: RequestInit, base: string = API_BASE): Promise<T> {
  const url = `${base}${path}`
  return authFetch<T>(url, { ...init, headers: buildAuthHeaders({ 'Content-Type': 'application/json', ...(init?.headers || {}) }) })
}

export async function listSources(): Promise<ListSourcesResponse> {
  // API_BASE already points to "/api", so we only append "/data/*"
  return http<ListSourcesResponse>(`/data/sources`, undefined, DATA_API_BASE)
}

export async function listSymbols(sourceId: string, opts?: { query?: string; limit?: number }): Promise<SymbolListResponse> {
  const params = new URLSearchParams()
  if (opts?.query) params.set('query', opts.query)
  if (opts?.limit != null) params.set('limit', String(opts.limit))
  return http<SymbolListResponse>(`/data/sources/${encodeURIComponent(sourceId)}/symbols?${params.toString()}`, undefined, DATA_API_BASE)
}

export async function getMarketDataPage(
  sourceId: string,
  symbol: string,
  opts: { interval?: string; limit?: number; pageToken?: string | null; startDate?: string; endDate?: string }
): Promise<MarketDataJsonResponse> {
  const params = new URLSearchParams()
  if (opts.interval) params.set('interval', opts.interval)
  if (opts.limit != null) params.set('limit', String(opts.limit))
  if (opts.pageToken) params.set('page_token', opts.pageToken)
  if (opts.startDate) params.set('start_date', opts.startDate)
  if (opts.endDate) params.set('end_date', opts.endDate)
  return http<MarketDataJsonResponse>(`/data/sources/${encodeURIComponent(sourceId)}/data/${encodeURIComponent(symbol)}?${params.toString()}`,
    undefined,
    DATA_API_BASE
  )
}

export async function downloadMarketDataCsv(
  sourceId: string,
  symbol: string,
  opts: { interval?: string; limit?: number; pageToken?: string | null }
): Promise<{ blob: Blob; filename: string }> {
  const params = new URLSearchParams()
  params.set('format', 'csv')
  if (opts.interval) params.set('interval', opts.interval)
  if (opts.limit != null) params.set('limit', String(opts.limit))
  if (opts.pageToken) params.set('page_token', opts.pageToken)

  const url = `${DATA_API_BASE}/data/sources/${encodeURIComponent(sourceId)}/data/${encodeURIComponent(symbol)}?${params.toString()}`
  const res = await fetch(url, { headers: buildAuthHeaders() })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`CSV HTTP ${res.status} ${res.statusText}: ${text}`)
  }
  const disp = res.headers.get('content-disposition') || ''
  const m = /filename=([^;]+)/i.exec(disp)
  const filename = m ? m[1] : `${symbol}.csv`
  const blob = await res.blob()
  return { blob, filename }
}
