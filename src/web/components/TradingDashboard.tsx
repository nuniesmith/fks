import { Activity, BarChart3, Settings, TrendingUp } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import useSecurity from '../hooks/useSecurity';
import { config } from '../services/config';
import { buildAuthHeaders } from '../services/authToken';

import TradingChart from '@/features/lazy/TradingChartLazy';

// Simple card component for this dashboard
const DashboardCard: React.FC<{ children: React.ReactNode; className?: string }> = ({ 
  children, 
  className = '' 
}) => (
  <div className={`bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-lg ${className}`}>
    {children}
  </div>
);

// (removed duplicate DashboardCard definition)

interface TradingDashboardProps {
  className?: string;
}

const TradingDashboard: React.FC<TradingDashboardProps> = ({ className = '' }) => {
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL');
  const [selectedTimeframe, setSelectedTimeframe] = useState('1h');
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(['sma20', 'sma50']);
  const [marketData, setMarketData] = useState<any[]>([]);
  const [realTimeEnabled, setRealTimeEnabled] = useState(false);

  // Common trading symbols
  const symbols = useMemo(() => [
    'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA',
    'SPY', 'QQQ', 'IWM', 'GLD', 'TLT'
  ], []);

  const timeframes = [
    { value: '1m', label: '1 Minute' },
    { value: '5m', label: '5 Minutes' },
    { value: '15m', label: '15 Minutes' },
    { value: '1h', label: '1 Hour' },
    { value: '4h', label: '4 Hours' },
    { value: '1d', label: '1 Day' }
  ];

  const availableIndicators = [
    { value: 'sma20', label: 'SMA 20' },
    { value: 'sma50', label: 'SMA 50' },
    { value: 'ema9', label: 'EMA 9' },
    { value: 'ema21', label: 'EMA 21' },
    { value: 'rsi', label: 'RSI' }
  ];

  const [security] = useSecurity();
  // Fetch market overview data (after security ready to avoid 401 + ensure auth headers)
  useEffect(() => {
    if (!security.ready) return; // wait until auth posture known
    let cancelled = false;
    const fetchMarketData = async () => {
      try {
        const API_BASE = (config.apiBaseUrl || '/api').replace(/\/$/, '');
  const headers = buildAuthHeaders();
        const promises = symbols.slice(0, 5).map(async (symbol) => {
          try {
            const response = await fetch(`${API_BASE}/chart-data/${symbol}?timeframe=1d&limit=2`, { headers });
            if (!response.ok) return null;
            const result = await response.json();
            if (result.data && result.data.length >= 2) {
              const current = result.data[result.data.length - 1];
              const previous = result.data[result.data.length - 2];
              const change = current.close - previous.close;
              const changePercent = (change / previous.close) * 100;
              return { symbol, price: current.close, change, changePercent, volume: current.volume };
            }
            return null;
          } catch { return null; }
        });
        const results = (await Promise.all(promises)).filter(Boolean) as any[];
        if (!cancelled) setMarketData(results);
      } catch (error) {
        if (!cancelled) console.warn('Failed to fetch market data:', error);
      }
    };
    fetchMarketData();
    const interval = setInterval(fetchMarketData, 60000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [symbols, security.ready]);

  const handleIndicatorToggle = (indicator: string) => {
    setSelectedIndicators(prev => 
      prev.includes(indicator) 
        ? prev.filter(i => i !== indicator)
        : [...prev, indicator]
    );
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Trading</h2>
          <p className="text-gray-400">Real-time market analysis with lightweight charts</p>
        </div>
        
        <div className="flex items-center gap-4">
          <button
            onClick={() => setRealTimeEnabled(!realTimeEnabled)}
            className={`px-4 py-2 rounded-lg transition-colors ${
              realTimeEnabled
                ? 'bg-green-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Activity className="w-4 h-4 inline mr-2" />
            {realTimeEnabled ? 'Live' : 'Static'}
          </button>
        </div>
      </div>

      {/* Market Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {marketData.map((data) => (
          <DashboardCard key={data.symbol} className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-white">{data.symbol}</span>
              <TrendingUp className={`w-4 h-4 ${data.change >= 0 ? 'text-green-400' : 'text-red-400'}`} />
            </div>
            <div className="space-y-1">
              <div className="text-lg font-mono text-white">
                ${data.price?.toFixed(2)}
              </div>
              <div className={`text-sm ${data.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {data.change >= 0 ? '+' : ''}{data.change?.toFixed(2)} ({data.changePercent?.toFixed(2)}%)
              </div>
            </div>
          </DashboardCard>
        ))}
      </div>

      {/* Chart Controls */}
      <DashboardCard className="p-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Symbol Selection */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Symbol
            </label>
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {symbols.map(symbol => (
                <option key={symbol} value={symbol}>{symbol}</option>
              ))}
            </select>
          </div>

          {/* Timeframe Selection */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Timeframe
            </label>
            <select
              value={selectedTimeframe}
              onChange={(e) => setSelectedTimeframe(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {timeframes.map(tf => (
                <option key={tf.value} value={tf.value}>{tf.label}</option>
              ))}
            </select>
          </div>

          {/* Indicators */}
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Indicators
            </label>
            <div className="flex flex-wrap gap-2">
              {availableIndicators.map(indicator => (
                <button
                  key={indicator.value}
                  onClick={() => handleIndicatorToggle(indicator.value)}
                  className={`px-3 py-1 rounded-md text-sm transition-colors ${
                    selectedIndicators.includes(indicator.value)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {indicator.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </DashboardCard>

      {/* Main Chart */}
      <DashboardCard className="p-6">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center">
            <BarChart3 className="w-5 h-5 mr-2" />
            {selectedSymbol} - {timeframes.find(tf => tf.value === selectedTimeframe)?.label}
          </h3>
          {selectedIndicators.length > 0 && (
            <p className="text-sm text-gray-400 mt-1">
              Indicators: {selectedIndicators.map(ind => 
                availableIndicators.find(ai => ai.value === ind)?.label
              ).join(', ')}
            </p>
          )}
        </div>
        
        <TradingChart
          symbol={selectedSymbol}
          timeframe={selectedTimeframe}
          height={500}
          realTimeEnabled={realTimeEnabled}
          indicators={selectedIndicators}
          className="w-full"
        />
      </DashboardCard>

      {/* Additional Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DashboardCard className="p-4">
          <h4 className="text-md font-semibold text-white mb-4">SPY Overview</h4>
          <TradingChart
            symbol="SPY"
            timeframe="1d"
            height={300}
            realTimeEnabled={false}
            className="w-full"
          />
        </DashboardCard>
        
        <DashboardCard className="p-4">
          <h4 className="text-md font-semibold text-white mb-4">QQQ Overview</h4>
          <TradingChart
            symbol="QQQ"
            timeframe="1d"
            height={300}
            realTimeEnabled={false}
            className="w-full"
          />
        </DashboardCard>
      </div>

      {/* Integration Status */}
      <DashboardCard className="p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <Settings className="w-5 h-5 mr-2" />
          Integration Status
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-green-400 rounded-full"></div>
            <span className="text-gray-300">Lightweight Charts</span>
          </div>
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-green-400 rounded-full"></div>
            <span className="text-gray-300">Python API</span>
          </div>
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${realTimeEnabled ? 'bg-green-400' : 'bg-gray-400'}`}></div>
            <span className="text-gray-300">Real-time Data</span>
          </div>
        </div>

        <div className="mt-4 text-sm text-gray-400">
          <p>✅ React TradingView Lightweight Charts integrated</p>
          <p>✅ Python API endpoints for historical data</p>
          <p>✅ Technical indicators support</p>
          <p>⏳ WebSocket real-time updates (in development)</p>
          <p>⏳ NinjaTrader integration (in development)</p>
        </div>
      </DashboardCard>
    </div>
  );
};

export default TradingDashboard;
