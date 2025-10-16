// Lightweight JWT/refresh token manager for Rust auth service
// Responsibilities:
//  - Parse stored tokens (auth_tokens)
//  - Detect expiry and schedule proactive refresh (60s before)
//  - Attempt refresh via POST /refresh (configurable base URL)
//  - Broadcast CustomEvents: auth:tokenRefreshed, auth:tokenRefreshFailed
//  - Graceful no-op if refresh_token absent

export interface StoredTokens {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number; // seconds (optional if JWT has exp claim)
  obtained_at?: number; // ms epoch when stored
}

type RefreshResult = { ok: boolean; refreshed?: boolean; error?: string };

export class AuthTokenManager {
  private static instance: AuthTokenManager;
  private refreshTimer: any = null;
  private scheduling = false;
  private lastRefreshAttempt = 0;
  private consecutiveFailures = 0;
  private static readonly MAX_CONSECUTIVE_FAILURES = 3;

  static getInstance(): AuthTokenManager {
    if (!AuthTokenManager.instance) {
      AuthTokenManager.instance = new AuthTokenManager();
    }
    return AuthTokenManager.instance;
  }

  getAuthBase(): string {
    const explicit = (import.meta as any).env?.VITE_RUST_AUTH_URL;
    if (explicit && explicit.trim().length) return explicit.replace(/\/$/, '');
    if (typeof window !== 'undefined' && window.location.port === '4100') {
      return 'http://localhost:4100';
    }
    return '/auth';
  }

  readTokens(): StoredTokens | null {
    try {
      const raw = localStorage.getItem('auth_tokens');
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed || null;
    } catch { return null; }
  }

  writeTokens(tokens: StoredTokens) {
    try {
      tokens.obtained_at = Date.now();
      localStorage.setItem('auth_tokens', JSON.stringify(tokens));
    } catch { /* ignore */ }
  }

  clear() {
    if (this.refreshTimer) { clearTimeout(this.refreshTimer); this.refreshTimer = null; }
    this.scheduling = false;
  }

  private decodeJwt(token: string): any | null {
    try {
      const parts = token.split('.');
      if (parts.length < 2) return null;
      const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const json = atob(payload);
      return JSON.parse(json);
    } catch { return null; }
  }

  private getExpiry(tokens: StoredTokens): number | null {
    if (!tokens) return null;
    // Priority 1: JWT exp claim
    const jwt = tokens.access_token && this.decodeJwt(tokens.access_token);
    if (jwt?.exp) { return jwt.exp * 1000; }
    // Priority 2: expires_in relative
    if (tokens.expires_in && tokens.obtained_at) {
      return tokens.obtained_at + tokens.expires_in * 1000;
    }
    return null;
  }

  ensureSchedule(): void {
    if (this.scheduling) return;
    const tokens = this.readTokens();
    if (!tokens) return;
    const exp = this.getExpiry(tokens);
    if (!exp) return; // cannot schedule without expiry info
    const leadMs = 60_000; // refresh 60s before expiry
    const delay = Math.max(5_000, exp - Date.now() - leadMs);
    this.scheduling = true;
    this.refreshTimer = setTimeout(() => {
      this.scheduling = false;
      this.attemptRefresh();
    }, delay);
  }

  async attemptRefresh(): Promise<RefreshResult> {
    const tokens = this.readTokens();
    if (!tokens || !tokens.refresh_token) { return { ok: false, error: 'no-refresh-token' }; }
    // Basic throttle: avoid hammering if failing
    if (Date.now() - this.lastRefreshAttempt < 10_000) { return { ok: false, error: 'throttled' }; }
    this.lastRefreshAttempt = Date.now();
    try {
      const resp = await fetch(`${this.getAuthBase().replace(/\/$/, '')}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: tokens.refresh_token })
      });
      if (!resp.ok) {
        window.dispatchEvent(new CustomEvent('auth:tokenRefreshFailed', { detail: { status: resp.status } }));
        this.consecutiveFailures++;
        if (resp.status === 401 && this.consecutiveFailures >= AuthTokenManager.MAX_CONSECUTIVE_FAILURES) {
          // Clear invalid tokens to stop loops
          try { localStorage.removeItem('auth_tokens'); } catch {}
          this.clear();
          window.dispatchEvent(new CustomEvent('auth:tokensCleared', { detail: { reason: 'refresh-unauthorized' } }));
        }
        return { ok: false, error: 'refresh-failed' };
      }
      const data = await resp.json().catch(() => ({}));
      if (!data.access_token) {
        window.dispatchEvent(new CustomEvent('auth:tokenRefreshFailed', { detail: { reason: 'no-access-token' } }));
        return { ok: false, error: 'invalid-response' };
      }
      this.writeTokens({ ...tokens, ...data });
      window.dispatchEvent(new CustomEvent('auth:tokenRefreshed'));
      // Re-schedule
      this.scheduling = false;
      this.ensureSchedule();
      this.consecutiveFailures = 0;
      return { ok: true, refreshed: true };
    } catch (e:any) {
      window.dispatchEvent(new CustomEvent('auth:tokenRefreshFailed', { detail: { error: e.message } }));
      this.consecutiveFailures++;
      if (this.consecutiveFailures >= AuthTokenManager.MAX_CONSECUTIVE_FAILURES) {
        try { localStorage.removeItem('auth_tokens'); } catch {}
        this.clear();
        window.dispatchEvent(new CustomEvent('auth:tokensCleared', { detail: { reason: 'refresh-error' } }));
      }
      return { ok: false, error: e.message };
    }
  }
}

export default AuthTokenManager;