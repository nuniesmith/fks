interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
  category: 'render' | 'network' | 'memory' | 'security' | 'database';
  metadata?: Record<string, any>;
}

interface SecurityMetric {
  type: 'authentication' | 'authorization' | 'encryption' | 'vpn' | 'audit';
  event: string;
  success: boolean;
  duration: number;
  userId?: string;
  timestamp: number;
  details?: Record<string, any>;
}

interface ComponentPerformance {
  componentName: string;
  renderTime: number;
  updateCount: number;
  lastRender: number;
  avgRenderTime: number;
  props: Record<string, any>;
}

interface NetworkMetric {
  url: string;
  method: string;
  status: number;
  duration: number;
  size: number;
  timestamp: number;
  cached: boolean;
  secured: boolean; // Indicates if request went through Tailscale
}

export class PerformanceMonitor {
  private static instance: PerformanceMonitor;
  private metrics: PerformanceMetric[] = [];
  private securityMetrics: SecurityMetric[] = [];
  private componentMetrics: Map<string, ComponentPerformance> = new Map();
  private networkMetrics: NetworkMetric[] = [];
  private observers: PerformanceObserver[] = [];
  private isMonitoring = false;
  private reportingInterval: NodeJS.Timeout | null = null;

  private constructor() {
    this.initializeObservers();
  }

  static getInstance(): PerformanceMonitor {
    if (!PerformanceMonitor.instance) {
      PerformanceMonitor.instance = new PerformanceMonitor();
    }
    return PerformanceMonitor.instance;
  }

  /**
   * Start performance monitoring
   */
  startMonitoring(): void {
    if (this.isMonitoring) return;

    this.isMonitoring = true;
    this.setupPerformanceObservers();
    this.startNetworkMonitoring();
    this.setupReporting();
    console.log('Performance monitoring started');
  }

  /**
   * Stop performance monitoring
   */
  stopMonitoring(): void {
    if (!this.isMonitoring) return;

    this.isMonitoring = false;
    this.observers.forEach(observer => observer.disconnect());
    this.observers = [];
    
    if (this.reportingInterval) {
      clearInterval(this.reportingInterval);
      this.reportingInterval = null;
    }
    
    console.log('Performance monitoring stopped');
  }

  /**
   * Record a custom performance metric
   */
  recordMetric(name: string, value: number, category: PerformanceMetric['category'], metadata?: Record<string, any>): void {
    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      category,
      metadata
    };

    this.metrics.push(metric);
    this.trimMetrics();
  }

  /**
   * Record security-related performance metrics
   */
  recordSecurityMetric(metric: Omit<SecurityMetric, 'timestamp'>): void {
    const securityMetric: SecurityMetric = {
      ...metric,
      timestamp: Date.now()
    };

    this.securityMetrics.push(securityMetric);
    this.trimSecurityMetrics();
  }

  /**
   * Measure and record component render performance
   */
  measureComponentRender<T extends Record<string, any>>(
    componentName: string,
    renderFunction: () => T,
    props: Record<string, any> = {}
  ): T {
    const startTime = performance.now();
    const result = renderFunction();
    const renderTime = performance.now() - startTime;

    this.updateComponentMetrics(componentName, renderTime, props);
    
    return result;
  }

  /**
   * Measure async operations with automatic security validation
   */
  async measureAsyncOperation<T>(
    operationName: string,
    operation: () => Promise<T>,
    validateSecurity: boolean = true
  ): Promise<T> {
    const startTime = performance.now();
    let success = false;
    let result: T;

    try {
      if (validateSecurity) {
        await this.validateSecureConnection();
      }

      result = await operation();
      success = true;
      
      return result;
    } catch (error) {
      success = false;
      throw error;
    } finally {
      const duration = performance.now() - startTime;
      
      this.recordMetric(operationName, duration, 'network', {
        success,
        secured: validateSecurity
      });

      if (validateSecurity) {
        this.recordSecurityMetric({
          type: 'encryption',
          event: operationName,
          success,
          duration
        });
      }
    }
  }

  /**
   * Monitor network requests automatically
   */
  private startNetworkMonitoring(): void {
    const originalFetch = window.fetch;
    if ((window as any)._fksFetchWrapped) return;
    (window as any)._fksFetchWrapped = true;
    let consecutive401 = 0;

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = typeof input === 'string' ? input : input.toString();
      const method = init?.method || 'GET';
      const startTime = performance.now();
      let localInit = init || {};
      const noisyPattern = /\/api\/(openapi\.json|active-assets|strategy\/assignments|data\/dataset\/verify)(\b|\/)/;

      // Helper: determine if we currently consider auth established (light heuristic)
      const authEstablished = (() => {
        try {
          const user = localStorage.getItem('auth_user');
          const tokens = localStorage.getItem('auth_tokens');
          if (!tokens) return false;
          // If tokens present but no user object yet, treat as not fully established (common on cold load)
          if (tokens && !user) return false;
          return true;
        } catch { return false; }
      })();

      // Backoff key for noisy unauthenticated endpoints to avoid repeated 401 spam
      const backoffKey = 'fks.noisy.backoff.global';
      try {
        if (noisyPattern.test(url)) {
          const until = parseInt(sessionStorage.getItem(backoffKey) || '0', 10);
          if (Date.now() < until) {
            try {
              const key = 'fks.suppressed.noauth.count';
              const cur = parseInt(sessionStorage.getItem(key) || '0', 10) + 1;
              sessionStorage.setItem(key, String(cur));
              try {
                const mapKey = 'fks.suppressed.map';
                const rawMap = sessionStorage.getItem(mapKey);
                const parsedMap = rawMap ? JSON.parse(rawMap) : {};
                parsedMap[url] = (parsedMap[url] || 0) + 1;
                sessionStorage.setItem(mapKey, JSON.stringify(parsedMap));
              } catch { /* ignore */ }
              window.dispatchEvent(new CustomEvent('auth:suppressedRequest', { detail: { url, count: cur, reason: 'backoff' } }));
            } catch {}
            const backoffPref = localStorage.getItem('fks.suppression.statusCode');
            const backoff204 = backoffPref === '204' || (import.meta as any).env?.VITE_SUPPRESSION_NOERROR === 'true';
            if (backoff204) {
              return new Response(null, { status: 204, statusText: 'Backoff Suppressed' });
            }
            return new Response('suppressed (backoff)', { status: 401, statusText: 'Backoff Suppressed' }); // (kept 401 here intentionally; earlier section already adapts based on preference)
          }
        }
      } catch { /* ignore */ }

      // Determine suppression response strategy (default 401, optional 204 via config/env)
      const suppressionResponseInfo = (() => {
        try {
          const envNoError = (import.meta as any).env?.VITE_SUPPRESSION_NOERROR === 'true';
          const lsPref = localStorage.getItem('fks.suppression.statusCode');
          if (envNoError || lsPref === '204') return { code: 204, text: 'Suppressed' } as const;
        } catch { /* ignore */ }
        return { code: 401, text: 'Unauth Suppressed' } as const;
      })();

      // Short-circuit known chatty endpoints if unauthenticated to prevent 401 floods
      try {
        const hasToken = !!localStorage.getItem('auth_tokens');
        if (!hasToken) {
          if (noisyPattern.test(url)) {
            // Record suppression count in sessionStorage
            try {
              const key = 'fks.suppressed.noauth.count';
              const cur = parseInt(sessionStorage.getItem(key) || '0', 10) + 1;
              sessionStorage.setItem(key, String(cur));
              try {
                const mapKey = 'fks.suppressed.map';
                const rawMap = sessionStorage.getItem(mapKey);
                const parsedMap = rawMap ? JSON.parse(rawMap) : {};
                parsedMap[url] = (parsedMap[url] || 0) + 1;
                sessionStorage.setItem(mapKey, JSON.stringify(parsedMap));
              } catch { /* ignore */ }
              window.dispatchEvent(new CustomEvent('auth:suppressedRequest', { detail: { url, count: cur, status: suppressionResponseInfo.code } }));
            } catch { /* ignore */ }
            if (suppressionResponseInfo.code === 204) {
              return new Response(null, { status: 204, statusText: suppressionResponseInfo.text });
            }
            return new Response('unauthenticated suppressed probe', { status: suppressionResponseInfo.code, statusText: suppressionResponseInfo.text });
          }
        }
      } catch { /* ignore */ }

      // Inject Authorization header for relative /api or /auth requests
      try {
        const raw = localStorage.getItem('auth_tokens');
        if (raw) {
          const parsed = JSON.parse(raw);
          const access = parsed.access_token;
          if (access) {
            const shouldAttach = (() => {
              // Immediate hit for relative paths
              if (url.startsWith('/api') || url.startsWith('/auth')) return true;
              // Attempt to normalize absolute or protocol-relative URLs to same-origin
              try {
                const normalized = new URL(url, window.location.origin);
                if (normalized.origin === window.location.origin && (normalized.pathname.startsWith('/api') || normalized.pathname.startsWith('/auth'))) {
                  return true;
                }
              } catch { /* ignore parse errors */ }
              return false;
            })();
            if (shouldAttach) {
              const headers = new Headers(localInit.headers || (typeof input !== 'string' && (input as Request).headers));
              if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${access}`);
              if (!headers.has('X-API-Key')) headers.set('X-API-Key', access);
              localInit = { ...localInit, headers };
              // One-time debug log for visibility when absolute URL auth injection occurs (helps confirm patch effectiveness)
              try {
                if (!sessionStorage.getItem('fks.logged.abs_url_auth_patch') && (url.startsWith('http://') || url.startsWith('https://'))) {
                  sessionStorage.setItem('fks.logged.abs_url_auth_patch', '1');
                  console.debug('[PerformanceMonitor] Attached auth headers to absolute same-origin request:', url);
                }
              } catch { /* ignore */ }
            }
          }
        }
      } catch { /* ignore */ }

      try {
        let response = await originalFetch(input, localInit);

        if (response.status === 401) {
          // Establish a temporary backoff window for noisy endpoints when auth not yet established
          try {
            if (!authEstablished && noisyPattern.test(url)) {
              const WINDOW_MS = 30_000; // 30s backoff
              sessionStorage.setItem(backoffKey, String(Date.now() + WINDOW_MS));
              window.dispatchEvent(new CustomEvent('auth:suppressedRequest', { detail: { url, reason: 'backoff-set', windowMs: WINDOW_MS } }));
            }
          } catch { /* ignore */ }
          try {
            const raw = localStorage.getItem('auth_tokens');
            if (raw) {
              const parsed = JSON.parse(raw);
              if (parsed.refresh_token) {
                const alreadyRetried = (localInit as any).__retried401;
                // Only attempt refresh if original request had Authorization header (avoid noise for public endpoints)
                const originalAuth = (localInit.headers instanceof Headers ? localInit.headers.get('Authorization') : undefined) || undefined;
                const isAuthMeOrRefresh = /\/auth\/(me|refresh)\b/.test(url);
                if (!originalAuth || isAuthMeOrRefresh) {
                  // Do not attempt refresh for /auth/me or /auth/refresh endpoints or when no original auth header.
                  consecutive401++;
                } else if (!alreadyRetried) {
                  const authBase = (import.meta as any).env?.VITE_RUST_AUTH_URL || '/auth';
                  const refreshResp = await originalFetch(`${authBase.replace(/\/$/, '')}/refresh`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: parsed.refresh_token })
                  }).catch(() => null);
                  if (refreshResp && refreshResp.ok) {
                    const data = await refreshResp.json().catch(() => ({}));
                    if (data.access_token) {
                      const merged = { ...parsed, ...data, obtained_at: Date.now() };
                      localStorage.setItem('auth_tokens', JSON.stringify(merged));
                      const headers = new Headers(localInit.headers || (typeof input !== 'string' && (input as Request).headers));
                      headers.set('Authorization', `Bearer ${data.access_token}`);
                      headers.set('X-API-Key', data.access_token);
                      response = await originalFetch(input, { ...localInit, headers, __retried401: true } as any);
                      consecutive401 = 0;
                    } else {
                      consecutive401++;
                    }
                  } else {
                    consecutive401++;
                  }
                }
              }
            }
          } catch { consecutive401++; }
        } else {
          consecutive401 = 0;
        }

        if (consecutive401 >= 3) {
          window.dispatchEvent(new CustomEvent('auth:excessive401', { detail: { url } }));
          // After 5 consecutive 401s, clear tokens proactively to break loops
          if (consecutive401 >= 5) {
            try { localStorage.removeItem('auth_tokens'); localStorage.removeItem('auth_user'); localStorage.setItem('auth_last_error', 'cleared after consecutive 401s'); } catch {}
            window.dispatchEvent(new CustomEvent('auth:tokensCleared', { detail: { reason: 'consecutive401', count: consecutive401 } }));
          }
        }

        const duration = performance.now() - startTime;
        const secured = this.isSecuredRequest(url, response);
        const networkMetric: NetworkMetric = {
          url,
          method,
          status: response.status,
          duration,
          size: parseInt(response.headers.get('content-length') || '0'),
          timestamp: Date.now(),
          cached: response.headers.get('cache-control') !== null,
          secured
        };
        this.networkMetrics.push(networkMetric);
        this.trimNetworkMetrics();

        if (!this.isInternalRequest(url)) {
          this.recordSecurityMetric({
            type: 'encryption',
            event: 'external_request',
            success: response.ok,
            duration,
            details: { url, method, secured }
          });
        }

        if (response.status === 404 && /\/active-assets(\b|\/)/.test(url)) {
          try {
            const key = 'fks.logged.active_assets_network_404';
            if (typeof sessionStorage === 'undefined' || !sessionStorage.getItem(key)) {
              console.warn('[PerformanceMonitor] 404 for active-assets endpoint (network layer). Further 404s suppressed.');
              if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(key, '1');
            }
          } catch {}
        }
        return response;
      } catch (error: any) {
        const duration = performance.now() - startTime;
        this.recordSecurityMetric({
          type: 'encryption',
          event: 'network_error',
          success: false,
          duration,
          details: { url, method, error: error.message }
        });
        throw error;
      }
    };
  }

  /**
   * Setup performance observers for browser APIs
   */
  private setupPerformanceObservers(): void {
    if (typeof PerformanceObserver === 'undefined') return;

    // Navigation timing
    const navObserver = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        if (entry.entryType === 'navigation') {
          this.recordMetric('page_load', entry.duration, 'render', {
            type: 'navigation',
            entry: entry.toJSON()
          });
        }
      });
    });

    // Resource timing
    const resourceObserver = new PerformanceObserver((list) => {
      list.getEntries().forEach((entry) => {
        if (entry.entryType === 'resource') {
          this.recordMetric('resource_load', entry.duration, 'network', {
            name: entry.name,
            type: (entry as PerformanceResourceTiming).initiatorType,
            size: (entry as PerformanceResourceTiming).transferSize
          });
        }
      });
    });

    // Memory usage (if supported)
    if ('memory' in performance) {
      const memoryObserver = setInterval(() => {
        const memory = (performance as any).memory;
        this.recordMetric('memory_usage', memory.usedJSHeapSize, 'memory', {
          total: memory.totalJSHeapSize,
          limit: memory.jsHeapSizeLimit
        });
      }, 5000);

      // Store interval for cleanup
      this.observers.push({
        disconnect: () => clearInterval(memoryObserver)
      } as PerformanceObserver);
    }

    try {
      navObserver.observe({ entryTypes: ['navigation'] });
      resourceObserver.observe({ entryTypes: ['resource'] });
      
      this.observers.push(navObserver, resourceObserver);
    } catch (error) {
      console.warn('Performance observers not fully supported:', error);
    }
  }

  /**
   * Initialize core observers
   */
  private initializeObservers(): void {
    // Setup mutation observer for DOM changes
    if (typeof MutationObserver !== 'undefined') {
      const mutationObserver = new MutationObserver((mutations) => {
        const changeCount = mutations.length;
        this.recordMetric('dom_mutations', changeCount, 'render', {
          timestamp: Date.now()
        });
      });

      // Will be configured when monitoring starts
      this.observers.push(mutationObserver as any);
    }
  }

  /**
   * Update component performance metrics
   */
  private updateComponentMetrics(componentName: string, renderTime: number, props: Record<string, any>): void {
    const existing = this.componentMetrics.get(componentName);
    
    if (existing) {
      existing.updateCount++;
      existing.lastRender = Date.now();
      existing.avgRenderTime = (existing.avgRenderTime * (existing.updateCount - 1) + renderTime) / existing.updateCount;
      existing.props = { ...existing.props, ...props };
    } else {
      this.componentMetrics.set(componentName, {
        componentName,
        renderTime,
        updateCount: 1,
        lastRender: Date.now(),
        avgRenderTime: renderTime,
        props
      });
    }
  }

  /**
   * Validate secure connection through Tailscale
   */
  private async validateSecureConnection(): Promise<void> {
    // This would check if the current connection is through Tailscale
    // For now, we'll do a simple check
    try {
      const response = await fetch('/api/security/validate-connection');
      if (!response.ok) {
        throw new Error('Insecure connection detected');
      }
    } catch (error) {
      this.recordSecurityMetric({
        type: 'vpn',
        event: 'validation_failed',
        success: false,
        duration: 0,
        details: { error: error.message }
      });
      throw error;
    }
  }

  /**
   * Check if request is secured through Tailscale
   */
  private isSecuredRequest(url: string, response: Response): boolean {
    // Check for Tailscale indicators
    return url.includes('.ts.net') || 
           url.includes('100.') || 
           response.headers.get('x-tailscale-secured') === 'true';
  }

  /**
   * Check if request is internal to the application
   */
  private isInternalRequest(url: string): boolean {
    return url.startsWith('/') || 
           url.includes(window.location.hostname) ||
           url.includes('localhost') ||
           url.includes('127.0.0.1');
  }

  /**
   * Setup periodic reporting
   */
  private setupReporting(): void {
    this.reportingInterval = setInterval(() => {
      this.generatePerformanceReport();
    }, 60000); // Report every minute
  }

  /**
   * Generate comprehensive performance report
   */
  generatePerformanceReport(): {
    summary: any;
    metrics: PerformanceMetric[];
    security: SecurityMetric[];
    components: ComponentPerformance[];
    network: NetworkMetric[];
  } {
    const now = Date.now();
    const lastHour = now - (60 * 60 * 1000);

    const recentMetrics = this.metrics.filter(m => m.timestamp > lastHour);
    const recentSecurity = this.securityMetrics.filter(m => m.timestamp > lastHour);
    const recentNetwork = this.networkMetrics.filter(m => m.timestamp > lastHour);

    const summary = {
      timeframe: '1 hour',
      totalMetrics: recentMetrics.length,
      avgRenderTime: this.calculateAverage(recentMetrics.filter(m => m.category === 'render'), 'value'),
      avgNetworkTime: this.calculateAverage(recentNetwork, 'duration'),
      securityEvents: recentSecurity.length,
      securitySuccessRate: this.calculateSuccessRate(recentSecurity),
      topComponents: this.getTopComponentsByRenderTime(),
      slowestRequests: this.getSlowestRequests(recentNetwork),
      securityIssues: recentSecurity.filter(m => !m.success).length
    };

    console.log('Performance Report:', summary);

    return {
      summary,
      metrics: recentMetrics,
      security: recentSecurity,
      components: Array.from(this.componentMetrics.values()),
      network: recentNetwork
    };
  }

  /**
   * Get performance insights and recommendations
   */
  getPerformanceInsights(): string[] {
    const insights: string[] = [];
    const components = Array.from(this.componentMetrics.values());
    const recentNetwork = this.networkMetrics.slice(-50);

    // Component performance insights
    const slowComponents = components.filter(c => c.avgRenderTime > 100);
    if (slowComponents.length > 0) {
      insights.push(`${slowComponents.length} components have slow render times (>100ms)`);
    }

    // Network performance insights
    const slowRequests = recentNetwork.filter(n => n.duration > 2000);
    if (slowRequests.length > 0) {
      insights.push(`${slowRequests.length} slow network requests detected (>2s)`);
    }

    // Security insights
    const securityIssues = this.securityMetrics.filter(m => !m.success).slice(-20);
    if (securityIssues.length > 0) {
      insights.push(`${securityIssues.length} recent security validation failures`);
    }

    // Tailscale usage insights
    const unsecuredRequests = recentNetwork.filter(n => !n.secured && !this.isInternalRequest(n.url));
    if (unsecuredRequests.length > 0) {
      insights.push(`${unsecuredRequests.length} external requests not secured through Tailscale`);
    }

    return insights;
  }

  // Utility methods
  private calculateAverage(items: any[], field: string): number {
    if (items.length === 0) return 0;
    return items.reduce((sum, item) => sum + item[field], 0) / items.length;
  }

  private calculateSuccessRate(metrics: SecurityMetric[]): number {
    if (metrics.length === 0) return 100;
    const successful = metrics.filter(m => m.success).length;
    return (successful / metrics.length) * 100;
  }

  private getTopComponentsByRenderTime(): ComponentPerformance[] {
    return Array.from(this.componentMetrics.values())
      .sort((a, b) => b.avgRenderTime - a.avgRenderTime)
      .slice(0, 5);
  }

  private getSlowestRequests(requests: NetworkMetric[]): NetworkMetric[] {
    return requests
      .sort((a, b) => b.duration - a.duration)
      .slice(0, 5);
  }

  private trimMetrics(): void {
    if (this.metrics.length > 1000) {
      this.metrics = this.metrics.slice(-500);
    }
  }

  private trimSecurityMetrics(): void {
    if (this.securityMetrics.length > 500) {
      this.securityMetrics = this.securityMetrics.slice(-250);
    }
  }

  private trimNetworkMetrics(): void {
    if (this.networkMetrics.length > 500) {
      this.networkMetrics = this.networkMetrics.slice(-250);
    }
  }

  /**
   * Export metrics for external analysis
   */
  exportMetrics(): {
    metrics: PerformanceMetric[];
    security: SecurityMetric[];
    components: ComponentPerformance[];
    network: NetworkMetric[];
    timestamp: number;
  } {
    return {
      metrics: [...this.metrics],
      security: [...this.securityMetrics],
      components: Array.from(this.componentMetrics.values()),
      network: [...this.networkMetrics],
      timestamp: Date.now()
    };
  }

  /**
   * Clear all collected metrics
   */
  clearMetrics(): void {
    this.metrics = [];
    this.securityMetrics = [];
    this.componentMetrics.clear();
    this.networkMetrics = [];
  }

  /**
   * Health check for performance monitor
   */
  healthCheck(): { status: string; details: any } {
    return {
      status: this.isMonitoring ? 'monitoring' : 'stopped',
      details: {
        metricsCount: this.metrics.length,
        securityMetricsCount: this.securityMetrics.length,
        componentCount: this.componentMetrics.size,
        networkMetricsCount: this.networkMetrics.length,
        observersActive: this.observers.length,
        reportingActive: this.reportingInterval !== null
      }
    };
  }
}

export default PerformanceMonitor;
