import { 
  Play,
  Pause,
  Save,
  Download,
  Code,
  BarChart3,
  TrendingUp,
  Zap,
  Brain,
  Settings,
  Copy,
  Trash2,
  Plus,
  Eye,
  EyeOff,
  Edit
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useMilestones } from '../../context/MilestoneContext';
import { runBacktest } from '../../services/backtest';
import {
  createBacktestV1,
  getBacktestListV1,
  getBacktestStatusV1,
  getBacktestResultsV1,
  cancelBacktestV1,
  mapV1ToSimpleMetrics
} from '../../services/backtestV1';

import StrategyOptimizationModal from './StrategyOptimizationModal';

import type {
  V1BacktestStatus} from '../../services/backtestV1';


interface Strategy {
  id: string;
  name: string;
  description: string;
  language: 'python' | 'javascript' | 'pinescript';
  code: string;
  parameters: { [key: string]: any };
  backtest: {
    winRate: number;
    totalReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
  };
  isActive: boolean;
  lastModified: string;
}

interface CodeTemplate {
  id: string;
  name: string;
  description: string;
  language: 'python' | 'javascript' | 'pinescript';
  code: string;
}

const StrategyDevelopment: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [activeTab, setActiveTab] = useState<'code' | 'parameters' | 'backtest'>('code');
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [showOptimize, setShowOptimize] = useState(false);
  const [asset, setAsset] = useState<string>('ES');
  const [exchange, setExchange] = useState<string>('CME');
  const [reducedParams, setReducedParams] = useState<boolean>(true);
  const [useV1Flow, setUseV1Flow] = useState<boolean>(false);
  const [dataSource, setDataSource] = useState<string>('polygon');
  const [symbols, setSymbols] = useState<string>('ES');
  const [dateFrom, setDateFrom] = useState<string>('2023-01-01');
  const [dateTo, setDateTo] = useState<string>('2023-12-31');
  const [strategyType, setStrategyType] = useState<string>('momentum');
  const [v1JobId, setV1JobId] = useState<string | null>(null);
  const [v1Progress, setV1Progress] = useState<{ status: string; progress: number; message: string } | null>(null);
  const [v1Polling, setV1Polling] = useState<boolean>(false);
  const [v1History, setV1History] = useState<V1BacktestStatus[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [selectedHistoryMetrics, setSelectedHistoryMetrics] = useState<{ winRate: number; totalReturn: number; maxDrawdown: number; sharpeRatio: number } | null>(null);
  const { awardExperience, completeMilestone, userProgress, updateMilestoneRequirement } = useMilestones();

  const codeTemplates: CodeTemplate[] = [
    {
      id: 'momentum-template',
      name: 'Momentum Strategy Template',
      description: 'Basic momentum-based trading strategy',
      language: 'python',
      code: `def momentum_strategy(data, lookback=14, threshold=0.02):
    """
    Simple momentum strategy
    """
    # Calculate price momentum
    momentum = data['close'].pct_change(lookback)
    
    # Generate signals
    signals = []
    for i, mom in enumerate(momentum):
        if mom > threshold:
            signals.append('BUY')
        elif mom < -threshold:
            signals.append('SELL')
        else:
            signals.append('HOLD')
    
    return signals

# Strategy parameters
LOOKBACK_PERIOD = 14
MOMENTUM_THRESHOLD = 0.02
POSITION_SIZE = 0.1  # 10% of portfolio
STOP_LOSS = 0.02     # 2% stop loss
TAKE_PROFIT = 0.04   # 4% take profit`,
    },
    {
      id: 'mean-reversion-template',
      name: 'Mean Reversion Template',
      description: 'Counter-trend strategy for range-bound markets',
      language: 'python',
      code: `def mean_reversion_strategy(data, period=20, std_dev=2):
    """
    Bollinger Bands mean reversion strategy
    """
    # Calculate Bollinger Bands
    sma = data['close'].rolling(period).mean()
    std = data['close'].rolling(period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    
    # Generate signals
    signals = []
    for i, price in enumerate(data['close']):
        if price < lower_band[i]:
            signals.append('BUY')  # Oversold
        elif price > upper_band[i]:
            signals.append('SELL')  # Overbought
        else:
            signals.append('HOLD')
    
    return signals

# Strategy parameters
BB_PERIOD = 20
BB_STD_DEV = 2
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70`,
    }
  ];

  const mockStrategies: Strategy[] = [
    {
      id: '1',
      name: 'Momentum Scalper',
      description: 'Quick momentum scalps on 5-minute timeframe',
      language: 'python',
      code: codeTemplates[0].code,
      parameters: {
        lookback: 14,
        threshold: 0.02,
        positionSize: 0.1,
        stopLoss: 0.02,
        takeProfit: 0.04
      },
      backtest: {
        winRate: 68.5,
        totalReturn: 24.7,
        maxDrawdown: -8.2,
        sharpeRatio: 1.85
      },
      isActive: true,
      lastModified: '2024-01-15T10:30:00'
    },
    {
      id: '2',
      name: 'Mean Reversion Bot',
      description: 'Counter-trend strategy using Bollinger Bands',
      language: 'python',
      code: codeTemplates[1].code,
      parameters: {
        period: 20,
        stdDev: 2,
        rsiPeriod: 14,
        oversold: 30,
        overbought: 70
      },
      backtest: {
        winRate: 72.1,
        totalReturn: 18.9,
        maxDrawdown: -5.7,
        sharpeRatio: 2.15
      },
      isActive: false,
      lastModified: '2024-01-10T14:20:00'
    }
  ];

  React.useEffect(() => {
    setStrategies(mockStrategies);
    setSelectedStrategy(mockStrategies[0]);
  }, []);

  const createNewStrategy = () => {
    const newStrategy: Strategy = {
      id: Date.now().toString(),
      name: 'New Strategy',
      description: 'Describe your strategy here',
      language: 'python',
      code: '# Write your strategy code here\n\ndef my_strategy(data):\n    # Your logic here\n    pass',
      parameters: {},
      backtest: {
        winRate: 0,
        totalReturn: 0,
        maxDrawdown: 0,
        sharpeRatio: 0
      },
      isActive: false,
      lastModified: new Date().toISOString()
    };
    
    setStrategies([...strategies, newStrategy]);
    setSelectedStrategy(newStrategy);
    setIsEditing(true);
  };

  const saveStrategy = () => {
    if (selectedStrategy) {
      const updatedStrategies = strategies.map(s => 
        s.id === selectedStrategy.id 
          ? { ...selectedStrategy, lastModified: new Date().toISOString() }
          : s
      );
      setStrategies(updatedStrategies);
      setIsEditing(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!selectedStrategy) return;
    setIsBacktesting(true);
    setBacktestError(null);
    const controller = new AbortController();
    try {
      if (useV1Flow) {
        const createRes = await createBacktestV1({
          name: selectedStrategy.name || 'Strategy Backtest',
          description: selectedStrategy.description,
          data: {
            source: dataSource,
            symbols: symbols.split(',').map(s => s.trim()).filter(Boolean),
            start_date: dateFrom,
            end_date: dateTo,
            interval: '1d',
          },
          strategy: {
            type: strategyType,
            params: selectedStrategy.parameters,
          },
          initial_capital: 100000,
          commission: 0.0005,
          slippage: 0.0,
        });
        setV1JobId(createRes.backtest_id);
        setV1Progress({ status: createRes.status, progress: 0, message: createRes.message });
        setActiveTab('backtest');

        setV1Polling(true);
        const pollInterval = 1500;
        await new Promise<void>((resolve, reject) => {
          const interval = setInterval(async () => {
            try {
              const st = await getBacktestStatusV1(createRes.backtest_id);
              setV1Progress({ status: st.status, progress: st.progress, message: st.message });
              if (['completed', 'error', 'cancelled'].includes(st.status)) {
                clearInterval(interval);
                setV1Polling(false);
                if (st.status === 'completed') {
                  const res = await getBacktestResultsV1(createRes.backtest_id, false, 0);
                  const mapped = mapV1ToSimpleMetrics(res);
                  const updated = strategies.map(s => 
                    s.id === selectedStrategy.id
                      ? {
                          ...s,
                          backtest: {
                            winRate: mapped.winRate,
                            totalReturn: mapped.totalReturn,
                            maxDrawdown: mapped.maxDrawdown,
                            sharpeRatio: mapped.sharpeRatio,
                          },
                          lastModified: new Date().toISOString(),
                        }
                      : s
                  );
                  setStrategies(updated);
                  const fresh = updated.find(s => s.id === selectedStrategy.id) || null;
                  setSelectedStrategy(fresh);
                  // Award XP and complete strategy milestone
                  awardExperience('STRATEGY_VALIDATED');
                  // Mark requirement as completed for visibility
                  updateMilestoneRequirement('first_validated_strategy', 'strategy_backtested', { isCompleted: true, current: true });
                  if (!userProgress.completedMilestones.includes('first_validated_strategy')) {
                    completeMilestone('first_validated_strategy');
                  }
                } else if (st.status === 'error') {
                  setBacktestError('Backtest failed. See server logs.');
                }
                resolve();
              }
            } catch (err: any) {
              clearInterval(interval);
              setV1Polling(false);
              setBacktestError(err?.message || 'Polling failed');
              reject(err);
            }
          }, pollInterval);
        });
      } else {
        const result = await runBacktest({
          code: selectedStrategy.code,
          language: selectedStrategy.language,
          parameters: selectedStrategy.parameters,
          asset,
          exchange,
          reducedParams
        }, controller.signal);

        const updated = strategies.map(s => 
          s.id === selectedStrategy.id
            ? {
                ...s,
                backtest: {
                  winRate: result.winRate,
                  totalReturn: result.totalReturn,
                  maxDrawdown: result.maxDrawdown,
                  sharpeRatio: result.sharpeRatio
                },
                lastModified: new Date().toISOString()
              }
            : s
        );
        setStrategies(updated);
        const fresh = updated.find(s => s.id === selectedStrategy.id) || null;
        setSelectedStrategy(fresh);
        setActiveTab('backtest');
        // Award XP and complete strategy milestone in simple flow as well
        awardExperience('STRATEGY_VALIDATED');
  updateMilestoneRequirement('first_validated_strategy', 'strategy_backtested', { isCompleted: true, current: true });
        if (!userProgress.completedMilestones.includes('first_validated_strategy')) {
          completeMilestone('first_validated_strategy');
        }
      }
    } catch (e: any) {
      setBacktestError(e?.message || 'Backtest failed');
    } finally {
      setIsBacktesting(false);
    }
    return () => controller.abort();
  };

  const handleCancelV1 = async () => {
    if (!v1JobId) return;
    try {
      await cancelBacktestV1(v1JobId);
    } catch {}
  };

  const refreshV1History = async () => {
    if (!useV1Flow) return;
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const list = await getBacktestListV1();
      // newest first
      const sorted = [...list].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setV1History(sorted);
    } catch (e: any) {
      setHistoryError(e?.message || 'Failed to load history');
    } finally {
      setLoadingHistory(false);
    }
  };

  const openHistoryItem = async (item: V1BacktestStatus) => {
    setSelectedHistoryId(item.backtest_id);
    setSelectedHistoryMetrics(null);
    setBacktestError(null);
    try {
      if (item.status !== 'completed') {
        setBacktestError('Job is not completed yet.');
        return;
      }
      const res = await getBacktestResultsV1(item.backtest_id, false, 0);
      const mapped = mapV1ToSimpleMetrics(res);
      setSelectedHistoryMetrics(mapped);
    } catch (e: any) {
      setBacktestError(e?.message || 'Failed to load job results');
    }
  };

  // Load v1 history when toggling v1 flow on
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!useV1Flow) return;
      setLoadingHistory(true);
      setHistoryError(null);
      try {
        const list = await getBacktestListV1();
        if (cancelled) return;
        const sorted = [...list].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setV1History(sorted);
      } catch (e: any) {
        if (!cancelled) setHistoryError(e?.message || 'Failed to load history');
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [useV1Flow]);

  // After polling ends, refresh history once
  useEffect(() => {
    if (!useV1Flow) return;
    if (v1Polling) return;
    let cancelled = false;
    (async () => {
      try {
        const list = await getBacktestListV1();
        if (cancelled) return;
        const sorted = [...list].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        setV1History(sorted);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [useV1Flow, v1Polling]);

  const deleteStrategy = (id: string) => {
    setStrategies(strategies.filter(s => s.id !== id));
    if (selectedStrategy?.id === id) {
      setSelectedStrategy(strategies.find(s => s.id !== id) || null);
    }
  };

  const toggleStrategyActive = (id: string) => {
    const updatedStrategies = strategies.map(s => 
      s.id === id ? { ...s, isActive: !s.isActive } : s
    );
    setStrategies(updatedStrategies);
    if (selectedStrategy?.id === id) {
      setSelectedStrategy({ ...selectedStrategy, isActive: !selectedStrategy.isActive });
    }
  };

  const loadTemplate = (template: CodeTemplate) => {
    if (selectedStrategy) {
      setSelectedStrategy({
        ...selectedStrategy,
        code: template.code,
        language: template.language
      });
      setShowTemplates(false);
      setIsEditing(true);
    }
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Strategy Development</h1>
            <p className="text-gray-400">Create, test, and optimize automated trading strategies</p>
          </div>
          
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setShowTemplates(!showTemplates)}
              className="flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
            >
              <Code className="w-4 h-4" />
              <span>Templates</span>
            </button>
            
            <button
              onClick={createNewStrategy}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>New Strategy</span>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Strategy List */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-white">Strategies</h2>
            </div>
            
            <div className="p-4 space-y-2">
              {strategies.map((strategy) => (
                <div
                  key={strategy.id}
                  onClick={() => setSelectedStrategy(strategy)}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedStrategy?.id === strategy.id
                      ? 'bg-blue-600/30 border border-blue-500/50'
                      : 'bg-gray-700/30 hover:bg-gray-700/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-white font-medium text-sm">{strategy.name}</h3>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleStrategyActive(strategy.id);
                      }}
                      className={`p-1 rounded transition-colors ${
                        strategy.isActive 
                          ? 'text-green-400 hover:bg-green-500/20'
                          : 'text-gray-400 hover:bg-gray-600'
                      }`}
                    >
                      {strategy.isActive ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                    </button>
                  </div>
                  
                  <p className="text-gray-400 text-xs mb-2">{strategy.description}</p>
                  
                  <div className="flex items-center justify-between text-xs">
                    <span className={`px-2 py-1 rounded ${
                      strategy.language === 'python' ? 'bg-blue-500/20 text-blue-400' :
                      strategy.language === 'javascript' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-purple-500/20 text-purple-400'
                    }`}>
                      {strategy.language}
                    </span>
                    <span className={`font-medium ${
                      strategy.backtest.winRate >= 60 ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {strategy.backtest.winRate.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Strategy Editor */}
        <div className="lg:col-span-3">
          {selectedStrategy ? (
            <div className="bg-gray-800 rounded-lg border border-gray-700">
              {/* Strategy Header */}
              <div className="p-4 border-b border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <Brain className="w-6 h-6 text-blue-400" />
                    <div>
                      <h2 className="text-xl font-semibold text-white">{selectedStrategy.name}</h2>
                      <p className="text-gray-400 text-sm">{selectedStrategy.description}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => setIsEditing(!isEditing)}
                      className={`p-2 rounded-lg transition-colors ${
                        isEditing 
                          ? 'bg-blue-600 text-white' 
                          : 'bg-gray-700 text-gray-400 hover:text-white'
                      }`}
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    
                    <button
                      onClick={saveStrategy}
                      disabled={!isEditing}
                      className="p-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
                    >
                      <Save className="w-4 h-4" />
                    </button>
                    
                    <button
                      onClick={() => deleteStrategy(selectedStrategy.id)}
                      className="p-2 bg-red-600 hover:bg-red-700 rounded-lg text-white transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Tab Navigation */}
              <div className="flex border-b border-gray-700">
                {[
                  { id: 'code', label: 'Code Editor', icon: Code },
                  { id: 'parameters', label: 'Parameters', icon: Settings },
                  { id: 'backtest', label: 'Backtest Results', icon: BarChart3 }
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex items-center space-x-2 px-6 py-3 font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-700/30'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    <tab.icon className="w-4 h-4" />
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {activeTab === 'code' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <select
                          value={selectedStrategy.language}
                          onChange={(e) => setSelectedStrategy({
                            ...selectedStrategy,
                            language: e.target.value as any
                          })}
                          disabled={!isEditing}
                          className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                        >
                          <option value="python">Python</option>
                          <option value="javascript">JavaScript</option>
                          <option value="pinescript">Pine Script</option>
                        </select>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <select
                          value={asset}
                          onChange={(e)=> setAsset(e.target.value)}
                          className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
                          title="Asset"
                        >
                          <option value="ES">ES (E-mini S&P)</option>
                          <option value="NQ">NQ (E-mini Nasdaq)</option>
                          <option value="CL">CL (Crude Oil)</option>
                          <option value="BTCUSDT">BTCUSDT (Crypto)</option>
                        </select>
                        <select
                          value={exchange}
                          onChange={(e)=> setExchange(e.target.value)}
                          className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
                          title="Exchange"
                        >
                          <option value="CME">CME</option>
                          <option value="BINANCE">Binance</option>
                          <option value="BYBIT">Bybit</option>
                        </select>
                        <label className="flex items-center gap-2 text-gray-300 text-sm">
                          <input type="checkbox" checked={reducedParams} onChange={(e)=> setReducedParams(e.target.checked)} />
                          Intelligence-reduced params
                        </label>
                        <label className="flex items-center gap-2 text-gray-300 text-sm">
                          <input type="checkbox" checked={useV1Flow} onChange={(e)=> setUseV1Flow(e.target.checked)} />
                          Use v1 lifecycle
                        </label>
                        <button className="flex items-center space-x-1 px-3 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg text-white transition-colors">
                          <Copy className="w-4 h-4" />
                          <span>Copy</span>
                        </button>
                        <button className="flex items-center space-x-1 px-3 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg text-white transition-colors">
                          <Download className="w-4 h-4" />
                          <span>Export</span>
                        </button>
                        <button onClick={() => setShowOptimize(true)} className="flex items-center space-x-1 px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors">
                          <Zap className="w-4 h-4" />
                          <span>Optimize</span>
                        </button>
                      </div>
                    </div>
                    
                    <div className="relative">
                      <textarea
                        value={selectedStrategy.code}
                        onChange={(e) => setSelectedStrategy({
                          ...selectedStrategy,
                          code: e.target.value
                        })}
                        disabled={!isEditing}
                        className="w-full h-96 px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white font-mono text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50"
                        style={{ fontFamily: 'Monaco, Consolas, "Courier New", monospace' }}
                      />
                    </div>
                    {useV1Flow && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Data Source</label>
                          <input value={dataSource} onChange={(e)=> setDataSource(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Symbols (comma-separated)</label>
                          <input value={symbols} onChange={(e)=> setSymbols(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">Start Date</label>
                          <input type="date" value={dateFrom} onChange={(e)=> setDateFrom(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-1">End Date</label>
                          <input type="date" value={dateTo} onChange={(e)=> setDateTo(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white" />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-sm text-gray-400 mb-1">Strategy Type</label>
                          <input value={strategyType} onChange={(e)=> setStrategyType(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white" />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'parameters' && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(selectedStrategy.parameters).map(([key, value]) => (
                        <div key={key}>
                          <label className="block text-sm font-medium text-gray-400 mb-2 capitalize">
                            {key.replace(/([A-Z])/g, ' $1').trim()}
                          </label>
                          <input
                            type={typeof value === 'number' ? 'number' : 'text'}
                            value={value}
                            onChange={(e) => setSelectedStrategy({
                              ...selectedStrategy,
                              parameters: {
                                ...selectedStrategy.parameters,
                                [key]: typeof value === 'number' ? Number(e.target.value) : e.target.value
                              }
                            })}
                            disabled={!isEditing}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                          />
                        </div>
                      ))}
                    </div>
                    
                    {isEditing && (
                      <button
                        onClick={() => {
                          const newKey = prompt('Parameter name:');
                          if (newKey) {
                            setSelectedStrategy({
                              ...selectedStrategy,
                              parameters: {
                                ...selectedStrategy.parameters,
                                [newKey]: ''
                              }
                            });
                          }
                        }}
                        className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Add Parameter</span>
                      </button>
                    )}
                  </div>
                )}

                {activeTab === 'backtest' && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div className="bg-gray-700/30 rounded-lg p-4">
                        <div className="text-gray-400 text-sm mb-1">Win Rate</div>
                        <div className={`text-2xl font-bold ${
                          selectedStrategy.backtest.winRate >= 60 ? 'text-green-400' : 'text-yellow-400'
                        }`}>
                          {selectedStrategy.backtest.winRate.toFixed(1)}%
                        </div>
                      </div>
                      
                      <div className="bg-gray-700/30 rounded-lg p-4">
                        <div className="text-gray-400 text-sm mb-1">Total Return</div>
                        <div className={`text-2xl font-bold ${
                          selectedStrategy.backtest.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {formatPercentage(selectedStrategy.backtest.totalReturn)}
                        </div>
                      </div>
                      
                      <div className="bg-gray-700/30 rounded-lg p-4">
                        <div className="text-gray-400 text-sm mb-1">Max Drawdown</div>
                        <div className="text-2xl font-bold text-red-400">
                          {formatPercentage(selectedStrategy.backtest.maxDrawdown)}
                        </div>
                      </div>
                      
                      <div className="bg-gray-700/30 rounded-lg p-4">
                        <div className="text-gray-400 text-sm mb-1">Sharpe Ratio</div>
                        <div className={`text-2xl font-bold ${
                          selectedStrategy.backtest.sharpeRatio >= 1.5 ? 'text-green-400' : 'text-yellow-400'
                        }`}>
                          {selectedStrategy.backtest.sharpeRatio.toFixed(2)}
                        </div>
                      </div>
                    </div>
                    {backtestError && (
                      <div className="p-3 rounded bg-red-500/20 border border-red-500/40 text-red-300">
                        {backtestError}
                      </div>
                    )}

                    <div className="flex items-center space-x-4">
                      <button
                        onClick={handleRunBacktest}
                        disabled={isBacktesting}
                        className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
                      >
                        <Play className="w-4 h-4" />
                        <span>{isBacktesting ? 'Running…' : 'Run Backtest'}</span>
                      </button>
                      {useV1Flow && v1JobId && (
                        <>
                          <button onClick={handleCancelV1} className="flex items-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white transition-colors">
                            <Pause className="w-4 h-4" />
                            <span>Cancel</span>
                          </button>
                          {v1Progress && (
                            <div className="text-sm text-gray-300">
                              <span className="mr-2">Status: {v1Progress.status}</span>
                              <span className="mr-2">Progress: {Math.round(v1Progress.progress)}%</span>
                              <span className="text-gray-400">{v1Progress.message}</span>
                            </div>
                          )}
                        </>
                      )}
                      <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors">
                        <TrendingUp className="w-4 h-4" />
                        <span>Deploy to Simulation</span>
                      </button>
                    </div>

                    {useV1Flow && (
                      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <div className="lg:col-span-1 bg-gray-700/30 rounded-lg p-4 border border-gray-700">
                          <div className="flex items-center justify-between mb-3">
                            <h3 className="text-white font-semibold text-sm">v1 Backtest History</h3>
                            <button onClick={refreshV1History} className="text-xs px-2 py-1 bg-gray-600 hover:bg-gray-500 rounded text-white">
                              {loadingHistory ? 'Loading…' : 'Refresh'}
                            </button>
                          </div>
                          {historyError && <div className="text-xs text-red-300 mb-2">{historyError}</div>}
                          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                            {v1History.length === 0 && !loadingHistory && (
                              <div className="text-xs text-gray-400">No history yet.</div>
                            )}
                            {v1History.map((job) => (
                              <div key={job.backtest_id} className={`p-2 rounded border cursor-pointer ${selectedHistoryId === job.backtest_id ? 'border-blue-500 bg-blue-500/10' : 'border-gray-600 hover:bg-gray-700/40'}`} onClick={() => openHistoryItem(job)}>
                                <div className="flex items-center justify-between">
                                  <div className="text-xs text-white font-medium truncate mr-2">{job.name || job.backtest_id}</div>
                                  <span className={`text-[10px] px-2 py-0.5 rounded ${job.status === 'completed' ? 'bg-green-500/20 text-green-300' : job.status === 'error' ? 'bg-red-500/20 text-red-300' : 'bg-yellow-500/20 text-yellow-200'}`}>{job.status}</span>
                                </div>
                                <div className="text-[10px] text-gray-400 mt-1">{new Date(job.created_at).toLocaleString()}</div>
                                {['running','loading_data','preparing_strategy','analyzing','initialized'].includes(job.status) && (
                                  <div className="flex items-center justify-between mt-1">
                                    <div className="h-1 w-24 bg-gray-600 rounded overflow-hidden">
                                      <div className="h-1 bg-blue-500" style={{ width: `${Math.max(5, Math.round(job.progress))}%` }} />
                                    </div>
                                    <button
                                      className="text-[10px] px-2 py-0.5 bg-red-600/80 hover:bg-red-600 rounded text-white"
                                      onClick={(e) => { e.stopPropagation(); cancelBacktestV1(job.backtest_id).then(refreshV1History).catch(()=>{}); }}
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="lg:col-span-2 bg-gray-700/30 rounded-lg p-4 border border-gray-700">
                          <h3 className="text-white font-semibold text-sm mb-3">Selected Job Results</h3>
                          {!selectedHistoryId && (
                            <div className="text-sm text-gray-400">Select a completed job from the history to view summary metrics.</div>
                          )}
                          {selectedHistoryId && !selectedHistoryMetrics && (
                            <div className="text-sm text-gray-400">{backtestError ? backtestError : 'Fetching results…'}</div>
                          )}
                          {selectedHistoryMetrics && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              <div className="bg-gray-800/60 rounded p-3">
                                <div className="text-gray-400 text-xs">Win Rate</div>
                                <div className="text-green-400 text-lg font-bold">{selectedHistoryMetrics.winRate.toFixed(1)}%</div>
                              </div>
                              <div className="bg-gray-800/60 rounded p-3">
                                <div className="text-gray-400 text-xs">Total Return</div>
                                <div className={`${selectedHistoryMetrics.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'} text-lg font-bold`}>{selectedHistoryMetrics.totalReturn.toFixed(2)}%</div>
                              </div>
                              <div className="bg-gray-800/60 rounded p-3">
                                <div className="text-gray-400 text-xs">Max Drawdown</div>
                                <div className="text-red-400 text-lg font-bold">{selectedHistoryMetrics.maxDrawdown.toFixed(2)}%</div>
                              </div>
                              <div className="bg-gray-800/60 rounded p-3">
                                <div className="text-gray-400 text-xs">Sharpe Ratio</div>
                                <div className={`${selectedHistoryMetrics.sharpeRatio >= 1.5 ? 'text-green-400' : 'text-yellow-400'} text-lg font-bold`}>{selectedHistoryMetrics.sharpeRatio.toFixed(2)}</div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-800 rounded-lg p-12 border border-gray-700 text-center">
              <Brain className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">No Strategy Selected</h3>
              <p className="text-gray-400 mb-6">
                Select a strategy from the list or create a new one to get started.
              </p>
              <button
                onClick={createNewStrategy}
                className="flex items-center space-x-2 px-6 py-3 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors mx-auto"
              >
                <Plus className="w-4 h-4" />
                <span>Create New Strategy</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Templates Modal */}
      {showTemplates && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-gray-800 rounded-xl p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white">Strategy Templates</h2>
              <button
                onClick={() => setShowTemplates(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {codeTemplates.map((template) => (
                <div key={template.id} className="bg-gray-700/30 rounded-lg p-4 border border-gray-600">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-white font-semibold">{template.name}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      template.language === 'python' ? 'bg-blue-500/20 text-blue-400' :
                      template.language === 'javascript' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-purple-500/20 text-purple-400'
                    }`}>
                      {template.language}
                    </span>
                  </div>
                  
                  <p className="text-gray-400 text-sm mb-4">{template.description}</p>
                  
                  <div className="bg-gray-900 rounded-lg p-3 mb-4">
                    <pre className="text-xs text-gray-300 overflow-x-auto">
                      <code>{template.code.substring(0, 200)}...</code>
                    </pre>
                  </div>
                  
                  <button
                    onClick={() => loadTemplate(template)}
                    className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
                  >
                    Use Template
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <StrategyOptimizationModal
        open={showOptimize && !!selectedStrategy}
        onClose={() => setShowOptimize(false)}
        code={selectedStrategy?.code || ''}
        language={(selectedStrategy?.language || 'python') as any}
        parameters={selectedStrategy?.parameters || {}}
        onOptimized={(params) => {
          if (!selectedStrategy) return;
          setSelectedStrategy({ ...selectedStrategy, parameters: params });
        }}
      />
    </div>
  );
};

export default StrategyDevelopment;
