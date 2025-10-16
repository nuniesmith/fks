// Moved from components/TradingDashboard/TradingDashboard.tsx to features/trading/components/dashboard
import { TrendingUp, TrendingDown, DollarSign, Activity, AlertTriangle, Target } from 'lucide-react';
import PageContainer from '@layout/PageContainer';
import React, { useState } from 'react';

import { useTradingEnv } from '@/context/TradingEnvContext';
import StrategyAssignments from '../strategy/StrategyAssignments';

interface TradingDashboardProps { userAccounts?: any[] }

const TradingDashboard: React.FC<TradingDashboardProps> = ({ userAccounts }) => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1D');
  const { focus, setFocus, sim, live, start, pause, stop, readiness, assetsSource, assetsWarning, hasActiveAssetsRoute } = useTradingEnv();
  const showAssetsWarning = assetsSource !== 'api' && hasActiveAssetsRoute !== false; // suppress if route known absent

  const mockTradingData = {
    activeTrades: [
      { id: 1, pair: 'EUR/USD', type: 'LONG', entry: 1.0850, current: 1.0872, pnl: 220, pnlPercent: 2.03 },
      { id: 2, pair: 'GBP/JPY', type: 'SHORT', entry: 188.45, current: 187.12, pnl: 330, pnlPercent: 0.71 },
      { id: 3, pair: 'USD/CAD', type: 'LONG', entry: 1.3420, current: 1.3401, pnl: -95, pnlPercent: -0.14 },
    ],
    dailyStats: { totalPnL: 455, winRate: 67, totalTrades: 12, bestTrade: 480, worstTrade: -120 },
    accountOverview: { totalBalance: 15420, availableMargin: 12800, usedMargin: 2620, equity: 15875 }
  };
  const timeframes = ['1M', '5M', '15M', '1H', '4H', '1D', '1W'];

  return (
    <PageContainer>
        <div className="mb-8 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Active Trading</h1>
            <p className="text-white/70">Real-time trading performance and active positions</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-xs text-white/70">Env:</div>
            <div className="flex rounded overflow-hidden border border-white/20">
              <button onClick={() => setFocus('simulation')} className={`px-3 py-1 text-sm ${focus==='simulation' ? 'bg-green-600 text-white' : 'bg-white/10 text-white/70 hover:bg-white/20'}`}>Simulation</button>
              <button onClick={() => setFocus('live')} disabled={!readiness.ok} title={!readiness.ok ? 'Complete checks to enable Live' : ''} className={`px-3 py-1 text-sm ${focus==='live' ? 'bg-red-600 text-white' : 'bg-white/10 text-white/70 hover:bg-white/20'} ${!readiness.ok ? 'opacity-50 cursor-not-allowed' : ''}`}>Live</button>
            </div>
            <div className="flex items-center gap-1 ml-2">
              {focus==='simulation' ? (
                sim.status !== 'active' ? <button onClick={() => start('simulation')} className="px-2 py-1 text-xs bg-green-600 text-white rounded">Start</button> : <button onClick={() => pause('simulation')} className="px-2 py-1 text-xs bg-yellow-600 text-white rounded">Pause</button>
              ) : (
                live.status !== 'active' ? <button onClick={() => start('live')} disabled={!readiness.ok} className="px-2 py-1 text-xs bg-red-600 text-white rounded disabled:opacity-50">Start</button> : <button onClick={() => pause('live')} className="px-2 py-1 text-xs bg-yellow-600 text-white rounded">Pause</button>
              )}
              <button onClick={() => stop(focus)} className="px-2 py-1 text-xs bg-gray-600 text-white rounded">Stop</button>
            </div>
          </div>
        </div>
        <StrategyAssignments />
        {showAssetsWarning && (
          <div className="mt-4 p-3 rounded-md border border-yellow-500/40 bg-yellow-500/10 text-yellow-200 text-xs">
            <strong className="mr-1">Active Assets Fallback:</strong>
            Using <code className="text-yellow-300">{assetsSource}</code> source{assetsWarning ? ` (${assetsWarning})` : ''}. API endpoint <code className="text-yellow-300">/api/active-assets</code> not available.
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="glass-card p-6"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-white/70">Total Balance</p><p className="text-2xl font-bold text-white">${mockTradingData.accountOverview.totalBalance.toLocaleString()}</p></div><DollarSign className="h-8 w-8 text-green-400" /></div></div>
          <div className="glass-card p-6"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-white/70">Equity</p><p className="text-2xl font-bold text-white">${mockTradingData.accountOverview.equity.toLocaleString()}</p></div><TrendingUp className="h-8 w-8 text-blue-400" /></div></div>
          <div className="glass-card p-6"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-white/70">Available Margin</p><p className="text-2xl font-bold text-white">${mockTradingData.accountOverview.availableMargin.toLocaleString()}</p></div><Activity className="h-8 w-8 text-purple-400" /></div></div>
          <div className="glass-card p-6"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-white/70">Daily P&L</p><p className={`text-2xl font-bold ${mockTradingData.dailyStats.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>${mockTradingData.dailyStats.totalPnL >= 0 ? '+' : ''}{mockTradingData.dailyStats.totalPnL}</p></div>{mockTradingData.dailyStats.totalPnL >= 0 ? <TrendingUp className="h-8 w-8 text-green-400" /> : <TrendingDown className="h-8 w-8 text-red-400" />}</div></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="glass-card p-6">
            <div className="flex items-center justify-between mb-6"><h3 className="text-xl font-semibold text-white">Active Trades</h3><span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm border border-blue-500/30">{mockTradingData.activeTrades.length} Open</span></div>
            <div className="space-y-4">
              {mockTradingData.activeTrades.map(t => (
                <div key={t.id} className="p-4 bg-white/10 rounded-lg border border-white/20">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3"><span className="font-bold text-white">{t.pair}</span><span className={`px-2 py-1 rounded text-xs font-medium ${t.type==='LONG' ? 'bg-green-500/20 text-green-300 border border-green-500/50' : 'bg-red-500/20 text-red-300 border border-red-500/50'}`}>{t.type}</span></div>
                    <span className={`font-bold ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>${t.pnl >= 0 ? '+' : ''}{t.pnl}</span>
                  </div>
                  <div className="flex justify-between text-sm text-white/70"><span>Entry: {t.entry}</span><span>Current: {t.current}</span><span className={t.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}>{t.pnlPercent >= 0 ? '+' : ''}{t.pnlPercent}%</span></div>
                </div>
              ))}
            </div>
          </div>
          <div className="glass-card p-6">
            <h3 className="text-xl font-semibold text-white mb-6">Daily Performance</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center"><span className="text-white/80">Win Rate</span><div className="flex items-center gap-2"><span className="text-white font-semibold">{mockTradingData.dailyStats.winRate}%</span><div className="w-20 bg-white/20 rounded-full h-2"><div className="bg-green-400 h-2 rounded-full" style={{ width: `${mockTradingData.dailyStats.winRate}%` }} /></div></div></div>
              <div className="flex justify-between items-center"><span className="text-white/80">Total Trades</span><span className="text-white font-semibold">{mockTradingData.dailyStats.totalTrades}</span></div>
              <div className="flex justify-between items-center"><span className="text-white/80">Best Trade</span><span className="text-green-400 font-semibold">+${mockTradingData.dailyStats.bestTrade}</span></div>
              <div className="flex justify-between items-center"><span className="text-white/80">Worst Trade</span><span className="text-red-400 font-semibold">${mockTradingData.dailyStats.worstTrade}</span></div>
            </div>
            <div className="mt-6 p-4 bg-yellow-500/20 rounded-lg border border-yellow-500/30"><div className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-yellow-400" /><span className="text-yellow-300 font-medium">Risk Check</span></div><p className="text-yellow-200 text-sm mt-1">Using {((mockTradingData.accountOverview.usedMargin / mockTradingData.accountOverview.totalBalance) * 100).toFixed(1)}% of account balance as margin</p></div>
          </div>
        </div>
    <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-6"><h3 className="text-xl font-semibold text-white">Performance Chart</h3><div className="flex gap-2">{timeframes.map(tf => (<button key={tf} onClick={() => setSelectedTimeframe(tf)} className={`px-3 py-1 rounded text-sm font-medium transition-colors ${selectedTimeframe===tf ? 'bg-blue-500/30 text-blue-300 border border-blue-500/50' : 'bg-white/10 text-white/70 border border-white/20 hover:bg-white/20'}`}>{tf}</button>))}</div></div>
          <div className="h-64 bg-white/5 rounded-lg border border-white/20 flex items-center justify-center">
            <div className="text-center"><Target className="h-12 w-12 text-white/30 mx-auto mb-2" /><p className="text-white/50">Chart Integration Coming Soon</p><p className="text-white/30 text-sm">TradingView or custom chart component</p></div>
          </div>
        </div>
  </PageContainer>
  );
};

export default TradingDashboard;
