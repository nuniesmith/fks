import {
  Activity,
  AlertCircle,
  BarChart3,
  Brain,
  CheckCircle,
  Database,
  Globe,
  LineChart,
  TrendingUp,
  Zap,
  XCircle,
  RefreshCw,
  Play,
  Square,
  ToggleLeft,
  ToggleRight,
  DollarSign,
  Users
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useTradingEnv } from '../../context/TradingEnvContext';
import { 
  realTimeDataService 
} from '../../services/realTimeDataService';

import type { 
  SystemHealth, 
  TradingMetrics as LiveTradingMetrics, 
  ComponentStatus as LiveComponentStatus 
} from '../../services/realTimeDataService';

interface SystemStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'down';
  uptime: string;
  lastCheck: string;
}

interface TradingMetrics {
  dailyPnL: number;
  totalTrades: number;
  winRate: number;
  activePositions: number;
  signalQuality: number;
  marketRegime: string;
  environment: 'SIMULATION' | 'LIVE';
}

interface ComponentStatus {
  name: string;
  connected: boolean;
  version?: string;
  lastUpdate?: string;
}

const Dashboard: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<SystemHealth[]>([]);
  const [simulationMetrics, setSimulationMetrics] = useState<LiveTradingMetrics | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<LiveTradingMetrics | null>(null);
  const [fksComponents, setFksComponents] = useState<LiveComponentStatus[]>([]);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isLoading, setIsLoading] = useState(true);
  const [lastDataUpdate, setLastDataUpdate] = useState<Date>(new Date());
  
  // Trading environment context
  const { environment, tradingConfig, updateEnvironment, isLive, isSimulation } = useTradingEnv();

  // Real-time data subscriptions
  useEffect(() => {
    const loadInitialData = async () => {
      setIsLoading(true);
      try {
        const [health, metrics, components] = await Promise.all([
          realTimeDataService.getSystemHealth(),
          realTimeDataService.getTradingMetrics(),
          realTimeDataService.getComponentStatus()
        ]);
        
        setSystemStatus(health);
        // Set metrics based on current environment
        if (isSimulation) {
          setSimulationMetrics(metrics);
        } else {
          setLiveMetrics(metrics);
        }
        setFksComponents(components);
        setLastDataUpdate(new Date());
      } catch (error) {
        console.error('Failed to load initial data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();

    // Subscribe to real-time updates
    const unsubscribeHealth = realTimeDataService.subscribe('systemHealth', (data: SystemHealth[]) => {
      setSystemStatus(data);
      setLastDataUpdate(new Date());
    });

    const unsubscribeMetrics = realTimeDataService.subscribe('tradingMetrics', (data: LiveTradingMetrics) => {
      // Update appropriate metrics based on current environment
      if (isSimulation) {
        setSimulationMetrics(data);
      } else {
        setLiveMetrics(data);
      }
      setLastDataUpdate(new Date());
    });

    const unsubscribeComponents = realTimeDataService.subscribe('componentStatus', (data: LiveComponentStatus[]) => {
      setFksComponents(data);
      setLastDataUpdate(new Date());
    });

    // Cleanup subscriptions
    return () => {
      unsubscribeHealth();
      unsubscribeMetrics();
      unsubscribeComponents();
    };
  }, [isSimulation]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Get current trading metrics based on environment
  const currentMetrics = isSimulation ? simulationMetrics : liveMetrics;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'degraded':
        return <AlertCircle className="w-5 h-5 text-yellow-500" />;
      case 'down':
        return <XCircle className="w-5 h-5 text-red-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'degraded':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'down':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Environment Switcher */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">FKS Trading Systems</h1>
            <div className="flex items-center space-x-4">
              <p className="text-gray-400">Real-time system monitoring and trading overview</p>
              {isLoading && (
                <div className="flex items-center space-x-2 text-blue-400">
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Loading...</span>
                </div>
              )}
            </div>
            
            {/* Environment Toggle */}
            <div className="mt-4 flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-400">Environment:</span>
                <button
                  onClick={() => updateEnvironment(isLive ? 'SIMULATION' : 'LIVE')}
                  className={`flex items-center space-x-2 px-3 py-1 rounded-lg border transition-colors ${
                    isSimulation 
                      ? 'bg-blue-500/20 border-blue-500 text-blue-400' 
                      : 'bg-red-500/20 border-red-500 text-red-400'
                  }`}
                >
                  {isSimulation ? <Play className="w-4 h-4" /> : <Square className="w-4 h-4" />}
                  <span className="font-medium">{environment}</span>
                  {isSimulation ? <ToggleLeft className="w-4 h-4" /> : <ToggleRight className="w-4 h-4" />}
                </button>
              </div>
              <div className="text-xs text-gray-500">
                {isSimulation ? 'Safe practice mode with simulated data' : 'Live trading with real money'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Current Time</div>
            <div className="text-xl font-mono text-white">
              {currentTime.toLocaleTimeString()}
            </div>
            <div className="text-sm text-gray-400">
              {currentTime.toLocaleDateString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Last Update: {lastDataUpdate.toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>

      {/* Dual Environment Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Simulation Environment */}
        <div className={`rounded-lg p-6 border-2 transition-all ${
          isSimulation ? 'bg-blue-900/30 border-blue-500' : 'bg-gray-800 border-gray-700'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-white flex items-center">
              <Play className="w-5 h-5 mr-2 text-blue-400" />
              Simulation Environment
            </h2>
            <div className={`px-3 py-1 rounded-full text-xs ${
              isSimulation ? 'bg-blue-500 text-white' : 'bg-gray-600 text-gray-300'
            }`}>
              {isSimulation ? 'ACTIVE' : 'STANDBY'}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-lg font-bold text-blue-400">
                ${simulationMetrics?.dailyPnL.toLocaleString() || '--'}
              </div>
              <div className="text-xs text-gray-400">Sim P&L</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-white">
                {simulationMetrics?.totalTrades || 0}
              </div>
              <div className="text-xs text-gray-400">Sim Trades</div>
            </div>
          </div>
        </div>

        {/* Live Environment */}
        <div className={`rounded-lg p-6 border-2 transition-all ${
          isLive ? 'bg-red-900/30 border-red-500' : 'bg-gray-800 border-gray-700'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-white flex items-center">
              <DollarSign className="w-5 h-5 mr-2 text-red-400" />
              Live Trading Environment
            </h2>
            <div className={`px-3 py-1 rounded-full text-xs ${
              isLive ? 'bg-red-500 text-white' : 'bg-gray-600 text-gray-300'
            }`}>
              {isLive ? 'LIVE' : 'STANDBY'}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-lg font-bold text-red-400">
                ${liveMetrics?.dailyPnL.toLocaleString() || '--'}
              </div>
              <div className="text-xs text-gray-400">Live P&L</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-white">
                {liveMetrics?.totalTrades || 0}
              </div>
              <div className="text-xs text-gray-400">Live Trades</div>
            </div>
          </div>
        </div>
      </div>

      {/* Current Environment Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-400">Daily P&L ({environment})</p>
              <p className={`text-2xl font-bold ${
                currentMetrics && currentMetrics.dailyPnL >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {currentMetrics ? `$${currentMetrics.dailyPnL.toLocaleString()}` : '--'}
              </p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-400">Today's Trades</p>
              <p className="text-2xl font-bold text-white">
                {currentMetrics?.totalTrades || '--'}
              </p>
            </div>
            <BarChart3 className="w-8 h-8 text-blue-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-400">Win Rate</p>
              <p className="text-2xl font-bold text-white">
                {currentMetrics ? `${currentMetrics.winRate.toFixed(1)}%` : '--%'}
              </p>
            </div>
            <Activity className="w-8 h-8 text-purple-400" />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-400">Signal Quality</p>
              <p className="text-2xl font-bold text-yellow-400">
                {currentMetrics ? `${currentMetrics.signalQuality.toFixed(1)}%` : '--%'}
              </p>
            </div>
            <Brain className="w-8 h-8 text-yellow-400" />
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Status */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
            <Globe className="w-5 h-5 mr-2" />
            System Status
          </h2>
          <div className="space-y-3">
            {systemStatus.map((service, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(service.status)}
                  <div>
                    <div className="font-medium text-white">{service.service}</div>
                    <div className="text-sm text-gray-400">Uptime: {service.uptime}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-xs px-2 py-1 rounded border ${getStatusColor(service.status)}`}>
                    {service.status.toUpperCase()}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{service.lastCheck}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* FKS Components */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
            <Brain className="w-5 h-5 mr-2" />
            FKS Components
          </h2>
          <div className="space-y-3">
            {fksComponents.map((component, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg">
                <div className="flex items-center space-x-3">
                  {component.connected ? (
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-red-500" />
                  )}
                  <div>
                    <div className="font-medium text-white">{component.name}</div>
                    <div className="text-sm text-gray-400">{component.version}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-xs px-2 py-1 rounded border ${
                    component.connected 
                      ? 'bg-green-500/20 text-green-400 border-green-500/30'
                      : 'bg-red-500/20 text-red-400 border-red-500/30'
                  }`}>
                    {component.connected ? 'CONNECTED' : 'OFFLINE'}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{component.lastUpdate}</div>
                  {component.healthScore && (
                    <div className="text-xs text-blue-400 mt-1">
                      Health: {component.healthScore}%
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Trading Overview */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <LineChart className="w-5 h-5 mr-2" />
          Trading Overview ({environment})
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-400">
              {currentMetrics?.activePositions || 0}
            </div>
            <div className="text-sm text-gray-400">Active Positions</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-400">
              {currentMetrics?.marketRegime || 'UNKNOWN'}
            </div>
            <div className="text-sm text-gray-400">Market Regime</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-400">
              {currentMetrics ? `${currentMetrics.signalQuality.toFixed(1)}%` : '--%'}
            </div>
            <div className="text-sm text-gray-400">Signal Quality</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-400">
              {tradingConfig.accounts.length}
            </div>
            <div className="text-sm text-gray-400">Connected Accounts</div>
          </div>
        </div>
        
        {/* Environment-specific info */}
        <div className="mt-4 p-4 rounded-lg bg-gray-900/50 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">
                {isSimulation ? 'Simulation Settings' : 'Live Trading Settings'}
              </h3>
              <div className="space-y-1 text-xs text-gray-500">
                <div>Max Daily Loss: ${tradingConfig.riskLimits.maxDailyLoss.toLocaleString()}</div>
                <div>Max Position Size: ${tradingConfig.riskLimits.maxPositionSize.toLocaleString()}</div>
                <div>Max Open Positions: {tradingConfig.riskLimits.maxOpenPositions}</div>
              </div>
            </div>
            <div className="text-right">
              <div className={`inline-flex items-center px-3 py-1 rounded-full text-xs ${
                isSimulation 
                  ? 'bg-blue-500/20 text-blue-400' 
                  : 'bg-red-500/20 text-red-400'
              }`}>
                {isSimulation ? 'SAFE MODE' : 'LIVE MONEY'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center">
          <Zap className="w-5 h-5 mr-2" />
          Quick Actions
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <button 
            onClick={() => {/* Navigation handled by main app */}}
            className="p-4 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors"
          >
            <TrendingUp className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm">Trading Interface</span>
          </button>
          <button 
            onClick={() => {/* Navigation handled by main app */}}
            className="p-4 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
          >
            <LineChart className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm">Live Charts</span>
          </button>
          <button 
            onClick={() => {/* Navigation handled by main app */}}
            className="p-4 bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors"
          >
            <BarChart3 className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm">Portfolio</span>
          </button>
          <button 
            onClick={() => {/* Navigation handled by main app */}}
            className="p-4 bg-orange-600 hover:bg-orange-700 rounded-lg text-white transition-colors"
          >
            <Activity className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm">Analytics</span>
          </button>
          <button 
            onClick={() => {/* Navigation handled by main app */}}
            className="p-4 bg-indigo-600 hover:bg-indigo-700 rounded-lg text-white transition-colors"
          >
            <Users className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm">Accounts</span>
          </button>
          <button 
            onClick={() => {/* Navigation handled by main app */}}
            className="p-4 bg-gray-600 hover:bg-gray-700 rounded-lg text-white transition-colors"
          >
            <Database className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm">System Logs</span>
          </button>
        </div>
        
        {/* Strategy Status */}
        <div className="mt-6 p-4 rounded-lg bg-gray-900/50 border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Active Strategies</h3>
          {tradingConfig.activeStrategies.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {tradingConfig.activeStrategies.map((strategy, index) => (
                <span 
                  key={index}
                  className="px-3 py-1 bg-green-500/20 text-green-400 text-xs rounded-full border border-green-500/30"
                >
                  {strategy}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-500">No strategies currently active</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
