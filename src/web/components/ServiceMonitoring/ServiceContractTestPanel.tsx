import React from 'react';

import { useNotifications } from '../NotificationSystem';
import { useServiceContractTests } from '../../hooks/useServiceContractTests';

import LatencyBudgetEditor from './LatencyBudgetEditor';

import type { ContractTestSpec } from '../../hooks/useServiceContractTests';



interface Props {
  serviceId: string;
  baseUrl: string;
  specs: ContractTestSpec[];
}

const statusColor: Record<string, string> = {
  pass: 'text-emerald-400',
  fail: 'text-rose-400',
  error: 'text-amber-400',
  skip: 'text-slate-400'
};

const ServiceContractTestPanel: React.FC<Props> = ({ serviceId, baseUrl, specs }) => {
  const { addNotification } = useNotifications();
  const [runtimeSpecs, setRuntimeSpecs] = React.useState(specs);
  // Ticker to update countdown timers for open circuit breakers
  const [cbTick, setCbTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setCbTick(t => t+1), 1000);
    return () => clearInterval(id);
  }, []);
  const { results, runAll, isRunning, summary, history } = useServiceContractTests(serviceId, baseUrl, runtimeSpecs, {
    onAlert: ({ spec, result, reason }) => {
      addNotification({
        type: reason === 'status-fail' ? 'error' : 'warning',
        title: `${serviceId}:${spec.id} ${reason === 'status-fail' ? 'FAILED' : 'SLA Breach'}`,
        message: `${result.message || ''} ${result.latencyMs ? '('+result.latencyMs.toFixed(0)+'ms)' : ''}`.trim(),
        duration: 6000
      });
    }
  });
  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white/90 text-sm">Contract Tests</h3>
        <button
          onClick={() => runAll({ parallel: true })}
          disabled={isRunning}
          className="px-3 py-1 text-xs rounded bg-white/10 hover:bg-white/20 transition disabled:opacity-40"
        >{isRunning ? 'Running...' : 'Run All'}</button>
        <LatencyBudgetEditor serviceId={serviceId} specs={runtimeSpecs} onUpdate={setRuntimeSpecs} />
      </div>
  <div className="grid grid-cols-8 gap-2 text-[11px]">
        {['pass','fail','error','skip'].map(k => (
          <div key={k} className="bg-white/5 rounded p-2 text-center">
            <div className={`font-mono ${statusColor[k]} font-medium`}>{summary.counts[k] || 0}</div>
            <div className="uppercase tracking-wide text-[10px] text-white/40">{k}</div>
          </div>
        ))}
        {['p50','p95','p99'].map(p => (
          <div key={p} className="bg-white/5 rounded p-2 text-center">
            <div className="font-mono text-blue-300 font-medium">{summary[p] ? Math.round(summary[p])+'ms' : '—'}</div>
            <div className="uppercase tracking-wide text-[10px] text-white/40">{p}</div>
          </div>
        ))}
        <div className="bg-white/5 rounded p-2 text-center">
          <div className="font-mono text-rose-300 font-medium" title={`Rate ${(summary.slaBreachRate*100).toFixed(1)}%`}>{summary.slaBreaches ?? 0}</div>
          <div className="uppercase tracking-wide text-[10px] text-white/40">SLA✖</div>
        </div>
        <div className="bg-white/5 rounded p-2 text-center" title="Open circuit breakers">
          <div className="font-mono text-orange-300 font-medium">{summary.openCircuits || 0}</div>
          <div className="uppercase tracking-wide text-[10px] text-white/40">CB Open</div>
        </div>
        <div className="bg-white/5 rounded p-2 text-center" title="Max failure streak across specs">
          <div className="font-mono text-fuchsia-300 font-medium">{summary.maxFailureStreak || 0}</div>
          <div className="uppercase tracking-wide text-[10px] text-white/40">Max Streak</div>
        </div>
      </div>
      <div className="overflow-x-auto max-h-56 border border-white/5 rounded">
        <table className="min-w-full text-[11px]">
          <thead className="bg-white/5 text-white/60">
            <tr>
              <th className="text-left font-medium px-2 py-1">Test</th>
              <th className="text-left font-medium px-2 py-1">Status</th>
              <th className="text-left font-medium px-2 py-1">HTTP</th>
              <th className="text-left font-medium px-2 py-1">Latency</th>
              <th className="text-left font-medium px-2 py-1">Trend</th>
              <th className="text-left font-medium px-2 py-1">Message</th>
              <th className="text-left font-medium px-2 py-1">Req</th>
            </tr>
          </thead>
          <tbody>
            {runtimeSpecs.map(spec => {
              const latest = summary.latest[spec.id];
              return (
                <tr key={spec.id} className="border-t border-white/5">
                  <td className="px-2 py-1 text-white/80 whitespace-nowrap flex items-center gap-1">
                    <span>{spec.label}</span>
                    {spec.circuitBreaker && summary.cbStates?.[spec.id] && (() => {
                      const st = summary.cbStates[spec.id];
                      let remaining: number | undefined;
                      if (st.open && st.openedAt && spec.circuitBreaker) {
                        remaining = Math.max(0, spec.circuitBreaker.cooldownMs - (Date.now() - st.openedAt));
                      }
                      return (
                        <span
                          className={`px-1 rounded text-[10px] font-mono flex items-center gap-0.5 ${st.open ? 'bg-rose-500/30 text-rose-300 border border-rose-400/30' : st.streak>0 ? 'bg-yellow-500/20 text-yellow-300 border border-yellow-400/30' : 'bg-white/10 text-white/40 border border-white/10'}`}
                          title={st.open ? `Circuit open (streak ${st.streak}) closes in ${(remaining!/1000).toFixed(0)}s` : `Failure streak ${st.streak}`}
                        >CB{st.streak}{st.open && remaining!=null && <span className="text-[9px] opacity-75">{Math.ceil(remaining/1000)}s</span>}</span>
                      );
                    })()}
                  </td>
                  <td className={`px-2 py-1 font-mono ${latest ? statusColor[latest.status] : 'text-white/40'}`}>{latest?.status || '—'}</td>
                  <td className="px-2 py-1 font-mono text-white/60">{latest?.httpStatus ?? '—'}</td>
                  <td className="px-2 py-1 font-mono text-white/60">{latest?.latencyMs ? `${latest.latencyMs.toFixed(0)}ms` : '—'}</td>
                  <td className="px-2 py-1">
                    {history[spec.id]?.length ? (
                      <div className="flex items-end h-6 gap-[1px]">
                        {history[spec.id].slice(-20).map((v,i,arr)=>{ const max=Math.max(...arr); const h=max?Math.max(2,(v/max)*20):2; return <div key={i} className={`flex-1 bg-white/15 ${i===arr.length-1?'bg-blue-400':''}`} style={{height:h}} title={v.toFixed(0)+'ms'} />; })}
                      </div>
                    ) : '—'}
                  </td>
                  <td className="px-2 py-1 text-white/50">
                    {latest?.message || ''}
                    {latest?.message?.startsWith('latency budget exceeded') && <span className="ml-1 text-rose-400 font-mono">!</span>}
                  </td>
                  <td className="px-2 py-1 text-white/40 font-mono">
                    {spec.requiredKeys?.length ? 'K' : ''}{spec.jsonSchema ? 'S' : ''}{spec.maxLatencyMs ? 'L' : ''}{spec.hardLatencyBudgetMs ? 'B' : ''}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ServiceContractTestPanel;
