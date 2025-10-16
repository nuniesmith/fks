import React, { useEffect, useState } from 'react';

/** Displays count of suppressed unauthenticated API probes (openapi / active-assets etc.) with backoff awareness */
const SuppressedProbeBadge: React.FC = () => {
  const [count, setCount] = useState<number>(() => {
    try { return parseInt(sessionStorage.getItem('fks.suppressed.noauth.count') || '0', 10); } catch { return 0; }
  });
  const [backoffMs, setBackoffMs] = useState<number>(0);
  const [reason, setReason] = useState<string>('');

  useEffect(() => {
    const onSuppressed = (e: any) => {
      if (typeof e.detail?.count === 'number') setCount(e.detail.count);
      if (e.detail?.reason === 'backoff-set') {
        setReason('backoff');
        if (typeof e.detail.windowMs === 'number') setBackoffMs(e.detail.windowMs);
      } else if (e.detail?.reason === 'backoff') {
        setReason('backoff');
      } else if (e.detail?.reason) {
        setReason(e.detail.reason);
      }
    };
    const onTokensCleared = () => {
      // Keep count (historical) but clear active backoff indicator
      setBackoffMs(0); setReason('');
    };
    const onAuthSuccessPoll = () => {
      // On authenticated transition, freeze final count then hide after short delay
      setReason('resolved');
      const hide = setTimeout(() => { setCount(0); setBackoffMs(0); setReason(''); }, 3000);
      return () => clearTimeout(hide);
    };
    window.addEventListener('auth:suppressedRequest', onSuppressed as any);
    window.addEventListener('auth:tokensCleared', onTokensCleared as any);
    // Heuristic: watch storage for auth_tokens presence & user object
    const interval = setInterval(() => {
      try {
        const tokens = localStorage.getItem('auth_tokens');
        const user = localStorage.getItem('auth_user');
        if (tokens && user) {
          onAuthSuccessPoll();
          clearInterval(interval);
        }
      } catch { /* ignore */ }
    }, 1500);
    return () => {
      window.removeEventListener('auth:suppressedRequest', onSuppressed as any);
      window.removeEventListener('auth:tokensCleared', onTokensCleared as any);
      clearInterval(interval);
    };
  }, []);

  if (count === 0) return null;

  const label = reason === 'backoff' ? `${count} suppressed (backoff)` : reason === 'resolved' ? `${count} suppressed (resolved)` : `${count} suppressed`;
  const title = reason === 'backoff'
    ? `Temporary backoff active for noisy unauthenticated endpoints. Window ≈ ${Math.round(backoffMs/1000)}s.`
    : 'Suppressed unauthenticated API probes prevented from hitting backend';

  return (
    <div
      className="absolute top-2 right-2 text-[10px] px-2 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/40 backdrop-blur-sm"
      title={title}
    >
      {label}
    </div>
  );
};

export default SuppressedProbeBadge;
