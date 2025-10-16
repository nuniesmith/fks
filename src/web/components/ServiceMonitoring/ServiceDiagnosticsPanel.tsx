import { RefreshCw, Activity, Trash2 } from 'lucide-react';
import React from 'react';

import { useServiceDiagnostics } from '../../hooks/useServiceDiagnostics';

import { useSingleService } from './ServiceHealthProvider';

interface Props { serviceId: string; className?: string; }

const ServiceDiagnosticsPanel: React.FC<Props> = ({ serviceId, className }) => {
  const svc = useSingleService(serviceId);
  const { endpoint, results, runTest, clear, average, last5Avg, prev5Avg, trendDelta5 } = useServiceDiagnostics(serviceId);
  return (
    <div className={`glass-card p-5 space-y-4 ${className || ''}`}>      
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-semibold text-white text-lg flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" /> Diagnostics: {serviceId}
          </h3>
          <div className="text-xs text-white/60">{endpoint?.url || 'No endpoint registered'}</div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={runTest} disabled={!endpoint} className="btn-secondary text-xs px-3 py-1 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Test Endpoint
          </button>
          <button onClick={clear} className="btn-secondary text-xs px-3 py-1 flex items-center gap-1">
            <Trash2 className="w-3 h-3" /> Clear
          </button>
        </div>
      </div>
      <div className="grid sm:grid-cols-4 gap-4 text-sm">
        <Metric label="Status" value={svc ? svc.status : '—'} />
        <Metric label="Latest Latency" value={svc?.responseTime != null ? svc.responseTime + ' ms' : '—'} />
        <Metric label="Avg Observed" value={svc?.latencyHistory?.length ? Math.round(svc.latencyHistory.reduce((a,b)=>a+b,0)/svc.latencyHistory.length)+' ms' : '—'} />
        <Metric label="Diag Avg (all)" value={average ? average.toFixed(0)+' ms' : '—'} />
        <Metric label="Diag Last5" value={last5Avg ? last5Avg.toFixed(0)+' ms' : '—'} />
        <Metric label="Diag Prev5" value={prev5Avg ? prev5Avg.toFixed(0)+' ms' : '—'} />
        <Metric label="Trend Δ5" value={prev5Avg ? (trendDelta5>0?'+':'')+trendDelta5.toFixed(0)+' ms' : '—'} highlight={trendDelta5>0? 'text-red-300': trendDelta5<0? 'text-green-300': ''} />
        <Metric label="Samples" value={(results.length)+' diag / '+(svc?.latencyHistory?.length||0)+' obs'} />
      </div>
      <div className="h-12 flex items-end gap-[2px]">
        {svc?.latencyHistory?.map((v,i,arr)=>{ const max=Math.max(...arr); const h=max?Math.max(2,(v/max)*48):2; return <div key={i} className={`flex-1 bg-white/20 ${i===arr.length-1?'bg-blue-400':''} rounded-sm`} style={{height:h}} title={v+'ms'} />; })}
      </div>
      <div className="text-xs text-white/50">Observed latency history</div>
      <div className="overflow-auto max-h-60 border border-white/10 rounded">
        <table className="w-full text-xs">
          <thead className="bg-white/5 sticky top-0">
            <tr className="text-left text-white/60">
              <th className="py-1 px-2">Time</th>
              <th className="py-1 px-2">Dur</th>
              <th className="py-1 px-2">OK</th>
              <th className="py-1 px-2">Code</th>
              <th className="py-1 px-2">Size</th>
              <th className="py-1 px-2">Error</th>
            </tr>
          </thead>
          <tbody>
            {results.slice().reverse().map((r,i)=>(
              <tr key={i} className="border-t border-white/5 hover:bg-white/5">
                <td className="py-1 px-2 font-mono">{new Date(r.timestamp).toLocaleTimeString()}</td>
                <td className="py-1 px-2">{r.duration}ms</td>
                <td className="py-1 px-2">{r.ok? '✔️':'❌'}</td>
                <td className="py-1 px-2">{r.statusCode||'—'}</td>
                <td className="py-1 px-2">{r.size!=null? r.size: '—'}</td>
                <td className="py-1 px-2 max-w-[160px] truncate" title={r.error}>{r.error || ''}</td>
              </tr>
            ))}
            {!results.length && <tr><td colSpan={6} className="py-4 text-center text-white/40">No diagnostics yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const Metric: React.FC<{label:string; value: React.ReactNode; highlight?: string}> = ({label,value,highlight}) => (
  <div className="space-y-1">
    <div className="text-xs uppercase tracking-wide text-white/50">{label}</div>
    <div className={`text-sm font-medium text-white ${highlight||''}`}>{value}</div>
  </div>
);

export default ServiceDiagnosticsPanel;
