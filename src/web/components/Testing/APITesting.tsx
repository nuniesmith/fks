import {
  Send,
  Server,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Code,
  Copy,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import React, { useState } from 'react';

import { useApi } from '../../context/ApiContext';

interface ServiceEndpoint {
  service: string;
  name: string;
  url: string;
  methods: string[];
  description: string;
  status?: 'online' | 'offline' | 'unknown';
}

interface TestResult {
  id: string;
  timestamp: string;
  service: string;
  endpoint: string;
  method: string;
  status: number;
  success: boolean;
  duration: number;
  request: any;
  response: any;
}

const APITesting: React.FC = () => {
  const { apiService } = useApi();
  const [selectedService, setSelectedService] = useState<string>('api');
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>('/health');
  const [selectedMethod, setSelectedMethod] = useState<string>('GET');
  const [requestBody, setRequestBody] = useState<string>('{}');
  const [requestHeaders, setRequestHeaders] = useState<string>('{}');
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  const services: ServiceEndpoint[] = [
    {
      service: 'api',
      name: 'Main API',
      url: 'https://api.fkstrading.xyz',
      methods: ['GET', 'POST', 'PUT', 'DELETE'],
      description: 'Core API service',
      status: 'online'
    },
    {
      service: 'data',
      name: 'Data Service',
      url: 'https://data.fkstrading.xyz',
      methods: ['GET', 'POST'],
      description: 'Market data service',
      status: 'online'
    },
    {
      service: 'worker',
      name: 'Worker Service',
      url: 'https://worker.fkstrading.xyz',
      methods: ['GET', 'POST'],
      description: 'Background job service',
      status: 'offline'
    },
    {
      service: 'node-network',
      name: 'Node Network',
      url: 'https://nodes.fkstrading.xyz',
      methods: ['GET', 'POST'],
      description: 'Distributed node network',
      status: 'unknown'
    }
  ];

  const commonEndpoints = [
    '/health',
    '/api/v1/status',
    '/api/v1/market/data',
    '/api/v1/signals',
    '/api/v1/portfolio',
    '/api/v1/orders',
    '/api/v1/config',
    '/metrics',
  ];

  const executeTest = async () => {
    setIsLoading(true);
    const startTime = Date.now();
    
    try {
      const service = services.find(s => s.service === selectedService);
      if (!service) return;

      const headers = JSON.parse(requestHeaders);
      const body = selectedMethod !== 'GET' ? JSON.parse(requestBody) : undefined;

      const response = await fetch(`${service.url}${selectedEndpoint}`, {
        method: selectedMethod,
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: body ? JSON.stringify(body) : undefined
      });

      const duration = Date.now() - startTime;
      const responseData = await response.json().catch(() => response.text());

      const result: TestResult = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        service: service.name,
        endpoint: selectedEndpoint,
        method: selectedMethod,
        status: response.status,
        success: response.ok,
        duration,
        request: {
          url: `${service.url}${selectedEndpoint}`,
          method: selectedMethod,
          headers,
          body
        },
        response: responseData
      };

      setTestResults([result, ...testResults.slice(0, 9)]);
    } catch (error) {
      const duration = Date.now() - startTime;
      const result: TestResult = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        service: services.find(s => s.service === selectedService)?.name || selectedService,
        endpoint: selectedEndpoint,
        method: selectedMethod,
        status: 0,
        success: false,
        duration,
        request: {
          url: `${services.find(s => s.service === selectedService)?.url}${selectedEndpoint}`,
          method: selectedMethod,
          headers: JSON.parse(requestHeaders),
          body: selectedMethod !== 'GET' ? JSON.parse(requestBody) : undefined
        },
        response: { error: error instanceof Error ? error.message : 'Network error' }
      };
      
      setTestResults([result, ...testResults.slice(0, 9)]);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-green-400';
    if (status >= 300 && status < 400) return 'text-yellow-400';
    if (status >= 400 && status < 500) return 'text-orange-400';
    if (status >= 500) return 'text-red-400';
    return 'text-gray-400';
  };

  const getServiceStatusIcon = (status?: string) => {
    switch (status) {
      case 'online':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'offline':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <AlertCircle className="w-4 h-4 text-yellow-400" />;
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="space-y-6">
      {/* Service Selection */}
      <div className="bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <Server className="w-5 h-5 mr-2 text-blue-400" />
          Service Selection
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {services.map(service => (
            <button
              key={service.service}
              onClick={() => setSelectedService(service.service)}
              className={`p-4 rounded-lg border transition-all ${
                selectedService === service.service
                  ? 'bg-blue-500/20 border-blue-500'
                  : 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-white">{service.name}</span>
                {getServiceStatusIcon(service.status)}
              </div>
              <p className="text-xs text-gray-400 text-left">{service.description}</p>
              <p className="text-xs text-gray-500 mt-1">{service.url}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Request Builder */}
      <div className="bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <Code className="w-5 h-5 mr-2 text-purple-400" />
          Request Builder
        </h3>
        
        <div className="space-y-4">
          {/* Method and Endpoint */}
          <div className="flex space-x-4">
            <select
              value={selectedMethod}
              onChange={(e) => setSelectedMethod(e.target.value)}
              className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
            </select>
            
            <input
              type="text"
              value={selectedEndpoint}
              onChange={(e) => setSelectedEndpoint(e.target.value)}
              placeholder="/api/v1/endpoint"
              className="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
              list="endpoints"
            />
            <datalist id="endpoints">
              {commonEndpoints.map(endpoint => (
                <option key={endpoint} value={endpoint} />
              ))}
            </datalist>
            
            <button
              onClick={executeTest}
              disabled={isLoading}
              className={`px-6 py-2 rounded-lg font-medium flex items-center space-x-2 transition-colors ${
                isLoading
                  ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              }`}
            >
              <Send className="w-4 h-4" />
              <span>{isLoading ? 'Testing...' : 'Send'}</span>
            </button>
          </div>

          {/* Headers */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Headers (JSON)
            </label>
            <textarea
              value={requestHeaders}
              onChange={(e) => setRequestHeaders(e.target.value)}
              rows={3}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:border-blue-500 focus:outline-none"
              placeholder='{"Authorization": "Bearer token"}'
            />
          </div>

          {/* Request Body */}
          {selectedMethod !== 'GET' && (
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Request Body (JSON)
              </label>
              <textarea
                value={requestBody}
                onChange={(e) => setRequestBody(e.target.value)}
                rows={5}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm focus:border-blue-500 focus:outline-none"
                placeholder='{"key": "value"}'
              />
            </div>
          )}
        </div>
      </div>

      {/* Test Results */}
      <div className="bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <Clock className="w-5 h-5 mr-2 text-orange-400" />
          Test Results
        </h3>
        
        {testResults.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No test results yet. Send a request to see results.</p>
        ) : (
          <div className="space-y-3">
            {testResults.map(result => (
              <div key={result.id} className="bg-gray-800/50 rounded-lg border border-gray-700">
                <div
                  className="p-4 cursor-pointer"
                  onClick={() => setExpandedResult(expandedResult === result.id ? null : result.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      {result.success ? (
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-400" />
                      )}
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-medium text-white">{result.method}</span>
                          <span className="text-gray-400">{result.endpoint}</span>
                          <span className={`font-mono ${getStatusColor(result.status)}`}>
                            {result.status || 'Error'}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-500 mt-1">
                          <span>{result.service}</span>
                          <span>{result.duration}ms</span>
                          <span>{new Date(result.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </div>
                    </div>
                    {expandedResult === result.id ? (
                      <ChevronUp className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                </div>
                
                {expandedResult === result.id && (
                  <div className="border-t border-gray-700 p-4 space-y-4">
                    {/* Request Details */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium text-gray-400">Request</h4>
                        <button
                          onClick={() => copyToClipboard(JSON.stringify(result.request, null, 2))}
                          className="text-xs text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                        >
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </button>
                      </div>
                      <pre className="bg-gray-900 rounded p-3 text-xs text-gray-300 overflow-x-auto">
                        {JSON.stringify(result.request, null, 2)}
                      </pre>
                    </div>
                    
                    {/* Response Details */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium text-gray-400">Response</h4>
                        <button
                          onClick={() => copyToClipboard(JSON.stringify(result.response, null, 2))}
                          className="text-xs text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                        >
                          <Copy className="w-3 h-3" />
                          <span>Copy</span>
                        </button>
                      </div>
                      <pre className="bg-gray-900 rounded p-3 text-xs text-gray-300 overflow-x-auto max-h-64 overflow-y-auto">
                        {JSON.stringify(result.response, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default APITesting;
