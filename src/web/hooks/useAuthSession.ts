import { useEffect, useState } from 'react';

interface SessionInfo {
  accessToken?: string;
  expiresAt?: number; // ms epoch
  remainingSec: number;
  valid: boolean;
  hasRefresh: boolean;
  refreshing: boolean;
}

function decodeJwt(token: string): any | null {
  try {
    const [, payload] = token.split('.');
    if (!payload) return null;
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch { return null; }
}

export function useAuthSession(pollMs: number = 1000): SessionInfo {
  const [info, setInfo] = useState<SessionInfo>({ remainingSec: 0, valid: false, hasRefresh: false, refreshing: false });

  useEffect(() => {
    let cancelled = false;
    const update = () => {
      try {
        const raw = localStorage.getItem('auth_tokens');
        if (!raw) { if (!cancelled) setInfo({ remainingSec: 0, valid: false, hasRefresh: false, refreshing: false }); return; }
        const parsed = JSON.parse(raw);
        const access: string | undefined = parsed.access_token;
        let exp: number | undefined;
        const jwt = access && decodeJwt(access);
        if (jwt?.exp) exp = jwt.exp * 1000;
        else if (parsed.expires_in && parsed.obtained_at) exp = parsed.obtained_at + parsed.expires_in * 1000;
        const now = Date.now();
        const remainingSec = exp ? Math.max(0, Math.floor((exp - now) / 1000)) : 0;
        if (!cancelled) setInfo({ accessToken: access, expiresAt: exp, remainingSec, valid: !!access && remainingSec > 0, hasRefresh: !!parsed.refresh_token, refreshing: info.refreshing });
      } catch { /* ignore */ }
    };
    update();
    const id = setInterval(update, pollMs);
    const onRefStart = () => { setInfo(prev => ({ ...prev, refreshing: true })); };
    const onRefDone = () => { setInfo(prev => ({ ...prev, refreshing: false })); update(); };
    window.addEventListener('auth:tokenRefreshing', onRefStart as any);
    window.addEventListener('auth:tokenRefreshed', onRefDone as any);
    window.addEventListener('auth:tokenRefreshFailed', onRefDone as any);
    return () => { cancelled = true; clearInterval(id); window.removeEventListener('auth:tokenRefreshing', onRefStart as any); window.removeEventListener('auth:tokenRefreshed', onRefDone as any); window.removeEventListener('auth:tokenRefreshFailed', onRefDone as any); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return info;
}

export default useAuthSession;