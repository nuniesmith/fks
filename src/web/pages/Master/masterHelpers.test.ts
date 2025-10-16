import { describe, it, expect } from 'vitest';
import { mapStatus, countStatuses, deriveOverall, summarize } from './masterHelpers';

describe('masterHelpers', () => {
  it('maps various raw statuses', () => {
    expect(mapStatus('ok')).toBe('healthy');
    expect(mapStatus('WARNING')).toBe('warning');
    expect(mapStatus('critical')).toBe('error');
    expect(mapStatus('offline')).toBe('offline');
    expect(mapStatus(undefined)).toBe('offline');
  });

  it('counts statuses correctly', () => {
    const counts = countStatuses([
      { id:'a', name:'A', status:'healthy' },
      { id:'b', name:'B', status:'warning' },
      { id:'c', name:'C', status:'warning' },
      { id:'d', name:'D', status:'error' },
      { id:'e', name:'E', status:'offline' }
    ] as any);
    expect(counts).toEqual({ healthy:1, warning:2, error:1, offline:1 });
  });

  it('derives overall', () => {
    expect(deriveOverall({ healthy:5, warning:0, error:0, offline:0 })).toBe('healthy');
    expect(deriveOverall({ healthy:3, warning:1, error:0, offline:0 })).toBe('degraded');
    expect(deriveOverall({ healthy:3, warning:0, error:0, offline:2 })).toBe('degraded');
    expect(deriveOverall({ healthy:1, warning:0, error:1, offline:0 })).toBe('critical');
  });

  it('summarizes services', () => {
    const services = [
      { id:'a', name:'A', status:'healthy' },
      { id:'b', name:'B', status:'warning' }
    ] as any;
    const agg = summarize(services);
    expect(agg.totalServices).toBe(2);
    expect(agg.overallStatus).toBe('degraded');
  });
});
