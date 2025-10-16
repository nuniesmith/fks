import React, { useEffect, useState } from 'react';
import { Plus, Save, Trash2, Edit, Play, Zap } from 'lucide-react';
import { useMilestones } from '@/context/MilestoneContext';
import { runBacktest } from '@/services/backtest';
import StrategyOptimizationModal from './StrategyOptimizationModal';

interface Strategy { id: string; name: string; description: string; language: 'python' | 'javascript' | 'pinescript'; code: string; parameters: Record<string, any>; backtest: { winRate: number; totalReturn: number; maxDrawdown: number; sharpeRatio: number }; isActive: boolean; lastModified: string; }

const StrategyDevelopment: React.FC = () => {
  const { awardExperience } = useMilestones();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selected, setSelected] = useState<Strategy | null>(null);
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<'code' | 'parameters' | 'backtest'>('code');
  const [optimizing, setOptimizing] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const mock: Strategy[] = [{ id: '1', name: 'Momentum Scalper', description: 'Quick momentum scalps', language: 'python', code: '# strategy code', parameters: { lookback: 14 }, backtest: { winRate: 65, totalReturn: 10, maxDrawdown: -3, sharpeRatio: 1.4 }, isActive: true, lastModified: new Date().toISOString() }];
    setStrategies(mock); setSelected(mock[0]);
  }, []);

  const createStrategy = () => {
    const s: Strategy = { id: Date.now().toString(), name: 'New Strategy', description: 'Describe strategy', language: 'python', code: '# Write code', parameters: {}, backtest: { winRate: 0, totalReturn: 0, maxDrawdown: 0, sharpeRatio: 0 }, isActive: false, lastModified: new Date().toISOString() };
    setStrategies(prev => [...prev, s]); setSelected(s); setEditing(true);
  };
  const save = () => { if (!selected) return; setStrategies(prev => prev.map(p => p.id === selected.id ? { ...selected, lastModified: new Date().toISOString() } : p)); setEditing(false); };
  const run = async () => { if (!selected) return; setRunning(true); try { const res = await runBacktest({ code: selected.code, language: selected.language, parameters: selected.parameters, asset: 'ES', exchange: 'CME', reducedParams: true } as any); setStrategies(prev => prev.map(p => p.id === selected.id ? { ...p, backtest: res, lastModified: new Date().toISOString() } : p)); awardExperience('STRATEGY_VALIDATED'); setTab('backtest'); } catch { /* ignore */ } finally { setRunning(false); } };

  return (
    <div className="space-y-6 p-6" data-testid="strategy-development">
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 flex items-center justify-between">
        <div><h1 className="text-2xl font-bold text-white">Strategy Development</h1><p className="text-gray-400 text-sm">Create, test, and optimize automated strategies</p></div>
        <div className="flex gap-2">
          <button onClick={() => setOptimizing(true)} className="px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded text-white text-sm flex items-center gap-1"><Zap className="w-4 h-4"/>Optimize</button>
          <button onClick={createStrategy} className="px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-white text-sm flex items-center gap-1"><Plus className="w-4 h-4"/>New</button>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 bg-gray-800 rounded-lg border border-gray-700">
          <div className="p-3 border-b border-gray-700 text-sm font-medium text-white">Strategies</div>
          <div className="p-3 space-y-2 max-h-[60vh] overflow-y-auto">
            {strategies.map(s => (
              <div key={s.id} onClick={()=>setSelected(s)} className={`p-2 rounded cursor-pointer text-xs ${selected?.id===s.id ? 'bg-blue-600/40 border border-blue-500/40':'bg-gray-700/40 hover:bg-gray-700/60 border border-transparent'}`}> <div className="flex justify-between"><span className="text-white font-medium">{s.name}</span><span className="px-1 py-0.5 rounded bg-blue-500/20 text-blue-300">{s.language}</span></div><div className="text-gray-400 truncate">{s.description}</div></div>
            ))}
          </div>
        </div>
        <div className="lg:col-span-3 bg-gray-800 rounded-lg border border-gray-700 min-h-[60vh] flex flex-col">
          {!selected && <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Select or create a strategy.</div>}
          {selected && (
            <>
              <div className="flex border-b border-gray-700 text-xs">
                {['code','parameters','backtest'].map(t => <button key={t} onClick={()=>setTab(t as any)} className={`px-4 py-2 font-medium ${tab===t ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/40':'text-gray-400 hover:text-white'}`}>{t}</button>)}
                <div className="ml-auto flex items-center gap-2 pr-3">
                  <button onClick={()=>setEditing(e=>!e)} className={`p-1 rounded ${editing?'bg-blue-600 text-white':'bg-gray-700 text-gray-300 hover:text-white'}`}><Edit className="w-4 h-4"/></button>
                  <button onClick={save} disabled={!editing} className="p-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded text-white"><Save className="w-4 h-4"/></button>
                  <button onClick={()=> setStrategies(prev => prev.filter(p=>p.id!==selected.id))} className="p-1 bg-red-600 hover:bg-red-700 rounded text-white" aria-label="delete"><Trash2 className="w-4 h-4"/></button>
                </div>
              </div>
              <div className="flex-1 p-4 space-y-4 overflow-auto">
                {tab==='code' && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs">
                      <select value={selected.language} disabled={!editing} onChange={e=>setSelected({...selected, language: e.target.value as any})} className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white">
                        <option value="python">Python</option>
                        <option value="javascript">JavaScript</option>
                        <option value="pinescript">Pine Script</option>
                      </select>
                      <button onClick={run} disabled={running} className="flex items-center gap-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded text-white text-xs"><Play className="w-3 h-3"/>{running ? 'Running…':'Backtest'}</button>
                      <div className="flex items-center gap-3 text-[10px] text-gray-400 ml-auto">
                        <span>Win {selected.backtest.winRate.toFixed(1)}%</span>
                        <span>Ret {selected.backtest.totalReturn.toFixed(1)}%</span>
                        <span>DD {selected.backtest.maxDrawdown.toFixed(1)}%</span>
                        <span>Sharpe {selected.backtest.sharpeRatio.toFixed(2)}</span>
                      </div>
                    </div>
                    <textarea value={selected.code} disabled={!editing} onChange={e=>setSelected({...selected, code: e.target.value})} className="w-full h-80 bg-gray-900 rounded border border-gray-700 px-3 py-2 text-xs font-mono text-white focus:outline-none" />
                  </div>
                )}
                {tab==='parameters' && (
                  <div className="space-y-3 text-xs">
                    {Object.entries(selected.parameters).map(([k,v]) => (
                      <div key={k} className="flex items-center gap-2">
                        <label className="w-32 text-gray-400 capitalize">{k}</label>
                        <input value={v as any} disabled={!editing} onChange={e=>setSelected({...selected, parameters: {...selected.parameters, [k]: e.target.value}})} className="flex-1 bg-gray-900 rounded border border-gray-700 px-2 py-1 text-white" />
                      </div>
                    ))}
                    {editing && <button onClick={()=>{ const name = prompt('Param name'); if(name) setSelected({...selected, parameters: {...selected.parameters, [name]: ''}}); }} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-white text-xs flex items-center gap-1"><Plus className="w-3 h-3"/>Add Param</button>}
                  </div>
                )}
                {tab==='backtest' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="bg-gray-700/30 rounded p-3"><div className="text-gray-400">Win Rate</div><div className="text-green-400 text-lg font-bold">{selected.backtest.winRate.toFixed(1)}%</div></div>
                    <div className="bg-gray-700/30 rounded p-3"><div className="text-gray-400">Return</div><div className={selected.backtest.totalReturn>=0?'text-green-400':'text-red-400'}>{selected.backtest.totalReturn.toFixed(1)}%</div></div>
                    <div className="bg-gray-700/30 rounded p-3"><div className="text-gray-400">Drawdown</div><div className="text-red-400">{selected.backtest.maxDrawdown.toFixed(1)}%</div></div>
                    <div className="bg-gray-700/30 rounded p-3"><div className="text-gray-400">Sharpe</div><div className={selected.backtest.sharpeRatio>=1.5?'text-green-400':'text-yellow-400'}>{selected.backtest.sharpeRatio.toFixed(2)}</div></div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
      <StrategyOptimizationModal open={optimizing} onClose={()=>setOptimizing(false)} code={selected?.code||''} language={(selected?.language||'python') as any} parameters={selected?.parameters||{}} onOptimized={p => { if (!selected) return; setSelected({...selected, parameters: p}); }} />
    </div>
  );
};
export default StrategyDevelopment;
