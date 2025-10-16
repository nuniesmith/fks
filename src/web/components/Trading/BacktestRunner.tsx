import { Play, RefreshCw, StopCircle, CheckCircle2, AlertTriangle, Calendar, Settings, BarChart3 } from 'lucide-react';
import React from 'react';
import { useEffect, useRef } from 'react';

import {
  createBacktestV1,
  getBacktestStatusV1,
  getBacktestResultsV1,
  cancelBacktestV1,
  mapV1ToSimpleMetrics,
  type V1BacktestCreateConfig,
  type V1BacktestStatus,
  type V1BacktestResultsResponse,
} from '../../services/backtestV1';
import { listSources, listSymbols, type SourceInfo } from '../../services/DataApi';
import { useNotifications } from '../Notifications';


type Metrics = { winRate: number; totalReturn: number; maxDrawdown: number; sharpeRatio: number };

const fmtDate = (d: Date) => d.toISOString().slice(0, 10);

const defaultStart = (() => { const d = new Date(); d.setFullYear(d.getFullYear() - 1); return fmtDate(d); })();
const defaultEnd = fmtDate(new Date());

const statusBadge: Record<string, string> = {
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

interface BacktestRunnerProps { embedded?: boolean }
const BacktestRunner: React.FC<BacktestRunnerProps> = ({ embedded = false }) => {
  const { addNotification } = useNotifications();
  const completionNotifiedRef = useRef<string | null>(null);
  // Data sources
  const [sources, setSources] = React.useState<Record<string, SourceInfo>>({});
  const [sourceId, setSourceId] = React.useState<string>('');
  const [interval, setInterval] = React.useState<string>('1d');

  // Form fields
  const [name, setName] = React.useState<string>('My Backtest');
  const [description, setDescription] = React.useState<string>('Exploring HMM+Transformer signals');
  const [symbols, setSymbols] = React.useState<string>('AAPL');
  const [symbolQuery, setSymbolQuery] = React.useState<string>('');
  const [symbolSuggestions, setSymbolSuggestions] = React.useState<Array<{ symbol: string; name?: string }>>([]);
  const [loadingSuggestions, setLoadingSuggestions] = React.useState<boolean>(false);
  const [startDate, setStartDate] = React.useState<string>(defaultStart);
  const [endDate, setEndDate] = React.useState<string>(defaultEnd);
  const [initialCapital, setInitialCapital] = React.useState<number>(50000);
  const [commission, setCommission] = React.useState<number>(0);
  const [slippage, setSlippage] = React.useState<number>(0);
  const [strategyType, setStrategyType] = React.useState<string>('hmm_transformer');
  const [paramsText, setParamsText] = React.useState<string>(JSON.stringify({
    hmm_states: 3,
    transformer_window: 64,
    risk_per_trade: 0.01
  }, null, 2));

  // Risk settings (optional)
  const [riskPerTrade, setRiskPerTrade] = React.useState<number>(0.01);
  const [maxDailyLossPct, setMaxDailyLossPct] = React.useState<number | ''>('');
  const [maxPositionSizePct, setMaxPositionSizePct] = React.useState<number | ''>('');
  const [sizingMode, setSizingMode] = React.useState<string>('fixed');
  const [atrPeriod, setAtrPeriod] = React.useState<number | ''>('');
  const [atrMult, setAtrMult] = React.useState<number | ''>('');

  // Lifecycle
  const [creating, setCreating] = React.useState<boolean>(false);
  const [currentId, setCurrentId] = React.useState<string | null>(null);
  const [status, setStatus] = React.useState<V1BacktestStatus | null>(null);
  const [polling, setPolling] = React.useState<boolean>(false);
  const [metrics, setMetrics] = React.useState<Metrics | null>(null);
  const [results, setResults] = React.useState<V1BacktestResultsResponse | null>(null);
  const [globalError, setGlobalError] = React.useState<string | null>(null);

  React.useEffect(() => {
    // Load sources for selection
    (async () => {
      try {
        const res = await listSources();
        setSources(res.sources || {});
        // pick a sensible default
        const pref = Object.keys(res.sources || {}).find(id => id.toLowerCase().includes('fks') || id.toLowerCase().includes('yahoo'))
          || Object.keys(res.sources || {})[0];
        if (pref) {
          setSourceId(pref);
          const s = res.sources[pref];
          if (s?.intervals?.length) setInterval(s.intervals[0]!);
        }
      } catch (e: any) {
        setGlobalError(e?.message || 'Failed to load data sources');
      }
    })();
  }, []);

  // Reset interval if not supported when source changes; clear suggestions
  React.useEffect(() => {
    const s = sources[sourceId];
    if (s?.intervals?.length) {
      setInterval(prev => (s.intervals!.includes(prev) ? prev : s.intervals![0]!));
    }
    setSymbolSuggestions([]);
    setSymbolQuery('');
  }, [sourceId, sources]);

  // Polling for status
  React.useEffect(() => {
    if (!currentId) return;
    let timer: any;
    const tick = async () => {
      try {
        const st = await getBacktestStatusV1(currentId);
        setStatus(st);
    if (st.status === 'completed' || st.status === 'error' || st.status === 'cancelled') {
          setPolling(false);
          // Try fetch results summary
          if (st.status === 'completed') {
            try {
      const res = await getBacktestResultsV1(currentId, true, 200);
      setResults(res);
      setMetrics(mapV1ToSimpleMetrics(res));
            } catch (e) {
              // Ignore; results might be delayed slightly
            }
          }
          return;
        }
      } catch (e: any) {
        setGlobalError(e?.message || 'Failed to fetch status');
      }
      timer = setTimeout(tick, 2500);
    };
    setPolling(true);
    tick();
    return () => timer && clearTimeout(timer);
  }, [currentId]);

  // Debounced symbol suggestions for the last token in the list
  React.useEffect(() => {
    if (!sourceId) return;
    const q = symbolQuery.trim();
    let timer: any;
    if (q.length < 2) {
      setSymbolSuggestions([]);
      return () => {};
    }
    setLoadingSuggestions(true);
    timer = setTimeout(async () => {
      try {
        const res = await listSymbols(sourceId, { query: q, limit: 8 });
        setSymbolSuggestions((res.symbols || []).map(s => ({ symbol: s.symbol, name: s.name })));
      } catch (e) {
        setSymbolSuggestions([]);
      } finally {
        setLoadingSuggestions(false);
      }
    }, 250);
    return () => timer && clearTimeout(timer);
  }, [symbolQuery, sourceId]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setGlobalError(null);
    setMetrics(null);
  setResults(null);
    try {
      if (!name.trim()) throw new Error('Name is required');
      if (!sourceId) throw new Error('Select a data source');
      const sym = symbols.split(',').map(s => s.trim()).filter(Boolean);
      const isBinance = sourceId.toLowerCase().includes('binance');
      if (isBinance) {
        const bad = sym.find(s => /[-\s]/.test(s) || s !== s.toUpperCase() || s.length < 5);
        if (bad) throw new Error(`Binance symbol "${bad}" looks invalid. Use e.g., BTCUSDT (no dashes, uppercase).`);
      }
      if (!sym.length) throw new Error('Enter at least one symbol');
      let parsedParams: Record<string, any> = {};
      if (paramsText.trim()) {
        try {
          parsedParams = JSON.parse(paramsText);
        } catch (e) {
          throw new Error('Parameters JSON is invalid');
        }
      }

      // Optional risk object – only include set values
      const risk: any = {
        risk_per_trade: Number.isFinite(riskPerTrade) ? riskPerTrade : undefined,
        max_daily_loss_pct: maxDailyLossPct === '' ? undefined : Number(maxDailyLossPct),
        max_position_size_pct: maxPositionSizePct === '' ? undefined : Number(maxPositionSizePct),
        sizing_mode: sizingMode || undefined,
        atr_period: atrPeriod === '' ? undefined : Number(atrPeriod),
        atr_mult: atrMult === '' ? undefined : Number(atrMult),
      };
      Object.keys(risk).forEach(k => risk[k] == null && delete risk[k]);

      const payload: V1BacktestCreateConfig = {
        name: name.trim(),
        description: description.trim() || undefined,
        initial_capital: Number.isFinite(initialCapital) ? initialCapital : undefined,
        commission: Number.isFinite(commission) ? commission : undefined,
        slippage: Number.isFinite(slippage) ? slippage : undefined,
        data: {
          source: sourceId,
          symbols: sym,
          start_date: startDate,
          end_date: endDate,
          interval: interval || undefined,
        },
        strategy: {
          type: strategyType,
          params: parsedParams,
        },
        ...(Object.keys(risk).length ? { risk } : {}),
      };

      setCreating(true);
  const res = await createBacktestV1(payload);
      setCurrentId(res.backtest_id);
      setStatus({
        backtest_id: res.backtest_id,
        name: payload.name,
        status: 'initialized',
        progress: 0,
        message: res.message,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
      addNotification({
        type: 'success',
        title: 'Backtest started',
        message: `Job ${res.backtest_id} created for ${symbols.split(',')[0]}`,
        duration: 3500,
      } as any);
    } catch (e: any) {
      setGlobalError(e?.message || 'Failed to create backtest');
      addNotification({
        type: 'warning',
        title: 'Backtest failed to start',
        message: e?.message || 'See logs for details',
        duration: 5000,
      } as any);
    } finally {
      setCreating(false);
    }
  }

  async function onCancel() {
    if (!currentId) return;
    try {
      await cancelBacktestV1(currentId);
      // Status will update on next poll
      addNotification({ type: 'milestone', title: 'Cancellation requested', message: `Backtest ${currentId} will stop shortly.`, duration: 3000 } as any);
    } catch (e: any) {
      setGlobalError(e?.message || 'Failed to cancel backtest');
      addNotification({ type: 'warning', title: 'Cancel failed', message: e?.message || 'Could not cancel job', duration: 5000 } as any);
    }
  }

  // Notify when a run completes and metrics are available (once per job)
  useEffect(() => {
    if (status?.status === 'completed' && metrics && currentId) {
      if (completionNotifiedRef.current !== currentId) {
        completionNotifiedRef.current = currentId;
        try {
          const sharpe = (metrics as any).sharpeRatio;
          const totalReturn = (metrics as any).totalReturn;
          const sharpeStr = typeof sharpe === 'number' ? sharpe.toFixed(2) : String(sharpe ?? 'N/A');
          const returnStr = typeof totalReturn === 'number' ? totalReturn.toFixed(2) : String(totalReturn ?? 'N/A');
          addNotification({
            type: 'success',
            title: 'Backtest completed',
            message: `Sharpe ${sharpeStr}, Return ${returnStr}%`,
            duration: 6000,
          } as any);
        } catch {
          addNotification({
            type: 'success',
            title: 'Backtest completed',
            message: `Results are ready to view`,
            duration: 6000,
          } as any);
        }
      }
    }
  }, [status?.status, metrics, currentId, addNotification]);

  return (
    <div className={embedded ? '' : 'min-h-screen p-6'}>
      <div className={embedded ? '' : 'max-w-7xl mx-auto space-y-6'}>
        {/* Header */}
        {!embedded && (
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white">Backtest Runner</h1>
              <p className="text-white/70">Create and monitor backtests using FKS Engine v1 jobs.</p>
            </div>
          </div>
        )}

        {globalError && (
          <div className="glass-card p-3 border border-red-400/40 bg-red-500/10 text-red-200">{globalError}</div>
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
                {Object.entries(sources).map(([id, s]) => (
                  <option key={id} value={id}>{s.name || id}</option>
                ))}
              </select>
            </label>
            <label className="text-sm text-white/80">
              <div className="mb-1">Interval</div>
              <select value={interval} onChange={e=>setInterval(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">
                {(sources[sourceId]?.intervals || ['1d','1h','5m']).map(iv => (
                  <option key={iv} value={iv}>{iv}</option>
                ))}
              </select>
            </label>
            <label className="text-sm text-white/80">
              <div className="mb-1">Symbols (comma-separated)</div>
              <div className="relative">
                <input
                  value={symbols}
                  onChange={e=>{
                    const v = e.target.value;
                    setSymbols(v);
                    const parts = v.split(',');
                    const last = (parts[parts.length - 1] || '').trim();
                    setSymbolQuery(last);
                  }}
                  className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"
                  placeholder={sourceId.toLowerCase().includes('binance') ? 'BTCUSDT,ETHUSDT' : 'AAPL,MSFT or BTC-USD'}
                />
                {(symbolSuggestions.length > 0 || loadingSuggestions) && (
                  <div className="absolute z-10 mt-1 w-full max-h-56 overflow-auto rounded border border-white/20 bg-[#0b1020] shadow-lg">
                    {loadingSuggestions && (
                      <div className="px-3 py-2 text-white/60 text-sm">Loading…</div>
                    )}
                    {!loadingSuggestions && symbolSuggestions.map((sug, idx) => (
                      <button
                        type="button"
                        key={`${sug.symbol}-${idx}`}
                        onClick={() => {
                          const parts = symbols.split(',');
                          parts[parts.length - 1] = ` ${sug.symbol}`; // replace last token
                          const next = parts.join(',').replace(/^\s+,/, '');
                          setSymbols(next);
                          setSymbolSuggestions([]);
                          setSymbolQuery('');
                        }}
                        className="w-full text-left px-3 py-2 hover:bg-white/10 text-white/90 text-sm"
                      >
                        <span className="font-mono text-white">{sug.symbol}</span>
                        {sug.name ? <span className="text-white/50 ml-2">{sug.name}</span> : null}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="mt-1 text-[11px] text-white/50">
                {sourceId.toLowerCase().includes('binance') ? (
                  <span>Tip: Binance uses continuous symbols without dashes, e.g., BTCUSDT, ETHUSDT.</span>
                ) : (
                  <span>Tip: Stocks like AAPL, MSFT; crypto as BTC-USD, ETH-USD via Yahoo.</span>
                )}
              </div>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="text-sm text-white/80">
              <div className="mb-1 flex items-center gap-2"><Calendar className="w-4 h-4" /> Start Date</div>
              <input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
            </label>
            <label className="text-sm text-white/80">
              <div className="mb-1 flex items-center gap-2"><Calendar className="w-4 h-4" /> End Date</div>
              <input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
            </label>
            <div className="grid grid-cols-2 gap-4">
              <label className="text-sm text-white/80">
                <div className="mb-1">Initial Capital</div>
                <input type="number" value={initialCapital} onChange={e=>setInitialCapital(Number(e.target.value)||0)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">Commission</div>
                <input type="number" value={commission} step="0.01" onChange={e=>setCommission(Number(e.target.value)||0)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="text-sm text-white/80">
              <div className="mb-1 flex items-center gap-2"><Settings className="w-4 h-4" /> Strategy Type</div>
              <select value={strategyType} onChange={e=>setStrategyType(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">
                <option value="hmm_transformer">HMM + Transformer</option>
                <option value="mean_reversion">Mean Reversion</option>
                <option value="momentum_scalp">Momentum Scalping</option>
                <option value="breakout">Breakout</option>
              </select>
            </label>
            <label className="text-sm text-white/80 md:col-span-2">
              <div className="mb-1">Parameters (JSON)</div>
              <textarea value={paramsText} onChange={e=>setParamsText(e.target.value)} rows={6} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white font-mono text-xs" />
            </label>
          </div>

          {/* Risk settings */}
          <div className="glass-card bg-white/5 rounded p-4 border border-white/10">
            <div className="text-white/80 font-semibold mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Risk Settings</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="text-sm text-white/80">
                <div className="mb-1">Risk per Trade</div>
                <input type="number" min={0} max={0.1} step={0.001} value={riskPerTrade}
                  onChange={e=>setRiskPerTrade(Number(e.target.value)||0)}
                  className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
                <div className="text-[11px] text-white/50 mt-1">Fraction of equity (e.g., 0.01 = 1%)</div>
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">Max Daily Loss %</div>
                <input type="number" min={0} max={1} step={0.01} value={maxDailyLossPct}
                  onChange={e=>setMaxDailyLossPct(e.target.value === '' ? '' : Number(e.target.value))}
                  placeholder="0.05"
                  className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">Max Position Size %</div>
                <input type="number" min={0} max={1} step={0.01} value={maxPositionSizePct}
                  onChange={e=>setMaxPositionSizePct(e.target.value === '' ? '' : Number(e.target.value))}
                  placeholder="0.10"
                  className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
              <label className="text-sm text-white/80">
                <div className="mb-1">Sizing Mode</div>
                <select value={sizingMode} onChange={e=>setSizingMode(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">
                  <option value="fixed">Fixed</option>
                  <option value="atr">ATR</option>
                  <option value="volatility">Volatility</option>
                </select>
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">ATR Period</div>
                <input type="number" min={1} max={365} step={1} value={atrPeriod}
                  onChange={e=>setAtrPeriod(e.target.value === '' ? '' : Number(e.target.value))}
                  placeholder="14"
                  className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
              <label className="text-sm text-white/80">
                <div className="mb-1">ATR Multiplier</div>
                <input type="number" min={0.1} max={20} step={0.1} value={atrMult}
                  onChange={e=>setAtrMult(e.target.value === '' ? '' : Number(e.target.value))}
                  placeholder="1.0"
                  className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
              </label>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button type="submit" disabled={creating || !!currentId && polling} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-60 flex items-center gap-2">
              {creating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              <span>{creating ? 'Creating…' : 'Create Backtest'}</span>
            </button>
            {!!currentId && (
              <button type="button" onClick={onCancel} className="px-4 py-2 rounded bg-red-600 hover:bg-red-700 text-white flex items-center gap-2">
                <StopCircle className="w-4 h-4" />
                <span>Cancel</span>
              </button>
            )}
          </div>
        </form>

  {/* Status */}
  {!!currentId && (
          <div className="glass-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-white font-semibold">Job ID: <span className="text-white/80 font-mono">{currentId}</span></div>
                <div className="text-white/70 text-sm">{status?.message}</div>
              </div>
              <div>
                <span className={`text-[10px] px-2 py-0.5 rounded ${statusBadge[status?.status || 'initialized'] || 'bg-gray-500/20 text-gray-300'}`}>{status?.status}</span>
              </div>
            </div>
            <div className="mt-3">
              <div className="h-2 bg-white/10 rounded overflow-hidden">
                <div className="h-2 bg-blue-500 transition-all" style={{ width: `${Math.max(5, Math.round(status?.progress || 0))}%` }} />
              </div>
              <div className="mt-2 text-xs text-white/60 flex items-center justify-between">
                <span>Progress</span>
                <span>{Math.round(status?.progress || 0)}%</span>
              </div>
            </div>

            {status?.status === 'completed' && (
              <div className="mt-4">
                <div className="flex items-center gap-2 text-green-300"><CheckCircle2 className="w-4 h-4" /> Completed</div>
                {metrics ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
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
                ) : (
                  <div className="mt-2 text-white/70 text-sm">Preparing summary…</div>
                )}
                {/* Completion notification handled via useEffect to avoid side-effects in render */}
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
                        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `${(results.name || 'backtest').replace(/\s+/g,'_')}_${results.backtest_id}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                      className="ml-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm"
                    >
                      Download JSON
                    </button>
                  )}
                </div>
                {!embedded && (
                  <div className="mt-4">
                    <a href="/strategy/backtests" className="inline-flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm">
                      <BarChart3 className="w-4 h-4" />
                      View in Backtests History
                    </a>
                  </div>
                )}

                {/* Visuals: equity sparkline and trades table if available */}
                {results && (
                  <div className="mt-5 grid grid-cols-1 gap-4">
                    <EquitySparkline results={results} />
                    <TradesTable results={results} />
                  </div>
                )}
              </div>
            )}

            {status?.status === 'error' && (
              <div className="mt-4 text-red-300 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Error running backtest. Check logs.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Helpers: equity sparkline and trades table
function extractEquitySeries(res: V1BacktestResultsResponse): number[] | null {
  const tryArray = (v: any): number[] | null => {
    if (!v) return null;
    if (Array.isArray(v) && v.length > 0) {
      if (typeof v[0] === 'number') return v as number[];
      if (typeof v[0] === 'object') {
        // common shapes: { y } or { value } or [t, y]
        const arr = (v as any[])
          .map((p: any) => (typeof p === 'number' ? p : (p?.y ?? p?.value ?? (Array.isArray(p) ? p[1] : null))))
          .filter((n: any) => typeof n === 'number');
        return arr.length ? arr : null;
      }
    }
    return null;
  };
  // 1) metrics.equity_curve or summary.equity_curve
  const m = tryArray((res as any).metrics?.equity_curve) || tryArray((res as any).summary?.equity_curve);
  if (m) return m;
  // 2) charts[] find something equity-like
  if (Array.isArray(res.charts)) {
    const equityChart = res.charts.find((c: any) => {
      const name = (c?.id || c?.name || '').toString().toLowerCase();
      return name.includes('equity');
    });
    if (equityChart) {
      return tryArray((equityChart as any).data || (equityChart as any).series || (equityChart as any).values);
    }
  }
  return null;
}

const EquitySparkline: React.FC<{ results: V1BacktestResultsResponse }> = ({ results }) => {
  const data = React.useMemo(() => extractEquitySeries(results), [results]);
  if (!data || data.length < 2) return (
    <div className="glass-card p-4 text-white/70">No equity curve data available.</div>
  );
  const width = 640;
  const height = 120;
  const padding = 8;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = (width - padding * 2) / (data.length - 1);
  const points = data.map((v, i) => {
    const x = padding + i * stepX;
    const y = padding + (height - padding * 2) * (1 - (v - min) / span);
    return `${x},${y}`;
  }).join(' ');
  const last = data[data.length - 1];
  const first = data[0];
  const pct = ((last - first) / (first || 1)) * 100;
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-white font-semibold">Equity Curve</div>
        <div className={pct >= 0 ? 'text-green-300' : 'text-red-300'}>{pct.toFixed(2)}%</div>
      </div>
      <svg width={width} height={height} className="w-full h-[120px]">
        <polyline fill="none" stroke="#60a5fa" strokeWidth="2" points={points} />
      </svg>
    </div>
  );
};

function pick(obj: any, keys: string[]): any {
  for (const k of keys) {
    if (obj && obj[k] != null) return obj[k];
  }
  return undefined;
}

const TradesTable: React.FC<{ results: V1BacktestResultsResponse }> = ({ results }) => {
  const rows = (results.trades || []).slice(0, 20);
  if (!rows.length) return (
    <div className="glass-card p-4 text-white/70">No trades available.</div>
  );
  return (
    <div className="glass-card p-4">
      <div className="text-white font-semibold mb-2">Trades (first {rows.length})</div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="text-white/60">
              <th className="px-2 py-1">Time</th>
              <th className="px-2 py-1">Symbol</th>
              <th className="px-2 py-1">Side</th>
              <th className="px-2 py-1">Qty</th>
              <th className="px-2 py-1">Price</th>
              <th className="px-2 py-1">PnL</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t: any, i: number) => {
              const ts = pick(t, ['date','time','timestamp','exit_time','entry_time']);
              const sym = pick(t, ['symbol','ticker','asset']) ?? (Array.isArray(results.summary?.symbols) ? results.summary.symbols[0] : undefined);
              const side = (pick(t, ['side','action','type']) || '').toString().toUpperCase();
              const qty = Number(pick(t, ['quantity','qty','size','shares']) || 0);
              const price = Number(pick(t, ['price','fill_price','entry_price','avg_price']) || 0);
              const pnl = Number(pick(t, ['pnl','profit','pl','p_l']) || 0);
              return (
                <tr key={i} className="border-t border-white/10 text-white/80">
                  <td className="px-2 py-1 font-mono text-xs">{ts ? new Date(ts).toLocaleString() : '-'}</td>
                  <td className="px-2 py-1">{sym ?? '-'}</td>
                  <td className={`px-2 py-1 ${/SELL|SHORT|EXIT/.test(side) ? 'text-red-300' : 'text-green-300'}`}>{side || '-'}</td>
                  <td className="px-2 py-1">{qty || '-'}</td>
                  <td className="px-2 py-1">{price ? price.toFixed(2) : '-'}</td>
                  <td className={`px-2 py-1 ${pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>{pnl ? pnl.toFixed(2) : '-'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BacktestRunner;
