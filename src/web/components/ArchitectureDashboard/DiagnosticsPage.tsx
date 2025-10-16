import { Play, RefreshCw } from 'lucide-react';
import PageContainer from '@layout/PageContainer';
import React, { useState } from 'react';

import { serviceEndpoints } from '../../hooks/useServiceMonitoring';

interface BenchmarkResult { id: string; url: string; timeMs: number; size?: number; status: number | 'error'; }

const DiagnosticsPage: React.FC = () => {
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const [running, setRunning] = useState(false);

  const runBenchmarks = async () => {
    setRunning(true);
    const tests = serviceEndpoints.slice(0, 8); // limit for now
    const out: BenchmarkResult[] = [];
    for (const t of tests) {
      const start = performance.now();
      try {
        const resp = await fetch(t.url, { method: 'GET', mode: 'no-cors' as RequestMode });
        const timeMs = performance.now() - start;
        out.push({ id: t.id, url: t.url, timeMs: Math.round(timeMs), status: (resp as any).status ?? 0 });
      } catch (e) {
        const timeMs = performance.now() - start;
        out.push({ id: t.id, url: t.url, timeMs: Math.round(timeMs), status: 'error' });
      }
      setResults([...out]);
      await new Promise(r => setTimeout(r, 50));
    }
    setRunning(false);
  };

  return (
    <PageContainer className="space-y-6">
        <header className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Diagnostics & Network Benchmarks</h1>
            <p className="text-white/70 text-sm max-w-2xl">Run simple latency probes (client-side) against registered service endpoints to spot anomalies.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={()=>setResults([])} className="btn-secondary text-sm px-3">Clear</button>
            <button onClick={runBenchmarks} disabled={running} className="btn-primary flex items-center gap-2 text-sm px-4">
              {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} {running? 'Running':'Run Benchmarks'}
            </button>
          </div>
        </header>
        <div className="glass-card p-4">
          <table className="w-full text-sm">
            <thead className="text-white/60">
              <tr>
                <th className="text-left py-2 pr-3 font-medium">Service</th>
                <th className="text-left py-2 pr-3 font-medium">URL</th>
                <th className="text-left py-2 pr-3 font-medium">Latency (ms)</th>
                <th className="text-left py-2 pr-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.id} className="border-t border-white/10 hover:bg-white/5">
                  <td className="py-2 pr-3 font-mono">{r.id}</td>
                  <td className="py-2 pr-3 truncate max-w-xs"><span className="text-white/60">{r.url}</span></td>
                  <td className="py-2 pr-3">{r.timeMs}</td>
                  <td className="py-2 pr-3">
                    {r.status === 'error' ? <span className="text-red-400">error</span> : r.status === 0 ? <span className="text-white/50">n/a</span> : r.status}
                  </td>
                </tr>
              ))}
              {results.length === 0 && (
                <tr><td colSpan={4} className="py-8 text-center text-white/40">No results yet. Click Run Benchmarks.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="text-xs text-white/40 max-w-2xl">
          Note: These measurements are naive client-side fetch timings (no-cors); for accurate backend profiling integrate server-side metrics / tracing.
        </div>
    </PageContainer>
  );
};

export default DiagnosticsPage;
