import {
  History,
  Play,
  BarChart3,
  Settings,
  Download,
  RefreshCw,
  Filter
} from 'lucide-react';
import React, { useState, useEffect } from 'react';


interface BacktestResult {
  id: string;
  strategyName: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  totalTrades: number;
  winRate: number;
  totalReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  calmarRatio: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
  status: 'completed' | 'running' | 'failed';
}

const Backtesting: React.FC = () => {
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedTimeframe, setSelectedTimeframe] = useState('1Y');
  const [selectedStrategy, setSelectedStrategy] = useState('momentum-scalp');

  useEffect(() => {
    // Mock backtest results
    const mockResults: BacktestResult[] = [
      {
        id: '1',
        strategyName: 'Momentum Scalping',
        timeframe: '5m',
        startDate: '2024-01-01',
        endDate: '2024-12-31',
        totalTrades: 1247,
        winRate: 68.5,
        totalReturn: 24.7,
        maxDrawdown: -8.2,
        sharpeRatio: 1.85,
        calmarRatio: 3.01,
        profitFactor: 1.72,
        avgWin: 127.50,
        avgLoss: -85.30,
        status: 'completed'
      },
      {
        id: '2',
        strategyName: 'Mean Reversion',
        timeframe: '15m',
        startDate: '2024-01-01',
        endDate: '2024-12-31',
        totalTrades: 423,
        winRate: 72.1,
        totalReturn: 18.9,
        maxDrawdown: -5.7,
        sharpeRatio: 2.15,
        calmarRatio: 3.32,
        profitFactor: 2.01,
        avgWin: 195.80,
        avgLoss: -98.40,
        status: 'completed'
      },
      {
        id: '3',
        strategyName: 'Breakout Strategy',
        timeframe: '1h',
        startDate: '2024-01-01',
        endDate: '2024-12-31',
        totalTrades: 156,
        winRate: 58.3,
        totalReturn: 31.2,
        maxDrawdown: -12.4,
        sharpeRatio: 1.64,
        calmarRatio: 2.52,
        profitFactor: 1.48,
        avgWin: 385.20,
        avgLoss: -245.60,
        status: 'completed'
      }
    ];

    setResults(mockResults);
  }, []);

  const runBacktest = () => {
    setIsRunning(true);
    // Simulate backtest running
    setTimeout(() => {
      setIsRunning(false);
      // Add new result or update existing
    }, 5000);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-400 bg-green-500/20';
      case 'running': return 'text-yellow-400 bg-yellow-500/20';
      case 'failed': return 'text-red-400 bg-red-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Backtesting</h1>
            <p className="text-gray-400">Test trading strategies against historical data</p>
          </div>
          
          <div className="flex items-center space-x-4">
            <button className="flex items-center space-x-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg text-white transition-colors">
              <Settings className="w-4 h-4" />
              <span>Configure</span>
            </button>
            
            <button
              onClick={runBacktest}
              disabled={isRunning}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-white transition-colors ${
                isRunning 
                  ? 'bg-gray-600 cursor-not-allowed' 
                  : 'bg-blue-600 hover:bg-blue-700'
              }`}
            >
              {isRunning ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span>{isRunning ? 'Running...' : 'Run Backtest'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Backtest Configuration */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Backtest Configuration</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Strategy
            </label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="momentum-scalp">Momentum Scalping</option>
              <option value="mean-reversion">Mean Reversion</option>
              <option value="breakout">Breakout Strategy</option>
              <option value="trend-following">Trend Following</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Timeframe
            </label>
            <select
              value={selectedTimeframe}
              onChange={(e) => setSelectedTimeframe(e.target.value)}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="1M">1 Month</option>
              <option value="3M">3 Months</option>
              <option value="6M">6 Months</option>
              <option value="1Y">1 Year</option>
              <option value="2Y">2 Years</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Initial Capital
            </label>
            <input
              type="number"
              defaultValue={50000}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Commission
            </label>
            <input
              type="number"
              step="0.01"
              defaultValue={2.50}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Results Summary */}
      {results.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-white">Backtest Results</h2>
            <div className="flex items-center space-x-2">
              <button className="p-2 hover:bg-gray-700 rounded-lg transition-colors">
                <Filter className="w-4 h-4 text-gray-400" />
              </button>
              <button className="p-2 hover:bg-gray-700 rounded-lg transition-colors">
                <Download className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-3 px-4 text-gray-400">Strategy</th>
                  <th className="text-left py-3 px-4 text-gray-400">Period</th>
                  <th className="text-left py-3 px-4 text-gray-400">Trades</th>
                  <th className="text-left py-3 px-4 text-gray-400">Win Rate</th>
                  <th className="text-left py-3 px-4 text-gray-400">Return</th>
                  <th className="text-left py-3 px-4 text-gray-400">Max DD</th>
                  <th className="text-left py-3 px-4 text-gray-400">Sharpe</th>
                  <th className="text-left py-3 px-4 text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr key={result.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                    <td className="py-3 px-4 font-medium text-white">{result.strategyName}</td>
                    <td className="py-3 px-4 text-gray-300">
                      {new Date(result.startDate).toLocaleDateString()} - {new Date(result.endDate).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-gray-300">{result.totalTrades}</td>
                    <td className="py-3 px-4">
                      <span className={`${result.winRate >= 60 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {result.winRate.toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`font-medium ${
                        result.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {formatPercentage(result.totalReturn)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-red-400">
                        {formatPercentage(result.maxDrawdown)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`${result.sharpeRatio >= 1.5 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {result.sharpeRatio.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(result.status)}`}>
                        {result.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Detailed Results */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Performance Metrics */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Performance Metrics</h3>
            
            <div className="space-y-4">
              {results.slice(0, 1).map((result) => (
                <div key={result.id} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Total Return</span>
                    <span className={`font-medium ${
                      result.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {formatPercentage(result.totalReturn)}
                    </span>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Sharpe Ratio</span>
                    <span className="text-white font-medium">{result.sharpeRatio.toFixed(2)}</span>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Calmar Ratio</span>
                    <span className="text-white font-medium">{result.calmarRatio.toFixed(2)}</span>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Profit Factor</span>
                    <span className="text-white font-medium">{result.profitFactor.toFixed(2)}</span>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Average Win</span>
                    <span className="text-green-400 font-medium">{formatCurrency(result.avgWin)}</span>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Average Loss</span>
                    <span className="text-red-400 font-medium">{formatCurrency(result.avgLoss)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Equity Curve Placeholder */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Equity Curve</h3>
            
            <div className="flex items-center justify-center h-64 text-gray-400">
              <div className="text-center">
                <BarChart3 className="w-16 h-16 mx-auto mb-4" />
                <p>Interactive equity curve chart coming soon</p>
                <p className="text-sm">Will show portfolio value over time</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* No Results State */}
      {results.length === 0 && (
        <div className="bg-gray-800 rounded-lg p-12 border border-gray-700 text-center">
          <History className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">No Backtest Results</h3>
          <p className="text-gray-400 mb-6">
            Run your first backtest to see how your strategies would have performed historically.
          </p>
          <button
            onClick={runBacktest}
            className="flex items-center space-x-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors mx-auto"
          >
            <Play className="w-4 h-4" />
            <span>Run First Backtest</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default Backtesting;
