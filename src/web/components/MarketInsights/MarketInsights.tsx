import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BarChart3,
  Brain,
  Clock,
  Eye,
  LineChart,
  Target,
  TrendingDown,
  TrendingUp,
  Zap
} from 'lucide-react';
import React, { useState } from 'react';

interface MarketData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  signal: 'buy' | 'sell' | 'hold';
  strength: number;
}

interface SignalData {
  type: string;
  quality: number;
  confidence: number;
  timeframe: string;
  setup: string;
  entry: number;
  target: number;
  stopLoss: number;
  riskReward: number;
}

interface MarketRegime {
  regime: string;
  confidence: number;
  duration: string;
  description: string;
  characteristics: string[];
}

interface TechnicalAnalysis {
  trend: 'bullish' | 'bearish' | 'neutral';
  momentum: number;
  volatility: number;
  support: number;
  resistance: number;
  rsi: number;
  macd: string;
}

const MarketInsights: React.FC = () => {
  const [selectedTimeframe, setSelectedTimeframe] = useState('5m');
  const [marketData, setMarketData] = useState<MarketData[]>([
    { symbol: 'ES', price: 4485.25, change: 12.50, changePercent: 0.28, volume: 1250000, signal: 'buy', strength: 78 },
    { symbol: 'NQ', price: 15234.75, change: -8.25, changePercent: -0.05, volume: 850000, signal: 'hold', strength: 52 },
    { symbol: 'GC', price: 2034.60, change: 5.40, changePercent: 0.27, volume: 325000, signal: 'buy', strength: 85 },
    { symbol: 'CL', price: 78.45, change: -1.20, changePercent: -1.51, volume: 950000, signal: 'sell', strength: 72 },
  ]);

  const [currentSignal, setCurrentSignal] = useState<SignalData>({
    type: 'G (Go Signal)',
    quality: 82.5,
    confidence: 78.2,
    timeframe: '5min',
    setup: 'Support Bounce + Momentum Confluence',
    entry: 4485.25,
    target: 4492.75,
    stopLoss: 4480.50,
    riskReward: 1.58
  });

  const [marketRegime, setMarketRegime] = useState<MarketRegime>({
    regime: 'TRENDING BULL',
    confidence: 87.3,
    duration: '4 hours 23 minutes',
    description: 'Strong upward momentum with healthy pullbacks',
    characteristics: [
      'Higher highs and higher lows pattern',
      'Volume confirming moves higher',
      'Momentum oscillators in bullish territory',
      'Support levels holding on retests'
    ]
  });

  const [technicalAnalysis, setTechnicalAnalysis] = useState<TechnicalAnalysis>({
    trend: 'bullish',
    momentum: 73.5,
    volatility: 18.2,
    support: 4480.25,
    resistance: 4495.50,
    rsi: 68.4,
    macd: 'Bullish Crossover'
  });

  const timeframes = ['1m', '5m', '15m', '1h', '4h', '1d'];

  const getSignalIcon = (signal: string) => {
    switch (signal) {
      case 'buy':
        return <ArrowUp className="w-4 h-4 text-green-400" />;
      case 'sell':
        return <ArrowDown className="w-4 h-4 text-red-400" />;
      default:
        return <Eye className="w-4 h-4 text-yellow-400" />;
    }
  };

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'buy':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'sell':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      default:
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    }
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'bullish':
        return <TrendingUp className="w-5 h-5 text-green-400" />;
      case 'bearish':
        return <TrendingDown className="w-5 h-5 text-red-400" />;
      default:
        return <Activity className="w-5 h-5 text-yellow-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
              <Brain className="w-8 h-8 mr-3 text-blue-400" />
              Market Insights
            </h1>
            <p className="text-gray-400">AI-powered market analysis and signal generation</p>
          </div>
          <div className="flex items-center space-x-2">
            {timeframes.map(tf => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedTimeframe === tf
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Current Signal */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Target className="w-5 h-5 mr-2 text-blue-400" />
          Current Signal Analysis
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Signal Type:</span>
              <span className="text-white font-medium">{currentSignal.type}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Setup:</span>
              <span className="text-white text-sm">{currentSignal.setup}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Timeframe:</span>
              <span className="text-white">{currentSignal.timeframe}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Signal Quality:</span>
              <div className="flex items-center space-x-2">
                <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-red-400 via-yellow-400 to-green-400"
                    style={{ width: `${currentSignal.quality}%` }}
                  />
                </div>
                <span className="text-white font-medium">{currentSignal.quality}%</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Confidence:</span>
              <span className="text-white font-medium">{currentSignal.confidence}%</span>
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Entry Price:</span>
              <span className="text-green-400 font-medium">${currentSignal.entry}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Target:</span>
              <span className="text-blue-400 font-medium">${currentSignal.target}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Stop Loss:</span>
              <span className="text-red-400 font-medium">${currentSignal.stopLoss}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Risk:Reward:</span>
              <span className="text-purple-400 font-medium">1:{currentSignal.riskReward}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Market Regime */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Zap className="w-5 h-5 mr-2 text-yellow-400" />
          Market Regime Analysis
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-400 mb-2">{marketRegime.regime}</div>
              <div className="text-gray-400 text-sm mb-4">Current Regime</div>
              <div className="flex items-center justify-center space-x-2">
                <span className="text-gray-400">Confidence:</span>
                <span className="text-white font-medium">{marketRegime.confidence}%</span>
              </div>
              <div className="flex items-center justify-center space-x-2 mt-2">
                <Clock className="w-4 h-4 text-gray-400" />
                <span className="text-gray-400 text-sm">{marketRegime.duration}</span>
              </div>
            </div>
          </div>
          <div className="lg:col-span-2">
            <div className="mb-4">
              <h3 className="text-white font-medium mb-2">Description</h3>
              <p className="text-gray-400 text-sm">{marketRegime.description}</p>
            </div>
            <div>
              <h3 className="text-white font-medium mb-2">Key Characteristics</h3>
              <ul className="space-y-1">
                {marketRegime.characteristics.map((char, index) => (
                  <li key={index} className="text-gray-400 text-sm flex items-start">
                    <span className="text-blue-400 mr-2">•</span>
                    {char}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Market Data Grid */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <BarChart3 className="w-5 h-5 mr-2 text-purple-400" />
          Multi-Asset Analysis
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {marketData.map((asset, index) => (
            <div key={index} className="bg-gray-900/50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="font-medium text-white">{asset.symbol}</div>
                <div className={`px-2 py-1 rounded text-xs border ${getSignalColor(asset.signal)}`}>
                  <div className="flex items-center space-x-1">
                    {getSignalIcon(asset.signal)}
                    <span>{asset.signal.toUpperCase()}</span>
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Price:</span>
                  <span className="text-white font-medium">${asset.price}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Change:</span>
                  <span className={`font-medium ${asset.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {asset.change >= 0 ? '+' : ''}{asset.change} ({asset.changePercent}%)
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Signal Strength:</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-red-400 via-yellow-400 to-green-400"
                        style={{ width: `${asset.strength}%` }}
                      />
                    </div>
                    <span className="text-white text-sm">{asset.strength}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Technical Analysis */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <LineChart className="w-5 h-5 mr-2 text-green-400" />
          Technical Analysis Summary
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="flex items-center justify-center mb-2">
              {getTrendIcon(technicalAnalysis.trend)}
            </div>
            <div className="text-lg font-semibold text-white capitalize">{technicalAnalysis.trend}</div>
            <div className="text-sm text-gray-400">Overall Trend</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-400 mb-1">{technicalAnalysis.momentum}</div>
            <div className="text-sm text-gray-400">Momentum Score</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-400 mb-1">{technicalAnalysis.volatility}%</div>
            <div className="text-sm text-gray-400">Volatility</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-400 mb-1">{technicalAnalysis.rsi}</div>
            <div className="text-sm text-gray-400">RSI</div>
          </div>
        </div>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Support Level</div>
            <div className="text-lg font-semibold text-green-400">${technicalAnalysis.support}</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Resistance Level</div>
            <div className="text-lg font-semibold text-red-400">${technicalAnalysis.resistance}</div>
          </div>
          <div className="bg-gray-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">MACD Signal</div>
            <div className="text-lg font-semibold text-blue-400">{technicalAnalysis.macd}</div>
          </div>
        </div>
      </div>

      {/* AI Recommendations */}
      <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 rounded-lg p-6 border border-blue-500/30">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Brain className="w-5 h-5 mr-2 text-blue-400" />
          AI Recommendations
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div>
                <div className="text-white font-medium">Risk Assessment</div>
                <div className="text-gray-400 text-sm">Medium risk environment. Consider reducing position size on new entries.</div>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <Target className="w-5 h-5 text-green-400 mt-0.5" />
              <div>
                <div className="text-white font-medium">Entry Opportunity</div>
                <div className="text-gray-400 text-sm">Strong setup forming on ES. Wait for confirmation above 4485.</div>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <Clock className="w-5 h-5 text-blue-400 mt-0.5" />
              <div>
                <div className="text-white font-medium">Timing</div>
                <div className="text-gray-400 text-sm">Optimal trading window: Next 2-3 hours based on volatility patterns.</div>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <Activity className="w-5 h-5 text-purple-400 mt-0.5" />
              <div>
                <div className="text-white font-medium">Market Focus</div>
                <div className="text-gray-400 text-sm">ES and GC showing strongest signals. Avoid NQ until momentum improves.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarketInsights;
