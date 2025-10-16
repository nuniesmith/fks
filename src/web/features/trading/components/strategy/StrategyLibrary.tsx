// Feature-slice StrategyLibrary (migrated & trimmed)
import React, { useEffect, useState } from 'react';
import { Plus, Pause, Edit, Trash2, Copy, Brain, Users, CheckCircle, Clock, BarChart3 } from 'lucide-react';

interface SimpleStrategy {
  id: string; name: string; description: string; code: string;
  type: 'entry' | 'exit' | 'filter' | 'risk';
  parameters: Record<string, unknown>;
  performance: { winRate: number; avgReturn: number; sharpeRatio: number };
  status: 'active' | 'inactive' | 'testing';
}
interface ComplexStrategy {
  id: string; name: string; description: string;
  simpleStrategies: string[]; combinationLogic: 'AND' | 'OR' | 'WEIGHTED' | 'SEQUENTIAL';
  weights?: Record<string, number>; accounts: string[]; environments: ('simulation' | 'live')[];
  performance: { totalTrades: number; winRate: number; totalReturn: number; sharpeRatio: number; maxDrawdown: number };
  status: 'active' | 'inactive' | 'testing'; lastBacktest: Date;
}
interface TradingAccount { id: string; name: string; type: 'futures' | 'crypto' | 'stocks'; provider: string; balance: number; enabled: boolean; strategies: string[]; }

const StrategyLibrary: React.FC = () => {
  const [simpleStrategies, setSimpleStrategies] = useState<SimpleStrategy[]>([]);
  const [complexStrategies, setComplexStrategies] = useState<ComplexStrategy[]>([]);
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [selectedView, setSelectedView] = useState<'simple' | 'complex' | 'deployment'>('simple');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => { loadStrategies(); loadAccounts(); }, []);

  const loadStrategies = () => {
    const sampleSimple: SimpleStrategy[] = [
      { id: 'sma-crossover', name: 'SMA Crossover Entry', description: 'Enter long when fast SMA crosses above slow SMA', code: '...', type: 'entry', parameters: {}, performance: { winRate: 0.65, avgReturn: 0.024, sharpeRatio: 1.2 }, status: 'active' },
      { id: 'rsi-filter', name: 'RSI Oversold Filter', description: 'Only trade when RSI is below 30 (oversold)', code: '...', type: 'filter', parameters: {}, performance: { winRate: 0.72, avgReturn: 0.018, sharpeRatio: 1.4 }, status: 'active' }
    ];
    const sampleComplex: ComplexStrategy[] = [
      { id: 'mean-reversion-suite', name: 'Mean Reversion Suite', description: 'Combination of core mean reversion components', simpleStrategies: ['sma-crossover','rsi-filter'], combinationLogic: 'AND', accounts: ['futures-1'], environments: ['simulation'], performance: { totalTrades: 156, winRate: 0.71, totalReturn: 0.324, sharpeRatio: 1.8, maxDrawdown: 0.12 }, status: 'active', lastBacktest: new Date() }
    ];
    setSimpleStrategies(sampleSimple); setComplexStrategies(sampleComplex);
  };
  const loadAccounts = () => setAccounts([{ id: 'futures-1', name: 'Rithmic Futures - Main', type: 'futures', provider: 'rithmic', balance: 50000, enabled: true, strategies: ['mean-reversion-suite'] }]);

  const renderSimple = () => (
    <div className="space-y-4" data-testid="simple-strategies">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-white">Simple Strategies</h2>
        <button onClick={() => setShowCreateModal(true)} className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm"><Plus className="w-4 h-4" /><span>New</span></button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {simpleStrategies.map(s => (
          <div key={s.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex justify-between mb-3"><h3 className="font-semibold text-white text-sm">{s.name}</h3><span className="px-2 py-1 rounded text-[10px] bg-blue-500/20 text-blue-400">{s.type}</span></div>
            <p className="text-xs text-gray-400 mb-3 line-clamp-3">{s.description}</p>
            <div className="grid grid-cols-3 text-center text-[10px] gap-2 mb-2">
              <div><div className="text-green-400 font-medium">{(s.performance.winRate*100).toFixed(1)}%</div><div className="text-gray-500">Win</div></div>
              <div><div className="text-blue-400 font-medium">{(s.performance.avgReturn*100).toFixed(1)}%</div><div className="text-gray-500">Ret</div></div>
              <div><div className="text-purple-400 font-medium">{s.performance.sharpeRatio.toFixed(1)}</div><div className="text-gray-500">Sharpe</div></div>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-1 text-xs text-gray-400">{s.status === 'active' ? <CheckCircle className="w-3 h-3 text-green-400"/> : s.status === 'testing' ? <Clock className="w-3 h-3 text-yellow-400"/> : <Pause className="w-3 h-3 text-gray-400"/>}<span className="capitalize">{s.status}</span></div>
              <div className="flex items-center gap-1 opacity-70">
                <button className="p-1 hover:bg-gray-700 rounded" aria-label="edit"><Edit className="w-3 h-3"/></button>
                <button className="p-1 hover:bg-gray-700 rounded" aria-label="clone"><Copy className="w-3 h-3"/></button>
                <button className="p-1 hover:bg-gray-700 rounded" aria-label="delete"><Trash2 className="w-3 h-3"/></button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderComplex = () => (
    <div className="space-y-4" data-testid="complex-strategies">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-white">Complex Strategies</h2>
        <button className="flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white text-sm"><Brain className="w-4 h-4"/><span>Combine</span></button>
      </div>
      <div className="space-y-4">
        {complexStrategies.map(s => (
          <div key={s.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex justify-between items-start mb-2"><div><h3 className="text-white font-semibold text-sm">{s.name}</h3><p className="text-gray-400 text-xs">{s.description}</p></div><span className="px-2 py-1 rounded-full text-[10px] bg-green-500/20 text-green-400">{s.status}</span></div>
            <div className="grid grid-cols-5 gap-2 mb-3 text-center text-[10px]">
              <div><div className="text-green-400 font-semibold">{s.performance.totalTrades}</div><div className="text-gray-500">Trades</div></div>
              <div><div className="text-blue-400 font-semibold">{(s.performance.winRate*100).toFixed(1)}%</div><div className="text-gray-500">Win</div></div>
              <div><div className="text-purple-400 font-semibold">{(s.performance.totalReturn*100).toFixed(1)}%</div><div className="text-gray-500">Return</div></div>
              <div><div className="text-orange-400 font-semibold">{s.performance.sharpeRatio.toFixed(1)}</div><div className="text-gray-500">Sharpe</div></div>
              <div><div className="text-red-400 font-semibold">{(s.performance.maxDrawdown*100).toFixed(1)}%</div><div className="text-gray-500">DD</div></div>
            </div>
            <div className="flex items-center justify-between text-xs text-gray-400">
              <div className="flex flex-wrap gap-1 items-center"><span>Components:</span>{s.simpleStrategies.map(id => <span key={id} className="px-1 py-0.5 bg-blue-500/20 text-blue-300 rounded text-[10px]">{id}</span>)}</div>
              <div className="flex gap-2"><button className="flex items-center gap-1 px-2 py-1 bg-green-600 hover:bg-green-700 rounded text-white text-[10px]"><BarChart3 className="w-3 h-3"/>Backtest</button><button className="flex items-center gap-1 px-2 py-1 bg-blue-600 hover:bg-blue-700 rounded text-white text-[10px]"><Users className="w-3 h-3"/>Deploy</button></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderDeployment = () => (
    <div className="space-y-4" data-testid="deployment-overview">
      <h2 className="text-xl font-semibold text-white">Strategy Deployment</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-white font-semibold mb-3 text-sm">Accounts</h3>
            <div className="space-y-2 text-xs">
              {accounts.map(a => (
                <div key={a.id} className="flex items-center justify-between p-2 bg-gray-700/40 rounded">
                  <div className="flex items-center gap-2"><div className={`w-2 h-2 rounded-full ${a.enabled ? 'bg-green-400':'bg-gray-500'}`}></div><span className="text-white">{a.name}</span></div>
                  <div className="text-gray-400">{a.strategies.length} strat</div>
                </div>
              ))}
            </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-white font-semibold mb-3 text-sm">Assignments</h3>
          <div className="space-y-2 text-xs">
            {complexStrategies.map(s => (
              <div key={s.id} className="p-2 bg-gray-700/40 rounded">
                <div className="font-medium text-white mb-1 text-sm">{s.name}</div>
                <div className="flex flex-wrap gap-1">{s.accounts.map(acc => <span key={acc} className="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded text-[10px]">{acc}</span>)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-6 space-y-6" data-testid="strategy-library">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Strategy Library</h1>
          <p className="text-gray-400 mt-1 text-sm">Build, combine, and deploy trading strategies</p>
        </div>
        <div className="flex gap-2">
          {['simple','complex','deployment'].map(v => (
            <button key={v} onClick={() => setSelectedView(v as any)} className={`px-4 py-2 rounded-lg text-sm transition-colors ${selectedView===v ? 'bg-blue-600 text-white':'bg-gray-700 text-gray-300'}`}>{v.charAt(0).toUpperCase()+v.slice(1)}</button>
          ))}
        </div>
      </div>
      {selectedView === 'simple' && renderSimple()}
      {selectedView === 'complex' && renderComplex()}
      {selectedView === 'deployment' && renderDeployment()}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-gray-800 rounded-xl p-6 w-full max-w-md space-y-4">
            <h2 className="text-white font-semibold text-lg">Create Strategy (placeholder)</h2>
            <p className="text-xs text-gray-400">Modal content TBD.</p>
            <button onClick={()=>setShowCreateModal(false)} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white text-sm">Close</button>
          </div>
        </div>
      )}
    </div>
  );
};
export default StrategyLibrary;
