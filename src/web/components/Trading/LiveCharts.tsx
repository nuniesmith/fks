import { BarChart3, TrendingUp, Activity, Settings, RefreshCw, Maximize2 } from 'lucide-react';
import React, { useState, useEffect, useRef } from 'react';

import { realTimeDataService } from '../../services/realTimeDataService';

import type { MarketData } from '../../services/realTimeDataService';

interface ChartConfig {
  symbol: string;
  interval: string;
  theme: 'light' | 'dark';
  studies: string[];
}

const LiveCharts: React.FC = () => {
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState('ES');
  const [selectedInterval, setSelectedInterval] = useState('5m');
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const intervals = [
    { value: '1m', label: '1 Minute' },
    { value: '5m', label: '5 Minutes' },
    { value: '15m', label: '15 Minutes' },
    { value: '1h', label: '1 Hour' },
    { value: '4h', label: '4 Hours' },
    { value: '1d', label: '1 Day' }
  ];

  useEffect(() => {
    const loadMarketData = async () => {
      setIsLoading(true);
      try {
        const data = await realTimeDataService.getMarketData();
        setMarketData(data);
        setLastUpdate(new Date());
      } catch (error) {
        console.error('Failed to load market data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadMarketData();

    // Subscribe to real-time market data updates
    const unsubscribe = realTimeDataService.subscribe('marketData', (data: MarketData[]) => {
      setMarketData(data);
      setLastUpdate(new Date());
    });

    return () => unsubscribe();
  }, []);

  const selectedMarketData = marketData.find(data => data.symbol === selectedSymbol);

  const generateMockChartData = () => {
    const basePrice = selectedMarketData?.price || 4485.25;
    const data = [];
    const now = new Date();
    
    for (let i = 100; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 5 * 60000); // 5 minutes intervals
      const variation = (Math.random() - 0.5) * 20;
      const price = basePrice + variation;
      
      data.push({
        time: time.toISOString(),
        open: price - (Math.random() - 0.5) * 2,
        high: price + Math.random() * 3,
        low: price - Math.random() * 3,
        close: price,
        volume: Math.floor(Math.random() * 1000) + 500
      });
    }
    
    return data;
  };

  const chartData = generateMockChartData();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
              <BarChart3 className="w-8 h-8 mr-3 text-green-400" />
              Live Charts
            </h1>
            <div className="flex items-center space-x-4">
              <p className="text-gray-400">Real-time charting and technical analysis</p>
              {isLoading && (
                <div className="flex items-center space-x-2 text-blue-400">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Loading...</span>
                </div>
              )}
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Last Update</div>
            <div className="text-lg font-mono text-white">
              {lastUpdate.toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>

      {/* Chart Controls */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Symbol</label>
              <select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white focus:border-blue-500 focus:outline-none"
              >
                {marketData.map(data => (
                  <option key={data.symbol} value={data.symbol}>
                    {data.symbol}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Interval</label>
              <select
                value={selectedInterval}
                onChange={(e) => setSelectedInterval(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white focus:border-blue-500 focus:outline-none"
              >
                {intervals.map(interval => (
                  <option key={interval.value} value={interval.value}>
                    {interval.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded text-white transition-colors">
              <Settings className="w-4 h-4" />
            </button>
            <button className="p-2 bg-gray-700 hover:bg-gray-600 rounded text-white transition-colors">
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Market Data Strip */}
      {selectedMarketData && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div>
              <div className="text-sm text-gray-400">Symbol</div>
              <div className="text-lg font-bold text-white">{selectedMarketData.symbol}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Price</div>
              <div className="text-lg font-bold text-white">${selectedMarketData.price}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Change</div>
              <div className={`text-lg font-bold ${
                selectedMarketData.change >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {selectedMarketData.change >= 0 ? '+' : ''}{selectedMarketData.change}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Change %</div>
              <div className={`text-lg font-bold ${
                selectedMarketData.changePercent >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {selectedMarketData.changePercent >= 0 ? '+' : ''}{selectedMarketData.changePercent}%
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Bid</div>
              <div className="text-lg font-bold text-blue-400">${selectedMarketData.bid}</div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Ask</div>
              <div className="text-lg font-bold text-red-400">${selectedMarketData.ask}</div>
            </div>
          </div>
        </div>
      )}

      {/* Chart Container */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">{selectedSymbol} - {selectedInterval}</h2>
        </div>
        <div 
          ref={chartContainerRef}
          className="relative h-96 p-4"
        >
          {/* Mock Chart Visualization */}
          <div className="w-full h-full bg-gray-900/50 rounded flex items-center justify-center">
            <div className="text-center">
              <TrendingUp className="w-16 h-16 text-green-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">Advanced Charting</h3>
              <p className="text-gray-400 mb-4">
                TradingView integration and custom FKS indicators coming soon
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                <div className="bg-gray-800 rounded-lg p-3">
                  <Activity className="w-6 h-6 text-blue-400 mx-auto mb-2" />
                  <div className="text-sm text-white font-medium">Real-time Data</div>
                  <div className="text-xs text-gray-400">Live price feeds</div>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <BarChart3 className="w-6 h-6 text-purple-400 mx-auto mb-2" />
                  <div className="text-sm text-white font-medium">FKS Indicators</div>
                  <div className="text-xs text-gray-400">AI signal overlay</div>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <TrendingUp className="w-6 h-6 text-green-400 mx-auto mb-2" />
                  <div className="text-sm text-white font-medium">Multi-timeframe</div>
                  <div className="text-xs text-gray-400">Multiple intervals</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chart Data Preview */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4">Recent Price Data</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-2 text-gray-400">Time</th>
                <th className="text-right py-2 text-gray-400">Open</th>
                <th className="text-right py-2 text-gray-400">High</th>
                <th className="text-right py-2 text-gray-400">Low</th>
                <th className="text-right py-2 text-gray-400">Close</th>
                <th className="text-right py-2 text-gray-400">Volume</th>
              </tr>
            </thead>
            <tbody>
              {chartData.slice(-10).reverse().map((candle, index) => (
                <tr key={index} className="border-b border-gray-800 hover:bg-gray-900/50">
                  <td className="py-2 text-white">
                    {new Date(candle.time).toLocaleTimeString()}
                  </td>
                  <td className="py-2 text-right text-white">{candle.open.toFixed(2)}</td>
                  <td className="py-2 text-right text-green-400">{candle.high.toFixed(2)}</td>
                  <td className="py-2 text-right text-red-400">{candle.low.toFixed(2)}</td>
                  <td className="py-2 text-right text-white font-medium">{candle.close.toFixed(2)}</td>
                  <td className="py-2 text-right text-gray-400">{candle.volume}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default LiveCharts;
