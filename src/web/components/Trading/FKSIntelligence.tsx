import { 
  Brain, 
  Cpu, 
  Server, 
  Wifi, 
  WifiOff,
  Clock,
  Play,
  Pause,
  RotateCcw,
  Plus
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

interface TransformerService {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'error' | 'starting';
  gpuUsage: number;
  memoryUsage: number;
  modelLoaded: string;
  lastActivity: Date;
  tasksInQueue: number;
  performanceMetrics: {
    avgResponseTime: number;
    successRate: number;
    totalRequests: number;
  };
}

interface IntelligenceWorkload {
  id: string;
  type: 'market_analysis' | 'strategy_optimization' | 'risk_assessment' | 'pattern_recognition';
  priority: 'high' | 'medium' | 'low';
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  estimatedTime: number;
  result?: any;
  createdAt: Date;
  completedAt?: Date;
}

interface SystemMetrics {
  cpuUsage: number;
  gpuUsage: number;
  memoryUsage: number;
  networkLatency: number;
  storageUsage: number;
  activeConnections: number;
  queueLength: number;
}

const FKSIntelligence: React.FC = () => {
  const [transformerServices, setTransformerServices] = useState<TransformerService[]>([]);
  const [workloads, setWorkloads] = useState<IntelligenceWorkload[]>([]);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [selectedView, setSelectedView] = useState<'overview' | 'services' | 'workloads' | 'monitoring'>('overview');
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    loadTransformerServices();
    loadWorkloads();
    loadSystemMetrics();
    
    // Simulate real-time updates
    const interval = setInterval(() => {
      updateMetrics();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const loadTransformerServices = () => {
    const services: TransformerService[] = [
      {
        id: 'main-transformer',
        name: 'Main Transformer (CUDA)',
        status: 'running',
        gpuUsage: 78,
        memoryUsage: 12.4,
        modelLoaded: 'FKS-Trading-v2.1',
        lastActivity: new Date(),
        tasksInQueue: 3,
        performanceMetrics: {
          avgResponseTime: 245,
          successRate: 0.987,
          totalRequests: 15678
        }
      },
      {
        id: 'backup-transformer',
        name: 'Backup Transformer (CPU)',
        status: 'stopped',
        gpuUsage: 0,
        memoryUsage: 2.1,
        modelLoaded: 'FKS-Trading-v1.8',
        lastActivity: new Date(Date.now() - 3600000),
        tasksInQueue: 0,
        performanceMetrics: {
          avgResponseTime: 1200,
          successRate: 0.942,
          totalRequests: 2341
        }
      },
      {
        id: 'analysis-transformer',
        name: 'Market Analysis Specialist',
        status: 'running',
        gpuUsage: 45,
        memoryUsage: 8.7,
        modelLoaded: 'FKS-Analysis-v1.5',
        lastActivity: new Date(),
        tasksInQueue: 7,
        performanceMetrics: {
          avgResponseTime: 180,
          successRate: 0.994,
          totalRequests: 8902
        }
      }
    ];

    setTransformerServices(services);
  };

  const loadWorkloads = () => {
    const workloads: IntelligenceWorkload[] = [
      {
        id: '1',
        type: 'market_analysis',
        priority: 'high',
        status: 'processing',
        progress: 67,
        estimatedTime: 45,
        createdAt: new Date(Date.now() - 120000)
      },
      {
        id: '2',
        type: 'strategy_optimization',
        priority: 'medium',
        status: 'queued',
        progress: 0,
        estimatedTime: 180,
        createdAt: new Date(Date.now() - 60000)
      },
      {
        id: '3',
        type: 'pattern_recognition',
        priority: 'high',
        status: 'completed',
        progress: 100,
        estimatedTime: 0,
        createdAt: new Date(Date.now() - 300000),
        completedAt: new Date(Date.now() - 30000),
        result: { patterns_found: 12, confidence: 0.89 }
      },
      {
        id: '4',
        type: 'risk_assessment',
        priority: 'low',
        status: 'queued',
        progress: 0,
        estimatedTime: 120,
        createdAt: new Date()
      }
    ];

    setWorkloads(workloads);
  };

  const loadSystemMetrics = () => {
    setSystemMetrics({
      cpuUsage: 45,
      gpuUsage: 78,
      memoryUsage: 67,
      networkLatency: 12,
      storageUsage: 34,
      activeConnections: 8,
      queueLength: 10
    });
  };

  const updateMetrics = () => {
    if (systemMetrics) {
      setSystemMetrics(prev => prev ? {
        ...prev,
        cpuUsage: Math.max(0, Math.min(100, prev.cpuUsage + (Math.random() - 0.5) * 10)),
        gpuUsage: Math.max(0, Math.min(100, prev.gpuUsage + (Math.random() - 0.5) * 5)),
        memoryUsage: Math.max(0, Math.min(100, prev.memoryUsage + (Math.random() - 0.5) * 8)),
        networkLatency: Math.max(0, prev.networkLatency + (Math.random() - 0.5) * 5),
        queueLength: Math.max(0, prev.queueLength + Math.floor((Math.random() - 0.6) * 3))
      } : null);
    }
  };

  const startService = (serviceId: string) => {
    setTransformerServices(prev => 
      prev.map(service => 
        service.id === serviceId ? { ...service, status: 'starting' as const } : service
      )
    );
    
    setTimeout(() => {
      setTransformerServices(prev => 
        prev.map(service => 
          service.id === serviceId ? { ...service, status: 'running' as const } : service
        )
      );
    }, 2000);
  };

  const stopService = (serviceId: string) => {
    setTransformerServices(prev => 
      prev.map(service => 
        service.id === serviceId ? { ...service, status: 'stopped' as const } : service
      )
    );
  };

  const restartService = (serviceId: string) => {
    stopService(serviceId);
    setTimeout(() => startService(serviceId), 1000);
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* System Status */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">System Status</p>
              <p className={`text-lg font-semibold ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
                {isConnected ? 'Online' : 'Offline'}
              </p>
            </div>
            {isConnected ? <Wifi className="w-6 h-6 text-green-400" /> : <WifiOff className="w-6 h-6 text-red-400" />}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Active Services</p>
              <p className="text-lg font-semibold text-white">
                {transformerServices.filter(s => s.status === 'running').length}/{transformerServices.length}
              </p>
            </div>
            <Server className="w-6 h-6 text-blue-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">Queue Length</p>
              <p className="text-lg font-semibold text-white">{systemMetrics?.queueLength || 0}</p>
            </div>
            <Clock className="w-6 h-6 text-yellow-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400">GPU Usage</p>
              <p className="text-lg font-semibold text-white">{systemMetrics?.gpuUsage || 0}%</p>
            </div>
            <Cpu className="w-6 h-6 text-purple-400" />
          </div>
        </div>
      </div>

      {/* Resource Usage */}
      {systemMetrics && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">Resource Usage</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">CPU</span>
                <span className="text-white">{systemMetrics.cpuUsage.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-blue-400 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${systemMetrics.cpuUsage}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">GPU</span>
                <span className="text-white">{systemMetrics.gpuUsage.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-purple-400 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${systemMetrics.gpuUsage}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">Memory</span>
                <span className="text-white">{systemMetrics.memoryUsage.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-green-400 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${systemMetrics.memoryUsage}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Workloads */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Recent Intelligence Tasks</h3>
        <div className="space-y-3">
          {workloads.slice(0, 5).map(workload => (
            <div key={workload.id} className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
              <div className="flex items-center space-x-3">
                <div className={`w-2 h-2 rounded-full ${
                  workload.status === 'completed' ? 'bg-green-400' :
                  workload.status === 'processing' ? 'bg-yellow-400' :
                  workload.status === 'failed' ? 'bg-red-400' :
                  'bg-gray-400'
                }`}></div>
                <div>
                  <p className="text-white font-medium capitalize">
                    {workload.type.replace('_', ' ')}
                  </p>
                  <p className="text-xs text-gray-400">
                    {workload.status === 'completed' ? 'Completed' : 
                     workload.status === 'processing' ? `${workload.progress}% complete` :
                     'Queued'}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className={`text-xs px-2 py-1 rounded ${
                  workload.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                  workload.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {workload.priority}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderServices = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-white">Transformer Services</h2>
        <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors">
          <Plus className="w-4 h-4" />
          <span>Add Service</span>
        </button>
      </div>

      <div className="space-y-4">
        {transformerServices.map(service => (
          <div key={service.id} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">{service.name}</h3>
                <p className="text-gray-400">Model: {service.modelLoaded}</p>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`px-3 py-1 rounded-full text-sm ${
                  service.status === 'running' ? 'bg-green-500/20 text-green-400' :
                  service.status === 'starting' ? 'bg-yellow-500/20 text-yellow-400' :
                  service.status === 'error' ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {service.status}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="text-center">
                <div className="text-lg font-bold text-purple-400">{service.gpuUsage}%</div>
                <div className="text-xs text-gray-500">GPU Usage</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-blue-400">{service.memoryUsage}GB</div>
                <div className="text-xs text-gray-500">Memory</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-yellow-400">{service.tasksInQueue}</div>
                <div className="text-xs text-gray-500">Queue</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-400">{service.performanceMetrics.avgResponseTime}ms</div>
                <div className="text-xs text-gray-500">Avg Response</div>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-400">
                Success Rate: {(service.performanceMetrics.successRate * 100).toFixed(1)}% • 
                Total Requests: {service.performanceMetrics.totalRequests.toLocaleString()}
              </div>
              
              <div className="flex items-center space-x-2">
                {service.status === 'running' ? (
                  <button 
                    onClick={() => stopService(service.id)}
                    className="flex items-center space-x-1 px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm text-white transition-colors"
                  >
                    <Pause className="w-3 h-3" />
                    <span>Stop</span>
                  </button>
                ) : (
                  <button 
                    onClick={() => startService(service.id)}
                    className="flex items-center space-x-1 px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm text-white transition-colors"
                  >
                    <Play className="w-3 h-3" />
                    <span>Start</span>
                  </button>
                )}
                <button 
                  onClick={() => restartService(service.id)}
                  className="flex items-center space-x-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Restart</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderWorkloads = () => (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-white">Intelligence Workloads</h2>
      
      <div className="space-y-3">
        {workloads.map(workload => (
          <div key={workload.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="font-semibold text-white capitalize">
                  {workload.type.replace('_', ' ')}
                </h3>
                <p className="text-sm text-gray-400">
                  Created {new Date(workload.createdAt).toLocaleTimeString()}
                </p>
              </div>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-1 rounded text-xs ${
                  workload.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                  workload.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {workload.priority}
                </span>
                <span className={`px-2 py-1 rounded text-xs ${
                  workload.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                  workload.status === 'processing' ? 'bg-blue-500/20 text-blue-400' :
                  workload.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-500/20 text-gray-400'
                }`}>
                  {workload.status}
                </span>
              </div>
            </div>

            {workload.status === 'processing' && (
              <div className="mb-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Progress</span>
                  <span className="text-white">{workload.progress}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div 
                    className="bg-blue-400 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${workload.progress}%` }}
                  ></div>
                </div>
              </div>
            )}

            {workload.result && (
              <div className="mt-3 p-3 bg-gray-700/50 rounded-lg">
                <p className="text-sm text-gray-400 mb-1">Result:</p>
                <pre className="text-xs text-white overflow-auto">
                  {JSON.stringify(workload.result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Brain className="w-8 h-8 text-purple-400" />
          <div>
            <h1 className="text-3xl font-bold text-white">FKS Intelligence</h1>
            <p className="text-gray-400">
              GPU-accelerated transformer service for trading intelligence
            </p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setSelectedView('overview')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              selectedView === 'overview' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setSelectedView('services')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              selectedView === 'services' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300'
            }`}
          >
            Services
          </button>
          <button
            onClick={() => setSelectedView('workloads')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              selectedView === 'workloads' ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300'
            }`}
          >
            Workloads
          </button>
        </div>
      </div>

      {/* Content */}
      {selectedView === 'overview' && renderOverview()}
      {selectedView === 'services' && renderServices()}
      {selectedView === 'workloads' && renderWorkloads()}
    </div>
  );
};

export default FKSIntelligence;
