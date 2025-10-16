// MasterMonitorApi.ts
// Client for interacting with the central fks_master monitor (read-only + basic actions)

export interface AggregateHealthSummary {
  overallStatus: 'healthy' | 'degraded' | 'critical';
  totalServices: number; healthyServices: number; warningServices: number; errorServices: number; offlineServices: number;
  lastUpdate: string;
  services: Array<{
    id: string; name: string; status: 'healthy' | 'warning' | 'error' | 'offline'; rawStatus?: string;
    lastCheck?: string; responseTimeMs?: number; critical?: boolean;
  }>;
}

export interface ComposeResult {
  action: string;
  services: string[];
  success: boolean;
  status_code?: number;
  stdout: string;
  stderr: string;
}

export class MasterMonitorApi {
  private base: string;
  private apiKey?: string;

  constructor(baseUrl?: string, apiKey?: string) {
    const envBase = (import.meta as any).env?.VITE_FKS_MONITOR_URL as string | undefined;
    this.base = (baseUrl || envBase || '').replace(/\/$/, '');
    this.apiKey = apiKey || (typeof localStorage !== 'undefined' ? localStorage.getItem('fks.monitor.apiKey') || undefined : undefined);
  }

  isConfigured() { return !!this.base; }

  getApiKey() { return this.apiKey; }

  setApiKey(key: string | undefined) {
    this.apiKey = key && key.trim() ? key.trim() : undefined;
    try {
      if (this.apiKey) localStorage.setItem('fks.monitor.apiKey', this.apiKey);
      else localStorage.removeItem('fks.monitor.apiKey');
    } catch { /* ignore storage errors */ }
  }

  private headers(extra?: Record<string,string>) {
    const h: Record<string,string> = { 'Accept': 'application/json' };
    if (this.apiKey) h['x-api-key'] = this.apiKey;
    return { ...h, ...(extra||{}) };
  }

  async getAggregate(): Promise<AggregateHealthSummary> {
    const resp = await fetch(`${this.base}/health/aggregate`, { headers: this.headers() });
    if (!resp.ok) throw new Error(`aggregate http ${resp.status}`);
    return resp.json();
  }

  async listServices(): Promise<AggregateHealthSummary['services']> {
    // Prefer aggregate (single call) but allow fallback to /api/services
    try { return (await this.getAggregate()).services; } catch {}
    const resp = await fetch(`${this.base}/api/services`, { headers: this.headers() });
    if (!resp.ok) throw new Error(`services http ${resp.status}`);
    return resp.json();
  }

  async restartService(id: string): Promise<{ success: boolean; message: string; timestamp: string; service_id: string; }>{
    const resp = await fetch(`${this.base}/api/services/${id}/restart`, { method: 'POST', headers: this.headers({ 'Content-Type': 'application/json' }) });
    if (!resp.ok) {
      try { return await resp.json(); } catch { throw new Error(`restart http ${resp.status}`); }
    }
    return resp.json();
  }

  async compose(action: string, services: string[] = [], opts: { detach?: boolean; tail?: number; dryRun?: boolean } = {}): Promise<ComposeResult> {
    const body = { action, services, file: 'docker-compose.yml', project: undefined, detach: !!opts.detach, tail: opts.tail, dry_run: opts.dryRun };
    const resp = await fetch(`${this.base}/api/compose`, { method: 'POST', headers: this.headers({ 'Content-Type': 'application/json' }), body: JSON.stringify(body) });
    if (!resp.ok) {
      let err: any = {}; try { err = await resp.json(); } catch {}
      throw new Error(err.stderr || err.error || `compose http ${resp.status}`);
    }
    return resp.json();
  }
}

export const masterMonitorApi = new MasterMonitorApi();
