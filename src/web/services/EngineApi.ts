// Lightweight client for the FKS Engine service (backtest + forecast)
export type EngineForecastResponse = {
  ok: boolean
  symbol: string
  n: number
  last_date?: string
  window: number
  tf_ok: boolean
  llm_comment?: string
  transformer: {
    ok: boolean
    shape?: number[]
    window_used?: number
    horizon_pred?: number
    device?: string
    y_tail?: number[]
    regime_states_tail?: number[]
    regime_last?: number
    confidence?: number
  }
  transformer_raw?: any
}

export type EngineBacktestResponse = {
  ok: boolean
  symbol: string
  trades: number
  equity: number
  tf_ok: boolean
  llm_comment?: string
  transformer: EngineForecastResponse['transformer']
  n: number
  last_date?: string
  signals_tail?: Array<{ date: string; action: string; price: number }>
}

const API_BASE = (import.meta as any).env?.VITE_API_URL?.replace(/\/$/, '') || ''
const ENGINE_BASE_RAW = (import.meta as any).env?.VITE_ENGINE_URL as string | undefined
const ENGINE_BASE = ENGINE_BASE_RAW ? ENGINE_BASE_RAW.replace(/\/$/, '') : API_BASE
import { buildAuthHeaders, authFetch } from './authToken'

function buildHeaders(extra?: HeadersInit): HeadersInit { return buildAuthHeaders(extra) }

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  return authFetch<T>(url, { ...init, headers: buildHeaders({ 'Content-Type': 'application/json', ...(init?.headers || {}) }) })
}

function buildEngineUrl(path: '/forecast' | '/backtest', qs: URLSearchParams): string {
  // Cases we support:
  // 1) ENGINE_BASE empty -> use gateway path /engine
  // 2) ENGINE_BASE points to gateway root (e.g., https://fkstrading.test) -> prefix /engine
  // 3) ENGINE_BASE ends with /engine -> append path directly
  // 4) ENGINE_BASE is direct engine origin (e.g., http://engine:9010) -> append path directly
  if (!ENGINE_BASE) return `/engine${path}?${qs.toString()}`
  const base = ENGINE_BASE.replace(/\/$/, '')
  if (/\/engine$/.test(base)) return `${base}${path}?${qs.toString()}`
  try {
    const u = new URL(base)
    // If base has no path or a non-/engine path, assume direct origin
    if (!u.pathname || u.pathname === '/' || !/\/engine\/?$/.test(u.pathname)) {
      return `${base}${path}?${qs.toString()}`
    }
  } catch {
    // Not a valid URL string; fallback to gateway-style prefix
  }
  return `${base}/engine${path}?${qs.toString()}`
}

export async function forecast(params: { symbol: string; period?: string; window?: number; start?: string; end?: string; withLLM?: boolean }): Promise<EngineForecastResponse> {
  const qs = new URLSearchParams()
  qs.set('symbol', params.symbol)
  if (params.period) qs.set('period', params.period)
  if (params.window != null) qs.set('window', String(params.window))
  if (params.start) qs.set('start', params.start)
  if (params.end) qs.set('end', params.end)
  if (params.withLLM) qs.set('with_llm', '1')
  const url = buildEngineUrl('/forecast', qs)
  return http<EngineForecastResponse>(url)
}

export async function backtest(params: { symbol: string; period?: string; start?: string; end?: string; withLLM?: boolean }): Promise<EngineBacktestResponse> {
  const qs = new URLSearchParams()
  qs.set('symbol', params.symbol)
  if (params.period) qs.set('period', params.period)
  if (params.start) qs.set('start', params.start)
  if (params.end) qs.set('end', params.end)
  if (params.withLLM) qs.set('with_llm', '1')
  const url = buildEngineUrl('/backtest', qs)
  return http<EngineBacktestResponse>(url)
}
