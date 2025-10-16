import { 
  Server, 
  Database, 
  Cpu, 
  Activity, 
  Zap, 
  Globe, 
  Search,
  ChevronDown,
  ChevronUp,
  Monitor,
  Code,
  BarChart3,
  TrendingUp,
  Users,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';
import React, { useState, useEffect, useRef } from 'react';
import PageContainer from '@layout/PageContainer';
import AsyncMermaid from '../AsyncMermaid';
import SystemDiagrams from '../SystemDiagrams';

import { config } from '../../config/environment';
import { useUser } from '../../context/UserContext';
import { useServiceMonitoring } from '../../hooks/useServiceMonitoring';

import ContractAggregateDashboard from './ContractAggregateDashboard';

interface ArchitectureService {
  id: string;
  name: string;
  status: 'healthy' | 'warning' | 'error' | 'offline';
  port?: number;
  description: string;
  technologies: string[];
  patterns?: string[];
  endpoints?: string[];
  metrics?: {
    [key: string]: number | string;
  };
  connections: string[];
  category: 'api' | 'data' | 'compute' | 'frontend' | 'ml' | 'infrastructure';
}

interface ArchitectureLayer {
  id: string;
  title: string;
  badge: string;
  description: string;
  services: ArchitectureService[];
  infrastructureItems?: Array<{ icon: string; name: string; description: string }>;
}

const ArchitectureDashboard: React.FC = () => {
  const { user, isDeveloper } = useUser();
  const { services: liveServices, systemHealth, isLoading: servicesLoading, refreshServices } = useServiceMonitoring();
  const [searchTerm, setSearchTerm] = useState('');
  const [collapsedLayers, setCollapsedLayers] = useState<Set<string>>(new Set());
  const [selectedService, setSelectedService] = useState<ArchitectureService | null>(null);
  const [realTimeMetrics, setRealTimeMetrics] = useState<{ [key: string]: any }>({});
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Merge live service data with architecture data
  const updateServiceWithLiveData = (service: ArchitectureService) => {
    const liveService = liveServices.find(ls => ls.id === service.id);
    if (liveService) {
      return {
        ...service,
        status: liveService.status,
        metrics: {
          ...service.metrics,
          ...liveService.metrics,
          'Response Time': liveService.responseTime ? `${liveService.responseTime}ms` : service.metrics?.['Response Time'],
          'Last Check': liveService.lastCheck.toLocaleTimeString(),
          'Uptime': liveService.uptime ? `${(liveService.uptime * 100).toFixed(2)}%` : service.metrics?.['Uptime']
        }
      };
    }
    return service;
  };
  // Real architecture data based on your FKS system (synced with docker-compose.yml)
  const architectureLayers: ArchitectureLayer[] = [
    {
      id: 'frontend',
      title: 'Frontend Layer',
      badge: 'User Interface',
      description: 'React-based trading interface with real-time updates and responsive design',
      services: [
        {
          id: 'web',
          name: 'Web UI (React)',
          status: 'healthy',
          port: 3000,
          description: 'Frontend UI built with React, TypeScript, and Tailwind; served via Node dev or through Nginx',
          technologies: ['React', 'TypeScript', 'Tailwind CSS', 'Vite'],
          endpoints: ['/', '/trading', '/services/data', '/services/engine', '/services/transformer'],
          connections: ['nginx', 'api'],
          category: 'frontend',
          metrics: {
            'Active Users': 12,
            'Page Load Time': '1.2s',
            'Components': 25,
            'Bundle Size': '2.1MB'
          }
        },
        {
          id: 'architecture-viz',
          name: 'Architecture Visualization',
          status: 'healthy',
          description: 'Dynamic architecture diagram with real-time service status',
          technologies: ['React', 'D3.js', 'SVG', 'WebSocket'],
          connections: [''],
          category: 'frontend',
          metrics: {
            'Services Monitored': 8,
            'Update Frequency': '5s',
            'Uptime': '99.9%'
          }
        }
      ]
    },
    {
      id: 'api',
      title: 'API Layer',
      badge: 'Service Gateway',
      description: 'Python API gateway (REST) handling orchestration, authentication, and routing',
      services: [
        {
          id: 'api',
          name: 'Core API Service',
          status: 'healthy',
          port: 8000,
          description: 'Main API service with health, routing, and integration points',
          technologies: ['Python', 'Flask/FastAPI', 'JWT', 'Redis', 'TimescaleDB'],
          patterns: ['API Gateway'],
          endpoints: ['/health', '/api/*'],
          connections: ['data', 'engine', 'authelia'],
          category: 'api',
          metrics: {
            'Requests/sec': 1500,
            'Avg Latency': '45ms',
            'Error Rate': '0.1%',
            'Active Connections': 89
          }
        }
      ]
    },
    {
      id: 'services',
      title: 'Core Services',
      badge: 'Business Logic',
      description: 'Microservices handling trading, data processing, and analytics',
      services: [
        {
          id: 'engine',
          name: 'Engine Orchestrator',
          status: 'healthy',
          port: 9010,
          description: 'Orchestrates data fetches and Transformer inference; exposes /forecast and /backtest',
          technologies: ['Python', 'Flask', 'Requests'],
          patterns: ['Orchestrator'],
          connections: ['data', 'transformer', 'api'],
          category: 'compute',
          metrics: {
            'Forecasts/min': 120,
            'Backtests/min': 8,
            'Avg Orchestration': '85ms'
          }
        },
        {
          id: 'data',
          name: 'Market Data Service',
          status: 'healthy',
          port: 9001,
          description: 'High-frequency market data ingestion and processing',
          technologies: ['Python', 'Flask', 'TimescaleDB', 'Redis'],
          patterns: ['ETL Pipeline'],
          connections: ['timescaledb', 'redis'],
          category: 'data',
          metrics: {
            'Data Points/sec': 50000,
            'Storage Used': '2.5TB',
            'Cache Hit Rate': '94%',
            'Data Latency': '3ms'
          }
        },
        {
          id: 'transformer',
          name: 'Transformer Inference (HMM+Transformer)',
          status: 'healthy',
          port: 8089,
          description: 'HMM-guided Transformer inference service exposing /predict',
          technologies: ['PyTorch', 'hmmlearn', 'Python', 'Flask'],
          patterns: ['Online Inference'],
          connections: ['engine', 'data'],
          category: 'ml',
          metrics: {
            'Inference/sec': 120,
            'Avg Latency': '25ms',
            'Device': 'cpu'
          }
        }
      ]
    },
    {
      id: 'data',
      title: 'Data Layer',
      badge: 'Persistence & Cache',
      description: 'Database systems, caching, and data storage infrastructure',
      services: [
        {
          id: 'timescaledb',
          name: 'TimescaleDB (Time-series)',
          status: 'healthy',
          port: 5432,
          description: 'Primary time-series database for market and application data',
          technologies: ['TimescaleDB (PG17)', 'Hypertables', 'Compression', 'Backup Automation'],
          connections: ['api', 'data'],
          category: 'data',
          metrics: {
            'Connections': 45,
            'TPS': 1200,
            'DB Size': '125GB',
            'Query Time': '8ms'
          }
        },
        {
          id: 'redis-cluster',
          name: 'Redis Cluster',
          status: 'healthy',
          port: 6379,
          description: 'In-memory cache and message broker',
          technologies: ['Redis 7', 'Clustering', 'Pub/Sub'],
          connections: ['api', 'data', 'engine'],
          category: 'data',
          metrics: {
            'Memory Usage': '8.5GB',
            'Hit Rate': '96%',
            'Operations/sec': 25000
          }
        }
      ]
    },
    {
      id: 'infrastructure',
      title: 'Infrastructure Layer',
      badge: 'Platform & DevOps',
      description: 'Container orchestration, monitoring, and deployment infrastructure',
      infrastructureItems: [
        {
          icon: '🐳',
          name: 'Docker Containers',
          description: 'All services containerized with Docker for consistent deployment'
        },
        {
          icon: '📊',
          name: 'Monitoring Stack',
          description: 'Prometheus, Grafana, and custom metrics for observability'
        },
        {
          icon: '🔒',
          name: 'Security Layer',
          description: 'JWT authentication, TLS encryption, and API security'
        },
        {
          icon: '🔄',
          name: 'CI/CD Pipeline',
          description: 'GitHub Actions for automated testing and deployment'
        }
      ],
      services: [
        {
          id: 'nginx',
          name: 'Nginx Gateway',
          status: 'healthy',
          description: 'Reverse proxy and TLS termination with routing to API/Data/Engine/Transformer/Web',
          technologies: ['Nginx', 'Reverse Proxy', 'TLS'],
          connections: ['api', 'data', 'engine', 'transformer', 'web', 'authelia'],
          category: 'infrastructure',
          metrics: {
            'Requests/sec': 1800,
            'Active Upstreams': 5
          }
        },
        {
          id: 'authelia',
          name: 'Authentik SSO',
          status: 'healthy',
          port: 9000,
          description: 'Self-hosted SSO provider integrated via Nginx',
          technologies: ['Authentik', 'OIDC', 'OAuth2'],
          connections: ['nginx', 'api', 'web'],
          category: 'infrastructure',
          metrics: {
            'Users': 3,
            'Clients': 2
          }
        },
      ]
    }
  ];

  // Derive service ids for aggregate contract dashboard (unique)
  const contractServiceIds = Array.from(new Set(architectureLayers.flatMap(l => (l.services || []).map(s => s.id))));

  // Simulate real-time metrics updates
  useEffect(() => {
    const interval = setInterval(() => {
      setRealTimeMetrics(prev => ({
        ...prev,
        timestamp: Date.now(),
        'api-requests': Math.floor(Math.random() * 2000) + 1000,
        'system-load': Math.random() * 100,
        'active-users': Math.floor(Math.random() * 50) + 10
      }));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && e.ctrlKey) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        setSelectedService(null);
        setSearchTerm('');
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const toggleLayer = (layerId: string) => {
    const newCollapsed = new Set(collapsedLayers);
    if (newCollapsed.has(layerId)) {
      newCollapsed.delete(layerId);
    } else {
      newCollapsed.add(layerId);
    }
    setCollapsedLayers(newCollapsed);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-500';
      case 'warning': return 'bg-yellow-500';
      case 'error': return 'bg-red-500';
      case 'offline': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getServiceIcon = (category: string) => {
    switch (category) {
      case 'frontend': return Globe;
      case 'api': return Server;
      case 'data': return Database;
      case 'compute': return Cpu;
      case 'ml': return BarChart3;
      case 'infrastructure': return Monitor;
      default: return Activity;
    }
  };

  const filteredLayers = architectureLayers.map(layer => ({
    ...layer,
    services: layer.services
      .map(service => updateServiceWithLiveData(service))
      .filter(service =>
        !searchTerm || 
        service.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        service.technologies.some(tech => tech.toLowerCase().includes(searchTerm.toLowerCase())) ||
        service.description.toLowerCase().includes(searchTerm.toLowerCase())
      )
  })).filter(layer => !searchTerm || layer.services.length > 0 || layer.title.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <PageContainer>
  {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2 flex items-center gap-3">
                <Activity className="h-10 w-10 text-blue-400" />
                FKS Trading Systems Architecture
              </h1>
              <p className="text-white/70">Interactive system architecture with real-time monitoring</p>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={config.services.grafana || 'http://localhost:3001'}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-2 text-sm rounded-lg border border-white/20 bg-white/10 hover:bg-white/20 text-white"
              >
                Open Grafana
              </a>
              <a
                href={config.services.prometheus || 'http://localhost:9090'}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-2 text-sm rounded-lg border border-white/20 bg-white/10 hover:bg-white/20 text-white"
              >
                Open Prometheus
              </a>
              <button
                onClick={refreshServices}
                disabled={servicesLoading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 text-blue-300 rounded-lg border border-blue-500/30 hover:bg-blue-500/30 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${servicesLoading ? 'animate-spin' : ''}`} />
                {servicesLoading ? 'Checking...' : 'Refresh Status'}
              </button>
            </div>
          </div>
          
          {isDeveloper && (
            <div className="mt-4 p-4 bg-blue-500/20 rounded-lg border border-blue-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Code className="h-4 w-4 text-blue-400" />
                <span className="text-blue-300 font-medium">Developer Mode Active</span>
              </div>
              <p className="text-blue-200 text-sm">
                Full system visibility with detailed metrics and service connections
              </p>
            </div>
          )}

          {/* System Health Alert */}
          {systemHealth.overallStatus !== 'healthy' && (
            <div className={`mt-4 p-4 rounded-lg border ${
              systemHealth.overallStatus === 'critical' 
                ? 'bg-red-500/20 border-red-500/30 text-red-300' 
                : 'bg-yellow-500/20 border-yellow-500/30 text-yellow-300'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4" />
                <span className="font-medium">
                  System Status: {systemHealth.overallStatus === 'critical' ? 'Critical' : 'Degraded'}
                </span>
              </div>
              <p className="text-sm">
                {systemHealth.errorServices > 0 && `${systemHealth.errorServices} services with errors. `}
                {systemHealth.offlineServices > 0 && `${systemHealth.offlineServices} services offline. `}
                {systemHealth.warningServices > 0 && `${systemHealth.warningServices} services with warnings.`}
              </p>
            </div>
          )}
        </div>

        {/* High-Level Architecture (Mermaid) */}
        <div className="glass-card p-6 mb-10">
          <h2 className="text-xl font-semibold text-white mb-2 flex items-center gap-2">
            <Code className="h-5 w-5 text-blue-400" /> High-Level System Diagram
          </h2>
          <p className="text-white/70 text-sm mb-4">
            Text-as-code architecture view rendered with Mermaid. Shows primary data & request flows across layers.
          </p>
          <AsyncMermaid
            chart={`flowchart LR
  subgraph UI[Web UI / React]
    A[User Browser]
  end
  A -->|HTTPS| N[Nginx Gateway]
  N -->|/api/*| API[Core API]
  N -->|/predict| ENG[Engine Orchestrator]
  N --> AUTH[Authentik SSO]
  AUTH --> API
  API --> REDIS[(Redis Cluster)]
  API --> TSDB[(TimescaleDB)]
  ENG --> DATA[Market Data Service]
  ENG --> TRF[Transformer Inference]
  DATA --> TSDB
  DATA --> REDIS
  TRF --> DATA
  classDef ext fill:#334155,stroke:#64748b,color:#f1f5f9,stroke-width:1px;
  classDef db fill:#0f172a,stroke:#38bdf8,color:#e0f2fe,stroke-dasharray:3 3;
  classDef cache fill:#1e293b,stroke:#f59e0b,color:#ffedd5;
  classDef svc fill:#1e293b,stroke:#3b82f6,color:#e2e8f0;
  class API,ENG,DATA,TRF svc;
  class TSDB db;
  class REDIS cache;
  class N,AUTH ext;
`}
            className="rounded-md bg-gray-900/60 p-4 border border-white/10"
            config={{ theme: 'dark' }}
          />
        </div>

        {/* Search Bar */}
        <div className="mb-8">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-white/50" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search services, technologies... (Ctrl+/)"
              className="w-full pl-10 pr-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:border-blue-400/50 focus:bg-white/15"
            />
          </div>
          {/* Supplemental Diagrams */}
          <div className="mt-8">
            <h2 className="text-xl font-semibold text-white mb-3 flex items-center gap-2">System Diagrams</h2>
            <SystemDiagrams />
          </div>
        </div>

        {/* Real-time System Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="glass-card p-4">
            <div className="flex items-center gap-2">
              <TrendingUp className={`h-5 w-5 ${
                systemHealth.overallStatus === 'healthy' ? 'text-green-400' :
                systemHealth.overallStatus === 'degraded' ? 'text-yellow-400' : 'text-red-400'
              }`} />
              <span className="text-white/70 text-sm">System Health</span>
            </div>
            <p className={`text-2xl font-bold ${
              systemHealth.overallStatus === 'healthy' ? 'text-green-400' :
              systemHealth.overallStatus === 'degraded' ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {systemHealth.overallStatus === 'healthy' ? '98.7%' : 
               systemHealth.overallStatus === 'degraded' ? '85.3%' : '12.1%'}
            </p>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-blue-400" />
              <span className="text-white/70 text-sm">Healthy Services</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {systemHealth.healthyServices}/{systemHealth.totalServices}
            </p>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-400" />
              <span className="text-white/70 text-sm">Requests/sec</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {realTimeMetrics['api-requests']?.toLocaleString() || '1,247'}
            </p>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-purple-400" />
              <span className="text-white/70 text-sm">Active Users</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {realTimeMetrics['active-users'] || '23'}
            </p>
          </div>
        </div>

        {/* Contract Tests Aggregate */}
        <div className="mb-10">
          <ContractAggregateDashboard services={contractServiceIds} />
        </div>

        {/* Architecture Layers */}
        <div className="space-y-6">
          {filteredLayers.map((layer, index) => {
            const isCollapsed = collapsedLayers.has(layer.id);
            
            return (
              <div key={layer.id}>
                <div className="glass-card">
                  {/* Layer Header */}
                  <div 
                    className="flex items-center justify-between p-6 cursor-pointer"
                    onClick={() => toggleLayer(layer.id)}
                  >
                    <div>
                      <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                        {layer.title}
                        <span className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded-full text-sm font-medium border border-blue-500/30">
                          {layer.badge}
                        </span>
                      </h2>
                      <p className="text-white/70 mt-1">{layer.description}</p>
                    </div>
                    {isCollapsed ? 
                      <ChevronDown className="h-6 w-6 text-white/70" /> : 
                      <ChevronUp className="h-6 w-6 text-white/70" />
                    }
                  </div>

                  {/* Layer Content */}
                  {!isCollapsed && (
                    <div className="px-6 pb-6">
                      {/* Infrastructure Items */}
                      {layer.infrastructureItems && (
                        <div className="mb-6">
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            {layer.infrastructureItems.map((item) => (
                              <div key={item.name} className="p-3 bg-white/10 rounded-lg border border-white/20 text-center">
                                <div className="text-2xl mb-2">{item.icon}</div>
                                <div className="text-white font-medium text-sm">{item.name}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Services Grid */}
                      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                        {layer.services.map((service) => {
                          const ServiceIcon = getServiceIcon(service.category);
                          
                          return (
                            <div
                              key={service.id}
                              onClick={() => setSelectedService(service)}
                              className="p-4 bg-white/10 rounded-lg border border-white/20 hover:border-blue-400/50 hover:bg-white/15 transition-all cursor-pointer"
                            >
                              <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <ServiceIcon className="h-5 w-5 text-blue-400" />
                                  <span className={`w-2 h-2 rounded-full ${getStatusColor(service.status)} animate-pulse`} />
                                </div>
                                {service.port && (
                                  <span className="text-xs text-white/50 bg-white/10 px-2 py-1 rounded">
                                    :{service.port}
                                  </span>
                                )}
                              </div>
                              
                              <h3 className="text-white font-semibold mb-2">{service.name}</h3>
                              <p className="text-white/70 text-sm mb-3 line-clamp-2">{service.description}</p>
                              
                              <div className="flex flex-wrap gap-1 mb-3">
                                {service.technologies.slice(0, 3).map((tech) => (
                                  <span key={tech} className="px-2 py-1 bg-blue-500/20 text-blue-300 rounded text-xs border border-blue-500/30">
                                    {tech}
                                  </span>
                                ))}
                                {service.technologies.length > 3 && (
                                  <span className="px-2 py-1 bg-white/10 text-white/50 rounded text-xs">
                                    +{service.technologies.length - 3}
                                  </span>
                                )}
                              </div>

                              {service.metrics && isDeveloper && (
                                <div className="text-xs text-white/60">
                                  {Object.entries(service.metrics).slice(0, 2).map(([key, value]) => (
                                    <div key={key} className="flex justify-between">
                                      <span>{key}:</span>
                                      <span className="font-medium">{value}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Flow Arrow */}
                {index < filteredLayers.length - 1 && (
                  <div className="flex justify-center py-4">
                    <div className="flex items-center gap-2 text-blue-400">
                      <div className="w-12 h-0.5 bg-blue-400/50" />
                      <ChevronDown className="h-6 w-6 animate-bounce" />
                      <div className="w-12 h-0.5 bg-blue-400/50" />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Service Detail Modal */}
  {selectedService && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="glass-card max-w-2xl w-full max-h-[80vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(selectedService.status)} animate-pulse`} />
                    <h2 className="text-2xl font-bold text-white">{selectedService.name}</h2>
                  </div>
                  <button
                    onClick={() => setSelectedService(null)}
                    className="text-white/70 hover:text-white text-2xl"
                  >
                    ×
                  </button>
                </div>

                <p className="text-white/80 mb-4">{selectedService.description}</p>

                {selectedService.port && (
                  <p className="text-white/70 mb-4">
                    <strong>Port:</strong> {selectedService.port}
                  </p>
                )}

                {selectedService.endpoints && (
                  <div className="mb-4">
                    <h3 className="text-white font-semibold mb-2">Endpoints:</h3>
                    <div className="space-y-1">
                      {selectedService.endpoints.map((endpoint) => (
                        <code key={endpoint} className="block text-sm bg-white/10 px-2 py-1 rounded text-blue-300">
                          {endpoint}
                        </code>
                      ))}
                    </div>
                  </div>
                )}

                <div className="mb-4">
                  <h3 className="text-white font-semibold mb-2">Technologies:</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedService.technologies.map((tech) => (
                      <span key={tech} className="px-3 py-1 bg-blue-500/20 text-blue-300 rounded border border-blue-500/30">
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>

                {selectedService.patterns && (
                  <div className="mb-4">
                    <h3 className="text-white font-semibold mb-2">Architectural Patterns:</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedService.patterns.map((pattern) => (
                        <span key={pattern} className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded border border-purple-500/30">
                          {pattern}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedService.metrics && isDeveloper && (
                  <div className="mb-4">
                    <h3 className="text-white font-semibold mb-2">Real-time Metrics:</h3>
                    <div className="grid grid-cols-2 gap-4">
                      {Object.entries(selectedService.metrics).map(([key, value]) => (
                        <div key={key} className="p-3 bg-white/10 rounded-lg">
                          <div className="text-white/70 text-sm">{key}</div>
                          <div className="text-white font-semibold">{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <h3 className="text-white font-semibold mb-2">Connected Services:</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedService.connections.map((connection) => (
                      <span key={connection} className="px-2 py-1 bg-white/10 text-white/70 rounded text-sm border border-white/20">
                        {connection}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
    )}
  </PageContainer>
  );
};

export default ArchitectureDashboard;
