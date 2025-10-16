import React, { createContext, useContext, useEffect } from 'react';

import useSecurity from '../hooks/useSecurity';

import type { ReactNode} from 'react';

interface SecurityContextType {
  // Security state
  initialized: boolean;
  vpnConnected: boolean;
  authenticated: boolean;
  user: any | null;
  loading: boolean;
  error: string | null;
  securityLevel: 'secure' | 'warning' | 'critical';
  
  // Security actions
  initializeSecurity: () => Promise<void>;
  login: (preferPasskey?: boolean, provider?: 'rust' | 'google') => Promise<string | void>;
  completeLogin: (code: string, state: string, provider?: 'rust' | 'google') => Promise<any>;
  logout: () => Promise<void>;
  registerPasskey: (deviceName?: string) => Promise<any>;
  validateSecurity: () => Promise<void>;
  getSecurityDashboard: () => any;
}

const SecurityContext = createContext<SecurityContextType | undefined>(undefined);

interface SecurityProviderProps {
  children: ReactNode;
  enforceVPN?: boolean;
  requirePasskeys?: boolean;
}

export function SecurityProvider({
  children,
  enforceVPN = true,
  requirePasskeys = false
}: SecurityProviderProps) {
  const [securityState, securityActions] = useSecurity();

  // Persist runtime override for VPN enforcement so lower-level services can honor it
  useEffect(() => {
    try {
      localStorage.setItem('security.enforceVPN', enforceVPN ? 'true' : 'false');
    } catch {
      // ignore storage errors in restricted environments
    }
  }, [enforceVPN]);

  // Auto-redirect to login if not authenticated
  useEffect(() => {
    if (securityState.initialized && !securityState.authenticated && !securityState.loading) {
      const currentPath = window.location.pathname;
      
      // Don't redirect if already on auth pages
      if (!currentPath.includes('/auth') && !currentPath.includes('/login')) {
        console.log('User not authenticated, security enforcement required');
        try {
          const disableAuto = localStorage.getItem('fks.disable.auto_login_redirect') === 'true' || (import.meta as any).env?.VITE_DISABLE_AUTO_LOGIN_REDIRECT === 'true';
          if (!disableAuto) {
            const ret = encodeURIComponent(window.location.pathname + window.location.search + window.location.hash);
            window.location.replace(`/login?returnTo=${ret}`);
          }
        } catch {
          // fallback
          const ret = encodeURIComponent(window.location.pathname + window.location.search + window.location.hash);
          window.location.replace(`/login?returnTo=${ret}`);
        }
      }
    }
  }, [securityState.initialized, securityState.authenticated, securityState.loading]);

  // Emit a global event when authentication becomes true (one-time per session)
  useEffect(() => {
    try {
      if (securityState.authenticated) {
        const already = sessionStorage.getItem('fks.emitted.authenticated');
        if (!already) {
          sessionStorage.setItem('fks.emitted.authenticated', '1');
          window.dispatchEvent(new CustomEvent('auth:authenticated', { detail: { user: securityState.user } }));
        }
      } else if (!securityState.authenticated) {
        sessionStorage.removeItem('fks.emitted.authenticated');
      }
    } catch { /* ignore */ }
  }, [securityState.authenticated, securityState.user]);

  // Show VPN warning if not connected and enforced
  useEffect(() => {
    if (enforceVPN && securityState.initialized && !securityState.vpnConnected) {
      console.warn('VPN connection required but not detected');
      
      // You could show a modal or notification here
      const notification = document.createElement('div');
      notification.innerHTML = `
        <div style="position: fixed; top: 0; left: 0; right: 0; background: #dc2626; color: white; padding: 1rem; text-align: center; z-index: 9999;">
          <strong>Security Warning:</strong> VPN connection required. Please connect to Tailscale.
        </div>
      `;
      document.body.appendChild(notification);
      
      // Auto-remove after 10 seconds
      setTimeout(() => {
        if (document.body.contains(notification)) {
          document.body.removeChild(notification);
        }
      }, 10000);
    }
  }, [enforceVPN, securityState.initialized, securityState.vpnConnected]);

  // Show passkey registration prompt if required
  useEffect(() => {
    if (requirePasskeys && securityState.authenticated && securityState.user) {
      // Check if user has passkeys registered
      // This would require additional API call to check user's passkeys
      console.log('Passkey registration may be required');
    }
  }, [requirePasskeys, securityState.authenticated, securityState.user]);

  // Listen for auth/token related browser events and surface as notifications (if provider present)
  useEffect(() => {
    const tryNotify = (title: string, message: string, type: any = 'warning') => {
      try {
        // Lazy access to NotificationContext to avoid circular import
        const anyWindow = window as any;
        // If a global helper was attached elsewhere you could use it; here we fall back to console
        // You can wire a bridge by setting window.fksNotify = (t,m,tp)=>...
        if (typeof anyWindow.fksNotify === 'function') {
          anyWindow.fksNotify({ title, message, type });
        } else {
          console.info(`[SecurityNotice] ${title}: ${message}`);
        }
      } catch { /* ignore */ }
    };

    const onRefreshed = () => tryNotify('Session Refreshed', 'Access token renewed', 'success');
    const onRefreshFailed = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      tryNotify('Token Refresh Failed', `Reason: ${detail.status || detail.reason || detail.error || 'unknown'}`, 'warning');
    };
    const onTokensCleared = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      tryNotify('Session Cleared', `Tokens removed (${detail.reason || 'security policy'})`, 'warning');
    };
    const onExcessive401 = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      tryNotify('Repeated Unauthorized', `Multiple 401 responses for ${detail.url || 'requests'}`, 'warning');
    };

    window.addEventListener('auth:tokenRefreshed', onRefreshed as any);
    window.addEventListener('auth:tokenRefreshFailed', onRefreshFailed as any);
    window.addEventListener('auth:tokensCleared', onTokensCleared as any);
    window.addEventListener('auth:excessive401', onExcessive401 as any);
    return () => {
      window.removeEventListener('auth:tokenRefreshed', onRefreshed as any);
      window.removeEventListener('auth:tokenRefreshFailed', onRefreshFailed as any);
      window.removeEventListener('auth:tokensCleared', onTokensCleared as any);
      window.removeEventListener('auth:excessive401', onExcessive401 as any);
    };
  }, []);

  const contextValue: SecurityContextType = {
    ...securityState,
    ...securityActions
  };

  return <SecurityContext.Provider value={contextValue}>{children}</SecurityContext.Provider>;
}

export const useSecurityContext = (): SecurityContextType => {
  const context = useContext(SecurityContext);
  if (context === undefined) {
    throw new Error('useSecurityContext must be used within a SecurityProvider');
  }
  return context;
};

export default SecurityContext;
