import React, { useEffect, useState } from 'react'
import { config } from '../services/config'
import useSecurity from '../hooks/useSecurity'
import { buildAuthHeaders } from '../services/authToken'

/** Displays current environment & API base (normalized) with connectivity probe. */
export const EnvironmentBadge: React.FC = () => {
  const [latency, setLatency] = useState<number | null>(null)
  const [status, setStatus] = useState<'ok' | 'warn' | 'err' | 'pending'>('pending')

  const [security] = useSecurity();

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      try {
        if (!security.ready) { setStatus('pending'); return; }
        // Avoid unauthenticated 401 noise; only probe if we have tokens
        const hasToken = typeof localStorage !== 'undefined' && !!localStorage.getItem('auth_tokens');
        if (!hasToken) { setStatus('pending'); return; }
        const start = performance.now();
        const res = await fetch(`${config.apiBaseUrl.replace(/\/$/, '')}/openapi.json`, { method: 'GET', headers: buildAuthHeaders() });
        const ms = performance.now() - start;
        if (cancelled) return;
        setLatency(ms);
        if (res.ok) setStatus(ms > 1200 ? 'warn' : 'ok');
        else if (res.status === 401) {
          // Treat as pending rather than error to prevent red badge pre-login
          setStatus('pending');
        } else setStatus('err');
      } catch {
        if (!cancelled) { setLatency(null); setStatus('err'); }
      }
    };
    run()
    const id = setInterval(run, 30000)
    return () => { cancelled = true; clearInterval(id) }
  }, [security.ready])

  const color = status === 'ok' ? 'bg-green-500/20 text-green-300 border-green-500/40' : status === 'warn' ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40' : status === 'pending' ? 'bg-white/10 text-white/60 border-white/20' : 'bg-red-500/20 text-red-300 border-red-500/40'

  return (
    <div className={`hidden md:flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-mono ${color}`}
         title={`API: ${config.apiBaseUrl}`}> 
      <span>{config.envName}</span>
      <span className="opacity-50">|</span>
      <span>{latency != null ? `${Math.round(latency)}ms` : '—'}</span>
    </div>
  )
}

export default EnvironmentBadge