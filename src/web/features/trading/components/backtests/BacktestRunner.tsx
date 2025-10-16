// Feature-slice BacktestRunner migrated from legacy component
// Simplified formatting; retains original functionality.
import React, { useEffect, useRef } from 'react';
import { Play, RefreshCw, StopCircle, CheckCircle2, AlertTriangle, Calendar, Settings, BarChart3 } from 'lucide-react';
import { createBacktestV1, getBacktestStatusV1, getBacktestResultsV1, cancelBacktestV1, mapV1ToSimpleMetrics, type V1BacktestCreateConfig, type V1BacktestStatus, type V1BacktestResultsResponse } from '@/services/backtestV1';
import { listSources, listSymbols, type SourceInfo } from '@/services/DataApi';
import { useNotifications } from '@/components/Notifications';

type Metrics = { winRate: number; totalReturn: number; maxDrawdown: number; sharpeRatio: number };
const fmtDate = (d: Date) => d.toISOString().slice(0, 10);
const defaultStart = (() => { const d = new Date(); d.setFullYear(d.getFullYear() - 1); return fmtDate(d); })();
const defaultEnd = fmtDate(new Date());
const statusBadge: Record<string, string> = { completed:'bg-green-500/20 text-green-300', running:'bg-blue-500/20 text-blue-300', analyzing:'bg-indigo-500/20 text-indigo-300', loading_data:'bg-yellow-500/20 text-yellow-200', preparing_strategy:'bg-yellow-500/20 text-yellow-200', initialized:'bg-gray-500/20 text-gray-300', error:'bg-red-500/20 text-red-300', canceling:'bg-orange-500/20 text-orange-300', cancelled:'bg-orange-500/20 text-orange-300' };

interface BacktestRunnerProps { embedded?: boolean }
const BacktestRunner: React.FC<BacktestRunnerProps> = ({ embedded = false }) => {
  const { addNotification } = useNotifications();
  const completionNotifiedRef = useRef<string | null>(null);
  const [sources, setSources] = React.useState<Record<string, SourceInfo>>({});
  const [sourceId, setSourceId] = React.useState<string>('');
  const [interval, setInterval] = React.useState<string>('1d');
  const [name, setName] = React.useState('My Backtest');
  const [description, setDescription] = React.useState('Exploring HMM+Transformer signals');
  const [symbols, setSymbols] = React.useState('AAPL');
  const [symbolQuery, setSymbolQuery] = React.useState('');
  const [symbolSuggestions, setSymbolSuggestions] = React.useState<Array<{ symbol: string; name?: string }>>([]);
  const [loadingSuggestions, setLoadingSuggestions] = React.useState(false);
  const [startDate, setStartDate] = React.useState(defaultStart);
  const [endDate, setEndDate] = React.useState(defaultEnd);
  const [initialCapital, setInitialCapital] = React.useState(50000);
  const [commission, setCommission] = React.useState(0);
  const [slippage, setSlippage] = React.useState(0);
  const [strategyType, setStrategyType] = React.useState('hmm_transformer');
  const [paramsText, setParamsText] = React.useState(JSON.stringify({ hmm_states:3, transformer_window:64, risk_per_trade:0.01 }, null, 2));
  const [riskPerTrade, setRiskPerTrade] = React.useState(0.01);
  const [maxDailyLossPct, setMaxDailyLossPct] = React.useState<number | ''>('');
  const [maxPositionSizePct, setMaxPositionSizePct] = React.useState<number | ''>('');
  const [sizingMode, setSizingMode] = React.useState('fixed');
  const [atrPeriod, setAtrPeriod] = React.useState<number | ''>('');
  const [atrMult, setAtrMult] = React.useState<number | ''>('');
  const [creating, setCreating] = React.useState(false);
  const [currentId, setCurrentId] = React.useState<string | null>(null);
  const [status, setStatus] = React.useState<V1BacktestStatus | null>(null);
  const [globalError, setGlobalError] = React.useState<string | null>(null);
  const [metrics, setMetrics] = React.useState<Metrics | null>(null);
  const [results, setResults] = React.useState<V1BacktestResultsResponse | null>(null);
  const [polling, setPolling] = React.useState(false);

    useEffect(() => { (async () => { try { const res = await listSources(); setSources(res.sources || {}); const pref = Object.keys(res.sources || {}).find(id => id.toLowerCase().includes('fks') || id.toLowerCase().includes('yahoo')) || Object.keys(res.sources || {})[0]; if (pref) { setSourceId(pref); const s = res.sources[pref]; if (s?.intervals?.length) setInterval(s.intervals[0]!); } } catch (e: any) { setGlobalError(e?.message || 'Failed to load data sources'); } })(); }, []);
    useEffect(() => { const s = sources[sourceId]; if (s?.intervals?.length) setInterval(prev => (s.intervals!.includes(prev) ? prev : s.intervals![0]!)); setSymbolSuggestions([]); setSymbolQuery(''); }, [sourceId, sources]);
    useEffect(() => { if (!currentId) return; let timer: any; const tick = async () => { try { const st = await getBacktestStatusV1(currentId); setStatus(st); if (['completed','error','cancelled'].includes(st.status)) { setPolling(false); if (st.status === 'completed') { try { const res = await getBacktestResultsV1(currentId, true, 200); setResults(res); setMetrics(mapV1ToSimpleMetrics(res)); } catch { } } return; } } catch (e: any) { setGlobalError(e?.message || 'Failed to fetch status'); } timer = setTimeout(tick, 2500); }; setPolling(true); tick(); return () => timer && clearTimeout(timer); }, [currentId]);
    useEffect(() => { if (!sourceId) return; const q = symbolQuery.trim(); let timer: any; if (q.length < 2) { setSymbolSuggestions([]); return () => {}; } setLoadingSuggestions(true); timer = setTimeout(async () => { try { const res = await listSymbols(sourceId, { query: q, limit: 8 }); setSymbolSuggestions((res.symbols || []).map(s => ({ symbol: s.symbol, name: s.name }))); } catch { setSymbolSuggestions([]); } finally { setLoadingSuggestions(false); } }, 250); return () => timer && clearTimeout(timer); }, [symbolQuery, sourceId]);

    async function onCreate(e: React.FormEvent) { e.preventDefault(); setGlobalError(null); setMetrics(null); setResults(null); try { if (!name.trim()) throw new Error('Name is required'); if (!sourceId) throw new Error('Select a data source'); const sym = symbols.split(',').map(s => s.trim()).filter(Boolean); const isBinance = sourceId.toLowerCase().includes('binance'); if (isBinance) { const bad = sym.find(s => /[-\s]/.test(s) || s !== s.toUpperCase() || s.length < 5); if (bad) throw new Error(`Binance symbol "${bad}" invalid.`); } if (!sym.length) throw new Error('Enter at least one symbol'); let parsedParams: Record<string, any> = {}; if (paramsText.trim()) { try { parsedParams = JSON.parse(paramsText); } catch { throw new Error('Parameters JSON is invalid'); } } const risk: any = { risk_per_trade: riskPerTrade, max_daily_loss_pct: maxDailyLossPct === '' ? undefined : Number(maxDailyLossPct), max_position_size_pct: maxPositionSizePct === '' ? undefined : Number(maxPositionSizePct), sizing_mode: sizingMode || undefined, atr_period: atrPeriod === '' ? undefined : Number(atrPeriod), atr_mult: atrMult === '' ? undefined : Number(atrMult) }; Object.keys(risk).forEach(k => risk[k] == null && delete risk[k]); const payload: V1BacktestCreateConfig = { name: name.trim(), description: description.trim() || undefined, initial_capital: initialCapital, commission, slippage, data: { source: sourceId, symbols: sym, start_date: startDate, end_date: endDate, interval: interval || undefined }, strategy: { type: strategyType, params: parsedParams }, ...(Object.keys(risk).length ? { risk } : {}) }; setCreating(true); const res = await createBacktestV1(payload); setCurrentId(res.backtest_id); setStatus({ backtest_id: res.backtest_id, name: payload.name, status: 'initialized', progress: 0, message: res.message, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }); addNotification({ type: 'success', title: 'Backtest started', message: `Job ${res.backtest_id} created`, duration: 3500 } as any); } catch (e: any) { setGlobalError(e?.message || 'Failed to create backtest'); addNotification({ type: 'warning', title: 'Backtest failed', message: e?.message || 'See logs', duration: 5000 } as any); } finally { setCreating(false); } }
    async function onCancel() { if (!currentId) return; try { await cancelBacktestV1(currentId); addNotification({ type: 'milestone', title: 'Cancellation requested', message: `Backtest ${currentId} stopping`, duration: 3000 } as any); } catch (e: any) { setGlobalError(e?.message || 'Failed to cancel'); addNotification({ type: 'warning', title: 'Cancel failed', message: e?.message || 'Could not cancel job', duration: 5000 } as any); } }
    useEffect(() => { if (status?.status === 'completed' && metrics && currentId && completionNotifiedRef.current !== currentId) { completionNotifiedRef.current = currentId; addNotification({ type: 'success', title: 'Backtest completed', message: `Sharpe ${metrics.sharpeRatio.toFixed(2)}, Return ${metrics.totalReturn.toFixed(2)}%`, duration: 6000 } as any); } }, [status?.status, metrics, currentId, addNotification]);

    return (
      <div className={embedded ? '' : 'min-h-screen p-6'} data-testid="backtest-runner">
        <div className={embedded ? '' : 'max-w-7xl mx-auto space-y-6'}>
          {!embedded && (
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-white">Backtest Runner</h1>
                <p className="text-white/70">Create and monitor backtests.</p>
              </div>
            </div>
          )}
          {globalError && (
            <div className="glass-card p-3 border border-red-400/40 bg-red-500/10 text-red-200" data-testid="backtest-error">{globalError}</div>
          )}
          {/* Form */}
          <form onSubmit={onCreate} className="glass-card p-5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="text-sm text-white/80">
                <div className="mb-1">Name</div>
                <input value={name} onChange={e=>setName(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">Description</div>
                <input value={description} onChange={e=>setDescription(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="text-sm text-white/80">
                <div className="mb-1">Data Source</div>
                <select value={sourceId} onChange={e=>setSourceId(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">
                  {Object.keys(sources).length === 0 && <option value="">Loading…</option>}
                  {Object.entries(sources).map(([id,s]) => <option key={id} value={id}>{s.name||id}</option>)}
                </select>
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">Interval</div>
                <select value={interval} onChange={e=>setInterval(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">{(sources[sourceId]?.intervals||['1d','1h','5m']).map(iv => <option key={iv} value={iv}>{iv}</option>)}</select>
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">Symbols</div>
                <div className="relative">
                  <input value={symbols} onChange={e=>{const v=e.target.value; setSymbols(v); const parts=v.split(','); setSymbolQuery((parts[parts.length-1]||'').trim());}} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
                  {(symbolSuggestions.length>0 || loadingSuggestions) && (
                    <div className="absolute z-10 mt-1 w-full max-h-56 overflow-auto rounded border border-white/20 bg-[#0b1020] shadow-lg">
                      {loadingSuggestions && <div className="px-3 py-2 text-white/60 text-sm">Loading…</div>}
                      {!loadingSuggestions && symbolSuggestions.map((sug,idx) => (
                        <button type="button" key={sug.symbol+idx} onClick={()=>{ const parts = symbols.split(','); parts[parts.length-1] = ` ${sug.symbol}`; setSymbols(parts.join(',')); setSymbolSuggestions([]); setSymbolQuery(''); }} className="w-full text-left px-3 py-2 hover:bg-white/10 text-white/90 text-sm">
                          <span className="font-mono text-white">{sug.symbol}</span>{sug.name && <span className="text-white/50 ml-2">{sug.name}</span>}
                        </button>
                      ))}
                    </div>)}
                </div>
              </label>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="text-sm text-white/80"><div className="mb-1 flex items-center gap-2"><Calendar className="w-4 h-4"/>Start</div><input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
              <label className="text-sm text-white/80"><div className="mb-1 flex items-center gap-2"><Calendar className="w-4 h-4"/>End</div><input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
              <div className="grid grid-cols-2 gap-4">
                <label className="text-sm text-white/80"><div className="mb-1">Capital</div><input type="number" value={initialCapital} onChange={e=>setInitialCapital(Number(e.target.value)||0)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
                <label className="text-sm text-white/80"><div className="mb-1">Commission</div><input type="number" value={commission} step="0.01" onChange={e=>setCommission(Number(e.target.value)||0)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="text-sm text-white/80"><div className="mb-1 flex items-center gap-2"><Settings className="w-4 h-4"/>Type</div><select value={strategyType} onChange={e=>setStrategyType(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"><option value="hmm_transformer">HMM + Transformer</option><option value="mean_reversion">Mean Reversion</option><option value="momentum_scalp">Momentum Scalping</option><option value="breakout">Breakout</option></select></label>
              <label className="text-sm text-white/80 md:col-span-2"><div className="mb-1">Parameters (JSON)</div><textarea value={paramsText} onChange={e=>setParamsText(e.target.value)} rows={6} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white font-mono text-xs" /></label>
            </div>
            <div className="glass-card bg-white/5 rounded p-4 border border-white/10">
              <div className="text-white/80 font-semibold mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4"/>Risk Settings</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <label className="text-sm text-white/80"><div className="mb-1">Risk / Trade</div><input type="number" value={riskPerTrade} step={0.001} onChange={e=>setRiskPerTrade(Number(e.target.value)||0)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
                <label className="text-sm text-white/80"><div className="mb-1">Daily Loss %</div><input type="number" value={maxDailyLossPct} onChange={e=>setMaxDailyLossPct(e.target.value===''?'':Number(e.target.value))} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
                <label className="text-sm text-white/80"><div className="mb-1">Pos Size %</div><input type="number" value={maxPositionSizePct} onChange={e=>setMaxPositionSizePct(e.target.value===''?'':Number(e.target.value))} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" /></label>
              </div>
            </div>
            <div className="flex items-center gap-3"><button type="submit" disabled={creating || (!!currentId && polling)} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-60 flex items-center gap-2">{creating ? <RefreshCw className="w-4 h-4 animate-spin"/> : <Play className="w-4 h-4"/>}<span>{creating? 'Creating…':'Create Backtest'}</span></button>{!!currentId && <button type="button" onClick={onCancel} className="px-4 py-2 rounded bg-red-600 hover:bg-red-700 text-white flex items-center gap-2"><StopCircle className="w-4 h-4"/><span>Cancel</span></button>}</div>
          </form>
          {!!currentId && (
            <div className="glass-card p-5">
              <div className="flex items-center justify-between"><div><div className="text-white font-semibold">Job ID: <span className="text-white/80 font-mono">{currentId}</span></div><div className="text-white/70 text-sm">{status?.message}</div></div><div><span className={`text-[10px] px-2 py-0.5 rounded ${statusBadge[status?.status || 'initialized'] || 'bg-gray-500/20 text-gray-300'}`}>{status?.status}</span></div></div>
              <div className="mt-3"><div className="h-2 bg-white/10 rounded overflow-hidden"><div className="h-2 bg-blue-500 transition-all" style={{ width: `${Math.max(5, Math.round(status?.progress || 0))}%` }} /></div><div className="mt-2 text-xs text-white/60 flex items-center justify-between"><span>Progress</span><span>{Math.round(status?.progress || 0)}%</span></div></div>
              {status?.status === 'completed' && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 text-green-300"><CheckCircle2 className="w-4 h-4"/>Completed</div>
                  {metrics ? (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">{['Win Rate','Total Return','Max Drawdown','Sharpe'].map((lbl,i) => { const map = [metrics.winRate.toFixed(1)+'%', metrics.totalReturn.toFixed(2)+'%', metrics.maxDrawdown.toFixed(2)+'%', metrics.sharpeRatio.toFixed(2)]; const color = i===0?'text-green-300': i===1? (metrics.totalReturn>=0?'text-green-300':'text-red-300'): i===2?'text-red-300': (metrics.sharpeRatio>=1.5?'text-green-300':'text-yellow-300'); return <div key={lbl} className="bg-white/5 rounded p-3"><div className="text-white/60 text-xs">{lbl}</div><div className={`text-lg font-bold ${color}`}>{map[i]}</div></div>; })}</div>
                  ) : (<div className="mt-2 text-white/70 text-sm">Preparing summary…</div>)}
                  <div className="mt-3">
                    <button
                      type="button"
                      onClick={async () => {
                        if (!currentId) return;
                        try {
                          const res = await getBacktestResultsV1(currentId, true, 200);
                          setResults(res);
                          setMetrics(mapV1ToSimpleMetrics(res));
                        } catch (e: any) {
                          setGlobalError(e?.message || 'Failed to fetch results');
                        }
                      }}
                      className="px-3 py-2 rounded bg-purple-600 hover:bg-purple-700 text-white text-sm"
                    >
                      Load details
                    </button>
                    {results && (
                      <button
                        type="button"
                        onClick={() => {
                          if (!results) return;
                          const filename = `${(results.name || 'backtest').replace(/\s+/g, '_')}_${results.backtest_id}.json`;
                          const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = filename;
                          a.click();
                          URL.revokeObjectURL(url);
                        }}
                        className="ml-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm"
                      >
                        Download JSON
                      </button>
                    )}
                  </div>
                  {!embedded && (<div className="mt-4"><a href="/trading/backtests" className="inline-flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm"><BarChart3 className="w-4 h-4"/>View in Backtests History</a></div>)}
                </div>
              )}
              {status?.status === 'error' && (<div className="mt-4 text-red-300 flex items-center gap-2"><AlertTriangle className="w-4 h-4"/>Error running backtest.</div>)}
            </div>
          )}
        </div>
      </div>
    );
  };
  export default BacktestRunner;
