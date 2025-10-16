import React, { useEffect, useMemo, useState } from 'react';
import { getBacktestListV1, getBacktestResultsV1, cancelBacktestV1, mapV1ToSimpleMetrics } from '@/services/backtestV1';
import type { V1BacktestStatus, V1BacktestResultsResponse } from '@/services/backtestV1';

const statusClasses: Record<string,string> = { completed:'bg-green-500/20 text-green-300', running:'bg-blue-500/20 text-blue-300', analyzing:'bg-indigo-500/20 text-indigo-300', loading_data:'bg-yellow-500/20 text-yellow-200', preparing_strategy:'bg-yellow-500/20 text-yellow-200', initialized:'bg-gray-500/20 text-gray-300', error:'bg-red-500/20 text-red-300', canceling:'bg-orange-500/20 text-orange-300', cancelled:'bg-orange-500/20 text-orange-300'};

const BacktestsHistory: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [jobs, setJobs] = useState<V1BacktestStatus[]>([]); const [loading, setLoading] = useState(false); const [error,setError] = useState<string|null>(null); const [query,setQuery]=useState(''); const [status,setStatus]=useState<'all'|V1BacktestStatus['status']>('all'); const [selected,setSelected]=useState<V1BacktestStatus|null>(null); const [metrics,setMetrics]=useState<{ winRate:number; totalReturn:number; maxDrawdown:number; sharpeRatio:number }|null>(null); const [result,setResult]=useState<V1BacktestResultsResponse|null>(null); const [fetching,setFetching] = useState(false);
  const refresh = async () => { setLoading(true); setError(null); try { const list = await getBacktestListV1(); setJobs([...list].sort((a,b)=> new Date(b.created_at).getTime()-new Date(a.created_at).getTime())); } catch(e:any){ setError(e?.message||'Failed to load backtests'); } finally { setLoading(false);} };
  useEffect(()=>{ refresh(); }, []);
  const filtered = useMemo(()=> jobs.filter(j => (status==='all'||j.status===status) && (!query || (j.name||'').toLowerCase().includes(query.toLowerCase()) || j.backtest_id.toLowerCase().includes(query.toLowerCase()))), [jobs, status, query]);
  const openJob = async (job: V1BacktestStatus) => { setSelected(job); setMetrics(null); setResult(null); if (job.status !== 'completed') return; setFetching(true); try { const res = await getBacktestResultsV1(job.backtest_id, true, 200); setMetrics(mapV1ToSimpleMetrics(res)); setResult(res); } catch(e:any){ setError(e?.message||'Failed to fetch results'); } finally { setFetching(false);} };
  const onCancel = async (job: V1BacktestStatus) => { try { await cancelBacktestV1(job.backtest_id); refresh(); } catch {/* ignore */} };
  return (
    <div className={embedded ? '' : 'p-6'} data-testid="backtests-history">
      {!embedded && <div className="mb-6"><h1 className="text-3xl font-bold text-white mb-2">Backtests History</h1><p className="text-white/70 text-sm">Review and inspect backtest jobs</p></div>}
      <div className="glass-card p-4 mb-4">
        <div className="flex flex-col md:flex-row gap-3 items-start md:items-center">
          <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search name or ID" className="px-3 py-2 rounded bg-white/10 border border-white/20 text-white w-full md:w-64 text-sm" />
          <select value={status} onChange={e=>setStatus(e.target.value as any)} className="px-3 py-2 rounded bg-white/10 border border-white/20 text-white text-sm">
            <option value="all">All statuses</option>
            {['completed','running','analyzing','loading_data','preparing_strategy','initialized','error','canceling','cancelled'].map(s=> <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={refresh} className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm">{loading? 'Loading…':'Refresh'}</button>
        </div>
      </div>
      {error && <div className="glass-card p-3 border border-red-500/40 bg-red-500/10 text-red-300 mb-4 text-sm">{error}</div>}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 glass-card p-4">
          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1 text-xs">
            {filtered.map(job => (
              <div key={job.backtest_id} onClick={()=>openJob(job)} className={`p-2 rounded cursor-pointer border ${selected?.backtest_id===job.backtest_id? 'border-blue-400 bg-blue-400/10':'border-white/10 hover:bg-white/5'}`}>
                <div className="flex items-center justify-between"><div className="text-white truncate mr-2">{job.name||job.backtest_id}</div><span className={`text-[10px] px-2 py-0.5 rounded ${statusClasses[job.status]||'bg-gray-500/20 text-gray-300'}`}>{job.status}</span></div>
                <div className="text-[10px] text-white/50 mt-1">{new Date(job.created_at).toLocaleString()}</div>
                {['running','loading_data','preparing_strategy','analyzing','initialized'].includes(job.status) && (
                  <div className="flex items-center justify-between mt-1">
                    <div className="h-1 w-24 bg-white/10 rounded overflow-hidden"><div className="h-1 bg-blue-500" style={{ width: `${Math.max(5, Math.round(job.progress))}%` }} /></div>
                    <button onClick={(e)=>{ e.stopPropagation(); onCancel(job); }} className="text-[10px] px-2 py-0.5 rounded bg-red-600/80 hover:bg-red-600 text-white">Cancel</button>
                  </div>
                )}
              </div>
            ))}
            {filtered.length===0 && !loading && <div className="text-white/50">No jobs.</div>}
          </div>
        </div>
        <div className="lg:col-span-2 glass-card p-4 text-xs">
          <h3 className="text-white font-semibold mb-2">Selected Job</h3>
          {!selected && <div className="text-white/50">Select a job.</div>}
          {selected && (
            <div className="space-y-3">
              <div className="flex items-center justify-between"><div className="text-white font-medium truncate">{selected.name||selected.backtest_id}</div><span className={`text-[10px] px-2 py-0.5 rounded ${statusClasses[selected.status]||'bg-gray-500/20 text-gray-300'}`}>{selected.status}</span></div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-[10px]">
                <div className="bg-white/5 rounded p-2 text-white/70">Created: {new Date(selected.created_at).toLocaleString()}</div>
                <div className="bg-white/5 rounded p-2 text-white/70">Updated: {new Date(selected.updated_at).toLocaleString()}</div>
                {selected.estimated_completion && <div className="bg-white/5 rounded p-2 text-white/70">ETA: {new Date(selected.estimated_completion).toLocaleString()}</div>}
              </div>
              {selected.status === 'completed' && (
                <div>
                  {!metrics && !fetching && <button onClick={()=>openJob(selected)} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-white text-[10px]">Load Summary</button>}
                  {fetching && <div className="text-white/60">Fetching…</div>}
                  {metrics && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">
                      <div className="bg-white/5 rounded p-2"><div className="text-white/60 text-[10px]">Win Rate</div><div className="text-green-300 text-base font-bold">{metrics.winRate.toFixed(1)}%</div></div>
                      <div className="bg-white/5 rounded p-2"><div className="text-white/60 text-[10px]">Return</div><div className={`${metrics.totalReturn>=0?'text-green-300':'text-red-300'} text-base font-bold`}>{metrics.totalReturn.toFixed(2)}%</div></div>
                      <div className="bg-white/5 rounded p-2"><div className="text-white/60 text-[10px]">Max DD</div><div className="text-red-300 text-base font-bold">{metrics.maxDrawdown.toFixed(2)}%</div></div>
                      <div className="bg-white/5 rounded p-2"><div className="text-white/60 text-[10px]">Sharpe</div><div className={`${metrics.sharpeRatio>=1.5?'text-green-300':'text-yellow-300'} text-base font-bold`}>{metrics.sharpeRatio.toFixed(2)}</div></div>
                    </div>
                  )}
                  {result && <div className="mt-2"><button className="px-3 py-1 rounded bg-gray-700 hover:bg-gray-600 text-white text-[10px]" onClick={()=>{ const blob = new Blob([JSON.stringify(result,null,2)],{type:'application/json'}); const url = URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`${(result.name||'backtest').replace(/\s+/g,'_')}_${result.backtest_id}.json`; a.click(); URL.revokeObjectURL(url); }}>Download JSON</button></div>}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
export default BacktestsHistory;
