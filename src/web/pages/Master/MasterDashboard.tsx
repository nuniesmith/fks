import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { masterMonitorApi, AggregateHealthSummary } from '../../services/MasterMonitorApi';
import { mapStatus, summarize } from './masterHelpers';

interface ActionState { running: boolean; message?: string; success?: boolean; lastTs?: string; }

const statusColor: Record<string,string> = { healthy: 'bg-emerald-500/20 text-emerald-300', warning: 'bg-amber-500/20 text-amber-300', error: 'bg-rose-500/20 text-rose-300', offline: 'bg-slate-600/40 text-slate-300', critical: 'bg-rose-600/30 text-rose-200', degraded: 'bg-amber-600/30 text-amber-200' };

// (Count/derive helpers now in masterHelpers.ts)

const MasterDashboard: React.FC = () => {
  const [summary, setSummary] = useState<AggregateHealthSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionStates, setActionStates] = useState<Record<string,ActionState>>({});
  const [eventLog, setEventLog] = useState<Array<{ ts: string; type: string; service?: string; msg?: string }>>([]);
  const [showEvents, setShowEvents] = useState(true);
  const [filterQuery, setFilterQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all'|'healthy'|'warning'|'error'|'offline'>('all');
  const [apiKeyDraft, setApiKeyDraft] = useState(masterMonitorApi.getApiKey()||'');
  const configured = masterMonitorApi.isConfigured();
  const wsRef = useRef<WebSocket | null>(null);

  const pushEvent = useCallback((ev: { ts?: string; type: string; service?: string; msg?: string }) => {
    setEventLog(prev => [{ ts: ev.ts || new Date().toISOString(), type: ev.type, service: ev.service, msg: ev.msg }, ...prev].slice(0,400));
  }, []);

  const applyAggregate = useCallback((services: AggregateHealthSummary['services']) => {
    setSummary(summarize(services));
  }, []);

  const load = useCallback(async () => {
    if (!configured) return;
    setLoading(true); setError(null);
    try {
      const data = await masterMonitorApi.getAggregate();
      // Normalize statuses
      const services = data.services.map(s => ({ ...s, status: mapStatus(s.status || s.rawStatus) }));
      applyAggregate(services);
    } catch (e:any) { setError(e.message || 'Failed to load aggregate'); }
    finally { setLoading(false); }
  }, [configured, applyAggregate]);

  // Initial load + periodic fallback poll
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  // Reconnection backoff state
  const reconnectAttempts = useRef(0);

  // WebSocket live updates
  useEffect(() => {
    if (!configured) return;
    const base = (masterMonitorApi as any).base as string | undefined;
    if (!base) return;

    let closedManually = false;
    function connect() {
      const wsUrl = base.replace(/^http/, 'ws') + '/ws';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => {
        reconnectAttempts.current = 0;
        ws.send(JSON.stringify({ command_type: 'subscribe_events' }));
        pushEvent({ type:'ws_open', msg:'WebSocket connected' });
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          switch (msg.type) {
            case 'initial':
            case 'update': {
              if (msg.services) {
                const services = msg.services.map((s: any) => ({ id: s.id, name: s.name, status: mapStatus(s.status || s.rawStatus), rawStatus: s.status || s.rawStatus, lastCheck: s.last_check, responseTimeMs: s.response_time_ms, critical: s.critical }));
                applyAggregate(services);
              }
              break;
            }
            case 'event': {
              pushEvent({ type: msg.event_type || 'event', service: msg.service_id, msg: msg.message, ts: msg.timestamp });
              break; }
            case 'restart_result': {
              const sid = msg.service_id;
              setActionStates(a => ({ ...a, [sid]: { running: false, success: msg.success, message: msg.success? 'restarted':'failed', lastTs: msg.timestamp } }));
              pushEvent({ type: 'restart_result', service: sid, msg: msg.success? 'success':'failed', ts: msg.timestamp });
              load();
              break; }
            default: break;
          }
        } catch { /* ignore */ }
      };
      ws.onerror = () => { pushEvent({ type:'ws_error', msg:'WebSocket error' }); };
      ws.onclose = () => {
        pushEvent({ type:'ws_close', msg:'WebSocket closed' });
        if (!closedManually) {
          const attempt = reconnectAttempts.current + 1;
          reconnectAttempts.current = attempt;
          const delay = Math.min(15000, 500 * Math.pow(2, attempt));
          pushEvent({ type:'ws_reconnect', msg:`Reconnecting in ${Math.round(delay/1000)}s (attempt ${attempt})` });
          setTimeout(connect, delay);
        }
      };
    }
    connect();
    return () => { closedManually = true; wsRef.current?.close(); };
  }, [configured, applyAggregate, load, pushEvent]);

  // Actions
  const restart = useCallback(async (id: string) => {
    setActionStates(a => ({ ...a, [id]: { running: true, message: 'restarting' } }));
    pushEvent({ type:'restart', service:id, msg:'requested' });
    // optimistic status -> warning
    setSummary(prev => prev ? { ...prev, services: prev.services.map(s => s.id===id? { ...s, status: 'warning' }: s) } : prev);
    try {
      const res = await masterMonitorApi.restartService(id);
      setActionStates(a => ({ ...a, [id]: { running:false, success: res.success, message: res.message, lastTs: res.timestamp } }));
      pushEvent({ type:'restart_api', service:id, msg: res.message, ts: res.timestamp });
      // Let websocket update final status; fallback refresh
      setTimeout(load, 2500);
    } catch (e:any) {
      setActionStates(a => ({ ...a, [id]: { running:false, success:false, message: e.message || 'error' } }));
      pushEvent({ type:'restart_error', service:id, msg: e.message });
    }
  }, [pushEvent, load]);

  const compose = useCallback(async (action: string) => {
    const key = `compose:${action}`;
    setActionStates(a => ({ ...a, [key]: { running:true, message:'running' } }));
    pushEvent({ type:'compose', msg: action });
    try {
      const res = await masterMonitorApi.compose(action);
      const tail = (res.stdout || '').split(/\n/).slice(-3).join(' | ').trim();
      setActionStates(a => ({ ...a, [key]: { running:false, success:res.success, message: tail || (res.success? 'ok':'fail') } }));
      pushEvent({ type:'compose_result', msg: `${action} ${res.success? 'ok':'fail'}` });
      if (['up','restart','down','build','pull'].includes(action)) setTimeout(load, 3000);
    } catch (e:any) {
      setActionStates(a => ({ ...a, [key]: { running:false, success:false, message:e.message || 'error' } }));
      pushEvent({ type:'compose_error', msg:`${action}: ${e.message}` });
    }
  }, [pushEvent, load]);

  const filteredServices = useMemo(() => {
    if (!summary) return [] as AggregateHealthSummary['services'];
    const q = filterQuery.trim().toLowerCase();
    return summary.services.filter(s => {
      const qOk = !q || s.id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q);
      const statusOk = statusFilter==='all' || s.status === statusFilter;
      return qOk && statusOk;
    });
  }, [summary, filterQuery, statusFilter]);

  if (!configured) {
    return <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-4">Master Orchestration</h1>
      <div className="glass-card p-6 space-y-4">
        <p className="text-white/80">Central monitor URL not configured.</p>
        <ol className="list-decimal list-inside text-white/70 space-y-1 text-sm">
          <li>Start the Rust fks_master service (default port 9090).</li>
          <li>Set <code className="px-1 bg-black/30 rounded">VITE_FKS_MONITOR_URL</code> in your web env (e.g. http://localhost:9090).</li>
          <li>Reload this page.</li>
        </ol>
      </div>
    </div>;
  }

  // Detail modal
  const [detailId, setDetailId] = useState<string | null>(null);
  const detailService = summary?.services.find(s => s.id === detailId);

  const overallColor = summary?.overallStatus === 'healthy'
    ? 'from-emerald-600/40 via-emerald-500/20'
    : summary?.overallStatus === 'degraded'
      ? 'from-amber-600/40 via-amber-500/10'
      : 'from-rose-600/40 via-rose-500/10';

  return (
    <div className="p-6 max-w-[1600px] mx-auto">
      {summary && (
        <div className={`mb-6 rounded-lg border border-white/10 bg-gradient-to-r ${overallColor} to-transparent px-4 py-3 flex items-center justify-between`}> 
          <div className="flex items-center gap-4">
            <span className="text-sm font-semibold uppercase tracking-wide text-white/70">Overall</span>
            <span className="px-3 py-1 rounded text-xs font-medium bg-white/10 text-white">{summary.overallStatus}</span>
            <span className="text-white/50 text-xs">Updated {new Date(summary.lastUpdate).toLocaleTimeString()}</span>
          </div>
          <button onClick={load} disabled={loading} className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-white/70 disabled:opacity-40">Refresh</button>
        </div>
      )}
      <div className="flex flex-wrap items-start gap-6 mb-6">
        <div className="flex-1 min-w-[260px] glass-card p-5">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-white">Master Orchestration</h1>
            <button onClick={load} disabled={loading} className="px-3 py-1 rounded bg-white/10 hover:bg-white/20 text-white text-sm disabled:opacity-50">{loading? 'Refreshing…':'Refresh'}</button>
          </div>
          {error && <div className="text-sm text-rose-300 mb-2">{error}</div>}
          {summary && <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            {['overallStatus','totalServices','healthyServices','warningServices','errorServices','offlineServices'].map(key => (
              <div key={key} className="bg-white/5 rounded p-3">
                <div className="text-white/60 uppercase tracking-wide text-[10px] mb-1">{key.replace(/([A-Z])/g,' $1')}</div>
                <div className="text-white font-semibold text-lg">{(summary as any)[key]}</div>
              </div>
            ))}
          </div>}
          <div className="mt-4 border-t border-white/10 pt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs uppercase tracking-wide text-white/50">API Key</span>
              {masterMonitorApi.getApiKey() && <span className="text-[10px] text-emerald-400">set</span>}
            </div>
            <div className="flex gap-2">
              <input value={apiKeyDraft} onChange={e=>setApiKeyDraft(e.target.value)} placeholder="x-api-key" className="flex-1 bg-white/10 focus:bg-white/15 text-white placeholder-white/30 text-xs rounded px-2 py-1 outline-none" />
              <button onClick={()=>{ masterMonitorApi.setApiKey(apiKeyDraft); load(); }} className="px-2 py-1 rounded bg-indigo-500/40 hover:bg-indigo-500/60 text-white text-xs">Save</button>
            </div>
          </div>
        </div>
        <div className="glass-card p-5 w-full md:w-auto flex-1">
          <h2 className="text-white font-semibold mb-3 text-sm uppercase tracking-wide">Compose Actions</h2>
          <div className="flex flex-wrap gap-2">
            {['ps','build','pull','up','restart','down'].map(a => {
              const st = actionStates[`compose:${a}`];
              return (
                <button key={a} onClick={() => compose(a)} disabled={st?.running} className="px-3 py-1.5 rounded text-xs font-medium bg-indigo-500/30 hover:bg-indigo-500/50 text-indigo-100 disabled:opacity-50">
                  {st?.running? '…': a}
                </button>
              );
            })}
          </div>
          <div className="mt-3 space-y-1 max-h-32 overflow-auto text-[11px] font-mono text-white/70">
            {Object.entries(actionStates).filter(([k])=>k.startsWith('compose:')).slice(-7).reverse().map(([k,v]) => (
              <div key={k} className={v.success===false? 'text-rose-300':''}>{k.split(':')[1]}: {v.message || (v.running? 'running':'done')}</div>
            ))}
          </div>
        </div>
        <div className="glass-card p-5 w-full md:w-[340px] flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-white font-semibold text-sm uppercase tracking-wide">Events</h2>
            <button onClick={()=>setShowEvents(s=>!s)} className="text-xs text-white/60 hover:text-white">{showEvents? 'Hide':'Show'}</button>
          </div>
          {showEvents && <>
            <div className="flex gap-2">
              <input value={filterQuery} onChange={e=>setFilterQuery(e.target.value)} placeholder="Filter services" className="flex-1 bg-white/10 focus:bg-white/15 text-white placeholder-white/40 text-xs rounded px-2 py-1 outline-none" />
              <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value as any)} className="bg-white/10 text-white text-xs rounded px-1 py-1">
                {['all','healthy','warning','error','offline'].map(s=> <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="text-[10px] font-mono max-h-40 overflow-auto leading-relaxed space-y-1 pr-1">
              {eventLog.slice(0,50).map((ev,i) => (
                <div key={i} className="truncate"><span className="text-white/40">{new Date(ev.ts).toLocaleTimeString()}</span> <span className="text-white/70">[{ev.type}]</span>{ev.service && <span className="text-white/60"> {ev.service}</span>} {ev.msg && <span className="text-white/50">- {ev.msg}</span>}</div>
              ))}
              {eventLog.length===0 && <div className="text-white/40">No events yet</div>}
            </div>
          </>}
        </div>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    {filteredServices.map(s => {
          const st = actionStates[s.id];
          return (
      <div key={s.id} className="glass-card p-4 flex flex-col gap-3 cursor-pointer" onClick={() => setDetailId(s.id)}>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-white/90 text-sm truncate" title={s.name}>{s.name}</h3>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${statusColor[s.status]||'bg-slate-500/30 text-slate-200'}`}>{s.status}</span>
              </div>
              <div className="flex flex-wrap gap-2 text-[10px] text-white/60">
                {s.responseTimeMs!=null && <span>latency <span className="text-white/80 font-semibold">{s.responseTimeMs}ms</span></span>}
                {s.critical && <span className="text-rose-300 font-semibold">critical</span>}
              </div>
              <div className="mt-auto flex items-center gap-2">
                <button onClick={()=>restart(s.id)} disabled={st?.running} className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-white/80 text-[11px] disabled:opacity-40">{st?.running? 'Restarting…':'Restart'}</button>
                {st && !st.running && <span className={`text-[10px] ${st.success? 'text-emerald-300':'text-rose-300'}`}>{st.message}</span>}
              </div>
            </div>
          );
        })}
        {filteredServices.length===0 && <div className="text-white/50 text-sm col-span-full">No services match filter.</div>}
      </div>
      {detailService && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setDetailId(null)}>
          <div className="bg-gray-900/90 border border-white/10 rounded-xl p-6 w-full max-w-lg mx-4 relative" onClick={e=>e.stopPropagation()}>
            <button className="absolute top-2 right-2 text-white/50 hover:text-white" onClick={()=>setDetailId(null)}>✕</button>
            <h2 className="text-xl font-semibold text-white mb-2">{detailService.name}</h2>
            <div className="flex gap-3 text-xs mb-4">
              <span className={`px-2 py-0.5 rounded ${statusColor[detailService.status]||'bg-slate-600/40 text-slate-200'}`}>{detailService.status}</span>
              {detailService.responseTimeMs!=null && <span className="text-white/60">latency <span className="text-white/80 font-semibold">{detailService.responseTimeMs}ms</span></span>}
              {detailService.critical && <span className="text-rose-300 font-semibold">critical</span>}
            </div>
            <div className="text-xs text-white/60 space-y-1 max-h-60 overflow-auto pr-1">
              <div>Service ID: <code className="bg-white/5 px-1 rounded text-white/70">{detailService.id}</code></div>
              {detailService.lastCheck && <div>Last Check: {new Date(detailService.lastCheck).toLocaleTimeString()}</div>}
              <div>Raw Status: <code className="bg-white/5 px-1 rounded text-white/70">{detailService.rawStatus || detailService.status}</code></div>
            </div>
            <div className="mt-4 flex justify-end">
              <button className="text-xs px-3 py-1 rounded bg-white/10 hover:bg-white/20 text-white/80" onClick={()=>restart(detailService.id)}>Restart</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MasterDashboard;
