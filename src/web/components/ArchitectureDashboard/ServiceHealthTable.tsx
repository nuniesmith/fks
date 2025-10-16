import { RefreshCw, ArrowUpDown } from 'lucide-react';
import React from 'react';

import { useServiceMonitoring } from '../../hooks/useServiceMonitoring';

import type { ServiceStatus } from '../../hooks/useServiceMonitoring';

interface Column {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (s: ServiceStatus) => React.ReactNode;
}

const columns: Column[] = [
  { key: 'name', label: 'Service', sortable: true },
  { key: 'status', label: 'Status', sortable: true, render: (s) => <span className={`px-2 py-0.5 rounded text-xs capitalize bg-white/10`}>{s.status}</span> },
  { key: 'responseTime', label: 'Latency', sortable: true, render: s => {
      const latestVal = s.responseTime;
      const latest = latestVal ? `${latestVal} ms` : '—';
      const avgNum = s.latencyHistory && s.latencyHistory.length > 1 ? (s.latencyHistory.reduce((a,b)=>a+b,0)/s.latencyHistory.length) : undefined;
      const avg = avgNum ? avgNum.toFixed(0)+' ms avg' : '';
      const prev = s.latencyHistory && s.latencyHistory.length > 1 ? s.latencyHistory[s.latencyHistory.length-2] : undefined;
      const delta = prev != null && latestVal != null ? latestVal - prev : undefined;
      // Trend last 5 vs previous 5 if we have >=10 samples
      let trend: number | undefined;
      if (s.latencyHistory && s.latencyHistory.length >= 10) {
        const last5 = s.latencyHistory.slice(-5);
        const prev5 = s.latencyHistory.slice(-10, -5);
        const avgA = last5.reduce((a,b)=>a+b,0)/5;
        const avgB = prev5.reduce((a,b)=>a+b,0)/5;
        trend = avgA - avgB; // positive => slower
      }
      const deltaEl = delta != null && delta !== 0 ? (
        <span className={`text-[10px] px-1 rounded ${delta > 0 ? 'text-amber-300' : 'text-green-300'}`}>{delta>0?'+':''}{delta}ms</span>
      ) : null;
      const trendEl = trend != null && Math.abs(trend) > 1 ? (
        <span className={`text-[10px] px-1 rounded ${trend > 0 ? 'text-red-300' : 'text-green-400'}`}>{trend>0?'+':''}{trend.toFixed(0)}ms/5</span>
      ) : null;
      return <div className="flex items-center gap-2">
        <span>{latest}</span>
        {deltaEl}
        {trendEl}
        {avg && <span className="text-xs text-white/40">{avg}</span>}
      </div>;
    } },
  { key: 'uptime', label: 'Uptime', sortable: true, render: s => s.uptime ? (s.uptime*100).toFixed(2)+ '%' : '—' },
  { key: 'port', label: 'Port', sortable: true, render: s => s.port || '—' },
  { key: 'lastCheck', label: 'Last Check', render: s => s.lastCheck.toLocaleTimeString() }
];

export const ServiceHealthTable: React.FC = () => {
  const { services, isLoading, refreshServices } = useServiceMonitoring();
  const [sortKey, setSortKey] = React.useState<string>('name');
  const [asc, setAsc] = React.useState<boolean>(true);
  const [auto, setAuto] = React.useState(true);
  const autoRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (auto) {
      if (autoRef.current) {
        clearInterval(autoRef.current);
      }
      autoRef.current = window.setInterval(() => refreshServices(), 30000);
    } else if (autoRef.current) {
      clearInterval(autoRef.current);
      autoRef.current = null;
    }
    return () => {
      if (autoRef.current) {
        clearInterval(autoRef.current);
      }
    };
  }, [auto, refreshServices]);

  const exportCsv = () => {
    const headers = ['id','name','status','latency','uptime'];
    const rows = services.map(s => [s.id, s.name, s.status, s.responseTime ?? '', s.uptime ?? '']);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'service-health.csv'; a.click(); URL.revokeObjectURL(url);
  };
  const sorted = React.useMemo(() => {
    const copy = [...services];
    copy.sort((a, b) => {
      const av = (a as any)[sortKey];
      const bv = (b as any)[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return asc ? av - bv : bv - av;
      return asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [services, sortKey, asc]);

  const toggleSort = (key: string) => {
    if (sortKey === key) setAsc(!asc); else { setSortKey(key); setAsc(true); }
  };

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
        <h3 className="font-semibold">Service Health</h3>
        <div className="flex items-center gap-2">
          <button onClick={refreshServices} disabled={isLoading} className="btn-secondary flex items-center gap-1 text-xs px-2 py-1">
            <RefreshCw className={`w-3 h-3 ${isLoading? 'animate-spin':''}`} /> {isLoading? 'Checking':'Refresh'}
          </button>
          <button onClick={exportCsv} className="btn-secondary text-xs px-2 py-1">Export CSV</button>
          <label className="flex items-center gap-1 text-xs cursor-pointer select-none">
            <input type="checkbox" checked={auto} onChange={e=>setAuto(e.target.checked)} className="accent-blue-500" /> Auto 30s
          </label>
        </div>
      </div>
      <div className="overflow-x-auto">
  <table className="w-full text-sm">
          <thead className="text-left text-white/70">
            <tr>
              {columns.map(c => (
                <th key={c.key} className="py-2 pr-4 font-medium">
                  <button
                    disabled={!c.sortable}
                    onClick={() => c.sortable && toggleSort(c.key)}
                    className={`flex items-center gap-1 ${c.sortable? 'hover:text-white':''}`}
                  >
                    {c.label}
                    {c.sortable && sortKey === c.key && <ArrowUpDown className={`w-3 h-3 ${asc? 'rotate-180':''}`} />}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
              {sorted.map(s => (
                <tr key={s.id} className="border-t border-white/10 hover:bg-white/5">
                  {columns.map(c => (
                    <td key={c.key} className="py-2 pr-4 align-top">
                      {c.render ? c.render(s) : (s as any)[c.key] ?? '—'}
                      {c.key === 'responseTime' && s.latencyHistory && s.latencyHistory.length > 1 && (
                        <div className="mt-1 h-5 flex items-end gap-[1px]">
                          {s.latencyHistory.map((v,i) => {
                            const max = Math.max(...s.latencyHistory!);
                            const h = max ? Math.max(2, Math.round((v/max)*16)) : 2;
                            const color = i === s.latencyHistory!.length-1 ? 'bg-blue-400' : 'bg-white/30';
                            return <div key={i} className={`${color} w-[3px] rounded-sm`} style={{height: h}} />;
                          })}
                        </div>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            {sorted.length === 0 && (
              <tr><td colSpan={columns.length} className="py-6 text-center text-white/40">No services</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ServiceHealthTable;
