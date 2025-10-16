import {
  Activity,
  AlertCircle,
  CheckCircle,
  Download,
  FileText,
  Package,
  Play,
  RefreshCw,
  Settings,
  Terminal
} from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';

interface NinjaTraderStatus {
  isConnected: boolean;
  version?: string;
  lastUpdate?: string;
  dataFeed?: string;
}

interface BuildApiStatus {
  isAvailable: boolean;
  lastBuild?: string;
  packageVersion?: string;
}

interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'error' | 'success' | 'warning';
}

const NinjaTraderIntegration: React.FC = () => {
  const [ntStatus, setNtStatus] = useState<NinjaTraderStatus>({
    isConnected: false
  });
  const [buildApiStatus, setBuildApiStatus] = useState<BuildApiStatus>({
    isAvailable: false
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isBuilding, setIsBuilding] = useState(false);
  const [isPackaging, setIsPackaging] = useState(false);

  // API endpoints
  const BUILD_API_BASE = import.meta.env.VITE_BUILD_API_URL || 'http://localhost:4000';
  const PYTHON_API_BASE = import.meta.env.VITE_PYTHON_API_URL || 'http://localhost:8002';

  const addLog = useCallback((message: string, type: LogEntry['type'] = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev.slice(-19), { timestamp, message, type }]);
  }, []);

  const checkBuildApiStatus = useCallback(async () => {
    try {
      const response = await fetch(`${BUILD_API_BASE}/api/health`);
      if (response.ok) {
        setBuildApiStatus(prev => ({ ...prev, isAvailable: true }));
        addLog('Build API connected', 'success');
      } else {
        setBuildApiStatus(prev => ({ ...prev, isAvailable: false }));
        addLog('Build API not responding', 'warning');
      }
    } catch (error) {
      setBuildApiStatus(prev => ({ ...prev, isAvailable: false }));
      addLog('Build API connection failed', 'error');
    }
  }, [BUILD_API_BASE, addLog]);

  const checkNinjaTraderStatus = useCallback(async () => {
    try {
      // Check Python backend for NinjaTrader connection status
      const response = await fetch(`${PYTHON_API_BASE}/api/health`);
      if (response.ok) {
        const data = await response.json();
        setNtStatus({
          isConnected: true,
          version: data.ninjatrader_version || 'Unknown',
          lastUpdate: new Date().toLocaleString(),
          dataFeed: data.data_feed || 'Unknown'
        });
        addLog('NinjaTrader connection verified', 'success');
      } else {
        setNtStatus(prev => ({ ...prev, isConnected: false }));
        addLog('NinjaTrader not connected', 'warning');
      }
    } catch (error) {
      setNtStatus(prev => ({ ...prev, isConnected: false }));
      addLog('Failed to check NinjaTrader status', 'error');
    }
  }, [PYTHON_API_BASE, addLog]);

  useEffect(() => {
    checkBuildApiStatus();
    checkNinjaTraderStatus();
    
    const interval = setInterval(() => {
      checkBuildApiStatus();
      checkNinjaTraderStatus();
    }, 30000);

    return () => clearInterval(interval);
  }, [checkBuildApiStatus, checkNinjaTraderStatus]);

  const handleBuild = async () => {
    setIsBuilding(true);
    addLog('Starting build process...', 'info');
    
    try {
      const response = await fetch(`${BUILD_API_BASE}/api/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const result = await response.json();
      
      if (result.success) {
        addLog('Build completed successfully', 'success');
        setBuildApiStatus(prev => ({ 
          ...prev, 
          lastBuild: new Date().toLocaleString() 
        }));
      } else {
        addLog(`Build failed: ${result.error || 'Unknown error'}`, 'error');
      }
    } catch (error) {
      addLog('Build request failed', 'error');
    } finally {
      setIsBuilding(false);
    }
  };

  const handlePackage = async () => {
    setIsPackaging(true);
    addLog('Starting package creation...', 'info');
    
    try {
      const response = await fetch(`${BUILD_API_BASE}/api/package`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const result = await response.json();
      
      if (result.success) {
        addLog('Package created successfully', 'success');
        setBuildApiStatus(prev => ({ 
          ...prev, 
          packageVersion: '1.0.0' 
        }));
      } else {
        addLog(`Package failed: ${result.error || 'Unknown error'}`, 'error');
      }
    } catch (error) {
      addLog('Package request failed', 'error');
    } finally {
      setIsPackaging(false);
    }
  };

  const handleDownload = async () => {
    try {
      addLog('Starting download...', 'info');
      const response = await fetch(`${BUILD_API_BASE}/api/download/fks_addon.zip`);
      
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'fks_trading-system.zip';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        addLog('Download completed', 'success');
      } else {
        addLog('Download failed', 'error');
      }
    } catch (error) {
      addLog('Download error', 'error');
    }
  };

  return (
    <div className="space-y-6">
      {/* Status Overview */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* NinjaTrader Status */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Terminal className="w-5 h-5 mr-2" />
              NinjaTrader Status
            </h3>
            <div className={`w-3 h-3 rounded-full ${ntStatus.isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          </div>
          
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">Connection:</span>
              <span className={ntStatus.isConnected ? 'text-green-600' : 'text-red-600'}>
                {ntStatus.isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            {ntStatus.version && (
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Version:</span>
                <span className="text-gray-900 dark:text-white">{ntStatus.version}</span>
              </div>
            )}
            {ntStatus.dataFeed && (
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Data Feed:</span>
                <span className="text-gray-900 dark:text-white">{ntStatus.dataFeed}</span>
              </div>
            )}
            {ntStatus.lastUpdate && (
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Last Update:</span>
                <span className="text-gray-900 dark:text-white">{ntStatus.lastUpdate}</span>
              </div>
            )}
          </div>
        </div>

        {/* Build API Status */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
              <Package className="w-5 h-5 mr-2" />
              Build API Status
            </h3>
            <div className={`w-3 h-3 rounded-full ${buildApiStatus.isAvailable ? 'bg-green-500' : 'bg-red-500'}`} />
          </div>
          
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600 dark:text-gray-400">API Status:</span>
              <span className={buildApiStatus.isAvailable ? 'text-green-600' : 'text-red-600'}>
                {buildApiStatus.isAvailable ? 'Available' : 'Unavailable'}
              </span>
            </div>
            {buildApiStatus.lastBuild && (
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Last Build:</span>
                <span className="text-gray-900 dark:text-white">{buildApiStatus.lastBuild}</span>
              </div>
            )}
            {buildApiStatus.packageVersion && (
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Package Version:</span>
                <span className="text-gray-900 dark:text-white">{buildApiStatus.packageVersion}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
          <Settings className="w-5 h-5 mr-2" />
          Build & Deploy Actions
        </h3>
        
        <div className="grid md:grid-cols-3 gap-4">
          <button
            onClick={handleBuild}
            disabled={isBuilding || !buildApiStatus.isAvailable}
            className="flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isBuilding ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            {isBuilding ? 'Building...' : 'Build'}
          </button>

          <button
            onClick={handlePackage}
            disabled={isPackaging || !buildApiStatus.isAvailable}
            className="flex items-center justify-center px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isPackaging ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Package className="w-4 h-4 mr-2" />
            )}
            {isPackaging ? 'Packaging...' : 'Package'}
          </button>

          <button
            onClick={handleDownload}
            disabled={!buildApiStatus.isAvailable}
            className="flex items-center justify-center px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="w-4 h-4 mr-2" />
            Download
          </button>
        </div>
      </div>

      {/* Activity Log */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
            <Activity className="w-5 h-5 mr-2" />
            Activity Log
          </h3>
          <button
            onClick={() => setLogs([])}
            className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Clear
          </button>
        </div>
        
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 h-48 overflow-y-auto">
          {logs.length === 0 ? (
            <p className="text-gray-500 text-center">No activity yet</p>
          ) : (
            <div className="space-y-1">
              {logs.map((log, index) => (
                <div key={index} className="flex items-start space-x-2 text-sm">
                  <span className="text-gray-500 font-mono">{log.timestamp}</span>
                  <div className="flex items-center space-x-1">
                    {log.type === 'success' && <CheckCircle className="w-4 h-4 text-green-500" />}
                    {log.type === 'error' && <AlertCircle className="w-4 h-4 text-red-500" />}
                    {log.type === 'warning' && <AlertCircle className="w-4 h-4 text-yellow-500" />}
                    {log.type === 'info' && <FileText className="w-4 h-4 text-blue-500" />}
                    <span className={`
                      ${log.type === 'success' ? 'text-green-600' : ''}
                      ${log.type === 'error' ? 'text-red-600' : ''}
                      ${log.type === 'warning' ? 'text-yellow-600' : ''}
                      ${log.type === 'info' ? 'text-gray-900 dark:text-white' : ''}
                    `}>
                      {log.message}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NinjaTraderIntegration;
