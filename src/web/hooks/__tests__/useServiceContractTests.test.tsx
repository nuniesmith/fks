import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { useServiceContractTests } from '../useServiceContractTests';

import type { ContractTestSpec } from '../useServiceContractTests';

// Lightweight fetch mock
global.fetch = vi.fn(async (url: string) => ({
  status: 200,
  ok: true,
  clone() { return this; },
  async json() { return { openapi: '3.1.0', info: {} }; }
})) as any;

describe('useServiceContractTests', () => {
  it('runs specs and returns summary', async () => {
    const specs: ContractTestSpec[] = [
      { id: 'openapi', label: 'OpenAPI', endpoint: '/openapi.json', requiredKeys: ['openapi'], expectedStatus: 200 },
      { id: 'metrics', label: 'Metrics', endpoint: '/metrics', expectedStatus: [200,404] }
    ];
    const { result } = renderHook(() => useServiceContractTests('api','http://localhost:8000', specs));
    await act(async () => { await result.current.runAll({ parallel: true }); });
    const { summary, results } = result.current;
    expect(results.length).toBeGreaterThanOrEqual(2);
    expect(Object.keys(summary.latest)).toContain('openapi');
  });

  it('invokes onAlert for status failure', async () => {
    // Mock fetch returning 500
    (global.fetch as any) = vi.fn(async () => ({ status: 500, ok: false, clone(){return this;}, async json(){ return {}; } }));
    const specs: ContractTestSpec[] = [ { id: 'fail-spec', label: 'Fail', endpoint: '/fail', expectedStatus: 200 } ];
    const onAlert = vi.fn();
    const { result } = renderHook(() => useServiceContractTests('api','http://localhost:8000', specs, { onAlert }));
    await act(async () => { await result.current.runAll({ parallel: true }); });
    expect(onAlert).toHaveBeenCalled();
    expect(onAlert.mock.calls[0][0].reason).toBe('status-fail');
  });

  it('invokes onAlert for severe SLA latency breach', async () => {
    // Simulate delayed fetch to exceed SLA (1ms *1.5)
    (global.fetch as any) = vi.fn(() => new Promise(resolve => setTimeout(() => resolve({ status: 200, ok: true, clone(){return this;}, json: async () => ({ status: 'ok' }) }), 15)));
    const specs: ContractTestSpec[] = [ { id: 'sla', label: 'SLA', endpoint: '/health', expectedStatus: 200, slaMs: 1 } ];
    const onAlert = vi.fn();
    const { result } = renderHook(() => useServiceContractTests('api','http://localhost:8000', specs, { onAlert }));
    await act(async () => { await result.current.runAll({ parallel: true }); });
    expect(onAlert).toHaveBeenCalled();
    const reasons = onAlert.mock.calls.map((c:any)=>c[0].reason);
    expect(reasons).toContain('sla-severe-latency');
  });

  it('fails when deep schema validation fails', async () => {
    (global.fetch as any) = vi.fn(async () => ({ status: 200, ok: true, clone(){return this;}, json: async () => ({ meta: { version: 1 } }) }));
    const specs: ContractTestSpec[] = [ {
      id: 'deep-schema',
      label: 'Deep Schema',
      endpoint: '/meta',
      expectedStatus: 200,
      jsonDeepSchema: {
        type: 'object',
        required: ['meta'],
        properties: {
          meta: {
            type: 'object',
            required: ['version'],
            properties: {
              version: { type: 'string' }
            }
          }
        }
      }
    } ];
    const { result } = renderHook(() => useServiceContractTests('api','http://localhost:8000', specs));
    await act(async () => { await result.current.runAll({ parallel: false }); });
    const res = result.current.results.find(r => r.id === 'deep-schema');
    expect(res?.status).toBe('fail');
    expect(res?.message?.startsWith('deep-schema')).toBe(true);
  });

  it('opens circuit breaker after consecutive failures and skips subsequent run', async () => {
    let call = 0;
    (global.fetch as any) = vi.fn(async () => { call++; return { status: 500, ok: false, clone(){return this;}, json: async () => ({}) }; });
    const specs: ContractTestSpec[] = [ { id: 'cb', label: 'CB', endpoint: '/cb', expectedStatus: 200, circuitBreaker: { failureThreshold: 2, cooldownMs: 5000 } } ];
    const { result } = renderHook(() => useServiceContractTests('api','http://localhost:8000', specs));
    // First run -> failure increments streak
    await act(async () => { await result.current.runAll({ parallel: false }); });
    // Second run -> failure opens circuit
    await act(async () => { await result.current.runAll({ parallel: false }); });
    // Third run should skip due to open circuit (no additional fetch call beyond 2?)
    await act(async () => { await result.current.runAll({ parallel: false }); });
    const latest = result.current.results.filter(r => r.id==='cb').slice(-1)[0];
    expect(latest.status === 'skip' && latest.message === 'circuit-open').toBe(true);
  });

  it('retries failed attempts up to retries count then succeeds', async () => {
    let call = 0;
    (global.fetch as any) = vi.fn(async () => {
      call++;
      if (call < 3) throw new Error('net fail');
      return { status: 200, ok: true, clone(){return this;}, json: async () => ({ ok: true }) };
    });
    const specs: ContractTestSpec[] = [ { id: 'retry', label: 'Retry', endpoint: '/retry', expectedStatus: 200, retries: 2, retryDelayMs: 1 } ];
    const { result } = renderHook(() => useServiceContractTests('api','http://localhost:8000', specs));
    await act(async () => { await result.current.runAll({ parallel: false }); });
    const latest = result.current.results.filter(r => r.id==='retry').slice(-1)[0];
    expect(call).toBe(3);
    expect(latest.status).toBe('pass');
  });
});
