import {
  Database,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  Search,
  Settings,
  BarChart3,
  TrendingUp,
  Calendar,
  Globe
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { useRealtime } from '@shared/hooks/useRealtime';
import { config } from '../../services/config';
import { realtimeClient } from '@shared/services/realtime/WebSocketService';
import LiveChannelViewer from '../Realtime/LiveChannelViewer';
import RealtimeTickerChart from '@/features/lazy/RealtimeTickerChartLazy';
import RecentTicksTable from '../Realtime/RecentTicksTable';

import ActiveAssetsManager from './ActiveAssetsManager';
import ApiIntegrationsManager from './ApiIntegrationsManager';
import DailyDataFetcher from './DailyDataFetcher';
import DataExplorer from './DataExplorer';
import DatasetSplitManager from './DatasetSplitManager';


interface DataSource {
  id: string;
  name: string;
  type: 'market_data' | 'news' | 'sentiment' | 'economic' | 'custom';
  status: 'active' | 'inactive' | 'error' | 'pending';
  lastUpdate: string;
  recordCount: number;
  dataSize: string;
  apiEndpoint?: string;
  refreshInterval: number; // minutes
}

interface DataValidationResult {
  source: string;
  totalRecords: number;
  validRecords: number;
  errorRecords: number;
  duplicates: number;
  missingFields: number;
  lastValidation: string;
  issues: string[];
}

const FKSData: React.FC = () => {
  const { status: wsStatus } = useRealtime();
  const defaultChannels = config.defaultRealtimeChannels || ['heartbeat'];
  const firstTickChannel = defaultChannels.find(c => c.toLowerCase().startsWith('ticks:')) || 'ticks:AAPL';
  let wsHost = '';
  try {
    const u = new URL(realtimeClient.getUrl());
    wsHost = u.host + u.pathname;
  } catch { wsHost = realtimeClient.getUrl(); }
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [validationResults, setValidationResults] = useState<DataValidationResult[]>([]);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [showAddSource, setShowAddSource] = useState(false);

  // Load from backend when available; avoid hardcoded demo values
  useEffect(() => {
    fetch('/data/sources').then(async r => {
      if (!r.ok) return setDataSources([])
      const j = await r.json()
      setDataSources(j.sources || [])
    }).catch(() => setDataSources([]))

    fetch('/data/validation/results').then(async r => {
      if (!r.ok) return setValidationResults([])
      const j = await r.json()
      setValidationResults(j.items || [])
    }).catch(() => setValidationResults([]))
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-400" />;
      default:
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'market_data':
        return <BarChart3 className="w-4 h-4 text-blue-400" />;
      case 'news':
        return <Globe className="w-4 h-4 text-purple-400" />;
      case 'sentiment':
        return <TrendingUp className="w-4 h-4 text-orange-400" />;
      case 'economic':
        return <Calendar className="w-4 h-4 text-green-400" />;
      default:
        return <Database className="w-4 h-4 text-gray-400" />;
    }
  };

  const filteredSources = dataSources.filter(source => {
    const matchesSearch = source.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterType === 'all' || source.type === filterType;
    return matchesSearch && matchesFilter;
  });

  const handleRefreshSource = async (sourceId: string) => {
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      setDataSources(prev => 
        prev.map(source => 
          source.id === sourceId 
            ? { ...source, lastUpdate: new Date().toISOString().slice(0, 19).replace('T', ' ') }
            : source
        )
      );
      setIsLoading(false);
    }, 2000);
  };

  const handleValidateData = async (sourceId: string) => {
    setIsLoading(true);
    // Simulate validation
    setTimeout(() => {
      console.log(`Validating data for source ${sourceId}`);
      setIsLoading(false);
    }, 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center space-x-3">
            <Database className="w-8 h-8 text-blue-400" />
            <span>FKS Data Service</span>
          </h1>
          <p className="text-gray-400 mt-2">
            Manage data sources, ETL pipelines, and data validation for trading algorithms
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs px-2 py-1 rounded-full border" title="WebSocket status"
            style={{
              borderColor: wsStatus === 'open' ? 'rgba(74,222,128,0.6)' : wsStatus === 'connecting' ? 'rgba(250,204,21,0.6)' : 'rgba(248,113,113,0.6)'
            }}
          >
            Realtime: {wsStatus}
          </span>
          <span className="hidden sm:inline text-[10px] px-2 py-1 rounded border border-gray-700 text-gray-300 font-mono" title="WebSocket URL">
            {wsHost}
          </span>
          <button
          onClick={() => setShowAddSource(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          Add Data Source
          </button>
        </div>
      </div>

  {/* Quick Daily fetch (Data service) */}
  <DailyDataFetcher />

  {/* Active Assets Manager */}
  <ActiveAssetsManager />

  {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Total Sources</p>
              <p className="text-2xl font-bold text-white">{dataSources.length}</p>
            </div>
            <Database className="w-8 h-8 text-blue-400" />
          </div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Active Sources</p>
              <p className="text-2xl font-bold text-green-400">
                {dataSources.filter(s => s.status === 'active').length}
              </p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Total Records</p>
              <p className="text-2xl font-bold text-white">
                {dataSources.length ? ((dataSources.reduce((sum, s) => sum + (s.recordCount || 0), 0) / 1000000).toFixed(1) + 'M') : '—'}
              </p>
            </div>
            <BarChart3 className="w-8 h-8 text-purple-400" />
          </div>
        </div>
        
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Data Size</p>
              <p className="text-2xl font-bold text-white">{dataSources.length ? dataSources.reduce((sum, s) => sum + parseFloat(String(s.dataSize||'0').replace(/[^0-9.]/g,'')), 0).toFixed(1) + ' GB' : '—'}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-orange-400" />
          </div>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search data sources..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
          />
        </div>
        
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Types</option>
          <option value="market_data">Market Data</option>
          <option value="news">News</option>
          <option value="sentiment">Sentiment</option>
          <option value="economic">Economic</option>
          <option value="custom">Custom</option>
        </select>
      </div>

  {/* API Integrations and Dataset Split */}
  <ApiIntegrationsManager />
  <DatasetSplitManager />

  {/* Data Sources Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-700">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Source
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Records
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Last Update
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredSources.map((source) => (
                <tr key={source.id} className="hover:bg-gray-700/50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-3">
                      {getTypeIcon(source.type)}
                      <div>
                        <div className="text-sm font-medium text-white">{source.name}</div>
                        <div className="text-sm text-gray-400 capitalize">{source.type.replace('_', ' ')}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(source.status)}
                      <span className={`text-sm capitalize ${
                        source.status === 'active' ? 'text-green-400' :
                        source.status === 'error' ? 'text-red-400' :
                        source.status === 'pending' ? 'text-yellow-400' :
                        'text-gray-400'
                      }`}>
                        {source.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    {source.recordCount.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                    {source.dataSize}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                    {source.lastUpdate}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleRefreshSource(source.id)}
                        disabled={isLoading}
                        className="p-1 hover:bg-gray-600 rounded transition-colors"
                        title="Refresh data"
                      >
                        <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                      </button>
                      <button
                        onClick={() => handleValidateData(source.id)}
                        className="p-1 hover:bg-gray-600 rounded transition-colors"
                        title="Validate data"
                      >
                        <CheckCircle className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setSelectedSource(source.id)}
                        className="p-1 hover:bg-gray-600 rounded transition-colors"
                        title="View details"
                      >
                        <Settings className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Data Validation Results */}
      {validationResults.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">Recent Validation Results</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {validationResults.map((result, index) => (
              <div key={index} className="bg-gray-700/50 rounded-lg p-4">
                <h4 className="font-medium text-white mb-2">{result.source}</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Total Records:</span>
                    <span className="text-white">{result.totalRecords.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Valid:</span>
                    <span className="text-green-400">{result.validRecords.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Errors:</span>
                    <span className="text-red-400">{result.errorRecords.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Quality Score:</span>
                    <span className="text-blue-400">
                      {((result.validRecords / result.totalRecords) * 100).toFixed(1)}%
                    </span>
                  </div>
                  {result.issues.length > 0 && (
                    <div className="mt-3">
                      <span className="text-gray-400 text-xs">Issues:</span>
                      <ul className="mt-1 space-y-1">
                        {result.issues.map((issue, issueIndex) => (
                          <li key={issueIndex} className="text-xs text-yellow-400">
                            • {issue}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live Data Explorer */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Live Market Data</h3>
        <p className="text-sm text-white/70 mb-3">Browse paginated market data from the API and export CSV.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
          {defaultChannels.map((ch) => (
            <LiveChannelViewer key={ch} initialChannel={ch} />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 mb-6">
          <RealtimeTickerChart channel={firstTickChannel} title={`${firstTickChannel.replace(/^.*?:/, '')} Ticks`} />
          <RecentTicksTable channel={firstTickChannel} limit={30} title={`Recent ${firstTickChannel.replace(/^.*?:/, '')} Ticks`} />
        </div>
  <DataExplorer pageSize={50} />
      </div>
    </div>
  );
};

export default FKSData;
