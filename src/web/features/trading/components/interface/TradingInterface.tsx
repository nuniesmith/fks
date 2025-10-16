import {
  Activity,
  AlertTriangle,
  BarChart3,
  DollarSign,
  Pause,
  Play,
  TrendingUp,
  RefreshCw,
  Settings,
  Zap,
  Target,
  Shield
} from 'lucide-react';
import React, { useState, useEffect, useMemo } from 'react';

import { useTradingEnv } from '@/context/TradingEnvContext';
import { config } from '@/services/config';
import { WebSocketServiceFactory } from '@/services/WebSocketService';

interface Position {
  symbol: string;
  side: 'long' | 'short';
  size: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPercentage: number;
  accountId: string;
  timestamp: string;
}

interface TradingMetrics {
  totalPnL: number;
  todayPnL: number;
  winRate: number;
  sharpeRatio: number;
  maxDrawdown: number;
  totalTrades: number;
  activeAccounts: number;
  enabledStrategies: number;
}

interface TradingAccount {
  id: string;
  name: string;
  type: 'prop' | 'personal' | 'crypto';
  balance: number;
  equity: number;
  enabled: boolean;
  environment: 'simulation' | 'live';
}

const TradingInterface: React.FC = () => {
  const { environment, updateEnvironment, isLive, isSimulation } = useTradingEnv();
  const [isLiveDataConnected, setIsLiveDataConnected] = useState(false);
  const [positions, setPositions] = useState<Position[]>([]);
  const [metrics, setMetrics] = useState<TradingMetrics>({
    totalPnL: 0,
    todayPnL: 0,
    winRate: 0,
    sharpeRatio: 0,
    maxDrawdown: 0,
    totalTrades: 0,
    activeAccounts: 0,
    enabledStrategies: 0
  });
  const [autoTradingEnabled, setAutoTradingEnabled] = useState(false);
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);

  useEffect(() => {
    const mockPositions: Position[] = [
      {
        symbol: 'BTC/USD',
        side: 'long',
        size: 0.5,
        entryPrice: 43250,
        currentPrice: 43620,
        pnl: 185,
        pnlPercentage: 0.86,
        accountId: 'prop-account-1',
        timestamp: new Date().toISOString()
      },
      {
        symbol: 'ETH/USD',
        side: 'short',
        size: 2.0,
        entryPrice: 2680,
        currentPrice: 2655,
        pnl: 50,
        pnlPercentage: 0.93,
        accountId: 'crypto-account-1',
        timestamp: new Date().toISOString()
      }
    ];

    const mockAccounts: TradingAccount[] = [
      {
        id: 'prop-account-1',
        name: 'Prop Firm Account #1',
        type: 'prop',
        balance: 50000,
        equity: 50235,
        enabled: true,
        environment: isLive ? 'live' : 'simulation'
      },
      {
        id: 'crypto-account-1',
        name: 'Crypto Trading Account',
        type: 'crypto',
        balance: 25000,
        equity: 25050,
        enabled: true,
        environment: isLive ? 'live' : 'simulation'
      }
    ];

    const mockMetrics: TradingMetrics = {
      totalPnL: 1247.50,
      todayPnL: 235.00,
      winRate: 68.5,
      sharpeRatio: 1.85,
      maxDrawdown: -324.50,
      totalTrades: 23,
      activeAccounts: mockAccounts.filter(acc => acc.enabled).length,
      enabledStrategies: 3
    };

    setPositions(mockPositions);
    setMetrics(mockMetrics);
    setAccounts(mockAccounts);

    let cleanup: (() => void) | undefined;
    if (config.mockServices || !config.apiBaseUrl) {
      const timer = setTimeout(() => {
        setIsLiveDataConnected(true);
      }, 1500);
      cleanup = () => clearTimeout(timer);
    } else {
      const base = config.wsBaseUrl || config.apiBaseUrl;
      const wsService = WebSocketServiceFactory.createMarketDataService(base);
      const onStatus = (status: 'connecting' | 'connected' | 'disconnected' | 'error') => {
        setIsLiveDataConnected(status === 'connected');
      };
      wsService.onStatusChange(onStatus);
      wsService.connect();
      cleanup = () => {
        wsService.offStatusChange(onStatus);
        WebSocketServiceFactory.cleanup();
      };
    }

    return () => { if (cleanup) cleanup(); };
  }, []);

  const toggleEnvironment = () => {
    const newMode = environment === 'SIMULATION' ? 'LIVE' : 'SIMULATION';
    if (newMode === 'LIVE') {
      const confirmed = window.confirm(
        '⚠️ CRITICAL WARNING: You are about to switch to LIVE TRADING mode.\n\n' +
        'This will:\n' +
        '• Execute real trades with actual money\n' +
        '• Connect to live market data feeds\n' +
        '• Apply strategies to enabled accounts\n\n' +
        'Are you absolutely sure you want to proceed?'
      );
      if (!confirmed) return;
    }
    updateEnvironment(newMode);
    setAccounts(prev => prev.map(acc => ({ ...acc, environment: newMode.toLowerCase() as 'simulation' | 'live' })));
  };

  const toggleAutoTrading = () => {
    if (isLive) {
      const confirmed = window.confirm(
        '⚠️ WARNING: You are about to toggle auto-trading in LIVE mode.\n\n' + 
        'This will execute real trades with actual money across all enabled accounts.\n\n' +
        'Current enabled accounts: ' + accounts.filter(acc => acc.enabled).length + '\n' +
        'Active strategies: ' + metrics.enabledStrategies + '\n\n' +
        'Are you sure?'
      );
      if (!confirmed) return;
    }
    setAutoTradingEnabled(!autoTradingEnabled);
  };

  const toggleAccountEnabled = (accountId: string) => {
    setAccounts(prev => prev.map(acc => acc.id === accountId ? { ...acc, enabled: !acc.enabled } : acc));
  };

  const totalAccountValue = useMemo(() => accounts.reduce((t, acc) => t + (acc.enabled ? acc.equity : 0), 0), [accounts]);
  const enabledAccounts = useMemo(() => accounts.filter(acc => acc.enabled), [accounts]);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Trading Interface</h1>
              <div className="flex items-center space-x-4 flex-wrap gap-2">
                <div className={`px-3 py-1 rounded-full text-sm font-medium ${isLive ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'}`}>{isLive ? '🔴 LIVE TRADING' : '🟢 SIMULATION'}</div>
                <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${isLiveDataConnected ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'}`}>
                  <Activity className={`w-4 h-4 ${isLiveDataConnected ? '' : 'animate-pulse'}`} />
                  <span>{isLiveDataConnected ? 'Connected' : 'Connecting...'}</span>
                </div>
                <div className="px-3 py-1 rounded-full text-sm bg-purple-500/20 text-purple-400 border border-purple-500/30"><span>{enabledAccounts.length} Active Accounts</span></div>
                <div className="px-3 py-1 rounded-full text-sm bg-orange-500/20 text-orange-400 border border-orange-500/30"><span>{metrics.enabledStrategies} Strategies</span></div>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={toggleEnvironment} className={`px-4 py-2 rounded-lg font-medium transition-colors ${isLive ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-red-600 hover:bg-red-700 text-white'}`}>Switch to {isLive ? 'Simulation' : 'Live'}</button>
              <button onClick={toggleAutoTrading} disabled={enabledAccounts.length === 0} className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${enabledAccounts.length === 0 ? 'bg-gray-600 text-gray-400 cursor-not-allowed' : autoTradingEnabled ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-gray-600 hover:bg-gray-700 text-white'}`}>{autoTradingEnabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}<span>{autoTradingEnabled ? 'Disable' : 'Enable'} Auto Trading</span></button>
              <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"><Settings className="w-5 h-5" /></button>
            </div>
          </div>
        </div>
      </div>
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-gray-800 rounded-lg p-4"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Total P&L</p><p className={`text-2xl font-bold ${metrics.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>${metrics.totalPnL.toFixed(2)}</p></div><TrendingUp className="w-8 h-8 text-green-400" /></div></div>
          <div className="bg-gray-800 rounded-lg p-4"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Today P&L</p><p className={`text-2xl font-bold ${metrics.todayPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>${metrics.todayPnL.toFixed(2)}</p></div><BarChart3 className="w-8 h-8 text-blue-400" /></div></div>
          <div className="bg-gray-800 rounded-lg p-4"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Win Rate</p><p className="text-2xl font-bold text-white">{metrics.winRate.toFixed(1)}%</p></div><Target className="w-8 h-8 text-yellow-400" /></div></div>
          <div className="bg-gray-800 rounded-lg p-4"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Active Accounts</p><p className="text-2xl font-bold text-white">{metrics.activeAccounts}</p></div><Shield className="w-8 h-8 text-purple-400" /></div></div>
          <div className="bg-gray-800 rounded-lg p-4"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Total Equity</p><p className="text-2xl font-bold text-white">${totalAccountValue.toLocaleString()}</p></div><DollarSign className="w-8 h-8 text-green-400" /></div></div>
          <div className="bg-gray-800 rounded-lg p-4"><div className="flex items-center justify-between"><div><p className="text-sm text-gray-400">Strategies</p><p className="text-2xl font-bold text-white">{metrics.enabledStrategies}</p></div><Zap className="w-8 h-8 text-orange-400" /></div></div>
        </div>
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-700"><div className="flex justify-between items-center"><h2 className="text-xl font-semibold text-white">Trading Accounts</h2><div className="flex items-center space-x-2"><span className="text-sm text-gray-400">{enabledAccounts.length} of {accounts.length} enabled</span></div></div></div>
          <div className="p-6"><div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{accounts.map(account => (<div key={account.id} className={`p-4 rounded-lg border-2 transition-all duration-200 cursor-pointer ${account.enabled ? 'border-green-500/50 bg-green-500/10' : 'border-gray-600 bg-gray-700/50'}`} onClick={() => toggleAccountEnabled(account.id)}><div className="flex items-center justify-between mb-3"><div className="flex items-center space-x-2"><div className={`w-3 h-3 rounded-full ${account.enabled ? 'bg-green-400' : 'bg-gray-500'}`} /><span className="font-medium text-white">{account.name}</span></div><span className={`px-2 py-1 text-xs rounded ${account.type === 'prop' ? 'bg-blue-500/20 text-blue-400' : account.type === 'crypto' ? 'bg-orange-500/20 text-orange-400' : 'bg-purple-500/20 text-purple-400'}`}>{account.type.toUpperCase()}</span></div><div className="space-y-2"><div className="flex justify-between text-sm"><span className="text-gray-400">Balance:</span><span className="text-white">${account.balance.toLocaleString()}</span></div><div className="flex justify-between text-sm"><span className="text-gray-400">Equity:</span><span className={`${account.equity >= account.balance ? 'text-green-400' : 'text-red-400'}`}>${account.equity.toLocaleString()}</span></div><div className="flex justify-between text-sm"><span className="text-gray-400">P&L:</span><span className={`${account.equity - account.balance >= 0 ? 'text-green-400' : 'text-red-400'}`}>${(account.equity - account.balance).toFixed(2)}</span></div></div></div>))}</div></div>
        </div>
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-700"><div className="flex justify-between items-center"><h2 className="text-xl font-semibold text-white">Active Positions</h2><div className="flex items-center space-x-2"><button className="flex items-center space-x-2 px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"><RefreshCw className="w-4 h-4" /><span className="text-sm">Refresh</span></button></div></div></div>
          {positions.length > 0 ? (<div className="overflow-x-auto"><table className="w-full"><thead className="bg-gray-700"><tr><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Symbol</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Account</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Side</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Size</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Entry Price</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Current Price</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">P&L</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">P&L %</th><th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Actions</th></tr></thead><tbody className="divide-y divide-gray-700">{positions.map((position, index) => (<tr key={index} className="hover:bg-gray-700/50"><td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">{position.symbol}</td><td className="px-6 py-4 whitespace-nowrap text-sm"><div className="flex flex-col"><span className="text-white text-xs">{accounts.find(acc => acc.id === position.accountId)?.name || position.accountId}</span><span className="text-gray-500 text-xs">{accounts.find(acc => acc.id === position.accountId)?.type || 'unknown'}</span></div></td><td className="px-6 py-4 whitespace-nowrap text-sm"><span className={`px-2 py-1 rounded-full text-xs font-medium ${position.side === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{position.side.toUpperCase()}</span></td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">{position.size}</td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">${position.entryPrice.toLocaleString()}</td><td className="px-6 py-4 whitespace-nowrap text-sm text-white">${position.currentPrice.toLocaleString()}</td><td className="px-6 py-4 whitespace-nowrap text-sm"><span className={position.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>${position.pnl.toFixed(2)}</span></td><td className="px-6 py-4 whitespace-nowrap text-sm"><span className={position.pnlPercentage >= 0 ? 'text-green-400' : 'text-red-400'}>{position.pnlPercentage >= 0 ? '+' : ''}{position.pnlPercentage.toFixed(2)}%</span></td><td className="px-6 py-4 whitespace-nowrap text-sm space-x-2"><button className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs transition-colors">Edit</button><button className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs transition-colors">Close</button></td></tr>))}</tbody></table></div>) : (<div className="text-center py-12"><DollarSign className="w-16 h-16 text-gray-400 mx-auto mb-4" /><p className="text-gray-400">No active positions</p></div>)}
        </div>
        {isLive && (<div className="bg-red-900/20 border border-red-500 rounded-lg p-6"><div className="flex items-start space-x-4"><AlertTriangle className="w-6 h-6 text-red-500 flex-shrink-0 mt-1" /><div className="flex-1"><h3 className="text-red-400 font-semibold text-lg mb-2">Live Trading Mode Active</h3><div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm"><div><p className="text-red-300 mb-2"><strong>All trades executed will use real money.</strong> Double-check all positions and settings.</p><ul className="text-red-300 space-y-1"><li>• Connected to live market data feeds</li><li>• {enabledAccounts.length} accounts enabled for trading</li><li>• {metrics.enabledStrategies} strategies will execute automatically</li></ul></div><div><h4 className="text-red-400 font-medium mb-2">Current Risk Exposure:</h4><ul className="text-red-300 space-y-1"><li>• Total Account Value: ${totalAccountValue.toLocaleString()}</li><li>• Open Positions: {positions.length}</li><li>• Auto Trading: {autoTradingEnabled ? 'ENABLED' : 'DISABLED'}</li></ul></div></div></div></div></div>)}
        {isSimulation && (<div className="bg-blue-900/20 border border-blue-500 rounded-lg p-4"><div className="flex items-center space-x-3"><Shield className="w-5 h-5 text-blue-500" /><div><h3 className="text-blue-400 font-semibold">Simulation Mode</h3><p className="text-blue-300 text-sm">Practice trading with real market data without financial risk. Perfect your strategies before switching to live trading.</p></div></div></div>)}
      </div>
    </div>
  );
};

export default TradingInterface;
