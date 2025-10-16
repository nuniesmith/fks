import { 
  Plus, 
  Pause, 
  Edit, 
  Trash2, 
  Copy, 
  Brain,
  Users,
  CheckCircle,
  Clock,
  BarChart3
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

interface SimpleStrategy {
  id: string;
  name: string;
  description: string;
  code: string;
  type: 'entry' | 'exit' | 'filter' | 'risk';
  parameters: Record<string, any>;
  performance: {
    winRate: number;
    avgReturn: number;
    sharpeRatio: number;
  };
  status: 'active' | 'inactive' | 'testing';
}

interface ComplexStrategy {
  id: string;
  name: string;
  description: string;
  simpleStrategies: string[]; // IDs of simple strategies
  combinationLogic: 'AND' | 'OR' | 'WEIGHTED' | 'SEQUENTIAL';
  weights?: Record<string, number>;
  accounts: string[]; // Account IDs where this strategy is applied
  environments: ('simulation' | 'live')[];
  performance: {
    totalTrades: number;
    winRate: number;
    totalReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
  };
  status: 'active' | 'inactive' | 'testing';
  lastBacktest: Date;
}

interface TradingAccount {
  id: string;
  name: string;
  type: 'futures' | 'crypto' | 'stocks';
  provider: 'rithmic' | 'binance' | 'coinbase' | 'interactive_brokers';
  balance: number;
  enabled: boolean;
  strategies: string[];
}

const StrategyLibrary: React.FC = () => {
  const [simpleStrategies, setSimpleStrategies] = useState<SimpleStrategy[]>([]);
  const [complexStrategies, setComplexStrategies] = useState<ComplexStrategy[]>([]);
  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [selectedView, setSelectedView] = useState<'simple' | 'complex' | 'deployment'>('simple');
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadStrategies();
    loadAccounts();
  }, []);

  const loadStrategies = () => {
    // Load sample strategies
    const sampleSimpleStrategies: SimpleStrategy[] = [
      {
        id: 'sma-crossover',
        name: 'SMA Crossover Entry',
        description: 'Enter long when fast SMA crosses above slow SMA',
        code: `
def sma_crossover_entry(data, fast_period=20, slow_period=50):
    fast_sma = data['close'].rolling(fast_period).mean()
    slow_sma = data['close'].rolling(slow_period).mean()
    
    signal = (fast_sma > slow_sma) & (fast_sma.shift(1) <= slow_sma.shift(1))
    return signal
        `,
        type: 'entry',
        parameters: { fast_period: 20, slow_period: 50 },
        performance: { winRate: 0.65, avgReturn: 0.024, sharpeRatio: 1.2 },
        status: 'active'
      },
      {
        id: 'rsi-filter',
        name: 'RSI Oversold Filter',
        description: 'Only trade when RSI is below 30 (oversold)',
        code: `
def rsi_oversold_filter(data, period=14, threshold=30):
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi < threshold
        `,
        type: 'filter',
        parameters: { period: 14, threshold: 30 },
        performance: { winRate: 0.72, avgReturn: 0.018, sharpeRatio: 1.4 },
        status: 'active'
      },
      {
        id: 'atr-stop',
        name: 'ATR-Based Stop Loss',
        description: 'Dynamic stop loss based on Average True Range',
        code: `
def atr_stop_loss(data, period=14, multiplier=2.0):
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    
    tr = np.maximum(high_low, np.maximum(high_close, low_close))
    atr = tr.rolling(period).mean()
    
    stop_loss = data['close'] - (atr * multiplier)
    return stop_loss
        `,
        type: 'risk',
        parameters: { period: 14, multiplier: 2.0 },
        performance: { winRate: 0.68, avgReturn: 0.015, sharpeRatio: 1.1 },
        status: 'active'
      }
    ];

    const sampleComplexStrategies: ComplexStrategy[] = [
      {
        id: 'mean-reversion-suite',
        name: 'Mean Reversion Suite',
        description: 'Combination of SMA crossover, RSI filter, and ATR stop for mean reversion trading',
        simpleStrategies: ['sma-crossover', 'rsi-filter', 'atr-stop'],
        combinationLogic: 'AND',
        accounts: ['futures-1', 'crypto-1'],
        environments: ['simulation', 'live'],
        performance: {
          totalTrades: 156,
          winRate: 0.71,
          totalReturn: 0.324,
          sharpeRatio: 1.8,
          maxDrawdown: 0.12
        },
        status: 'active',
        lastBacktest: new Date()
      }
    ];

    setSimpleStrategies(sampleSimpleStrategies);
    setComplexStrategies(sampleComplexStrategies);
  };

  const loadAccounts = () => {
    const sampleAccounts: TradingAccount[] = [
      {
        id: 'futures-1',
        name: 'Rithmic Futures - Main',
        type: 'futures',
        provider: 'rithmic',
        balance: 50000,
        enabled: true,
        strategies: ['mean-reversion-suite']
      },
      {
        id: 'crypto-1',
        name: 'Binance - BTC/ETH',
        type: 'crypto',
        provider: 'binance',
        balance: 25000,
        enabled: true,
        strategies: ['mean-reversion-suite']
      },
      {
        id: 'futures-2',
        name: 'Rithmic Futures - Test',
        type: 'futures',
        provider: 'rithmic',
        balance: 10000,
        enabled: false,
        strategies: []
      }
    ];

    setAccounts(sampleAccounts);
  };

  const deployStrategyToAccounts = (strategyId: string, accountIds: string[]) => {
    // Deploy strategy to multiple accounts
    setAccounts(prev => 
      prev.map(account => ({
        ...account,
        strategies: accountIds.includes(account.id) 
          ? [...account.strategies.filter(s => s !== strategyId), strategyId]
          : account.strategies.filter(s => s !== strategyId)
      }))
    );
  };

  const createComplexStrategy = (simpleStrategyIds: string[]) => {
    // Logic to combine simple strategies into complex ones
    console.log('Creating complex strategy from:', simpleStrategyIds);
    setShowCreateModal(true);
  };

  const renderSimpleStrategies = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-white">Simple Strategies</h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>New Strategy</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {simpleStrategies.map(strategy => (
          <div key={strategy.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-semibold text-white">{strategy.name}</h3>
                <p className="text-sm text-gray-400 mt-1">{strategy.description}</p>
              </div>
              <span className={`px-2 py-1 rounded text-xs ${
                strategy.type === 'entry' ? 'bg-green-500/20 text-green-400' :
                strategy.type === 'exit' ? 'bg-red-500/20 text-red-400' :
                strategy.type === 'filter' ? 'bg-blue-500/20 text-blue-400' :
                'bg-orange-500/20 text-orange-400'
              }`}>
                {strategy.type}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 mb-3 text-xs">
              <div className="text-center">
                <div className="text-green-400 font-medium">{(strategy.performance.winRate * 100).toFixed(1)}%</div>
                <div className="text-gray-500">Win Rate</div>
              </div>
              <div className="text-center">
                <div className="text-blue-400 font-medium">{(strategy.performance.avgReturn * 100).toFixed(1)}%</div>
                <div className="text-gray-500">Avg Return</div>
              </div>
              <div className="text-center">
                <div className="text-purple-400 font-medium">{strategy.performance.sharpeRatio.toFixed(1)}</div>
                <div className="text-gray-500">Sharpe</div>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {strategy.status === 'active' ? (
                  <CheckCircle className="w-4 h-4 text-green-400" />
                ) : strategy.status === 'testing' ? (
                  <Clock className="w-4 h-4 text-yellow-400" />
                ) : (
                  <Pause className="w-4 h-4 text-gray-400" />
                )}
                <span className="text-xs text-gray-400 capitalize">{strategy.status}</span>
              </div>
              
              <div className="flex items-center space-x-1">
                <button className="p-1 hover:bg-gray-700 rounded">
                  <Edit className="w-3 h-3 text-gray-400" />
                </button>
                <button className="p-1 hover:bg-gray-700 rounded">
                  <Copy className="w-3 h-3 text-gray-400" />
                </button>
                <button className="p-1 hover:bg-gray-700 rounded">
                  <Trash2 className="w-3 h-3 text-gray-400" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderComplexStrategies = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-white">Complex Strategies</h2>
        <button
          onClick={() => createComplexStrategy([])}
          className="flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
        >
          <Brain className="w-4 h-4" />
          <span>Combine Strategies</span>
        </button>
      </div>

      <div className="space-y-4">
        {complexStrategies.map(strategy => (
          <div key={strategy.id} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">{strategy.name}</h3>
                <p className="text-gray-400 mt-1">{strategy.description}</p>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm ${
                strategy.status === 'active' ? 'bg-green-500/20 text-green-400' :
                strategy.status === 'testing' ? 'bg-yellow-500/20 text-yellow-400' :
                'bg-gray-500/20 text-gray-400'
              }`}>
                {strategy.status}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
              <div className="text-center">
                <div className="text-xl font-bold text-green-400">{strategy.performance.totalTrades}</div>
                <div className="text-xs text-gray-500">Total Trades</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-blue-400">{(strategy.performance.winRate * 100).toFixed(1)}%</div>
                <div className="text-xs text-gray-500">Win Rate</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-purple-400">{(strategy.performance.totalReturn * 100).toFixed(1)}%</div>
                <div className="text-xs text-gray-500">Total Return</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-orange-400">{strategy.performance.sharpeRatio.toFixed(1)}</div>
                <div className="text-xs text-gray-500">Sharpe Ratio</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-red-400">{(strategy.performance.maxDrawdown * 100).toFixed(1)}%</div>
                <div className="text-xs text-gray-500">Max Drawdown</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              <span className="text-sm text-gray-400">Components:</span>
              {strategy.simpleStrategies.map(simpleId => {
                const simple = simpleStrategies.find(s => s.id === simpleId);
                return simple ? (
                  <span key={simpleId} className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                    {simple.name}
                  </span>
                ) : null;
              })}
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4 text-sm text-gray-400">
                <span>Logic: {strategy.combinationLogic}</span>
                <span>Accounts: {strategy.accounts.length}</span>
                <span>Environments: {strategy.environments.join(', ')}</span>
              </div>
              
              <div className="flex items-center space-x-2">
                <button className="flex items-center space-x-1 px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm text-white transition-colors">
                  <BarChart3 className="w-3 h-3" />
                  <span>Backtest</span>
                </button>
                <button className="flex items-center space-x-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white transition-colors">
                  <Users className="w-3 h-3" />
                  <span>Deploy</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderDeployment = () => (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-white">Strategy Deployment</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accounts */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">Trading Accounts</h3>
          <div className="space-y-3">
            {accounts.map(account => (
              <div key={account.id} className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className={`w-3 h-3 rounded-full ${account.enabled ? 'bg-green-400' : 'bg-gray-400'}`}></div>
                  <div>
                    <div className="font-medium text-white">{account.name}</div>
                    <div className="text-sm text-gray-400">{account.type} • ${account.balance.toLocaleString()}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-400">{account.strategies.length} strategies</div>
                  <div className="text-xs text-gray-500">{account.provider}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Strategy Assignments */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">Strategy Assignments</h3>
          <div className="space-y-3">
            {complexStrategies.map(strategy => (
              <div key={strategy.id} className="p-3 bg-gray-700/50 rounded-lg">
                <div className="font-medium text-white mb-2">{strategy.name}</div>
                <div className="flex flex-wrap gap-1">
                  {strategy.accounts.map(accountId => {
                    const account = accounts.find(a => a.id === accountId);
                    return account ? (
                      <span key={accountId} className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">
                        {account.name}
                      </span>
                    ) : null;
                  })}
                </div>
                <div className="flex items-center space-x-2 mt-2">
                  {strategy.environments.map(env => (
                    <span key={env} className={`px-2 py-1 rounded text-xs ${
                      env === 'live' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'
                    }`}>
                      {env}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Strategy Library</h1>
          <p className="text-gray-400 mt-1">
            Build, combine, and deploy trading strategies across multiple accounts
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setSelectedView('simple')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              selectedView === 'simple' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
            }`}
          >
            Simple Strategies
          </button>
          <button
            onClick={() => setSelectedView('complex')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              selectedView === 'complex' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
            }`}
          >
            Complex Strategies
          </button>
          <button
            onClick={() => setSelectedView('deployment')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              selectedView === 'deployment' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
            }`}
          >
            Deployment
          </button>
        </div>
      </div>

      {/* Content */}
      {selectedView === 'simple' && renderSimpleStrategies()}
      {selectedView === 'complex' && renderComplexStrategies()}
      {selectedView === 'deployment' && renderDeployment()}
    </div>
  );
};

export default StrategyLibrary;
