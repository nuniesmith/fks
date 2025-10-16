import { Activity, CheckCircle, XCircle, AlertTriangle, RefreshCw, Server, Database, Zap } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { realTimeDataService } from '../../services/realTimeDataService';

import type { SystemHealth, SystemOverview, ComponentStatus } from '../../services/realTimeDataService';

interface ServiceDetail {
  name: string;
  type: 'api' | 'database' | 'cache' | 'worker' | 'external';
  url: string;
  port: number;
  status: 'healthy' | 'warning' | 'error';
  responseTime: number;
  uptime: string;
  version: string;
  lastChecked: string;
  metrics?: {
    cpu?: number;
    memory?: number;
    connections?: number;
    requests?: number;
  };
}

const ServicesMonitor: React.FC = () => {
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth[]>([]);
  const [componentStatus, setComponentStatus] = useState<ComponentStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Mock detailed services data
  const [services, setServices] = useState<ServiceDetail[]>([
    {
      name: 'FKS API Server',
      type: 'api',
      url: 'https://api.fkstrading.xyz',
      port: 8000,
      status: 'healthy',
      responseTime: 45,
      uptime: '2d 14h 32m',
      version: '1.0.0',
      lastChecked: new Date().toISOString(),
      metrics: { cpu: 12.5, memory: 68.2, connections: 45, requests: 1250 }
    },
    {
      name: 'TimescaleDB Database',
      type: 'database',
      url: 'https://db.fkstrading.xyz',
      port: 5432,
      status: 'healthy',
      responseTime: 8,
      uptime: '15d 6h 42m',
      version: 'PG17 + Timescale 2.x',
      lastChecked: new Date().toISOString(),
      metrics: { cpu: 5.8, memory: 45.1, connections: 12, requests: 890 }
    },
    {
      name: 'Redis Cache',
      type: 'cache',
      url: 'https://cache.fkstrading.xyz',
      port: 6379,
      status: 'healthy',
      responseTime: 2,
      uptime: '15d 6h 42m',
      version: '7.2.0',
      lastChecked: new Date().toISOString(),
      metrics: { cpu: 2.1, memory: 28.5, connections: 8, requests: 2150 }
    },
    {
      name: 'Data Stream Service',
      type: 'api',
      url: 'https://data.fkstrading.xyz',
      port: 9001,
      status: 'warning',
      responseTime: 125,
      uptime: '1d 8h 15m',
      version: '0.9.8',
      lastChecked: new Date().toISOString(),
      metrics: { cpu: 25.8, memory: 82.1, connections: 3, requests: 450 }
    },
    {
      name: 'Worker Service',
      type: 'worker',
      url: 'internal://worker',
      port: 0,
      status: 'healthy',
      responseTime: 0,
      uptime: '2d 12h 8m',
      version: '1.0.0',
      lastChecked: new Date().toISOString(),
      metrics: { cpu: 8.2, memory: 32.4, connections: 0, requests: 0 }
    },
    {
      name: 'Rithmic Data Feed',
      type: 'external',
      url: 'external://rithmic',
      port: 0,
      status: 'healthy',
      responseTime: 95,
      uptime: '5d 2h 18m',
      version: 'R|API+',
      lastChecked: new Date().toISOString(),
      metrics: { cpu: 0, memory: 0, connections: 1, requests: 850 }
    }
  ]);

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        const [overview, health, components] = await Promise.all([
          realTimeDataService.getSystemOverview(),
          realTimeDataService.getSystemHealth(),
          realTimeDataService.getComponentStatus()
        ]);
        setSystemOverview(overview);
        setSystemHealth(health);
        setComponentStatus(components);
        setLastUpdate(new Date());
      } catch (error) {
        console.error('Failed to load services data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();

    // Subscribe to real-time updates
    const unsubscribeHealth = realTimeDataService.subscribe('systemHealth', (health: SystemHealth[]) => {
      setSystemHealth(health);
      setLastUpdate(new Date());
    });

    const unsubscribeComponents = realTimeDataService.subscribe('componentStatus', (components: ComponentStatus[]) => {
      setComponentStatus(components);
      setLastUpdate(new Date());
    });

    // Auto-refresh every 30 seconds
    const interval = autoRefresh ? setInterval(loadData, 30000) : null;

    return () => {
      unsubscribeHealth();
      unsubscribeComponents();
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <AlertTriangle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'api':
        return <Server className="w-5 h-5 text-blue-400" />;
      case 'database':
        return <Database className="w-5 h-5 text-green-400" />;
      case 'cache':
        return <Zap className="w-5 h-5 text-yellow-400" />;
      case 'worker':
        return <Activity className="w-5 h-5 text-purple-400" />;
      case 'external':
        return <RefreshCw className="w-5 h-5 text-indigo-400" />;
      default:
        return <Server className="w-5 h-5 text-gray-400" />;
    }
  };

  const handleRefresh = async () => {
    setIsLoading(true);
    try {
      const [overview, health, components] = await Promise.all([
        realTimeDataService.getSystemOverview(),
        realTimeDataService.getSystemHealth(),
        realTimeDataService.getComponentStatus()
      ]);
      setSystemOverview(overview);
      setSystemHealth(health);
      setComponentStatus(components);
      setLastUpdate(new Date());
      
      // Simulate refreshing service details
      setServices(prevServices => 
        prevServices.map(service => ({
          ...service,
          responseTime: Math.max(1, service.responseTime + (Math.random() - 0.5) * 20),
          lastChecked: new Date().toISOString(),
          metrics: service.metrics ? {
            ...service.metrics,
            cpu: Math.max(0, Math.min(100, service.metrics.cpu + (Math.random() - 0.5) * 10)),
            memory: Math.max(0, Math.min(100, service.metrics.memory + (Math.random() - 0.5) * 5))
          } : undefined
        }))
      );
    } catch (error) {
      console.error('Failed to refresh services data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading && !systemOverview) {
    return (
      <div className="space-y-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-center h-48">
            <div className="text-center">
              <Activity className="w-12 h-12 text-blue-400 mx-auto mb-4 animate-pulse" />
              <p className="text-gray-400">Loading services data...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center">
              <Activity className="w-8 h-8 mr-3 text-blue-400" />
              Services Monitor
            </h1>
            <p className="text-gray-400">Real-time monitoring of FKS system components</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <div className="text-sm text-gray-400">Last Update</div>
              <div className="text-lg font-mono text-white">
                {lastUpdate.toLocaleTimeString()}
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  autoRefresh 
                    ? 'bg-green-600 text-white' 
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                Auto-refresh
              </button>
              <button
                onClick={handleRefresh}
                disabled={isLoading}
                className="p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded text-white transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* System Overview */}
      {systemOverview && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <CheckCircle className="w-8 h-8 text-green-400" />
              <span className="text-2xl font-bold text-green-400">{systemOverview.healthScore}%</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-1">Health Score</h3>
            <p className="text-sm text-gray-400">Overall system health</p>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <Activity className="w-8 h-8 text-blue-400" />
              <span className="text-2xl font-bold text-blue-400">{systemOverview.servicesOnline}</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-1">Services Online</h3>
            <p className="text-sm text-gray-400">Active components</p>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <Server className="w-8 h-8 text-purple-400" />
              <span className="text-2xl font-bold text-purple-400">{systemOverview.avgResponseTime}ms</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-1">Avg Response</h3>
            <p className="text-sm text-gray-400">System response time</p>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <Database className="w-8 h-8 text-green-400" />
              <span className="text-2xl font-bold text-green-400">{systemOverview.uptime}</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-1">System Uptime</h3>
            <p className="text-sm text-gray-400">Continuous operation</p>
          </div>
        </div>
      )}

      {/* Services Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {services.map((service, index) => (
          <div key={index} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-3">
                {getServiceIcon(service.type)}
                <div>
                  <h3 className="text-lg font-semibold text-white">{service.name}</h3>
                  <p className="text-sm text-gray-400">{service.url}:{service.port || 'N/A'}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {getStatusIcon(service.status)}
                <span className="text-sm text-gray-400">v{service.version}</span>
              </div>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <div className="text-sm text-gray-400">Response</div>
                <div className="text-lg font-bold text-white">{service.responseTime}ms</div>
              </div>
              <div>
                <div className="text-sm text-gray-400">Uptime</div>
                <div className="text-lg font-bold text-white">{service.uptime}</div>
              </div>
              {service.metrics?.cpu !== undefined && (
                <div>
                  <div className="text-sm text-gray-400">CPU</div>
                  <div className="text-lg font-bold text-white">{service.metrics.cpu.toFixed(1)}%</div>
                </div>
              )}
              {service.metrics?.memory !== undefined && (
                <div>
                  <div className="text-sm text-gray-400">Memory</div>
                  <div className="text-lg font-bold text-white">{service.metrics.memory.toFixed(1)}%</div>
                </div>
              )}
            </div>
            
            {service.metrics && (
              <div className="space-y-2">
                {service.metrics.cpu !== undefined && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400">CPU Usage</span>
                      <span className="text-white">{service.metrics.cpu.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div 
                        className="bg-blue-400 h-2 rounded-full" 
                        style={{ width: `${service.metrics.cpu}%` }}
                      ></div>
                    </div>
                  </div>
                )}
                {service.metrics.memory !== undefined && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400">Memory Usage</span>
                      <span className="text-white">{service.metrics.memory.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div 
                        className="bg-green-400 h-2 rounded-full" 
                        style={{ width: `${service.metrics.memory}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            )}
            
            <div className="mt-4 text-xs text-gray-500">
              Last checked: {new Date(service.lastChecked).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>

      {/* Component Status Table */}
      {componentStatus.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4">Component Status</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-2 text-gray-400">Component</th>
                  <th className="text-center py-2 text-gray-400">Status</th>
                  <th className="text-center py-2 text-gray-400">Version</th>
                  <th className="text-center py-2 text-gray-400">Health</th>
                  <th className="text-right py-2 text-gray-400">Last Update</th>
                </tr>
              </thead>
              <tbody>
                {componentStatus.map((component, index) => (
                  <tr key={index} className="border-b border-gray-800 hover:bg-gray-900/50">
                    <td className="py-3 text-white font-medium">{component.name}</td>
                    <td className="py-3 text-center">
                      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        component.connected 
                          ? 'bg-green-900 text-green-300' 
                          : 'bg-red-900 text-red-300'
                      }`}>
                        {component.connected ? 'Connected' : 'Disconnected'}
                      </span>
                    </td>
                    <td className="py-3 text-center text-gray-300">{component.version || 'N/A'}</td>
                    <td className="py-3 text-center">
                      {component.healthScore !== undefined ? (
                        <span className="text-white">{component.healthScore}%</span>
                      ) : (
                        <span className="text-gray-400">N/A</span>
                      )}
                    </td>
                    <td className="py-3 text-right text-gray-400">
                      {component.lastUpdate ? new Date(component.lastUpdate).toLocaleTimeString() : 'N/A'}
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

export default ServicesMonitor;
