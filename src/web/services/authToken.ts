// Shared auth token utilities for FKS web clients
// Centralizes access token resolution and refresh for fetch-based APIs.
import AuthentikService from './security/AuthentikService'

/** Get the best current access token from localStorage or environment */
export function getCurrentAccessToken(): string | undefined {
  // jsdom provides localStorage, no need for window guard in tests.
  try {
    const ls: Storage | undefined = (globalThis as any)?.localStorage
    if (ls) {
      const raw = ls.getItem('auth_tokens')
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed?.access_token) return parsed.access_token as string
      }
      const legacy = ls.getItem('fks_api_token')
      if (legacy) return legacy
    }
    return (import.meta as any).env?.VITE_API_TOKEN
  } catch {
    return (import.meta as any).env?.VITE_API_TOKEN
  }
}

/** Attempt refresh of Authentik token if refresh_token present */
export async function refreshAccessToken(): Promise<string | undefined> {
  try {
    const raw = typeof window !== 'undefined' ? localStorage.getItem('auth_tokens') : null
    if (!raw) return
    const parsed = JSON.parse(raw)
    const refresh = parsed?.refresh_token as string | undefined
    if (!refresh) return
    const ak = AuthentikService.getInstance()
    const newTokens = await ak.refreshToken(refresh)
    localStorage.setItem('auth_tokens', JSON.stringify(newTokens))
    return newTokens.access_token
  } catch { return }
}

/** Build standard auth headers (Authorization, X-API-Key, api-key) */
export function buildAuthHeaders(base?: HeadersInit): HeadersInit {
  const headers: HeadersInit = { ...(base || {}) }
  const token = getCurrentAccessToken()
  if (token) {
    ;(headers as any).Authorization = `Bearer ${token}`
    ;(headers as any)['X-API-Key'] = token
    ;(headers as any)['api-key'] = token
  }
  return headers
}

/** Fetch wrapper with single automatic 401 refresh retry */
export async function authFetch<T>(url: string, init?: RequestInit, _retried = false): Promise<T> {
  const res = await fetch(url, { ...init, headers: buildAuthHeaders(init?.headers) })
  if (res.status === 401 && !_retried) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      const retryHeaders = buildAuthHeaders(init?.headers)
      const retryRes = await fetch(url, { ...init, headers: retryHeaders })
      if (!retryRes.ok) throw new Error(`${retryRes.status} ${retryRes.statusText}: ${await retryRes.text().catch(()=>'')}`)
      return retryRes.json() as Promise<T>
    }
  }
  if (!res.ok) {
    const text = await res.text().catch(()=>res.statusText)
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}
