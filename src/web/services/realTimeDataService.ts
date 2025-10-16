// services/realTimeDataService.ts
import { config } from '../config/environment';
import { isFeatureEnabled } from '../config/features';

export interface SystemHealth {
  service: string;
  status: 'healthy' | 'degraded' | 'down';
  uptime: string;
  lastCheck: string;
  responseTime?: number;
  url?: string;
}

export interface SystemOverview {
  healthScore: number;
  servicesOnline: number;
  avgResponseTime: number;
  uptime: string;
  totalServices: number;
}

export interface TradingMetrics {
  dailyPnL: number;
  totalTrades: number;
  winRate: number;
  activePositions: number;
  signalQuality: number;
  marketRegime: string;
  dailyVolume: number;
  successRate: number;
  lastUpdate: string;
}

export interface MarketData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  bid: number;
  ask: number;
  timestamp: string;
}

export interface ComponentStatus {
  name: string;
  connected: boolean;
  version?: string;
  lastUpdate?: string;
  healthScore?: number;
}

class RealTimeDataService {
  private wsConnections: Map<string, WebSocket> = new Map();
  // Map event name -> set of subscriber callbacks
  private subscribers: Map<string, Set<(data: unknown) => void>> = new Map();

  constructor() {
    this.initializeConnections();
  }

  private initializeConnections() {
    // Initialize API connections for real-time data
    this.setupHealthMonitoring();
    this.setupMarketDataStream();
  }

  // Health Monitoring
  async getSystemHealth(): Promise<SystemHealth[]> {
    // In development, use mock data or localhost services
    if (config.isDevelopment || config.useMockData) {
      return this.getMockSystemHealth();
    }

    const services = [
      { name: 'Web Interface', url: config.services.web, port: 3001 },
      { name: 'API Gateway', url: `${config.services.api}/health`, port: 8000 },
  { name: 'TimescaleDB', url: config.services.database, port: 5432 },
      { name: 'Redis Cache', url: config.services.cache, port: 6379 },
  { name: 'Data Stream', url: config.services.data, port: 9001 },
  ...(isFeatureEnabled('ninjaTrader') ? [{ name: 'NinjaTrader', url: config.services.ninja, port: 7496 }] : [] as any),
    ];

    const healthChecks = await Promise.allSettled(
      services.map(async (service) => {
        try {
          const startTime = Date.now();
          const response = await fetch(service.url, { 
            method: 'GET',
            signal: AbortSignal.timeout(config.apiTimeout)
          });
          const responseTime = Date.now() - startTime;
          
          return {
            service: service.name,
            status: response.ok ? 'healthy' : 'degraded',
            uptime: response.ok ? '99.9%' : '95.2%',
            lastCheck: new Date().toLocaleString(),
            responseTime,
            url: service.url
          } as SystemHealth;
        } catch (error) {
          return {
            service: service.name,
            status: 'down',
            uptime: '0%',
            lastCheck: new Date().toLocaleString(),
            responseTime: 0,
            url: service.url
          } as SystemHealth;
        }
      })
    );

    return healthChecks.map((result, index) => {
      if (result.status === 'fulfilled') {
        return result.value;
      } else {
        return {
          service: services[index].name,
          status: 'down',
          uptime: '0%',
          lastCheck: new Date().toLocaleString(),
          responseTime: 0,
          url: services[index].url
        } as SystemHealth;
      }
    });
  }

  private getMockSystemHealth(): SystemHealth[] {
    const services = [
      'Web Interface',
      'API Gateway', 
  'TimescaleDB',
      'Redis Cache',
      'Data Stream',
  ...(isFeatureEnabled('ninjaTrader') ? ['NinjaTrader'] : [])
    ];

    return services.map(service => ({
      service,
      status: Math.random() > 0.2 ? 'healthy' : (Math.random() > 0.5 ? 'degraded' : 'down'),
      uptime: `${(95 + Math.random() * 5).toFixed(1)}%`,
      lastCheck: new Date().toLocaleString(),
      responseTime: Math.floor(Math.random() * 200) + 50,
      url: `http://localhost:${3000 + Math.floor(Math.random() * 5000)}`
    })) as SystemHealth[];
  }

  // System Overview
  async getSystemOverview(): Promise<SystemOverview> {
    if (config.isDevelopment || config.useMockData) {
      // Generate mock overview for development
      const healthData = await this.getSystemHealth();
      const onlineServices = healthData.filter(s => s.status === 'healthy').length;
      const avgResponseTime = healthData.reduce((sum, s) => sum + (s.responseTime || 0), 0) / healthData.length;
      
      return {
        healthScore: Math.round((onlineServices / healthData.length) * 100),
        servicesOnline: onlineServices,
        avgResponseTime: Math.round(avgResponseTime),
        uptime: '99.8%',
        totalServices: healthData.length
      };
    }

    try {
      const response = await fetch(`${config.services.api}/api/system/overview`, {
        signal: AbortSignal.timeout(config.apiTimeout)
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.log('System overview API not available, using mock data');
    }

    // Fallback to mock data
    const healthData = await this.getSystemHealth();
    const onlineServices = healthData.filter(s => s.status === 'healthy').length;
    const avgResponseTime = healthData.reduce((sum, s) => sum + (s.responseTime || 0), 0) / healthData.length;
    
    return {
      healthScore: Math.round((onlineServices / healthData.length) * 100),
      servicesOnline: onlineServices,
      avgResponseTime: Math.round(avgResponseTime),
      uptime: '99.8%',
      totalServices: healthData.length
    };
  }

  // Trading Metrics
  async getTradingMetrics(): Promise<TradingMetrics> {
    if (config.isDevelopment || config.useMockData) {
      return this.getMockTradingMetrics();
    }

    try {
      const response = await fetch(`${config.services.api}/api/trading/metrics`, {
        signal: AbortSignal.timeout(config.apiTimeout)
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.log('Trading metrics API not available, using mock data');
    }

    return this.getMockTradingMetrics();
  }

  private getMockTradingMetrics(): TradingMetrics {
    return {
      dailyPnL: 2450.75 + (Math.random() - 0.5) * 200,
      totalTrades: 12 + Math.floor(Math.random() * 3),
      winRate: 75.0 + (Math.random() - 0.5) * 10,
      activePositions: 3,
      signalQuality: 82.5 + (Math.random() - 0.5) * 15,
      marketRegime: ['TRENDING BULL', 'RANGING', 'TRENDING BEAR'][Math.floor(Math.random() * 3)],
      dailyVolume: 850000 + Math.floor(Math.random() * 200000),
      successRate: 78.5 + (Math.random() - 0.5) * 12,
      lastUpdate: new Date().toISOString()
    };
  }

  // Market Data
  async getMarketData(): Promise<MarketData[]> {
    if (config.isDevelopment || config.useMockData) {
      return this.getMockMarketData();
    }

    try {
      const response = await fetch(`${config.services.data}/api/market/data`, {
        signal: AbortSignal.timeout(config.apiTimeout)
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.log('Market data API not available, using mock data');
    }

    return this.getMockMarketData();
  }

  private getMockMarketData(): MarketData[] {
    const baseData = [
      { symbol: 'ES', basePrice: 4485.25 },
      { symbol: 'NQ', basePrice: 15234.75 },
      { symbol: 'GC', basePrice: 2034.60 },
      { symbol: 'CL', basePrice: 78.45 },
    ];

    return baseData.map(item => {
      const change = (Math.random() - 0.5) * 20;
      const price = item.basePrice + change;
      const changePercent = (change / item.basePrice) * 100;
      
      return {
        symbol: item.symbol,
        price: Number(price.toFixed(2)),
        change: Number(change.toFixed(2)),
        changePercent: Number(changePercent.toFixed(2)),
        volume: Math.floor(Math.random() * 1000000) + 500000,
        bid: Number((price - 0.25).toFixed(2)),
        ask: Number((price + 0.25).toFixed(2)),
        timestamp: new Date().toISOString()
      };
    });
  }

  // Component Status
  async getComponentStatus(): Promise<ComponentStatus[]> {
    if (config.isDevelopment || config.useMockData) {
      return this.getMockComponentStatus();
    }

    try {
      const response = await fetch(`${config.services.api}/api/components/status`, {
        signal: AbortSignal.timeout(config.apiTimeout)
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.log('Component status API not available, using mock data');
    }

    return this.getMockComponentStatus();
  }

  private getMockComponentStatus(): ComponentStatus[] {
    return [
      { 
        name: 'FKS_AI', 
        connected: Math.random() > 0.1, 
        version: 'v2.1.0', 
        lastUpdate: new Date(Date.now() - Math.random() * 300000).toLocaleString(),
        healthScore: Math.floor(Math.random() * 20) + 80
      },
      { 
        name: 'FKS_AO', 
        connected: Math.random() > 0.05, 
        version: 'v2.1.0', 
        lastUpdate: new Date(Date.now() - Math.random() * 180000).toLocaleString(),
        healthScore: Math.floor(Math.random() * 25) + 75
      },
      { 
        name: 'FKS_Dashboard', 
        connected: true, 
        version: 'v2.1.0', 
        lastUpdate: new Date(Date.now() - Math.random() * 60000).toLocaleString(),
        healthScore: 95
      },
      { 
        name: 'FKS_Strategy', 
        connected: Math.random() > 0.3, 
        version: 'v2.1.0', 
        lastUpdate: new Date(Date.now() - Math.random() * 600000).toLocaleString(),
        healthScore: Math.floor(Math.random() * 30) + 70
      },
      { 
        name: 'Python Bridge', 
        connected: Math.random() > 0.2, 
        version: 'v1.0.0', 
        lastUpdate: new Date(Date.now() - Math.random() * 300000).toLocaleString(),
        healthScore: Math.floor(Math.random() * 20) + 80
      },
    ];
  }

  // WebSocket Setup for Real-time Updates
  private setupHealthMonitoring() {
    // Set up periodic health checks
    setInterval(async () => {
      const health = await this.getSystemHealth();
      this.notifySubscribers('systemHealth', health);
    }, 30000); // Every 30 seconds
  }

  private setupMarketDataStream() {
    // Set up periodic market data updates
    setInterval(async () => {
      const marketData = await this.getMarketData();
      this.notifySubscribers('marketData', marketData);
      
      const tradingMetrics = await this.getTradingMetrics();
      this.notifySubscribers('tradingMetrics', tradingMetrics);
      
      const componentStatus = await this.getComponentStatus();
      this.notifySubscribers('componentStatus', componentStatus);
    }, 5000); // Every 5 seconds
  }

  // Subscription Management
  subscribe<T = unknown>(event: string, callback: (data: T) => void) {
    if (!this.subscribers.has(event)) {
      this.subscribers.set(event, new Set());
    }
    this.subscribers.get(event)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.subscribers.get(event)?.delete(callback);
    };
  }

  private notifySubscribers(event: string, data: unknown) {
    const callbacks = this.subscribers.get(event);
    if (!callbacks) return;
    callbacks.forEach(callback => {
      try {
        callback(data);
      } catch (err) {
        // Swallow to prevent one bad subscriber from breaking others
        console.warn('[RealTimeDataService] subscriber callback error', err);
      }
    });
  }

  // Cleanup
  disconnect() {
    this.wsConnections.forEach(ws => ws.close());
    this.wsConnections.clear();
    this.subscribers.clear();
  }
}

export const realTimeDataService = new RealTimeDataService();
