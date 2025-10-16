import React, { useEffect, useState } from 'react';

import { usePrometheus } from '../../shared/hooks/usePrometheusMetrics';

interface SpecState { service: string; spec: string; status: string; latencyMs?: number; updatedAt: number; }

export const ContractAggregateDashboard: React.FC<{ services: string[] }> = ({ services }) => {
  const [rows, setRows] = useState<SpecState[]>([]);
  let prometheus: ReturnType<typeof usePrometheus> | null = null; try { prometheus = usePrometheus(); } catch {}

  useEffect(() => {
    const refresh = () => {
      const all: SpecState[] = [];
      services.forEach(svc => {
        try {
          const raw = localStorage.getItem(`fks_contract-${svc}`);
          if (!raw) return; const parsed = JSON.parse(raw);
          const latest: Record<string, any> = {};
          (parsed.results || []).forEach((r: any) => { latest[r.id] = r; });
          Object.values(latest).forEach((r: any) => {
            all.push({ service: svc, spec: r.id, status: r.status, latencyMs: r.latencyMs, updatedAt: r.timestamp });
            if (prometheus && r.latencyMs != null) {
              prometheus.observe('fks_contract_latency_aggregate_ms', r.latencyMs, { service: svc, spec: r.id, status: r.status });
            }
          });
        } catch {}
      });
      setRows(all);
    };
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [services]);

  const counts = rows.reduce<Record<string, number>>((acc, r) => { acc[r.status] = (acc[r.status]||0)+1; return acc; }, {});

  return (
    <div className="glass-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white/90">Contract Aggregate</h3>
        <div className="flex gap-3 text-[11px]">
          {['pass','fail','error','skip'].map(k => <div key={k} className="flex items-center gap-1"><span className="font-mono">{counts[k]||0}</span><span className="uppercase text-white/40">{k}</span></div>)}
          <div className="text-white/40">Specs {rows.length}</div>
        </div>
      </div>
      <div className="overflow-auto max-h-72 border border-white/5 rounded">
        <table className="min-w-full text-[11px]">
          <thead className="bg-white/5 text-white/60">
            <tr>
              <th className="text-left px-2 py-1">Service</th>
              <th className="text-left px-2 py-1">Spec</th>
              <th className="text-left px-2 py-1">Status</th>
              <th className="text-left px-2 py-1">Latency</th>
              <th className="text-left px-2 py-1">Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.sort((a,b)=>a.service.localeCompare(b.service)||a.spec.localeCompare(b.spec)).map(r => (
              <tr key={r.service+':'+r.spec} className="border-t border-white/5">
                <td className="px-2 py-1 text-white/70 font-mono">{r.service}</td>
                <td className="px-2 py-1 text-white/80">{r.spec}</td>
                <td className={`px-2 py-1 font-mono ${r.status==='pass'?'text-emerald-400':r.status==='fail'?'text-rose-400':r.status==='error'?'text-amber-400':'text-slate-400'}`}>{r.status}</td>
                <td className="px-2 py-1 font-mono text-white/60">{r.latencyMs!=null?Math.round(r.latencyMs)+'ms':'—'}</td>
                <td className="px-2 py-1 text-white/40">{((Date.now()-r.updatedAt)/1000).toFixed(0)}s ago</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ContractAggregateDashboard;
