import {
  Brain,
  MessageSquare,
  TrendingUp,
  BarChart3,
  RefreshCw,
  Zap,
  Eye,
  CheckCircle,
  AlertCircle,
  Clock,
  Layers,
  Target,
  Sparkles
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

interface TransformerModel {
  id: string;
  name: string;
  type: 'sentiment' | 'classification' | 'generation' | 'embedding';
  status: 'active' | 'loading' | 'idle' | 'error';
  accuracy: number;
  latency: number; // ms
  memoryUsage: number; // GB
  parameters: string; // e.g., "7B", "13B"
  lastUpdated: string;
}

interface AnalysisResult {
  id: string;
  type: 'sentiment' | 'trend' | 'risk' | 'opportunity';
  confidence: number;
  text: string;
  source: string;
  timestamp: string;
  metadata: Record<string, any>;
}

interface InferenceJob {
  id: string;
  model: string;
  input: string;
  output?: string;
  status: 'processing' | 'completed' | 'failed' | 'queued';
  startTime: string;
  processingTime?: number;
  confidence?: number;
}

interface ModelPerformance {
  modelId: string;
  requestsPerSecond: number;
  averageLatency: number;
  successRate: number;
  errorRate: number;
  gpuUtilization: number;
}

const FKSTransformer: React.FC = () => {
  const [models, setModels] = useState<TransformerModel[]>([]);
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([]);
  const [inferenceJobs, setInferenceJobs] = useState<InferenceJob[]>([]);
  const [performance, setPerformance] = useState<ModelPerformance[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [filter, setFilter] = useState<string>('all');
  // Live transformer demo state
  const [liveWindow, setLiveWindow] = useState<number>(64);
  const [liveLoading, setLiveLoading] = useState<boolean>(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [liveResult, setLiveResult] = useState<any>(null);

  // Initialize mock data
  useEffect(() => {
    setModels([
      {
        id: 'sentiment-v2',
        name: 'FKS Sentiment Analyzer v1.0',
        type: 'sentiment',
        status: 'active',
        accuracy: 94.2,
        latency: 45,
        memoryUsage: 2.8,
        parameters: '7B',
        lastUpdated: '2025-01-27 15:30:00'
      },
      {
        id: 'market-classifier',
        name: 'Market Event Classifier',
        type: 'classification',
        status: 'active',
        accuracy: 89.7,
        latency: 78,
        memoryUsage: 4.1,
        parameters: '13B',
        lastUpdated: '2025-01-27 14:45:00'
      },
      {
        id: 'news-generator',
        name: 'News Summary Generator',
        type: 'generation',
        status: 'idle',
        accuracy: 87.3,
        latency: 1200,
        memoryUsage: 6.2,
        parameters: '13B',
        lastUpdated: '2025-01-27 12:00:00'
      },
      {
        id: 'embedding-model',
        name: 'Financial Text Embeddings',
        type: 'embedding',
        status: 'active',
        accuracy: 92.1,
        latency: 23,
        memoryUsage: 1.9,
        parameters: '7B',
        lastUpdated: '2025-01-27 15:20:00'
      }
    ]);

    setAnalysisResults([
      {
        id: '1',
        type: 'sentiment',
        confidence: 0.89,
        text: 'Federal Reserve signals dovish stance on interest rates',
        source: 'Reuters',
        timestamp: '2025-01-27 15:45:00',
        metadata: { sentiment: 'positive', entities: ['Federal Reserve', 'interest rates'] }
      },
      {
        id: '2',
        type: 'opportunity',
        confidence: 0.76,
        text: 'Tech earnings showing strong momentum in AI sector',
        source: 'Bloomberg',
        timestamp: '2025-01-27 15:30:00',
        metadata: { sector: 'technology', keywords: ['earnings', 'AI', 'momentum'] }
      },
      {
        id: '3',
        type: 'risk',
        confidence: 0.82,
        text: 'Geopolitical tensions escalating in Eastern Europe',
        source: 'Financial Times',
        timestamp: '2025-01-27 14:15:00',
        metadata: { risk_level: 'high', regions: ['Eastern Europe'], impact: 'market_volatility' }
      }
    ]);

    setPerformance([
      {
        modelId: 'sentiment-v2',
        requestsPerSecond: 24.7,
        averageLatency: 45,
        successRate: 99.2,
        errorRate: 0.8,
        gpuUtilization: 34
      },
      {
        modelId: 'market-classifier',
        requestsPerSecond: 18.3,
        averageLatency: 78,
        successRate: 97.8,
        errorRate: 2.2,
        gpuUtilization: 28
      }
    ]);
  }, []);

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setPerformance(prev => prev.map(perf => ({
        ...perf,
        requestsPerSecond: perf.requestsPerSecond + (Math.random() - 0.5) * 2,
        averageLatency: Math.max(10, perf.averageLatency + (Math.random() - 0.5) * 10),
        gpuUtilization: Math.max(0, Math.min(100, perf.gpuUtilization + (Math.random() - 0.5) * 5))
      })));
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'loading':
        return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'idle':
        return <Clock className="w-4 h-4 text-yellow-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'sentiment':
        return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'classification':
        return <Layers className="w-4 h-4 text-blue-400" />;
      case 'generation':
        return <MessageSquare className="w-4 h-4 text-purple-400" />;
      case 'embedding':
        return <Target className="w-4 h-4 text-orange-400" />;
      default:
        return <Brain className="w-4 h-4 text-gray-400" />;
    }
  };

  const getAnalysisTypeIcon = (type: string) => {
    switch (type) {
      case 'sentiment':
        return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'trend':
        return <BarChart3 className="w-4 h-4 text-blue-400" />;
      case 'risk':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      case 'opportunity':
        return <Sparkles className="w-4 h-4 text-yellow-400" />;
      default:
        return <Eye className="w-4 h-4 text-gray-400" />;
    }
  };

  const handleInference = async () => {
    if (!selectedModel || !inputText.trim()) return;

    setIsProcessing(true);
    
    const newJob: InferenceJob = {
      id: Date.now().toString(),
      model: selectedModel,
      input: inputText,
      status: 'processing',
      startTime: new Date().toISOString()
    };

    setInferenceJobs(prev => [newJob, ...prev]);

    // Simulate processing
    setTimeout(() => {
      setInferenceJobs(prev => prev.map(job => 
        job.id === newJob.id 
          ? {
              ...job,
              status: 'completed',
              output: 'Simulated model output: Positive sentiment detected with high confidence.',
              processingTime: Math.random() * 200 + 50,
              confidence: Math.random() * 0.3 + 0.7
            }
          : job
      ));
      setIsProcessing(false);
      setInputText('');
    }, 2000);
  };

  const filteredResults = analysisResults.filter(result => 
    filter === 'all' || result.type === filter
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center space-x-3">
            <Brain className="w-8 h-8 text-purple-400" />
            <span>FKS Transformer Service</span>
          </h1>
          <p className="text-gray-400 mt-2">
            GPU-accelerated NLP and sentiment analysis for intelligent trading decisions
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors">
            Model Settings
          </button>
        </div>
      </div>

      {/* Model Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {models.map((model) => (
          <div key={model.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                {getTypeIcon(model.type)}
                {getStatusIcon(model.status)}
              </div>
              <span className="text-xs text-gray-400">{model.parameters}</span>
            </div>
            
            <h3 className="font-medium text-white mb-2 text-sm">{model.name}</h3>
            
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">Accuracy:</span>
                <span className="text-green-400">{model.accuracy}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Latency:</span>
                <span className="text-white">{model.latency}ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Memory:</span>
                <span className="text-blue-400">{model.memoryUsage}GB</span>
              </div>
            </div>

            {/* Performance indicator */}
            {performance.find(p => p.modelId === model.id) && (
              <div className="mt-3 pt-3 border-t border-gray-700">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">RPS:</span>
                  <span className="text-yellow-400">
                    {performance.find(p => p.modelId === model.id)?.requestsPerSecond.toFixed(1)}
                  </span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Interactive Inference */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Live Inference</h3>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Select Model
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-purple-500"
            >
              <option value="">Choose a model...</option>
              {models.filter(m => m.status === 'active').map(model => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.type})
                </option>
              ))}
            </select>

            <label className="block text-sm font-medium text-gray-400 mb-2 mt-4">
              Input Text
            </label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Enter text for analysis (news, earnings reports, market updates)..."
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-purple-500 h-32 resize-none"
            />

            <button
              onClick={handleInference}
              disabled={!selectedModel || !inputText.trim() || isProcessing}
              className="w-full mt-4 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center justify-center space-x-2"
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Run Inference</span>
                </>
              )}
            </button>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Recent Inference Jobs</h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {inferenceJobs.slice(0, 5).map((job) => (
                <div key={job.id} className="bg-gray-700/50 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white truncate">{job.model}</span>
                    <span className={`text-xs px-2 py-1 rounded ${
                      job.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                      job.status === 'processing' ? 'bg-blue-500/20 text-blue-400' :
                      job.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {job.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mb-2 truncate">{job.input}</p>
                  {job.output && (
                    <p className="text-xs text-green-400">{job.output}</p>
                  )}
                  {job.confidence && (
                    <div className="text-xs text-gray-400 mt-1">
                      Confidence: {(job.confidence * 100).toFixed(1)}%
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Live Transformer Ping (Backend demo) */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Transformer /predict demo</h3>
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-400">window</label>
            <input
              type="number"
              min={16}
              max={256}
              value={liveWindow}
              onChange={(e) => setLiveWindow(Math.max(16, Math.min(256, Number(e.target.value) || 64)))}
              className="w-24 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
            />
            <button
              onClick={async () => {
                setLiveLoading(true);
                setLiveError(null);
                setLiveResult(null);
                try {
                  // Prefer configured base if present, else same-origin path
                  const base = (import.meta as any).env?.VITE_TRANSFORMER_URL?.replace(/\/$/, '') || '';
                  const url = `${base}/transformer/predict?window=${encodeURIComponent(liveWindow)}`;
                  const res = await fetch(url, { method: 'GET' });
                  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
                  const json = await res.json();
                  setLiveResult(json);
                } catch (err: any) {
                  setLiveError(err?.message || String(err));
                } finally {
                  setLiveLoading(false);
                }
              }}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white rounded-lg transition-colors flex items-center gap-2"
              disabled={liveLoading}
            >
              {liveLoading ? (<><RefreshCw className="w-4 h-4 animate-spin" /><span>Requesting…</span></>) : (<><Zap className="w-4 h-4" /><span>Ping /predict</span></>)}
            </button>
          </div>
        </div>
        {liveError && (
          <div className="text-sm text-red-400">Error: {liveError}</div>
        )}
        {liveResult && (
          <div className="mt-3 text-xs text-gray-200 bg-gray-900/60 rounded p-3 overflow-auto">
            <pre className="whitespace-pre-wrap break-words">{JSON.stringify(liveResult, null, 2)}</pre>
          </div>
        )}
        {!liveError && !liveResult && !liveLoading && (
          <div className="text-sm text-gray-400">Use the button to call the backend demo endpoint. In dev behind nginx, /transformer/predict is routed automatically.</div>
        )}
      </div>

      {/* Analysis Results */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Real-time Analysis Results</h3>
            <div className="flex items-center space-x-3">
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="px-3 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-purple-500"
              >
                <option value="all">All Types</option>
                <option value="sentiment">Sentiment</option>
                <option value="trend">Trend</option>
                <option value="risk">Risk</option>
                <option value="opportunity">Opportunity</option>
              </select>
              <button className="p-2 hover:bg-gray-700 rounded transition-colors">
                <RefreshCw className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </div>
        </div>

        <div className="divide-y divide-gray-700">
          {filteredResults.map((result) => (
            <div key={result.id} className="p-6">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                  {getAnalysisTypeIcon(result.type)}
                  <div>
                    <div className={`text-sm font-medium capitalize ${
                      result.type === 'sentiment' ? 'text-green-400' :
                      result.type === 'trend' ? 'text-blue-400' :
                      result.type === 'risk' ? 'text-red-400' :
                      result.type === 'opportunity' ? 'text-yellow-400' :
                      'text-gray-400'
                    }`}>
                      {result.type}
                    </div>
                    <div className="text-xs text-gray-400">{result.source}</div>
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="text-sm text-white">
                    {(result.confidence * 100).toFixed(0)}% confidence
                  </div>
                  <div className="text-xs text-gray-400">{result.timestamp}</div>
                </div>
              </div>

              <p className="text-white mb-3">{result.text}</p>

              {/* Confidence bar */}
              <div className="w-full bg-gray-700 rounded-full h-1.5 mb-3">
                <div
                  className={`h-1.5 rounded-full ${
                    result.confidence > 0.8 ? 'bg-green-400' :
                    result.confidence > 0.6 ? 'bg-yellow-400' : 'bg-red-400'
                  }`}
                  style={{ width: `${result.confidence * 100}%` }}
                />
              </div>

              {/* Metadata */}
              {Object.keys(result.metadata).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(result.metadata).map(([key, value]) => (
                    <span
                      key={key}
                      className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded"
                    >
                      {key}: {Array.isArray(value) ? value.join(', ') : String(value)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {performance.map((perf) => {
          const model = models.find(m => m.id === perf.modelId);
          if (!model) return null;

          return (
            <div key={perf.modelId} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h4 className="font-medium text-white mb-4">{model.name} Performance</h4>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-gray-400">Requests/sec</div>
                  <div className="text-xl font-bold text-white">{perf.requestsPerSecond.toFixed(1)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400">Avg Latency</div>
                  <div className="text-xl font-bold text-white">{perf.averageLatency.toFixed(0)}ms</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400">Success Rate</div>
                  <div className="text-xl font-bold text-green-400">{perf.successRate.toFixed(1)}%</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400">GPU Usage</div>
                  <div className="text-xl font-bold text-blue-400">{perf.gpuUtilization.toFixed(0)}%</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="text-sm text-gray-400 mb-2">GPU Utilization</div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-400 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${perf.gpuUtilization}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default FKSTransformer;
