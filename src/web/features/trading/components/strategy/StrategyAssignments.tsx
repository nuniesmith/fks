// Moved from components/Trading/StrategyAssignments.tsx into feature slice
import { Check, Save, AlertTriangle } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';

import { useTradingEnv } from '@/context/TradingEnvContext';
import useSecurity from '@/hooks/useSecurity';
import { listActiveAssets, type ActiveAsset } from '@/services/ActiveAssetsApi';
import { listStrategies, saveAssignments, getAssignments, type StrategySummary } from '@/services/StrategiesApi';

const LOCAL_KEY = 'fks.asset.strategy.assignments';

export default function StrategyAssignments() {
  const [assets, setAssets] = useState<ActiveAsset[]>([]);
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [map, setMap] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const { refresh } = useTradingEnv();

  const [security] = useSecurity();
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const local = (() => { try { return JSON.parse(localStorage.getItem(LOCAL_KEY) || '{}'); } catch { return {}; } })();
      // Defer remote fetches until authenticated to avoid 401 loops
      const authed = security.authenticated && !!localStorage.getItem('auth_tokens');
      if (!authed) {
        setAssets([]); setStrategies([]); setMap(local);
        return;
      }
      try {
        const [a, s, serverAssignments] = await Promise.all([
          listActiveAssets().catch(() => ({ items: [], count: 0 })),
          listStrategies().catch(() => []),
          getAssignments().catch(() => ({})),
        ]);
        if (cancelled) return;
        setAssets(a.items || []);
        setStrategies(s);
        const merged: Record<string, string[]> = { ...serverAssignments, ...local };
        setMap(merged);
      } catch {
        if (!cancelled) { setAssets([]); setStrategies([]); setMap(local); }
      }
    })();
    return () => { cancelled = true };
  }, [security.authenticated]);

  const toggle = (assetId: number, strategyId: string) => {
    setMap(prev => {
      const key = String(assetId);
      const cur = new Set(prev[key] || []);
      if (cur.has(strategyId)) cur.delete(strategyId); else cur.add(strategyId);
      return { ...prev, [key]: Array.from(cur) };
    });
    setStatus('idle');
  };

  async function save() {
    setLoading(true); setStatus('saving');
    try {
      localStorage.setItem(LOCAL_KEY, JSON.stringify(map));
      await saveAssignments(map).catch(() => false);
      setStatus('saved');
      await refresh();
      setTimeout(() => setStatus('idle'), 2000);
    } catch {
      setStatus('error');
    } finally { setLoading(false); }
  }

  const assignedCount = useMemo(() => Object.values(map).reduce((a, arr) => a + (arr?.length || 0), 0), [map]);

  return (
    <div className="glass-card p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold text-white">Strategy Assignments</h3>
        <div className="flex items-center gap-2 text-sm">
          <div className="text-white/70">Assigned:</div>
          <div className="px-2 py-0.5 rounded bg-white/10 text-white">{assignedCount}</div>
          <button onClick={save} disabled={loading} className="ml-2 px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1 disabled:opacity-50">
            <Save className="w-4 h-4"/> Save
          </button>
          {status==='saved' && <span className="text-green-400 flex items-center gap-1"><Check className="w-4 h-4"/> Saved</span>}
          {status==='error' && <span className="text-red-400 flex items-center gap-1"><AlertTriangle className="w-4 h-4"/> Error</span>}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-white/80">
              <th className="py-2 pr-4">Asset</th>
              <th className="py-2 pr-4">Source</th>
              <th className="py-2 pr-4">Intervals</th>
              <th className="py-2 pr-4">Strategies</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {assets.map(a => (
              <tr key={a.id} className="text-white">
                <td className="py-2 pr-4 font-mono">{a.symbol}{a.exchange ? ` · ${a.exchange}` : ''}</td>
                <td className="py-2 pr-4">{a.source}{a.asset_type ? ` · ${a.asset_type}` : ''}</td>
                <td className="py-2 pr-4">{(a.intervals||[]).join(', ')}</td>
                <td className="py-2 pr-4">
                  <div className="flex flex-wrap gap-2">
                    {strategies.length === 0 ? (
                      <span className="text-white/60 text-xs">No strategies available</span>
                    ) : strategies.map(s => {
                      const checked = (map[String(a.id)] || []).includes(s.id);
                      return (
                        <label key={s.id} className={`px-2 py-1 rounded border text-xs cursor-pointer ${checked ? 'bg-blue-600/30 border-blue-500/50' : 'bg-white/5 border-white/10'}`}>
                          <input type="checkbox" className="mr-1 align-middle" checked={checked} onChange={() => toggle(a.id, s.id)} />
                          {s.name}
                        </label>
                      );
                    })}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {assets.length === 0 && (
        <div className="mt-3 text-white/70 text-sm">No active assets yet. Add assets in the Data → Active Assets section.</div>
      )}
    </div>
  );
}
