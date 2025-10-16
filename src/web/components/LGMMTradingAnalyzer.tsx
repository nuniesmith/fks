import { Activity, AlertCircle, BarChart3, CheckCircle, Clock, DollarSign, RefreshCw, TrendingUp } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';

interface AssetConfig {
  ticker: string;
  name: string;
  asset_type: string;
  tick_value: number;
  margin_per_contract: number;
  commission: number;
  multiplier?: number;
}

interface AnalysisResults {
  total_return: number;
  final_value: number;
  num_trades: number;
  win_rate: number;
  max_drawdown: number;
  sharpe_ratio: number;
  signal_quality_avg: number;
  buy_signals: number;
  sell_signals: number;
}

interface ChartData {
  dates: string[];
  prices: number[];
  predicted: number[];
  upper_bound: number[];
  lower_bound: number[];
  buy_signals: number[];
  sell_signals: number[];
}

interface AnalysisResponse {
  analysis_id?: string;
  status: string;
  progress: number;
  ticker: string;
  results?: AnalysisResults;
  chart_data?: ChartData;
  portfolio_performance?: {
    dates: string[];
    values: number[];
  };
  transactions?: any[];
  error?: string;
}

const LGMMTradingAnalyzer: React.FC = () => {
  const [assets, setAssets] = useState<AssetConfig[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<string>('GC=F');
  const [analysisParams, setAnalysisParams] = useState({
    start_date: '2023-01-01',
    end_date: '2024-12-31',
    account_size: 150000,
    risk_per_trade: 0.01,
    n_components: 2,
    poly_degree: 2,
    std_multiplier: 2.0,
    train_window: 252
  });
  const [currentAnalysis, setCurrentAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisResponse[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [, setWebsocket] = useState<WebSocket | null>(null);

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8002';
  const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8002';

  const fetchAssets = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/assets`);
      const data = await response.json();
      setAssets(data.assets);
    } catch (error) {
      console.error('Failed to fetch assets:', error);
    }
  }, [API_BASE]);

  const handleWebSocketMessage = useCallback((message: any) => {
    switch (message.type) {
      case 'analysis_update':
        if (currentAnalysis && message.analysis_id === currentAnalysis.analysis_id) {
          setCurrentAnalysis(message.analysis);
        }
        break;
      case 'analysis_complete':
        setCurrentAnalysis(message.analysis);
        setAnalysisHistory(prev => [message.analysis, ...prev.slice(0, 9)]);
        setIsRunning(false);
        break;
      default:
        break;
    }
  }, [currentAnalysis]);

  useEffect(() => {
    // Load available assets
    fetchAssets();
    
    // Setup WebSocket for real-time updates with error handling
    const setupWebSocket = () => {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws`);
        
        ws.onopen = () => {
          console.log('WebSocket connected');
          setWebsocket(ws);
        };
        
        ws.onmessage = (event) => {
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        };
        
        ws.onerror = (error) => {
          console.warn('WebSocket error:', error);
        };
        
        ws.onclose = () => {
          console.log('WebSocket disconnected, attempting to reconnect in 5s...');
          setTimeout(setupWebSocket, 5000);
        };
        
        return ws;
      } catch (error) {
        console.warn('Failed to establish WebSocket connection:', error);
        setTimeout(setupWebSocket, 5000);
        return null;
      }
    };

    const ws = setupWebSocket();

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [WS_BASE, fetchAssets, handleWebSocketMessage]);

  const runAnalysis = async () => {
    setIsRunning(true);
    setCurrentAnalysis({
      status: 'starting',
      progress: 0,
      ticker: selectedAsset
    });

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticker: selectedAsset,
          ...analysisParams
        }),
      });

      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.detail || 'Analysis failed');
      }

      // Analysis started, updates will come via WebSocket
      setCurrentAnalysis(prev => ({ ...prev!, analysis_id: result.analysis_id }));
      
    } catch (error) {
      console.error('Failed to start analysis:', error);
      setCurrentAnalysis({
        status: 'error',
        progress: 0,
        ticker: selectedAsset,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      setIsRunning(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercentage = (value: number) => {
    return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      case 'running':
      case 'starting':
        return <RefreshCw className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  const getReturnColor = (value: number) => {
    if (value > 0) return 'text-green-600';
    if (value < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          LGMM Trading Analyzer
        </h1>
        <p className="text-gray-600">
          Advanced trading analysis using Latent Gaussian Mixture Models for futures and equities
        </p>
      </div>

      {/* Analysis Configuration */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Analysis Configuration</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Asset</label>
            <select
              value={selectedAsset}
              onChange={(e) => setSelectedAsset(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            >
              {assets.map((asset) => (
                <option key={asset.ticker} value={asset.ticker}>
                  {asset.name} ({asset.ticker})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Start Date</label>
            <input
              type="date"
              value={analysisParams.start_date}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, start_date: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">End Date</label>
            <input
              type="date"
              value={analysisParams.end_date}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, end_date: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Account Size</label>
            <input
              type="number"
              value={analysisParams.account_size}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, account_size: Number(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Risk per Trade (%)</label>
            <input
              type="number"
              step="0.01"
              value={analysisParams.risk_per_trade * 100}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, risk_per_trade: Number(e.target.value) / 100 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">GMM Components</label>
            <input
              type="number"
              min="1"
              max="5"
              value={analysisParams.n_components}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, n_components: Number(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Std Multiplier</label>
            <input
              type="number"
              step="0.1"
              value={analysisParams.std_multiplier}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, std_multiplier: Number(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Training Window</label>
            <input
              type="number"
              min="50"
              max="1000"
              value={analysisParams.train_window}
              onChange={(e) => setAnalysisParams(prev => ({ ...prev, train_window: Number(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            />
          </div>
        </div>

        <button
          onClick={runAnalysis}
          disabled={isRunning}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {isRunning ? (
            <>
              <RefreshCw className="h-5 w-5 animate-spin" />
              Running Analysis...
            </>
          ) : (
            <>
              <TrendingUp className="h-5 w-5" />
              Run Analysis
            </>
          )}
        </button>
      </div>

      {/* Current Analysis Status */}
      {currentAnalysis && (
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Current Analysis: {currentAnalysis.ticker}</h2>
            <div className="flex items-center gap-2">
              {getStatusIcon(currentAnalysis.status)}
              <span className="text-sm font-medium capitalize">{currentAnalysis.status}</span>
            </div>
          </div>

          {currentAnalysis.status !== 'completed' && currentAnalysis.status !== 'error' && (
            <div className="mb-4">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Progress</span>
                <span>{currentAnalysis.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${currentAnalysis.progress}%` }}
                ></div>
              </div>
            </div>
          )}

          {currentAnalysis.error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800">{currentAnalysis.error}</p>
            </div>
          )}

          {/* Results Display */}
          {currentAnalysis.results && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <DollarSign className="h-5 w-5 text-green-600" />
                  <span className="font-medium">Total Return</span>
                </div>
                <p className={`text-2xl font-bold ${getReturnColor(currentAnalysis.results.total_return)}`}>
                  {formatPercentage(currentAnalysis.results.total_return)}
                </p>
                <p className="text-sm text-gray-600">
                  {formatCurrency(currentAnalysis.results.final_value)}
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <BarChart3 className="h-5 w-5 text-blue-600" />
                  <span className="font-medium">Win Rate</span>
                </div>
                <p className="text-2xl font-bold text-gray-900">
                  {currentAnalysis.results.win_rate.toFixed(1)}%
                </p>
                <p className="text-sm text-gray-600">
                  {currentAnalysis.results.num_trades} trades
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="h-5 w-5 text-purple-600" />
                  <span className="font-medium">Sharpe Ratio</span>
                </div>
                <p className="text-2xl font-bold text-gray-900">
                  {currentAnalysis.results.sharpe_ratio.toFixed(2)}
                </p>
                <p className="text-sm text-gray-600">
                  Risk-adjusted return
                </p>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-5 w-5 text-red-600" />
                  <span className="font-medium">Max Drawdown</span>
                </div>
                <p className="text-2xl font-bold text-red-600">
                  {formatPercentage(currentAnalysis.results.max_drawdown)}
                </p>
                <p className="text-sm text-gray-600">
                  Worst decline
                </p>
              </div>
            </div>
          )}

          {/* Signal Statistics */}
          {currentAnalysis.results && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-green-50 rounded-lg p-4">
                <h3 className="font-medium text-green-800 mb-2">Buy Signals</h3>
                <p className="text-2xl font-bold text-green-600">
                  {currentAnalysis.results.buy_signals}
                </p>
              </div>

              <div className="bg-red-50 rounded-lg p-4">
                <h3 className="font-medium text-red-800 mb-2">Sell Signals</h3>
                <p className="text-2xl font-bold text-red-600">
                  {currentAnalysis.results.sell_signals}
                </p>
              </div>

              <div className="bg-blue-50 rounded-lg p-4">
                <h3 className="font-medium text-blue-800 mb-2">Avg Signal Quality</h3>
                <p className="text-2xl font-bold text-blue-600">
                  {(currentAnalysis.results.signal_quality_avg * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Analysis History */}
      {analysisHistory.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Analysis History</h2>
          <div className="overflow-x-auto">
            <table className="w-full table-auto">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Asset</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Return</th>
                  <th className="text-left py-2">Win Rate</th>
                  <th className="text-left py-2">Trades</th>
                  <th className="text-left py-2">Sharpe</th>
                  <th className="text-left py-2">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {analysisHistory.map((analysis, index) => (
                  <tr key={index} className="border-b">
                    <td className="py-2 font-medium">{analysis.ticker}</td>
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(analysis.status)}
                        <span className="text-sm capitalize">{analysis.status}</span>
                      </div>
                    </td>
                    <td className={`py-2 font-medium ${analysis.results ? getReturnColor(analysis.results.total_return) : 'text-gray-500'}`}>
                      {analysis.results ? formatPercentage(analysis.results.total_return) : '-'}
                    </td>
                    <td className="py-2">
                      {analysis.results ? `${analysis.results.win_rate.toFixed(1)}%` : '-'}
                    </td>
                    <td className="py-2">
                      {analysis.results ? analysis.results.num_trades : '-'}
                    </td>
                    <td className="py-2">
                      {analysis.results ? analysis.results.sharpe_ratio.toFixed(2) : '-'}
                    </td>
                    <td className="py-2 text-red-600">
                      {analysis.results ? formatPercentage(analysis.results.max_drawdown) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default LGMMTradingAnalyzer;
