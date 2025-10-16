import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
// Light import of security hook to coordinate readiness (lazy import would complicate types; hook already guarded)
import useSecurity from '../hooks/useSecurity'

import { config } from '../services/config'

// Central helper to compute API base. By default we enforce a trailing '/api' so the
// frontend targets the conventional backend prefix. You can disable this behavior by:
//  - build-time env: VITE_API_NO_AUTO_SUFFIX=true
//  - runtime: localStorage.setItem('fks_api_no_auto_suffix','true')
// This is useful when the backend already serves endpoints at root (i.e. /openapi.json).
function buildApiBase(): string {
  const raw = (config.apiBaseUrl || '/api').replace(/\/$/, '')
  let disable = false
  try { if (typeof localStorage !== 'undefined') disable = localStorage.getItem('fks_api_no_auto_suffix') === 'true' } catch {}
  const envDisable = (import.meta as any).env?.VITE_API_NO_AUTO_SUFFIX === 'true'
  if (disable || envDisable) return raw
  return raw.endsWith('/api') ? raw : `${raw}/api`
}

export type TradingMode = 'simulation' | 'live'
export type SessionStatus = 'idle' | 'starting' | 'active' | 'paused' | 'stopping' | 'stopped'

export type TradingSessionState = {
  status: SessionStatus
  startedAt?: string
  pausedAt?: string
  stoppedAt?: string
  strategiesAssigned: number
  activeAssets: number
}

export type LiveReadiness = {
  ok: boolean
  checks: Array<{ id: string; label: string; status: 'passed' | 'warning' | 'failed'; message?: string }>
}

// Legacy (uppercase) mode type expected by older components
export type LegacyTradingMode = 'SIMULATION' | 'LIVE'

// Persisted trading configuration (from legacy TradingEnvironmentContext)
export interface TradingConfig {
  mode: LegacyTradingMode
  accounts: string[]
  activeStrategies: string[]
  riskLimits: {
    maxDailyLoss: number
    maxPositionSize: number
    maxOpenPositions: number
  }
  notifications: {
    enabled: boolean
    email: boolean
    push: boolean
    discord: boolean
  }
}

const defaultTradingConfig: TradingConfig = {
  mode: (config.defaultTradingMode || 'SIMULATION') as LegacyTradingMode,
  accounts: ['demo-account-1'],
  activeStrategies: [],
  riskLimits: {
    maxDailyLoss: 1000,
    maxPositionSize: 10000,
    maxOpenPositions: 5
  },
  notifications: {
    enabled: true,
    email: false,
    push: true,
    discord: false
  }
}

export interface TradingEnvContextValue {
  // New / unified (lowercase) focus & session lifecycle
  focus: TradingMode
  setFocus: (mode: TradingMode) => void
  sim: TradingSessionState
  live: TradingSessionState
  start: (mode: TradingMode) => Promise<void>
  pause: (mode: TradingMode) => Promise<void>
  stop: (mode: TradingMode) => Promise<void>
  refresh: () => Promise<void>
  readiness: LiveReadiness
  // Persisted configuration (legacy shape)
  tradingConfig: TradingConfig
  updateConfig: (partial: Partial<TradingConfig>) => void
  updateEnvironment: (mode: LegacyTradingMode) => void
  environment: LegacyTradingMode
  isLive: boolean
  isSimulation: boolean
  // Diagnostics about active-assets data source
  assetsSource: string
  assetsWarning?: string
  hasActiveAssetsRoute: boolean | null
  refreshCapabilities: () => Promise<void>
}

const TradingEnvContext = createContext<TradingEnvContextValue | undefined>(undefined)

function buildAuthHeaders(): HeadersInit | undefined {
  try {
    const authRaw = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_tokens') : null
    if (!authRaw) return undefined
    const token = JSON.parse(authRaw)?.access_token
    if (!token) return undefined
    return { Authorization: `Bearer ${token}`, 'X-API-Key': token }
  } catch { return undefined }
}

// Lightweight check used to gate API calls that we know will 401 loudly if unauthenticated.
function hasAuthToken(): boolean {
  try {
    const authRaw = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_tokens') : null
    if (!authRaw) return false
    const token = JSON.parse(authRaw)?.access_token
    return !!token
  } catch { return false }
}

async function verifyDatasetSplit(allowRemote: boolean = true): Promise<boolean> {
  try {
    // Endpoint is defined as POST /api/data/dataset/verify
  const base = buildApiBase()
  // Avoid spamming unauthenticated 401s – defer until a token exists
  if (!allowRemote || !hasAuthToken()) return false
  const headers = buildAuthHeaders()
  const res = await fetch(`${base}/data/dataset/verify`, { method: 'POST', headers })
    if (!res.ok) {
      if (res.status === 404) {
        console.warn('[verifyDatasetSplit] 404: dataset verify endpoint not found')
      } else if (res.status === 405) {
        console.warn('[verifyDatasetSplit] 405: method not allowed – backend expects POST?')
      }
      return false
    }
    const j = await res.json().catch(() => ({}))
    return !!(j && (j.ok === true || j.valid === true))
  } catch (e) {
    console.warn('[verifyDatasetSplit] error', e)
    return false
  }
}

async function countAssigned(allowRemote: boolean = true): Promise<{ strategiesAssigned: number; activeAssets: number; meta?: { source: string; warning?: string } }> {
  const base = buildApiBase()
  // If not authenticated yet, skip remote lookups (prevents 401 storm) and fall back immediately
  if (!allowRemote || !hasAuthToken()) {
    try {
      const ls = typeof localStorage !== 'undefined' ? localStorage.getItem('fks.asset.strategy.assignments') : null
      const map: Record<string, string[]> = ls ? JSON.parse(ls) : {}
      const ids = Object.keys(map)
      const strategiesAssigned = ids.reduce((a, k) => a + (map[k]?.length || 0), 0)
      return { strategiesAssigned, activeAssets: ids.length, meta: { source: 'local', warning: 'auth-pending' } }
    } catch {
      return { strategiesAssigned: 0, activeAssets: 0, meta: { source: 'none', warning: 'auth-pending' } }
    }
  }
  // Allow disabling active-assets call (dev) via env/localStorage
  try {
    const disable = (import.meta as any).env?.VITE_DISABLE_ACTIVE_ASSETS === 'true' || (typeof localStorage !== 'undefined' && localStorage.getItem('fks.disable.active_assets') === 'true')
    if (disable) throw new Error('disabled-by-config')
    const assetsUrl = `${base}/active-assets`
    const assignsUrl = `${base}/strategy/assignments`
    const headers = buildAuthHeaders()
    const [assetsRes, assignsRes] = await Promise.all([
      fetch(assetsUrl, { headers }).catch(e => { console.warn('[countAssigned] active-assets fetch failed', e); return undefined as any }),
      fetch(assignsUrl, { headers }).catch(() => undefined as any)
    ])
    if (assetsRes && assetsRes.ok) {
      const j = await assetsRes.json().catch(() => ({}))
      const items = j.items || []
      let serverMap: Record<string, string[]> = {}
      if (assignsRes && assignsRes.ok) {
        const aj = await assignsRes.json().catch(() => ({} as any))
        serverMap = (aj && aj.assignments) || {}
      }
      const ls = typeof localStorage !== 'undefined' ? localStorage.getItem('fks.asset.strategy.assignments') : null
      const localMap: Record<string, string[]> = ls ? JSON.parse(ls) : {}
      const map = { ...serverMap, ...localMap }
      const strategiesAssigned = items.reduce((acc: number, it: any) => acc + ((map[String(it.id)]?.length) || 0), 0)
      return { strategiesAssigned, activeAssets: items.length, meta: { source: 'api' } }
    } else if (assetsRes && assetsRes.status === 404) {
      // Deduplicate noisy 404 logs (only log first time)
      const key = 'fks.logged.active_assets_404'
      try {
        const already = typeof sessionStorage !== 'undefined' && sessionStorage.getItem(key)
        if (!already) {
          console.warn(`[countAssigned] 404 for active-assets at ${assetsRes.url}; treating as zero assets (service not deployed?)`)
          if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(key, '1')
        }
      } catch {
        console.warn(`[countAssigned] 404 for active-assets at ${assetsRes.url}; treating as zero assets (service not deployed?)`)
      }
      // Fall through to local mapping to at least count assigned strategies
      throw new Error('remote-404')
    }
  } catch (err: any) {
    if (err?.message && err.message !== 'remote-404' && err.message !== 'disabled-by-config') {
      console.warn('[countAssigned] falling back to local storage only due to error:', err.message)
    }
  }
  // Local fallback
  try {
    const ls = typeof localStorage !== 'undefined' ? localStorage.getItem('fks.asset.strategy.assignments') : null
    const map: Record<string, string[]> = ls ? JSON.parse(ls) : {}
    const ids = Object.keys(map)
    const strategiesAssigned = ids.reduce((a, k) => a + (map[k]?.length || 0), 0)
    return { strategiesAssigned, activeAssets: ids.length, meta: { source: 'local', warning: 'using-local-fallback' } }
  } catch {
    return { strategiesAssigned: 0, activeAssets: 0, meta: { source: 'none', warning: 'no-data' } }
  }
}

export const TradingEnvProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Security coordination
  const [securityState] = useSecurity();
  // Lowercase focus used by new components
  const [focus, setFocus] = useState<TradingMode>('simulation')
  // Session state
  const [sim, setSim] = useState<TradingSessionState>({ status: 'idle', strategiesAssigned: 0, activeAssets: 0 })
  const [live, setLive] = useState<TradingSessionState>({ status: 'idle', strategiesAssigned: 0, activeAssets: 0 })
  const [readiness, setReadiness] = useState<LiveReadiness>({ ok: false, checks: [] })
  // Persisted configuration (single source of truth replacing legacy provider)
  const [tradingConfig, setTradingConfig] = useState<TradingConfig>(() => {
    try {
  const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('fks_trading-config') : null
      if (saved) {
        const parsed = JSON.parse(saved)
        return { ...defaultTradingConfig, ...parsed }
      }
    } catch (e) {
      console.warn('[TradingEnvProvider] failed to parse saved trading config', e)
    }
    return defaultTradingConfig
  })

  // Keep lowercase focus in sync with persisted config mode
  useEffect(() => {
    const desired = tradingConfig.mode === 'LIVE' ? 'live' : 'simulation'
    setFocus(desired)
  }, [tradingConfig.mode])

  // Persist whenever config changes
  useEffect(() => {
  try { if (typeof localStorage !== 'undefined') localStorage.setItem('fks_trading-config', JSON.stringify(tradingConfig)) } catch {}
  }, [tradingConfig])

  const updateConfig = useCallback((partial: Partial<TradingConfig>) => {
    setTradingConfig(prev => ({ ...prev, ...partial }))
  }, [])

  const updateEnvironment = useCallback((mode: LegacyTradingMode) => {
    setTradingConfig(prev => ({ ...prev, mode }))
    setFocus(mode === 'LIVE' ? 'live' : 'simulation')
  }, [])

  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  // Diagnostics for active-assets source
  const [assetsMeta, setAssetsMeta] = useState<{ source: string; warning?: string }>({ source: 'unknown' })
  const [hasActiveAssetsRoute, setHasActiveAssetsRoute] = useState<boolean | null>(null)
  const OPENAPI_CACHE_KEY = 'fks.openapi.capabilities'
  const OPENAPI_TTL_MS = 5 * 60 * 1000 // 5 minutes
  const OPENAPI_THROTTLE_MS = 30 * 1000 // throttle unauthenticated attempts
  const OPENAPI_LAST_ATTEMPT_KEY = 'fks.openapi.lastAttemptTs'

  const loadCachedCapabilities = useCallback(() => {
    try {
      const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(OPENAPI_CACHE_KEY) : null
      if (!raw) return false
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object') return false
      if (Date.now() - (parsed.ts || 0) > OPENAPI_TTL_MS) return false
      if (typeof parsed.hasActiveAssetsRoute !== 'undefined') {
        setHasActiveAssetsRoute(!!parsed.hasActiveAssetsRoute)
        return true
      }
      return false
    } catch { return false }
  }, [])

  const refreshCapabilities = useCallback(async () => {
    try {
      const base = buildApiBase()
      const authed = hasAuthToken()
      // Allow disabling probe entirely (useful for backends without OpenAPI or to suppress 401 noise)
      const probeDisabled = (import.meta as any).env?.VITE_DISABLE_OPENAPI_PROBE === 'true' || (typeof localStorage !== 'undefined' && localStorage.getItem('fks.disable.openapi_probe') === 'true')
      if (probeDisabled) return
      // Throttle unauthenticated probing to avoid 401 spam
      if (!authed) {
        try {
          const last = parseInt(localStorage.getItem(OPENAPI_LAST_ATTEMPT_KEY) || '0')
          if (Date.now() - last < OPENAPI_THROTTLE_MS) return
          // If we still don't have auth, skip the probe entirely and rely on later refresh()
          // This prevents an initial guaranteed 401 during cold start.
          if (!authed) {
            localStorage.setItem(OPENAPI_LAST_ATTEMPT_KEY, String(Date.now()))
            return
          }
          localStorage.setItem(OPENAPI_LAST_ATTEMPT_KEY, String(Date.now()))
        } catch {}
      }
      const headers = buildAuthHeaders()
      let res = await fetch(`${base}/openapi.json`, { method: 'GET', headers }).catch(() => undefined as any)
      // Treat 401 like 404 for fallback purposes (common when OpenAPI served unauthenticated at root)
      if (!res || ((res.status === 404 || res.status === 401) && /\/api$/.test(base))) {
        const rootBase = base.replace(/\/api$/, '')
        const rootRes = await fetch(`${rootBase}/openapi.json`, { method: 'GET', headers }).catch(() => undefined as any)
        // Prefer successful root response
        if (rootRes && rootRes.ok) res = rootRes
      }
      if (!res || !res.ok) {
        // Only mutate state if we previously thought the route existed to avoid useless re-renders
        setHasActiveAssetsRoute(prev => prev === null ? prev : null)
        return
      }
      const j = await res.json().catch(() => ({}))
      const paths = j?.paths || {}
      const has = Boolean(paths['/active-assets'] || paths['/active-assets/'])
      setHasActiveAssetsRoute(has)
      try { localStorage.setItem(OPENAPI_CACHE_KEY, JSON.stringify({ ts: Date.now(), hasActiveAssetsRoute: has })) } catch {}
    } catch {
      setHasActiveAssetsRoute(null)
    }
  }, [])

  // Initial probe with cache usage
  useEffect(() => {
    let cancelled = false
    const run = async () => {
  const hit = loadCachedCapabilities()
  // Skip live probing until we have an auth token (prevents initial 401 spam). Cached value still used if valid.
  if (!hasAuthToken()) return
  if (!hit && !cancelled) await refreshCapabilities()
    }
    run()
    return () => { cancelled = true }
  }, [loadCachedCapabilities, refreshCapabilities])

  const computeReadiness = useCallback(async () => {
    const allowRemote = securityState.authenticated; // only hit network after security layer confirms auth
    const [splitOk, assigned] = await Promise.all([verifyDatasetSplit(allowRemote), countAssigned(allowRemote)])
    if (!mountedRef.current) return
    const checks: LiveReadiness['checks'] = [
      { id: 'dataset', label: 'Dataset split verified (80/10/10)', status: splitOk ? 'passed' : 'failed' },
      { id: 'assignments', label: 'Strategies assigned to active assets', status: assigned.strategiesAssigned > 0 ? 'passed' : 'warning' },
  ...(assigned.meta && assigned.meta.source !== 'api' && hasActiveAssetsRoute !== false
    ? [{ id: 'active-assets-source', label: `Active assets source (${assigned.meta.source})`, status: 'warning' as const, message: assigned.meta.warning || (hasActiveAssetsRoute ? 'fallback in use' : 'route unavailable') }]
    : [])
    ]
    setReadiness({ ok: checks.every(c => c.status === 'passed'), checks })
  }, [hasActiveAssetsRoute])

  const refresh = useCallback(async () => {
    await computeReadiness()
  const assigned = await countAssigned(securityState.authenticated)
    if (!mountedRef.current) return
    setSim(s => ({ ...s, strategiesAssigned: assigned.strategiesAssigned, activeAssets: assigned.activeAssets }))
    setLive(s => ({ ...s, strategiesAssigned: assigned.strategiesAssigned, activeAssets: assigned.activeAssets }))
  // Store diagnostic meta for context consumers
  setAssetsMeta({ source: assigned.meta?.source || 'unknown', warning: assigned.meta?.warning })
  }, [computeReadiness, securityState.authenticated])

  // Defer first refresh until security layer finished first init attempt to avoid 401 noise
  useEffect(() => {
    if (securityState.ready) {
      refresh();
    }
  // only fire when transitioning to ready true
  }, [securityState.ready, refresh])

  // After authentication transitions to true (might already have been "ready" unauthenticated)
  // perform a capability probe + full refresh (once per auth session).
  const authRef = useRef<boolean>(securityState.authenticated)
  useEffect(() => {
    if (securityState.authenticated && !authRef.current) {
      authRef.current = true
      // Refresh capabilities and environment data now that we can hit protected endpoints
      refreshCapabilities().catch(() => {})
      refresh().catch(() => {})
    } else if (!securityState.authenticated && authRef.current) {
      // Reset so next login triggers again
      authRef.current = false
    }
  }, [securityState.authenticated, refreshCapabilities, refresh])

  const start = useCallback(async (mode: TradingMode) => {
    const setter = mode === 'simulation' ? setSim : setLive
    setter(s => ({ ...s, status: 'starting' }))
  const base = buildApiBase()
    await fetch(`${base}/trading/sessions/start?mode=${mode}`, { method: 'POST' }).catch(() => {})
    if (mountedRef.current) {
      setter(s => ({ ...s, status: 'active', startedAt: new Date().toISOString() }))
    }
  }, [])

  const pause = useCallback(async (mode: TradingMode) => {
    const setter = mode === 'simulation' ? setSim : setLive
    setter(s => ({ ...s, status: 'paused', pausedAt: new Date().toISOString() }))
  const base = buildApiBase()
    await fetch(`${base}/trading/sessions/pause?mode=${mode}`, { method: 'POST' }).catch(() => {})
  }, [])

  const stop = useCallback(async (mode: TradingMode) => {
    const setter = mode === 'simulation' ? setSim : setLive
    setter(s => ({ ...s, status: 'stopping' }))
  const base = buildApiBase()
    await fetch(`${base}/trading/sessions/stop?mode=${mode}`, { method: 'POST' }).catch(() => {})
    if (!mountedRef.current) return
    setter(s => ({ ...s, status: 'stopped', stoppedAt: new Date().toISOString() }))
  }, [])

  const value = useMemo<TradingEnvContextValue>(() => ({
    focus,
    setFocus,
    sim,
    live,
    start,
    pause,
    stop,
    refresh,
    readiness,
    tradingConfig,
    updateConfig,
    updateEnvironment,
    environment: tradingConfig.mode,
    isLive: tradingConfig.mode === 'LIVE',
    isSimulation: tradingConfig.mode === 'SIMULATION',
    assetsSource: assetsMeta.source,
    assetsWarning: assetsMeta.warning,
    hasActiveAssetsRoute,
    refreshCapabilities
  }), [focus, sim, live, start, pause, stop, refresh, readiness, tradingConfig, updateConfig, updateEnvironment, assetsMeta, hasActiveAssetsRoute, refreshCapabilities])
  return (
    <TradingEnvContext.Provider value={value}>{children}</TradingEnvContext.Provider>
  )
}

export function useTradingEnv(): TradingEnvContextValue {
  const ctx = useContext(TradingEnvContext)
  if (!ctx) throw new Error('useTradingEnv must be used within TradingEnvProvider')
  return ctx
}
