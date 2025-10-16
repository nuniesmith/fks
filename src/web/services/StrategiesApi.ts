import { config } from './config'
import { buildAuthHeaders, authFetch } from './authToken'

export type StrategySummary = {
  id: string
  name: string
  type: 'entry' | 'exit' | 'filter' | 'risk' | 'composite'
  description?: string
  status?: 'active' | 'inactive' | 'testing'
}

const API_BASE = (config.apiBaseUrl || '/api').replace(/\/$/, '')
function headers(extra?: HeadersInit): HeadersInit { return buildAuthHeaders(extra) }

export async function listStrategies(): Promise<StrategySummary[]> {
  try {
  const j = await authFetch<any>(`${API_BASE}/strategies`, { headers: headers() })
    return j.items || j.strategies || []
  } catch {
    return []
  }
}

export async function saveAssignments(assignments: Record<string, string[]>): Promise<boolean> {
  try {
    await authFetch(`${API_BASE}/strategy/assignments`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ assignments }) })
    return true
  } catch {
    return false
  }
}

export async function getAssignments(): Promise<Record<string, string[]>> {
  try {
  const j = await authFetch<any>(`${API_BASE}/strategy/assignments`, { headers: headers() }).catch(() => ({} as any))
    return (j && j.assignments) || {}
  } catch {
    return {}
  }
}
