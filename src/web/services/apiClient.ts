import axios from 'axios';

import { config } from './config';
import AuthentikService from './security/AuthentikService';

export const api = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: Number(import.meta.env.VITE_API_TIMEOUT || 30000),
});

api.interceptors.request.use((req) => {
  try {
    const lsToken = typeof window !== 'undefined' ? localStorage.getItem('fks_api_token') : null;
    const envToken = (import.meta as any).env?.VITE_API_TOKEN as string | undefined;
    // Prefer Authentik access_token if available
    const authTokensRaw = typeof window !== 'undefined' ? localStorage.getItem('auth_tokens') : null;
    const authAccess = authTokensRaw ? (JSON.parse(authTokensRaw)?.access_token as string | undefined) : undefined;
    const token = authAccess || lsToken || envToken;
    if (token) {
      if ((req.headers as any)?.set) {
        (req.headers as any).set('Authorization', `Bearer ${token}`);
        (req.headers as any).set('X-API-Key', token);
      } else {
        (req.headers as any) = { ...(req.headers as any), Authorization: `Bearer ${token}`, 'X-API-Key': token };
      }
    }
  } catch {}
  return req;
});

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const status = err?.response?.status;
    const original = err?.config;
    // On 401 try to refresh Authentik token once
    if (status === 401 && !original?._retry) {
      try {
        const tokensRaw = typeof window !== 'undefined' ? localStorage.getItem('auth_tokens') : null;
        if (tokensRaw) {
          const tokens = JSON.parse(tokensRaw);
          const refresh = tokens?.refresh_token as string | undefined;
          if (refresh) {
            const ak = AuthentikService.getInstance();
            const newTokens = await ak.refreshToken(refresh);
            localStorage.setItem('auth_tokens', JSON.stringify(newTokens));
            // Retry original request with new token
            original._retry = true;
            original.headers = original.headers || {};
            original.headers['Authorization'] = `Bearer ${newTokens.access_token}`;
            original.headers['X-API-Key'] = newTokens.access_token;
            return api(original);
          }
        }
      } catch (e) {
        // fallthrough to reject
      }
    }
    return Promise.reject(err);
  }
);

export default api;
