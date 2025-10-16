// Helper utilities for MasterDashboard (exported for testing)
import type { AggregateHealthSummary } from '../../services/MasterMonitorApi';

export type SimpleStatus = 'healthy'|'warning'|'error'|'offline';
export type OverallStatus = 'healthy'|'degraded'|'critical';

export function mapStatus(raw?: string): SimpleStatus {
  if (!raw) return 'offline';
  const r = raw.toLowerCase();
  if (['ok','up','running','ready','healthy','live','alive'].includes(r)) return 'healthy';
  if (['warn','warning','degraded','slow'].includes(r)) return 'warning';
  if (['err','error','fail','failing','critical','panic'].includes(r)) return 'error';
  if (['down','offline','stopped','unknown'].includes(r)) return 'offline';
  return 'warning';
}

export interface StatusCounts { healthy:number; warning:number; error:number; offline:number; }

export function countStatuses(services: AggregateHealthSummary['services']): StatusCounts {
  const counts: StatusCounts = { healthy:0, warning:0, error:0, offline:0 };
  services.forEach(s => { counts[s.status] = (counts as any)[s.status] + 1; });
  return counts;
}

export function deriveOverall(c: StatusCounts): OverallStatus {
  if (c.error > 0) return 'critical';
  if (c.warning > 0 || c.offline > 0) return 'degraded';
  return 'healthy';
}

export function summarize(services: AggregateHealthSummary['services']) {
  const counts = countStatuses(services);
  return {
    overallStatus: deriveOverall(counts),
    totalServices: services.length,
    healthyServices: counts.healthy,
    warningServices: counts.warning,
    errorServices: counts.error,
    offlineServices: counts.offline,
    lastUpdate: new Date().toISOString(),
    services
  } as AggregateHealthSummary;
}
