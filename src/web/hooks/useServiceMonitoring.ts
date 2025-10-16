import { useState, useEffect, useRef } from 'react';

export interface ServiceStatus {
  id: string;
  name: string;
  status: 'healthy' | 'warning' | 'error' | 'offline';
  port?: number;
  lastCheck: Date;
  responseTime?: number;
  uptime?: number;
  metrics?: {
    [key: string]: number | string;
  };
  latencyHistory?: number[]; // ms measurements (recent)
}

export interface SystemHealth {
  overallStatus: 'healthy' | 'degraded' | 'critical';
  totalServices: number;
  healthyServices: number;
  warningServices: number;
  errorServices: number;
  offlineServices: number;
  lastUpdate: Date;
}

// Export the static endpoint registry so other tooling (health pages, diagnostics) can reuse it
export const serviceEndpoints = [
  { id: 'nginx', url: 'http://localhost/health', name: 'Nginx Gateway', port: 80 },
  { id: 'web', url: 'http://localhost:3000/', name: 'Web UI (React)', port: 3000 },
  { id: 'api', url: 'http://localhost:8000/health', name: 'Core API Service', port: 8000 },
  { id: 'data', url: 'http://localhost:9001/health', name: 'Market Data Service', port: 9001 },
  { id: 'engine', url: 'http://localhost:9010/health', name: 'Engine Orchestrator', port: 9010 },
  { id: 'transformer', url: 'http://localhost:8089/health', name: 'Transformer Inference', port: 8089 },
  // Planned / placeholder endpoints (update URLs when services exposed)
  { id: 'worker', url: 'http://localhost:9020/health', name: 'Background Worker', port: 9020 },
  { id: 'training', url: 'http://localhost:9030/health', name: 'Model Training Service', port: 9030 },
  // Removed authelia service (Authentik SSO) after migration to internal rust auth
  // External / ancillary (placeholder URLs)
  { id: 'cloudflare', url: 'https://cloudflare.com', name: 'Cloudflare Edge', port: undefined },
  { id: 'github', url: 'https://api.github.com', name: 'GitHub API', port: undefined }
];

export const useServiceMonitoring = () => {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth>({
    overallStatus: 'healthy',
    totalServices: 0,
    healthyServices: 0,
    warningServices: 0,
    errorServices: 0,
    offlineServices: 0,
    lastUpdate: new Date()
  });
  const [isLoading, setIsLoading] = useState(true);
  const loadedRef = (globalThis as any).__fksLatencyLoaded || { current: false };
  if (!(globalThis as any).__fksLatencyLoaded) (globalThis as any).__fksLatencyLoaded = loadedRef;
  const persistedHistory: Record<string, number[]> = !loadedRef.current ? (() => {
    try { return JSON.parse(localStorage.getItem('fks_service_latency_history') || '{}'); } catch { return {}; }
  })() : {};
  if (!loadedRef.current) loadedRef.current = true;

  // NOTE: external components may import serviceEndpoints directly; clone to avoid accidental mutation.
  const endpoints = [...serviceEndpoints];

  const realHealthEnabled = import.meta.env.VITE_ENABLE_REAL_HEALTH === 'true';
  const centralMonitorBase: string | undefined = (import.meta as any).env.VITE_FKS_MONITOR_URL;
  const centralEnabled = !!centralMonitorBase; // If provided, prefer aggregated monitor data

  const checkServiceHealth = async (endpoint: typeof endpoints[0]): Promise<ServiceStatus> => {
    const startTime = Date.now();
    
    try {
      let responseData: { status: 'healthy' | 'warning' | 'error'; uptime?: number; metrics?: Record<string, any> };
      if (realHealthEnabled) {
        // Attempt real fetch; treat network / non-2xx as degraded/offline
        const controller = new AbortController();
        const t = setTimeout(() => controller.abort(), 5000);
        let ok = false; let httpStatus = 0;
        try {
          const resp = await fetch(endpoint.url, { signal: controller.signal, mode: 'cors' });
          httpStatus = resp.status;
          ok = resp.ok;
        } finally { clearTimeout(t); }
        if (!ok) {
          if (httpStatus === 0) throw new Error('unreachable');
          responseData = { status: httpStatus >= 500 ? 'error' : 'warning' };
        } else {
          responseData = { status: 'healthy' };
        }
      } else {
        responseData = await simulateHealthCheck(endpoint);
      }
      const responseTime = Date.now() - startTime;
      
      return {
        id: endpoint.id,
        name: endpoint.name,
        status: responseData.status,
        port: endpoint.port,
        lastCheck: new Date(),
        responseTime,
        uptime: responseData.uptime,
        metrics: responseData.metrics
      };
    } catch (error) {
      return {
        id: endpoint.id,
        name: endpoint.name,
        status: 'offline',
        port: endpoint.port,
        lastCheck: new Date(),
        responseTime: Date.now() - startTime
      };
    }
  };

  // Simulate health check responses
  const simulateHealthCheck = async (endpoint: typeof endpoints[0]) => {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
    
    // Simulate different service states
    const random = Math.random();
    
  if (endpoint.id === 'transformer' && random < 0.2) {
      return {
        status: 'warning' as const,
        uptime: 0.987,
        metrics: {
      'Device': 'cpu',
      'Avg Latency': `${Math.floor(Math.random() * 15 + 20)}ms`,
      'Inferences/min': Math.floor(Math.random() * 120 + 60)
        }
      };
    }
    
    if (random < 0.05) {
      throw new Error('Service unreachable');
    }
    
    if (random < 0.1) {
      return {
        status: 'warning' as const,
        uptime: 0.995,
        metrics: generateMockMetrics(endpoint.id)
      };
    }
    
    return {
      status: 'healthy' as const,
      uptime: 0.999,
      metrics: generateMockMetrics(endpoint.id)
    };
  };

  const generateMockMetrics = (serviceId: string) => {
    const baseMetrics = {
      'CPU Usage': `${Math.floor(Math.random() * 30 + 10)}%`,
      'Memory': `${(Math.random() * 2 + 1).toFixed(1)}GB`,
      'Uptime': `${Math.floor(Math.random() * 20 + 5)}d`
    };

    switch (serviceId) {
      case 'api':
        return {
          ...baseMetrics,
          'Requests/min': Math.floor(Math.random() * 500 + 1000),
          'Avg Response': `${Math.floor(Math.random() * 20 + 30)}ms`,
          'Active Connections': Math.floor(Math.random() * 50 + 20)
        };
      case 'engine':
        return {
          ...baseMetrics,
          'Forecasts/min': Math.floor(Math.random() * 60 + 30),
          'Backtests/min': Math.floor(Math.random() * 10 + 5),
          'Orchestration Latency': `${Math.floor(Math.random() * 40 + 60)}ms`
        };
      case 'data':
        return {
          ...baseMetrics,
          'Data Points/sec': Math.floor(Math.random() * 10000 + 40000),
          'Cache Hit Rate': `${Math.floor(Math.random() * 10 + 90)}%`,
          'Storage Used': `${(Math.random() * 1 + 2).toFixed(1)}TB`
        };
      case 'nginx':
        return {
          ...baseMetrics,
          'Requests/min': Math.floor(Math.random() * 800 + 1200),
          'Upstreams': 5
        };
      case 'web':
        return {
          ...baseMetrics,
          'Active Users': Math.floor(Math.random() * 40 + 10),
          'Page Load': `${(Math.random() * 1 + 0.8).toFixed(2)}s`
        };
      case 'rust':
        return {
          ...baseMetrics,
          'Auth Sessions': Math.floor(Math.random() * 5 + 2),
          'Keys Loaded': Math.floor(Math.random() * 2 + 1)
        };
      default:
        return baseMetrics;
    }
  };

  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  const fetchCentralAggregate = async (): Promise<{
    services: ServiceStatus[];
    system: SystemHealth;
  } | null> => {
    if (!centralEnabled) return null;
    try {
      const resp = await fetch(`${centralMonitorBase.replace(/\/$/, '')}/health/aggregate`, { headers: { 'Accept': 'application/json' } });
      if (!resp.ok) throw new Error(`central monitor http ${resp.status}`);
      const data = await resp.json();
      const svc: ServiceStatus[] = (data.services || []).map((s: any) => ({
        id: s.id,
        name: s.name,
        status: (s.status || 'offline'),
        port: undefined,
        lastCheck: new Date(s.lastCheck || s.last_check || Date.now()),
        responseTime: s.responseTimeMs || s.response_time_ms,
        uptime: undefined,
        metrics: {
          Critical: s.critical ? 'yes' : 'no'
        }
      }));
      const system: SystemHealth = {
        overallStatus: data.overallStatus || 'healthy',
        totalServices: data.totalServices ?? svc.length,
        healthyServices: data.healthyServices ?? svc.filter(s => s.status === 'healthy').length,
        warningServices: data.warningServices ?? svc.filter(s => s.status === 'warning').length,
        errorServices: data.errorServices ?? svc.filter(s => s.status === 'error').length,
        offlineServices: data.offlineServices ?? svc.filter(s => s.status === 'offline').length,
        lastUpdate: new Date(data.lastUpdate || Date.now())
      };
      return { services: svc, system };
    } catch (e) {
      console.warn('[useServiceMonitoring] central monitor fetch failed, falling back', e);
      return null;
    }
  };

  const checkAllServices = async () => {
    if (!mountedRef.current) return;
    setIsLoading(true);
    
    try {
      // Prefer central aggregate if available
      const central = await fetchCentralAggregate();
      if (central) {
        if (!mountedRef.current) return;
        setServices(prev => central.services.map(s => {
          // attempt to retain latency history; compute synthetic history push
          const prior = prev.find(p => p.id === s.id);
          const history = prior?.latencyHistory ? [...prior.latencyHistory.slice(-19), s.responseTime || 0] : [s.responseTime || 0];
          return { ...s, latencyHistory: history };
        }));
        setSystemHealth(central.system);
        return; // skip legacy path
      }

      const serviceStatuses = await Promise.all(
        endpoints.map(async endpoint => {
          const prev = services.find(s => s.id === endpoint.id);
          const restored = prev?.latencyHistory || persistedHistory[endpoint.id];
          const current = await checkServiceHealth(endpoint);
          const historyBase = restored ? restored.slice(-19) : [];
          const history = [...historyBase, current.responseTime || 0];
          return { ...current, latencyHistory: history };
        })
      );

      // Persist updated history map
      try {
        const map: Record<string, number[]> = {};
        serviceStatuses.forEach(s => { if (s.latencyHistory) map[s.id] = s.latencyHistory; });
        localStorage.setItem('fks_service_latency_history', JSON.stringify(map));
      } catch {}
      
  if (!mountedRef.current) return;
  setServices(serviceStatuses);
      
      // Calculate system health
  const totalServices = serviceStatuses.length;
      const healthyServices = serviceStatuses.filter(s => s.status === 'healthy').length;
      const warningServices = serviceStatuses.filter(s => s.status === 'warning').length;
      const errorServices = serviceStatuses.filter(s => s.status === 'error').length;
      const offlineServices = serviceStatuses.filter(s => s.status === 'offline').length;
      
      let overallStatus: SystemHealth['overallStatus'] = 'healthy';
      if (errorServices > 0 || offlineServices > totalServices / 2) {
        overallStatus = 'critical';
      } else if (warningServices > 0 || offlineServices > 0) {
        overallStatus = 'degraded';
      }
      
  setSystemHealth({
        overallStatus,
        totalServices,
        healthyServices,
        warningServices,
        errorServices,
        offlineServices,
        lastUpdate: new Date()
      });
    } catch (error) {
      console.error('Failed to check service health:', error);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  };

  // Initial check and periodic updates
  useEffect(() => {
    checkAllServices();
    
    // Check every 30 seconds
    const interval = setInterval(checkAllServices, 30000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    services,
    systemHealth,
    isLoading,
    refreshServices: checkAllServices
  };
};
