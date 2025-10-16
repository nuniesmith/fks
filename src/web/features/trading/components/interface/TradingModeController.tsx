import { 
  PlayCircle, 
  PauseCircle, 
  Square, 
  Zap, 
  Shield, 
  AlertTriangle, 
  CheckCircle
} from 'lucide-react';
import React, { useState, useEffect } from 'react';
import { useTradingEnv } from '@/context/TradingEnvContext';

interface TradingMode {
  id: 'simulation' | 'live';
  name: string;
  description: string;
  riskLevel: 'low' | 'medium' | 'high';
  enabled: boolean;
}

interface TradingSession {
  id: string;
  mode: 'simulation' | 'live';
  status: 'active' | 'paused' | 'stopped';
  startTime: Date;
  endTime?: Date;
  strategies: string[];
  accounts: string[];
  performance: {
    totalTrades: number;
    winningTrades: number;
    totalPnL: number;
    currentDrawdown: number;
  };
}

interface SafetyCheck {
  id: string;
  name: string;
  status: 'passed' | 'failed' | 'warning';
  description: string;
  required: boolean;
}

interface TradingEnvironment {
  dataFeed: 'real-time' | 'delayed' | 'simulated';
  orderExecution: 'real' | 'simulated';
  accountBalance: 'real' | 'virtual';
  riskManagement: 'strict' | 'relaxed' | 'disabled';
}

const TradingModeController: React.FC = () => {
  const { focus, setFocus, readiness } = useTradingEnv();
  const [currentMode, setCurrentMode] = useState<'simulation' | 'live'>('simulation');
  const [currentSession, setCurrentSession] = useState<TradingSession | null>(null);
  const [safetyChecks, setSafetyChecks] = useState<SafetyCheck[]>([]);
  const [environment, setEnvironment] = useState<TradingEnvironment>({
    dataFeed: 'simulated',
    orderExecution: 'simulated',
    accountBalance: 'virtual',
    riskManagement: 'strict'
  });
  const [showModeSwitch, setShowModeSwitch] = useState(false);

  const tradingModes: TradingMode[] = [
    {
      id: 'simulation',
      name: 'Simulation Mode',
      description: 'Safe environment for strategy testing with virtual money',
      riskLevel: 'low',
      enabled: true
    },
    {
      id: 'live',
      name: 'Live Trading Mode',
      description: 'Real trading with actual money and market execution',
      riskLevel: 'high',
      enabled: false // Requires safety checks
    }
  ];

  useEffect(() => {
    loadSafetyChecks();
    updateEnvironmentSettings();
  }, [currentMode]);

  const loadSafetyChecks = () => {
    const checks: SafetyCheck[] = [
      {
        id: 'risk-limits',
        name: 'Risk Limits Configured',
        status: 'passed',
        description: 'Maximum position size and daily loss limits are set',
        required: true
      },
      {
        id: 'strategy-backtested',
        name: 'Strategies Backtested',
        status: currentMode === 'live' ? 'warning' : 'passed',
        description: 'All active strategies have been backtested on historical data',
        required: true
      },
      {
        id: 'account-verified',
        name: 'Trading Account Verified',
        status: currentMode === 'live' ? 'failed' : 'passed',
        description: 'Trading account credentials and permissions verified',
        required: true
      },
      {
        id: 'emergency-stop',
        name: 'Emergency Stop System',
        status: 'passed',
        description: 'Emergency stop mechanism is functional and tested',
        required: true
      },
      {
        id: 'balance-sufficient',
        name: 'Sufficient Balance',
        status: currentMode === 'live' ? 'warning' : 'passed',
        description: 'Account has sufficient balance for planned trading',
        required: true
      }
    ];
    setSafetyChecks(checks);
  };

  const updateEnvironmentSettings = () => {
    if (currentMode === 'simulation') {
      setEnvironment({
        dataFeed: 'simulated',
        orderExecution: 'simulated',
        accountBalance: 'virtual',
        riskManagement: 'strict'
      });
    } else {
      setEnvironment({
        dataFeed: 'real-time',
        orderExecution: 'real',
        accountBalance: 'real',
        riskManagement: 'strict'
      });
    }
  };

  const canSwitchToLive = () => readiness.ok;

  const startTradingSession = () => {
    const newSession: TradingSession = {
      id: `session-${Date.now()}`,
      mode: currentMode,
      status: 'active',
      startTime: new Date(),
      strategies: ['mean-reversion-suite'],
      accounts: currentMode === 'simulation' ? ['sim-account-1'] : ['futures-1'],
      performance: {
        totalTrades: 0,
        winningTrades: 0,
        totalPnL: 0,
        currentDrawdown: 0
      }
    };
    setCurrentSession(newSession);
  };

  const pauseTradingSession = () => {
    if (currentSession) {
      setCurrentSession({ ...currentSession, status: 'paused' });
    }
  };

  const stopTradingSession = () => {
    if (currentSession) {
      setCurrentSession({ ...currentSession, status: 'stopped', endTime: new Date() });
    }
  };

  const switchMode = (newMode: 'simulation' | 'live') => {
    if (newMode === 'live' && !canSwitchToLive()) {
      alert('Cannot switch to live mode. Please resolve all safety check failures.');
      return;
    }
    if (currentSession && currentSession.status === 'active') {
      stopTradingSession();
    }
    setCurrentMode(newMode);
    setFocus(newMode);
    setShowModeSwitch(false);
  };

  const renderModeSelector = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      {tradingModes.map(mode => (
        <div
          key={mode.id}
          className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
            currentMode === mode.id ? 'border-blue-500 bg-blue-500/10' : 'border-gray-700 bg-gray-800 hover:border-gray-600'
          }`}
          onClick={() => mode.id !== currentMode && setShowModeSwitch(true)}
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold text-white">{mode.name}</h3>
            <div className="flex items-center space-x-2">
              {currentMode === mode.id && <CheckCircle className="w-5 h-5 text-green-400" />}
              <span
                className={`px-2 py-1 rounded text-xs ${
                  mode.riskLevel === 'low'
                    ? 'bg-green-500/20 text-green-400'
                    : mode.riskLevel === 'medium'
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-red-500/20 text-red-400'
                }`}
              >
                {mode.riskLevel} risk
              </span>
            </div>
          </div>
          <p className="text-gray-400 text-sm">{mode.description}</p>
          {mode.id === 'live' && !canSwitchToLive() && (
            <div className="mt-3 flex items-center space-x-2 text-red-400">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-xs">Safety checks required</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );

  const renderEnvironmentSettings = () => (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
      <h3 className="text-lg font-semibold text-white mb-4">Environment Configuration</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="text-sm text-gray-400">Data Feed</label>
          <div
            className={`mt-1 px-3 py-2 rounded ${
              environment.dataFeed === 'real-time'
                ? 'bg-green-500/20 text-green-400'
                : environment.dataFeed === 'delayed'
                ? 'bg-yellow-500/20 text-yellow-400'
                : 'bg-blue-500/20 text-blue-400'
            }`}
          >
            {environment.dataFeed}
          </div>
        </div>
        <div>
          <label className="text-sm text-gray-400">Order Execution</label>
          <div
            className={`mt-1 px-3 py-2 rounded ${
              environment.orderExecution === 'real'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-blue-500/20 text-blue-400'
            }`}
          >
            {environment.orderExecution}
          </div>
        </div>
        <div>
          <label className="text-sm text-gray-400">Account Balance</label>
          <div
            className={`mt-1 px-3 py-2 rounded ${
              environment.accountBalance === 'real'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-green-500/20 text-green-400'
            }`}
          >
            {environment.accountBalance}
          </div>
        </div>
        <div>
          <label className="text-sm text-gray-400">Risk Management</label>
          <div className="mt-1 px-3 py-2 rounded bg-green-500/20 text-green-400">
            {environment.riskManagement}
          </div>
        </div>
      </div>
    </div>
  );

  const renderSafetyChecks = () => (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
      <h3 className="text-lg font-semibold text-white mb-4">Safety Checks</h3>
      <div className="space-y-3">
        {safetyChecks.map(check => (
          <div
            key={check.id}
            className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
          >
            <div className="flex items-center space-x-3">
              {check.status === 'passed' ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : check.status === 'warning' ? (
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-red-400" />
              )}
              <div>
                <p className="text-white font-medium">{check.name}</p>
                <p className="text-sm text-gray-400">{check.description}</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {check.required && (
                <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs">
                  Required
                </span>
              )}
              <span
                className={`px-2 py-1 rounded text-xs ${
                  check.status === 'passed'
                    ? 'bg-green-500/20 text-green-400'
                    : check.status === 'warning'
                    ? 'bg-yellow-500/20 text-yellow-400'
                    : 'bg-red-500/20 text-red-400'
                }`}
              >
                {check.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderCurrentSession = () => {
    if (!currentSession) return null;
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Current Trading Session</h3>
          <span
            className={`px-3 py-1 rounded-full text-sm ${
              currentSession.status === 'active'
                ? 'bg-green-500/20 text-green-400'
                : currentSession.status === 'paused'
                ? 'bg-yellow-500/20 text-yellow-400'
                : 'bg-gray-500/20 text-gray-400'
            }`}
          >
            {currentSession.status}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div className="text-center">
            <div className="text-xl font-bold text-white">
              {currentSession.performance.totalTrades}
            </div>
            <div className="text-xs text-gray-500">Total Trades</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-green-400">
              {currentSession.performance.totalTrades > 0
                ? (
                    (currentSession.performance.winningTrades /
                      currentSession.performance.totalTrades) * 100
                  ).toFixed(1)
                : 0}%
            </div>
            <div className="text-xs text-gray-500">Win Rate</div>
          </div>
          <div className="text-center">
            <div
              className={`text-xl font-bold ${
                currentSession.performance.totalPnL >= 0
                  ? 'text-green-400'
                  : 'text-red-400'
              }`}
            >
              ${currentSession.performance.totalPnL.toFixed(2)}
            </div>
            <div className="text-xs text-gray-500">P&L</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-red-400">
              {(currentSession.performance.currentDrawdown * 100).toFixed(1)}%
            </div>
            <div className="text-xs text-gray-500">Drawdown</div>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Started: {currentSession.startTime.toLocaleString()} • Mode: {currentSession.mode} • Strategies: {currentSession.strategies.length}
          </div>
          <div className="flex items-center space-x-2">
            {currentSession.status === 'active' ? (
              <button
                onClick={pauseTradingSession}
                className="flex items-center space-x-1 px-3 py-1 bg-yellow-600 hover:bg-yellow-700 rounded text-sm text-white transition-colors"
              >
                <PauseCircle className="w-4 h-4" />
                <span>Pause</span>
              </button>
            ) : (
              <button
                onClick={startTradingSession}
                className="flex items-center space-x-1 px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm text-white transition-colors"
              >
                <PlayCircle className="w-4 h-4" />
                <span>Resume</span>
              </button>
            )}
            <button
              onClick={stopTradingSession}
              className="flex items-center space-x-1 px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm text-white transition-colors"
            >
              <Square className="w-4 h-4" />
              <span>Stop</span>
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Trading Mode Controller</h1>
          <p className="text-gray-400 mt-1">
            Manage simulation and live trading environments with safety controls
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg ${
              currentMode === 'simulation' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
            }`}
          >
            {currentMode === 'simulation' ? <Shield className="w-5 h-5" /> : <Zap className="w-5 h-5" />}
            <span className="font-medium capitalize">{currentMode} Mode</span>
          </div>
          {!currentSession && (
            <button
              onClick={startTradingSession}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition-colors"
            >
              <PlayCircle className="w-5 h-5" />
              <span>Start Session</span>
            </button>
          )}
        </div>
      </div>
      {renderModeSelector()}
      {renderEnvironmentSettings()}
      {renderSafetyChecks()}
      {renderCurrentSession()}
      {showModeSwitch && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 max-w-md">
            <h3 className="text-lg font-semibold text-white mb-4">Confirm Mode Switch</h3>
            <p className="text-gray-400 mb-6">
              Are you sure you want to switch to {currentMode === 'simulation' ? 'Live' : 'Simulation'} mode?
              {currentMode === 'simulation' && ' This will use real money and execute actual trades.'}
            </p>
            <div className="flex space-x-3">
              <button
                onClick={() => setShowModeSwitch(false)}
                className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => switchMode(currentMode === 'simulation' ? 'live' : 'simulation')}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 rounded text-white transition-colors"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingModeController;
