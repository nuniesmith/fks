import { Search, ChevronDown, ChevronUp } from 'lucide-react';
import React, { useState, useEffect, useRef } from 'react';

interface Service {
  name: string;
  status: 'healthy' | 'warning' | 'error';
  port?: number;
  details: string[];
  patterns?: string[];
  technologies: string[];
  endpoints?: string[];
  gpu?: boolean;
  frontend?: boolean;
  borderColor?: string;
}

interface Layer {
  id: string;
  title: string;
  badge: string;
  description: string;
  services?: Service[];
  infrastructureItems?: { icon: string; name: string }[];
  flow?: { step: string; description: string }[];
}

const ArchitectureDiagram: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [collapsedLayers, setCollapsedLayers] = useState<Set<string>>(new Set());
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Architecture data
  const architectureData: Layer[] = [
    {
      id: 'framework',
      title: 'Framework Layer',
      badge: 'Core Infrastructure',
      description: 'Base infrastructure and cross-cutting concerns for the entire system',
      infrastructureItems: [
        { icon: '🔧', name: 'Base Classes' },
        { icon: '⚙️', name: 'Config Management' },
        { icon: '📝', name: 'Logging (Loguru)' },
        { icon: '📊', name: 'Monitoring' },
        { icon: '💾', name: 'Persistence' },
        { icon: '🔄', name: 'Lifecycle Management' },
        { icon: '🚨', name: 'Exception Handling' },
        { icon: '✅', name: 'Validation' }
      ],
      services: [
        {
          name: 'Architectural Patterns',
          status: 'healthy',
          details: [
            '📌 Disruptor Pattern (High-performance queues)',
            '🌌 Space-Based Architecture (Distributed processing)',
            '🔍 Filter Pattern (Data preprocessing)',
            '👁️ Observer Pattern (Event handling)',
            '🏭 Factory Pattern (Component creation)'
          ],
          technologies: ['Python', 'AsyncIO', 'Design Patterns']
        },
        {
          name: 'Cross-Cutting Concerns',
          status: 'healthy',
          details: [
            '🔐 Security (Authentication/Authorization)',
            '⚡ Performance Optimization',
            '📈 Telemetry & Metrics',
            '🔄 State Management',
            '🎯 Dependency Injection'
          ],
          technologies: ['JWT', 'OAuth2', 'Prometheus']
        }
      ]
    },
    {
      id: 'services',
      title: 'Service Layer',
      badge: 'Microservices',
      description: 'Independent microservices handling specific system functions',
      services: [
        {
          name: '📊 Data Service',
          status: 'healthy',
          port: 9001,
          details: [
            'Market data collection',
            'ETL processing pipeline',
            'ODS with CQL support',
            'Event streaming (Kafka-like)',
            'Data validation & enrichment'
          ],
          patterns: ['ETL Pattern', 'Filter Pattern'],
          technologies: ['FastAPI', 'Redis', 'PostgreSQL'],
          endpoints: ['/health', '/status', '/data/latest/{symbol}', '/data/query']
        },
        {
          name: '🎯 App Service (Core Engine)',
          status: 'healthy',
          port: 9000,
          details: [
            'Trading engine (SBA)',
            'Complex event processing',
            'Strategy orchestration',
            'Risk management',
            'Order generation'
          ],
          patterns: ['Disruptor Pattern', 'Observer Pattern'],
          technologies: ['Space-Based Architecture', 'CEP Engine'],
          borderColor: '#f39c12'
        },
        {
          name: '🔌 API Service',
          status: 'healthy',
          port: 8000,
          details: [
            'RESTful endpoints',
            'WebSocket support',
            'Authentication (JWT)',
            'Rate limiting',
            'Circuit breaker'
          ],
          technologies: ['FastAPI', 'WebSocket', 'JWT'],
          endpoints: ['/api/v1/*', '/ws', '/auth/token']
        },
        {
          name: '🌐 Web Service',
          status: 'healthy',
          port: 3000,
          details: [
            'Trading dashboard',
            'Real-time monitoring',
            'Interactive charts',
            'System controls',
            'Performance analytics'
          ],
          technologies: ['React', 'WebSocket', 'D3.js'],
          frontend: true
        }
      ]
    },
    {
      id: 'infrastructure',
      title: 'Infrastructure Layer',
      badge: 'Platform & DevOps',
      description: 'Platform services and infrastructure components',
      infrastructureItems: [
        { icon: '🔒', name: 'Security Layer' },
        { icon: '📊', name: 'Monitoring Stack' },
        { icon: '📝', name: 'Logging Pipeline' },
        { icon: '🔄', name: 'CI/CD Pipeline' },
        { icon: '🌐', name: 'API Gateway' },
        { icon: '💾', name: 'Backup Systems' }
      ],
      services: [
        {
          name: '🐳 Container Orchestration',
          status: 'healthy',
          details: [
            'Docker containerization',
            'Docker Compose orchestration',
            'Service mesh (future: K8s)',
            'Load balancing',
            'Auto-scaling capabilities'
          ],
          technologies: ['Docker', 'Docker Compose', 'Kubernetes (planned)']
        },
        {
          name: '💾 Data Persistence',
          status: 'healthy',
          details: [
            'PostgreSQL (OLTP)',
            'Redis (Cache + Queue)',
            'TimescaleDB (Time-series)',
            'S3-compatible storage',
            'Backup & Recovery'
          ],
          technologies: ['PostgreSQL', 'Redis', 'TimescaleDB', 'MinIO']
        }
      ]
    }
  ];

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsModalOpen(false);
      }
      if (e.key === '/' && e.ctrlKey) {
        e.preventDefault();
        searchInputRef.current?.focus();
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
      default: return 'bg-gray-500';
    }
  };

  const showServiceDetails = (service: Service) => {
    setSelectedService(service);
    setIsModalOpen(true);
  };

  const filteredLayers = architectureData.filter(layer => {
    if (!searchTerm) return true;
    const searchLower = searchTerm.toLowerCase();
    return (
      layer.title.toLowerCase().includes(searchLower) ||
      layer.description.toLowerCase().includes(searchLower) ||
      layer.services?.some(service => 
        service.name.toLowerCase().includes(searchLower) ||
        service.technologies.some(tech => tech.toLowerCase().includes(searchLower))
      )
    );
  });

  return (
    <div className="glass-card p-6">
      <h1 className="text-3xl font-bold text-center mb-8 text-primary-gradient bg-clip-text text-transparent">
        🚀 FKS Trading Systems - Interactive Architecture
      </h1>

      {/* Search Bar */}
      <div className="mb-6 flex justify-center">
        <div className="relative max-w-md w-full">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search services, patterns, or technologies... (Ctrl+/ to focus)"
            className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-600 rounded-full text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      </div>

      {/* Architecture Layers */}
      <div className="space-y-6">
        {filteredLayers.map((layer, index) => {
          const isCollapsed = collapsedLayers.has(layer.id);
          return (
            <div key={layer.id} className="relative">
              <div className="glass-card bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-600 rounded-xl overflow-hidden">
                {/* Layer Header */}
                <div 
                  className="flex items-center justify-between p-6 cursor-pointer hover:bg-gray-700/20 transition-colors"
                  onClick={() => toggleLayer(layer.id)}
                >
                  <div className="flex items-center gap-4">
                    <h2 className="text-xl font-bold text-white">{layer.title}</h2>
                    <span className="px-3 py-1 bg-blue-600 text-white text-sm rounded-full">
                      {layer.badge}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isCollapsed ? (
                      <ChevronDown className="w-5 h-5 text-gray-400" />
                    ) : (
                      <ChevronUp className="w-5 h-5 text-gray-400" />
                    )}
                  </div>
                </div>

                {/* Layer Content */}
                {!isCollapsed && (
                  <div className="px-6 pb-6">
                    <p className="text-gray-300 mb-4">{layer.description}</p>

                    {/* Infrastructure Items */}
                    {layer.infrastructureItems && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                        {layer.infrastructureItems.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-2 p-3 bg-gray-700/50 rounded-lg border border-gray-600">
                            <span className="text-lg">{item.icon}</span>
                            <span className="text-sm text-gray-300">{item.name}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Services Grid */}
                    {layer.services && (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {layer.services.map((service, idx) => (
                          <div
                            key={idx}
                            className="p-4 bg-gray-800/50 rounded-lg border border-gray-600 hover:border-gray-500 transition-colors cursor-pointer"
                            onClick={() => showServiceDetails(service)}
                            style={service.borderColor ? { borderColor: service.borderColor } : {}}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <h3 className="font-semibold text-white">{service.name}</h3>
                              <div className="flex items-center gap-2">
                                <div className={`w-2 h-2 rounded-full ${getStatusColor(service.status)}`} />
                                {service.port && (
                                  <span className="text-xs text-gray-400">:{service.port}</span>
                                )}
                              </div>
                            </div>
                            
                            <ul className="text-sm text-gray-300 space-y-1 mb-3">
                              {service.details.slice(0, 3).map((detail, detailIdx) => (
                                <li key={detailIdx}>• {detail}</li>
                              ))}
                            </ul>
                            
                            <div className="flex flex-wrap gap-1">
                              {service.technologies.slice(0, 3).map((tech, techIdx) => (
                                <span key={techIdx} className="px-2 py-1 bg-blue-600/20 text-blue-300 text-xs rounded">
                                  {tech}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Flow Arrow */}
              {index < filteredLayers.length - 1 && (
                <div className="flex justify-center py-4">
                  <div className="text-2xl text-blue-500 animate-bounce">⬇</div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Modal for Service Details */}
      {isModalOpen && selectedService && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-gray-800 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white">{selectedService.name}</h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className={`w-3 h-3 rounded-full ${getStatusColor(selectedService.status)}`} />
                <span className="text-gray-300">Status: {selectedService.status}</span>
                {selectedService.port && (
                  <span className="text-gray-300">Port: {selectedService.port}</span>
                )}
              </div>
              
              <div>
                <h3 className="font-semibold text-white mb-2">Details:</h3>
                <ul className="text-gray-300 space-y-1">
                  {selectedService.details.map((detail, idx) => (
                    <li key={idx}>• {detail}</li>
                  ))}
                </ul>
              </div>
              
              {selectedService.endpoints && (
                <div>
                  <h3 className="font-semibold text-white mb-2">Endpoints:</h3>
                  <ul className="text-gray-300 space-y-1">
                    {selectedService.endpoints.map((endpoint, idx) => (
                      <li key={idx}>
                        <code className="bg-gray-700 px-2 py-1 rounded text-sm">{endpoint}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              <div>
                <h3 className="font-semibold text-white mb-2">Technologies:</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedService.technologies.map((tech, idx) => (
                    <span key={idx} className="px-3 py-1 bg-blue-600/20 text-blue-300 text-sm rounded">
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ArchitectureDiagram;
