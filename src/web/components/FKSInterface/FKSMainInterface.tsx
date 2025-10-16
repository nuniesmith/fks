import {
  Brain,
  TrendingUp,
  AlertTriangle,
  Activity,
  DollarSign,
  BarChart3,
  Clock,
  Target,
  Zap,
  Info
} from 'lucide-react';
import React, { useState } from 'react';

import { useApi } from '../../context/ApiContext';

interface MarketAsset {
  symbol: string;
  name: string;
  price: number;
  change24h: number;
  volume: number;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  aiScore: number;
}

interface MarketInsight {
  id: string;
  timestamp: string;
  type: 'analysis' | 'alert' | 'opportunity';
  severity: 'info' | 'warning' | 'critical';
  title: string;
  message: string;
  asset?: string;
  confidence: number;
}

const FKSMainInterface: React.FC = () => {
  const apiContext = useApi();
  const [marketAssets, setMarketAssets] = useState<MarketAsset[]>([
    // Default data for demonstration
    { symbol: 'GC', name: 'Gold Futures', price: 2045.30, change24h: 0.45, volume: 145000, sentiment: 'bullish', aiScore: 72 },
    { symbol: 'NQ', name: 'Nasdaq Futures', price: 17845.50, change24h: -0.23, volume: 520000, sentiment: 'neutral', aiScore: 58 },
    { symbol: 'ES', name: 'S&P 500 Futures', price: 4985.75, change24h: 0.12, volume: 890000, sentiment: 'bullish', aiScore: 65 },
    { symbol: 'CL', name: 'Crude Oil Futures', price: 78.45, change24h: -1.82, volume: 340000, sentiment: 'bearish', aiScore: 42 },
    { symbol: 'BTC', name: 'Bitcoin Futures', price: 42850.00, change24h: 2.15, volume: 28000, sentiment: 'bullish', aiScore: 78 },
  ]);

  const [cryptoAssets, setCryptoAssets] = useState<MarketAsset[]>([
    { symbol: 'BTC', name: 'Bitcoin', price: 42850.00, change24h: 2.15, volume: 28500000000, sentiment: 'bullish', aiScore: 78 },
    { symbol: 'ETH', name: 'Ethereum', price: 2285.40, change24h: 1.85, volume: 15200000000, sentiment: 'bullish', aiScore: 75 },
    { symbol: 'SOL', name: 'Solana', price: 98.75, change24h: -0.45, volume: 2100000000, sentiment: 'neutral', aiScore: 62 },
    { symbol: 'DOGE', name: 'Dogecoin', price: 0.0825, change24h: 3.25, volume: 850000000, sentiment: 'bullish', aiScore: 68 },
  ]);

  const [insights, setInsights] = useState<MarketInsight[]>([
    {
      id: '1',
      timestamp: new Date().toISOString(),
      type: 'analysis',
      severity: 'info',
      title: 'Gold showing strength above 2040 support',
      message: 'Technical indicators suggest continued bullish momentum. RSI at 65, MACD positive.',
      asset: 'GC',
      confidence: 0.82
    },
    {
      id: '2',
      timestamp: new Date().toISOString(),
      type: 'alert',
      severity: 'warning',
      title: 'Crude Oil approaching key resistance',
      message: 'Price action near 79.50 resistance level. Watch for potential reversal signals.',
      asset: 'CL',
      confidence: 0.75
    },
    {
      id: '3',
      timestamp: new Date().toISOString(),
      type: 'opportunity',
      severity: 'info',
      title: 'BTC momentum trade setup forming',
      message: 'Breakout pattern detected on 4H timeframe. Volume confirming move above 42500.',
      asset: 'BTC',
      confidence: 0.88
    }
  ]);

  const [aiThoughts, setAiThoughts] = useState<string>(
    "Market conditions show mixed signals. Futures markets displaying defensive rotation with gold strength. Crypto showing renewed momentum led by BTC. Monitoring for potential volatility expansion in equity indices."
  );

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return 'text-green-500';
      case 'bearish': return 'text-red-500';
      default: return 'text-yellow-500';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'border-red-500 bg-red-500/10';
      case 'warning': return 'border-yellow-500 bg-yellow-500/10';
      default: return 'border-blue-500 bg-blue-500/10';
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
    return num.toFixed(2);
  };

  return (
    <div className="space-y-6">
      {/* AI Market Thoughts */}
      <div className="bg-gradient-to-r from-purple-900/20 to-blue-900/20 rounded-xl p-6 border border-purple-500/20">
        <div className="flex items-start space-x-4">
          <div className="w-12 h-12 bg-purple-500/20 rounded-lg flex items-center justify-center flex-shrink-0">
            <Brain className="w-6 h-6 text-purple-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-white mb-2">FKS AI Market Analysis</h3>
            <p className="text-gray-300 leading-relaxed">{aiThoughts}</p>
            <div className="mt-3 flex items-center space-x-4 text-sm">
              <span className="text-gray-500">Last updated: {new Date().toLocaleTimeString()}</span>
              <span className="text-purple-400">Confidence: 85%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Market Overview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Futures Markets */}
        <div className="bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
            <BarChart3 className="w-5 h-5 mr-2 text-blue-400" />
            Futures Markets
          </h3>
          <div className="space-y-3">
            {marketAssets.map(asset => (
              <div key={asset.symbol} className="bg-gray-800/50 rounded-lg p-4 hover:bg-gray-800/70 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-white">{asset.symbol}</span>
                      <span className="text-sm text-gray-400">{asset.name}</span>
                    </div>
                    <div className="flex items-center space-x-4 mt-1">
                      <span className="text-lg font-mono">${asset.price.toLocaleString()}</span>
                      <span className={`text-sm ${asset.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {asset.change24h >= 0 ? '+' : ''}{asset.change24h}%
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-sm font-medium ${getSentimentColor(asset.sentiment)}`}>
                      {asset.sentiment.toUpperCase()}
                    </div>
                    <div className="flex items-center space-x-1 mt-1">
                      <Zap className="w-3 h-3 text-yellow-400" />
                      <span className="text-sm text-gray-400">AI: {asset.aiScore}%</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Crypto Markets */}
        <div className="bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
            <DollarSign className="w-5 h-5 mr-2 text-green-400" />
            Crypto Markets
          </h3>
          <div className="space-y-3">
            {cryptoAssets.map(asset => (
              <div key={asset.symbol} className="bg-gray-800/50 rounded-lg p-4 hover:bg-gray-800/70 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-white">{asset.symbol}</span>
                      <span className="text-sm text-gray-400">{asset.name}</span>
                    </div>
                    <div className="flex items-center space-x-4 mt-1">
                      <span className="text-lg font-mono">${asset.price.toLocaleString()}</span>
                      <span className={`text-sm ${asset.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {asset.change24h >= 0 ? '+' : ''}{asset.change24h}%
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-500">Vol: {formatNumber(asset.volume)}</div>
                    <div className="flex items-center space-x-1 mt-1">
                      <Zap className="w-3 h-3 text-yellow-400" />
                      <span className="text-sm text-gray-400">AI: {asset.aiScore}%</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Market Insights Feed */}
      <div className="bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <Activity className="w-5 h-5 mr-2 text-orange-400" />
          Real-time Market Insights
        </h3>
        <div className="space-y-3">
          {insights.map(insight => (
            <div key={insight.id} className={`border-l-4 rounded-lg p-4 ${getSeverityColor(insight.severity)}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-1">
                    {insight.type === 'alert' && <AlertTriangle className="w-4 h-4 text-yellow-400" />}
                    {insight.type === 'opportunity' && <Target className="w-4 h-4 text-green-400" />}
                    {insight.type === 'analysis' && <Info className="w-4 h-4 text-blue-400" />}
                    <span className="font-medium text-white">{insight.title}</span>
                    {insight.asset && (
                      <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">{insight.asset}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-300">{insight.message}</p>
                </div>
                <div className="text-right ml-4">
                  <div className="text-xs text-gray-500">{new Date(insight.timestamp).toLocaleTimeString()}</div>
                  <div className="text-xs text-gray-400 mt-1">Conf: {(insight.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-900/50 backdrop-blur rounded-lg p-4 border border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Active Signals</p>
              <p className="text-2xl font-bold text-white">12</p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-400 opacity-50" />
          </div>
        </div>
        <div className="bg-gray-900/50 backdrop-blur rounded-lg p-4 border border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Win Rate</p>
              <p className="text-2xl font-bold text-white">68%</p>
            </div>
            <Target className="w-8 h-8 text-blue-400 opacity-50" />
          </div>
        </div>
        <div className="bg-gray-900/50 backdrop-blur rounded-lg p-4 border border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Risk Score</p>
              <p className="text-2xl font-bold text-white">3.2/10</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-yellow-400 opacity-50" />
          </div>
        </div>
        <div className="bg-gray-900/50 backdrop-blur rounded-lg p-4 border border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Uptime</p>
              <p className="text-2xl font-bold text-white">99.8%</p>
            </div>
            <Clock className="w-8 h-8 text-purple-400 opacity-50" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FKSMainInterface;
