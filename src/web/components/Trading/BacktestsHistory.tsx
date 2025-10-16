import React from 'react';

import {
  getBacktestListV1,
  getBacktestResultsV1,
  cancelBacktestV1,
  mapV1ToSimpleMetrics
} from '../../services/backtestV1';

import type {
  V1BacktestStatus,
  V1BacktestResultsResponse} from '../../services/backtestV1';

const statusColors: Record<string, string> = {
  completed: 'bg-green-500/20 text-green-300',
  running: 'bg-blue-500/20 text-blue-300',
  analyzing: 'bg-indigo-500/20 text-indigo-300',
  loading_data: 'bg-yellow-500/20 text-yellow-200',
  preparing_strategy: 'bg-yellow-500/20 text-yellow-200',
  initialized: 'bg-gray-500/20 text-gray-300',
  error: 'bg-red-500/20 text-red-300',
  canceling: 'bg-orange-500/20 text-orange-300',
  cancelled: 'bg-orange-500/20 text-orange-300',
};

interface BacktestsHistoryProps { embedded?: boolean }
const BacktestsHistory: React.FC<BacktestsHistoryProps> = ({ embedded = false }) => {
  const [jobs, setJobs] = React.useState<V1BacktestStatus[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState('');
  const [status, setStatus] = React.useState<'all' | V1BacktestStatus['status']>('all');
  const [selected, setSelected] = React.useState<V1BacktestStatus | null>(null);
  const [metrics, setMetrics] = React.useState<{ winRate: number; totalReturn: number; maxDrawdown: number; sharpeRatio: number } | null>(null);
  const [result, setResult] = React.useState<V1BacktestResultsResponse | null>(null);
  const [fetchingResult, setFetchingResult] = React.useState(false);
  const [autoRefresh, setAutoRefresh] = React.useState<boolean>(false);
  const refreshIntervalRef = React.useRef<any>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await getBacktestListV1();
      const sorted = [...list].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setJobs(sorted);
    } catch (e: any) {
      setError(e?.message || 'Failed to load backtests');
    } finally {
      setLoading(false);
    }
  };

  React.useEffect(() => {
    refresh();
  }, []);

  React.useEffect(() => {
    if (autoRefresh) {
      if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = setInterval(() => refresh(), 10000);
    } else if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
    return () => {
      if (refreshIntervalRef.current) clearInterval(refreshIntervalRef.current);
    };
  }, [autoRefresh]);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter(j =>
      (status === 'all' || j.status === status) &&
      (!q || (j.name || '').toLowerCase().includes(q) || j.backtest_id.toLowerCase().includes(q))
    );
  }, [jobs, query, status]);

  const openJob = async (job: V1BacktestStatus) => {
    setSelected(job);
    setMetrics(null);
    setResult(null);
    setError(null);
    if (job.status !== 'completed') return;
    setFetchingResult(true);
    try {
      const res: V1BacktestResultsResponse = await getBacktestResultsV1(job.backtest_id, true, 200);
      setMetrics(mapV1ToSimpleMetrics(res));
      setResult(res);
    } catch (e: any) {
      setError(e?.message || 'Failed to fetch results');
    } finally {
      setFetchingResult(false);
    }
  };

  const onCancel = async (job: V1BacktestStatus) => {
    try {
      await cancelBacktestV1(job.backtest_id);
      await refresh();
    } catch {}
  };

  return (
    <div className={embedded ? '' : 'min-h-screen p-6'}>
      <div className={embedded ? '' : 'max-w-7xl mx-auto'}>
        {!embedded && (
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-white mb-2">Backtests History (v1)</h1>
            <p className="text-white/70">Review, filter, and inspect your backtest jobs.</p>
          </div>
        )}

        <div className="glass-card p-4 mb-4">
          <div className="flex flex-col md:flex-row gap-3 items-start md:items-center justify-between">
            <div className="flex flex-col md:flex-row gap-3 items-start md:items-center">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name or ID"
              className="px-3 py-2 rounded bg-white/10 border border-white/20 text-white w-full md:w-64"
            />
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as any)}
              className="px-3 py-2 rounded bg-white/10 border border-white/20 text-white"
            >
              <option value="all">All statuses</option>
              {[
                'completed','running','analyzing','loading_data','preparing_strategy','initialized','error','canceling','cancelled'
              ].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button onClick={refresh} className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white">{loading ? 'Loading…' : 'Refresh'}</button>
            <label className="flex items-center gap-2 text-white/80 text-sm select-none">
              <input type="checkbox" checked={autoRefresh} onChange={(e)=>setAutoRefresh(e.target.checked)} />
              Auto-refresh
            </label>
            </div>
            {!embedded && (
              <a href="/strategy/backtest" className="px-3 py-2 rounded bg-green-600 hover:bg-green-700 text-white text-sm">New Backtest</a>
            )}
          </div>
        </div>

        {error && (
          <div className="glass-card p-3 border border-red-400/40 bg-red-500/10 text-red-200 mb-4">{error}</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 glass-card p-4">
            <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
              {filtered.length === 0 && !loading && (
                <div className="text-white/60">No jobs match your filters.</div>
              )}
              {filtered.map(job => (
                <div
                  key={job.backtest_id}
                  onClick={() => openJob(job)}
                  className={`p-3 rounded border cursor-pointer ${selected?.backtest_id === job.backtest_id ? 'border-blue-400 bg-blue-400/10' : 'border-white/10 hover:bg-white/5'}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-white truncate mr-2">{job.name || job.backtest_id}</div>
                    <span className={`text-[10px] px-2 py-0.5 rounded ${statusColors[job.status] || 'bg-gray-500/20 text-gray-300'}`}>{job.status}</span>
                  </div>
                  <div className="text-xs text-white/60 mt-1">{new Date(job.created_at).toLocaleString()}</div>
                  {['running','loading_data','preparing_strategy','analyzing','initialized'].includes(job.status) && (
                    <div className="flex items-center justify-between mt-2">
                      <div className="h-1 w-28 bg-white/10 rounded overflow-hidden">
                        <div className="h-1 bg-blue-500" style={{ width: `${Math.max(5, Math.round(job.progress))}%` }} />
                      </div>
                      <button onClick={(e) => { e.stopPropagation(); onCancel(job); }} className="text-[10px] px-2 py-0.5 rounded bg-red-600/90 hover:bg-red-600 text-white">Cancel</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          <div className="lg:col-span-2 glass-card p-4">
            <h3 className="text-white font-semibold mb-3">Selected Job</h3>
            {!selected && (
              <div className="text-white/60">Select a job to view details.</div>
            )}
            {selected && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-white font-medium">{selected.name || selected.backtest_id}</div>
                  <span className={`text-[10px] px-2 py-0.5 rounded ${statusColors[selected.status] || 'bg-gray-500/20 text-gray-300'}`}>{selected.status}</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                  <div className="bg-white/5 rounded p-2 text-white/80"><span className="text-white/60">Created:</span> {new Date(selected.created_at).toLocaleString()}</div>
                  <div className="bg-white/5 rounded p-2 text-white/80"><span className="text-white/60">Updated:</span> {new Date(selected.updated_at).toLocaleString()}</div>
                  {selected.estimated_completion && (
                    <div className="bg-white/5 rounded p-2 text-white/80"><span className="text-white/60">ETA:</span> {new Date(selected.estimated_completion).toLocaleString()}</div>
                  )}
                </div>

                {selected.status !== 'completed' && (
                  <div className="text-white/70">{selected.message}</div>
                )}

                {selected.status === 'completed' && (
                  <div>
                    {fetchingResult && <div className="text-white/70">Fetching results…</div>}
                    {!metrics && !fetchingResult && (
                      <button onClick={() => openJob(selected)} className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm">Load Summary</button>
                    )}
                    {metrics && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">
                        <div className="bg-white/5 rounded p-3">
                          <div className="text-white/60 text-xs">Win Rate</div>
                          <div className="text-green-300 text-lg font-bold">{metrics.winRate.toFixed(1)}%</div>
                        </div>
                        <div className="bg-white/5 rounded p-3">
                          <div className="text-white/60 text-xs">Total Return</div>
                          <div className={`${metrics.totalReturn >= 0 ? 'text-green-300' : 'text-red-300'} text-lg font-bold`}>{metrics.totalReturn.toFixed(2)}%</div>
                        </div>
                        <div className="bg-white/5 rounded p-3">
                          <div className="text-white/60 text-xs">Max Drawdown</div>
                          <div className="text-red-300 text-lg font-bold">{metrics.maxDrawdown.toFixed(2)}%</div>
                        </div>
                        <div className="bg-white/5 rounded p-3">
                          <div className="text-white/60 text-xs">Sharpe Ratio</div>
                          <div className={`${metrics.sharpeRatio >= 1.5 ? 'text-green-300' : 'text-yellow-300'} text-lg font-bold`}>{metrics.sharpeRatio.toFixed(2)}</div>
                        </div>
                      </div>
                    )}
                    {result && (
                      <div className="mt-3">
                        <button
                          className="px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm"
                          onClick={() => {
                            const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `${(result.name || 'backtest').replace(/\s+/g,'_')}_${result.backtest_id}.json`;
                            a.click();
                            URL.revokeObjectURL(url);
                          }}
                        >
                          Download JSON
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BacktestsHistory;
