import { describe, it, expect, beforeEach, vi } from 'vitest'
// Hoist mock before importing module under test
const mockAk = { refreshToken: vi.fn(async (r: string) => ({ access_token: 'newA', refresh_token: r })) }
vi.mock('../security/AuthentikService', () => ({ default: { getInstance: () => mockAk } }))
import { getCurrentAccessToken, buildAuthHeaders, authFetch, refreshAccessToken } from '../authToken'

function setTokens(tokens: any) {
  localStorage.setItem('auth_tokens', JSON.stringify(tokens))
}

describe('authToken utilities', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('prefers access_token from auth_tokens', () => {
    setTokens({ access_token: 'abc123', refresh_token: 'r1' })
    expect(getCurrentAccessToken()).toBe('abc123')
  })

  it('falls back to fks_api_token localStorage', () => {
    localStorage.setItem('fks_api_token', 'legacy-token')
    expect(getCurrentAccessToken()).toBe('legacy-token')
  })

  it('buildAuthHeaders sets all auth header variants', () => {
    setTokens({ access_token: 'tokX' })
    const h = buildAuthHeaders()
    expect((h as any).Authorization).toBe('Bearer tokX')
    expect((h as any)['X-API-Key']).toBe('tokX')
    expect((h as any)['api-key']).toBe('tokX')
  })

  it('authFetch retries once on 401 with refresh success', async () => {
    setTokens({ access_token: 'oldA', refresh_token: 'refreshA' })
    let calls: Array<{ url: string; auth?: string }> = []
    global.fetch = vi.fn(async (url: any, init: any) => {
      const auth = init?.headers?.Authorization || init?.headers?.authorization
      calls.push({ url, auth })
      if (calls.length === 1) {
        return new Response('unauthorized', { status: 401 }) as any
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 }) as any
    }) as any
    const res = await authFetch<any>('https://example.com/secure')
    expect(res.ok).toBe(true)
    expect(calls.length).toBe(2)
    expect(mockAk.refreshToken).toHaveBeenCalled()
  })

  it('refreshAccessToken returns undefined if no refresh token', async () => {
    setTokens({ access_token: 'onlyA' })
    const val = await refreshAccessToken()
    expect(val).toBeUndefined()
  })
})
