import React, { useEffect, useState } from 'react';

interface Entry { url: string; count: number }

/**
 * Displays detailed suppression diagnostics (per-endpoint) for unauthenticated noisy requests.
 * Intended for development / troubleshooting. Hidden behind a toggle.
 */
const SuppressionDebugPanel: React.FC<{ onClose?: () => void }> = ({ onClose }) => {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [backoffUntil, setBackoffUntil] = useState<number | null>(null);

  const load = () => {
    try {
      const raw = sessionStorage.getItem('fks.suppressed.map');
      const map = raw ? JSON.parse(raw) : {};
      const arr: Entry[] = Object.keys(map).sort().map(k => ({ url: k, count: map[k] }));
      setEntries(arr);
      const bo = parseInt(sessionStorage.getItem('fks.noisy.backoff.global') || '0', 10);
      setBackoffUntil(isFinite(bo) && bo > Date.now() ? bo : null);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    load();
    const handler = () => load();
    window.addEventListener('auth:suppressedRequest', handler as any);
    window.addEventListener('auth:authenticated', handler as any);
    return () => {
      window.removeEventListener('auth:suppressedRequest', handler as any);
      window.removeEventListener('auth:authenticated', handler as any);
    };
  }, []);

  return (
    <div className="mt-4 border border-amber-400/40 bg-amber-500/10 rounded-lg p-4 text-[11px] text-amber-200 relative">
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-amber-300">Suppression Diagnostics</span>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="px-2 py-0.5 rounded bg-amber-400/20 hover:bg-amber-400/30 text-amber-100"
            title="Refresh"
          >↻</button>
          <button
            onClick={onClose}
            className="px-2 py-0.5 rounded bg-amber-400/20 hover:bg-amber-400/30 text-amber-100"
            title="Close"
          >✕</button>
        </div>
      </div>
      {backoffUntil && (
        <div className="mb-2 text-amber-300">Backoff active for {(Math.max(0, backoffUntil - Date.now())/1000).toFixed(0)}s</div>
      )}
      {entries.length === 0 && <div className="text-amber-300/70">No suppressions recorded this session.</div>}
      {entries.length > 0 && (
        <ul className="space-y-1 max-h-40 overflow-auto pr-1">
          {entries.map(e => (
            <li key={e.url} className="flex items-center justify-between">
              <span className="truncate mr-2" title={e.url}>{e.url}</span>
              <span className="font-mono text-amber-100">{e.count}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={() => { sessionStorage.removeItem('fks.suppressed.map'); sessionStorage.removeItem('fks.suppressed.noauth.count'); load(); }}
          className="px-2 py-0.5 rounded bg-red-500/30 hover:bg-red-500/40 text-red-100 border border-red-500/40"
        >Clear</button>
        <button
          onClick={() => { try { navigator.clipboard.writeText(JSON.stringify(entries)); } catch {} }}
          className="px-2 py-0.5 rounded bg-amber-400/20 hover:bg-amber-400/30 text-amber-100 border border-amber-400/40"
        >Copy JSON</button>
      </div>
    </div>
  );
};

export default SuppressionDebugPanel;
