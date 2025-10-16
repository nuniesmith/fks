import { PieChart, BarChart, TrendingUp, Target, DollarSign, Activity, AlertTriangle } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { realTimeDataService } from '../../services/realTimeDataService';

import type { TradingMetrics } from '../../services/realTimeDataService';

interface AnalyticsData {
  performance: {
    totalPnL: number;
    todayPnL: number;
    winRate: number;
    totalTrades: number;
    avgWin: number;
    avgLoss: number;
    sharpeRatio: number;
    maxDrawdown: number;
  };
  riskMetrics: {
    portfolioValue: number;
    exposure: number;
    var95: number;
    beta: number;
    correlation: number;
  };
  recentTrades: Array<{
    id: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
    pnl: number;
    timestamp: string;
  }>;
}

const Analytics: React.FC = () => {
  const [tradingMetrics, setTradingMetrics] = useState<TradingMetrics | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState<'1D' | '1W' | '1M' | '3M' | '1Y'>('1D');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        const metrics = await realTimeDataService.getTradingMetrics();
        setTradingMetrics(metrics);
        
        // Generate mock analytics data
        setAnalyticsData({
          performance: {
            totalPnL: 15420.50,
            todayPnL: 850.25,
            winRate: 68.5,
            totalTrades: 147,
            avgWin: 234.50,
            avgLoss: -128.75,
            sharpeRatio: 1.85,
            maxDrawdown: -2150.00
          },
          riskMetrics: {
            portfolioValue: 125000,
            exposure: 78.5,
            var95: -1250.00,
            beta: 1.12,
            correlation: 0.78
          },
          recentTrades: [
            { id: '1', symbol: 'ES', side: 'BUY', quantity: 5, price: 4485.25, pnl: 425.00, timestamp: '2024-01-15T14:30:00Z' },
            { id: '2', symbol: 'NQ', side: 'SELL', quantity: 2, price: 16250.50, pnl: -150.00, timestamp: '2024-01-15T14:15:00Z' },
            { id: '3', symbol: 'RTY', side: 'BUY', quantity: 10, price: 2025.75, pnl: 320.50, timestamp: '2024-01-15T14:00:00Z' },
            { id: '4', symbol: 'YM', side: 'SELL', quantity: 3, price: 37850.00, pnl: 180.25, timestamp: '2024-01-15T13:45:00Z' },
            { id: '5', symbol: 'ES', side: 'BUY', quantity: 8, price: 4480.00, pnl: -275.00, timestamp: '2024-01-15T13:30:00Z' }
          ]
        });
      } catch (error) {
        console.error('Failed to load analytics data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();

    // Subscribe to real-time updates
    const unsubscribe = realTimeDataService.subscribe('tradingMetrics', (metrics: TradingMetrics) => {
      setTradingMetrics(metrics);
    });

    return () => unsubscribe();
  }, [selectedPeriod]);

  if (isLoading || !analyticsData || !tradingMetrics) {
    return (
      <div className="space-y-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-center h-48">
            <div className="text-center">
              <Activity className="w-12 h-12 text-blue-400 mx-auto mb-4 animate-pulse" />
              <p className="text-gray-400">Loading analytics data...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { performance, riskMetrics, recentTrades } = analyticsData;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
              <BarChart className="w-8 h-8 mr-3 text-blue-400" />
              Trading Analytics
            </h1>
            <p className="text-gray-400">Performance analysis and risk metrics</p>
          </div>
          <div className="flex items-center space-x-2">
            {['1D', '1W', '1M', '3M', '1Y'].map((period) => (
              <button
                key={period}
                onClick={() => setSelectedPeriod(period as any)}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  selectedPeriod === period
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {period}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Key Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <DollarSign className="w-8 h-8 text-green-400" />
            <span className={`text-sm px-2 py-1 rounded ${
              performance.todayPnL >= 0 ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'
            }`}>
              {performance.todayPnL >= 0 ? '+' : ''}{performance.todayPnL.toFixed(2)}
            </span>
          </div>
          <h3 className="text-lg font-semibold text-white mb-1">Total P&L</h3>
          <p className="text-2xl font-bold text-green-400">
            ${performance.totalPnL.toLocaleString()}
          </p>
          <p className="text-sm text-gray-400 mt-1">Today's P&L</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <Target className="w-8 h-8 text-blue-400" />
            <span className="text-sm px-2 py-1 rounded bg-blue-900 text-blue-300">
              {performance.totalTrades} trades
            </span>
          </div>
          <h3 className="text-lg font-semibold text-white mb-1">Win Rate</h3>
          <p className="text-2xl font-bold text-blue-400">{performance.winRate}%</p>
          <p className="text-sm text-gray-400 mt-1">Success ratio</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <TrendingUp className="w-8 h-8 text-purple-400" />
            <span className="text-sm px-2 py-1 rounded bg-purple-900 text-purple-300">
              {performance.sharpeRatio.toFixed(2)}
            </span>
          </div>
          <h3 className="text-lg font-semibold text-white mb-1">Avg Win</h3>
          <p className="text-2xl font-bold text-purple-400">
            ${performance.avgWin.toFixed(2)}
          </p>
          <p className="text-sm text-gray-400 mt-1">Per winning trade</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <AlertTriangle className="w-8 h-8 text-red-400" />
            <span className="text-sm px-2 py-1 rounded bg-red-900 text-red-300">
              {performance.maxDrawdown.toFixed(0)}
            </span>
          </div>
          <h3 className="text-lg font-semibold text-white mb-1">Avg Loss</h3>
          <p className="text-2xl font-bold text-red-400">
            ${Math.abs(performance.avgLoss).toFixed(2)}
          </p>
          <p className="text-sm text-gray-400 mt-1">Per losing trade</p>
        </div>
      </div>

      {/* Risk Metrics */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Risk Management</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-1">Portfolio Value</div>
            <div className="text-lg font-bold text-white">
              ${riskMetrics.portfolioValue.toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-1">Exposure</div>
            <div className="text-lg font-bold text-yellow-400">{riskMetrics.exposure}%</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-1">VaR (95%)</div>
            <div className="text-lg font-bold text-red-400">
              ${Math.abs(riskMetrics.var95).toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-1">Beta</div>
            <div className="text-lg font-bold text-blue-400">{riskMetrics.beta}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-400 mb-1">Correlation</div>
            <div className="text-lg font-bold text-purple-400">{riskMetrics.correlation}</div>
          </div>
        </div>
      </div>

      {/* Performance Chart Placeholder */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Performance Overview</h2>
        <div className="h-64 bg-gray-900/50 rounded flex items-center justify-center">
          <div className="text-center">
            <PieChart className="w-16 h-16 text-blue-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">Advanced Charts</h3>
            <p className="text-gray-400">Performance charts and visualizations coming soon</p>
          </div>
        </div>
      </div>

      {/* Recent Trades */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Recent Trades</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-2 text-gray-400">Time</th>
                <th className="text-left py-2 text-gray-400">Symbol</th>
                <th className="text-center py-2 text-gray-400">Side</th>
                <th className="text-right py-2 text-gray-400">Quantity</th>
                <th className="text-right py-2 text-gray-400">Price</th>
                <th className="text-right py-2 text-gray-400">P&L</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.map((trade) => (
                <tr key={trade.id} className="border-b border-gray-800 hover:bg-gray-900/50">
                  <td className="py-3 text-white">
                    {new Date(trade.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="py-3 text-white font-medium">{trade.symbol}</td>
                  <td className="py-3 text-center">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.side === 'BUY' 
                        ? 'bg-green-900 text-green-300' 
                        : 'bg-red-900 text-red-300'
                    }`}>
                      {trade.side}
                    </span>
                  </td>
                  <td className="py-3 text-right text-white">{trade.quantity}</td>
                  <td className="py-3 text-right text-white">${trade.price.toFixed(2)}</td>
                  <td className={`py-3 text-right font-medium ${
                    trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Trading Status */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Live Trading Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">Active Positions</span>
              <span className="text-xl font-bold text-white">{tradingMetrics.activePositions}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div 
                className="bg-blue-400 h-2 rounded-full" 
                style={{ width: `${(tradingMetrics.activePositions / 10) * 100}%` }}
              ></div>
            </div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">Daily Volume</span>
              <span className="text-xl font-bold text-white">${tradingMetrics.dailyVolume.toLocaleString()}</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div 
                className="bg-green-400 h-2 rounded-full" 
                style={{ width: `${Math.min((tradingMetrics.dailyVolume / 1000000) * 100, 100)}%` }}
              ></div>
            </div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">Success Rate</span>
              <span className="text-xl font-bold text-white">{tradingMetrics.successRate}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div 
                className="bg-purple-400 h-2 rounded-full" 
                style={{ width: `${tradingMetrics.successRate}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
