import { useCallback, useEffect, useRef, useState, useMemo } from 'react';

import { usePrometheus } from '../shared/hooks/usePrometheusMetrics';

export interface ContractTestSpec {
  id: string;
  label: string;
  endpoint: string; // relative to base or absolute
  method?: string;
  expectedStatus?: number | number[]; // defaults 200
  maxLatencyMs?: number; // soft limit
  requiredKeys?: string[]; // JSON body validation
  auth?: boolean; // include credentials
  enabled?: boolean | (() => boolean);
  headers?: Record<string, string>; // custom request headers
  jsonSchema?: { [k: string]: 'string' | 'number' | 'boolean' | 'object' | 'array' | 'any' }; // shallow schema expectation
  // Optional deep schema (subset of JSON Schema) for nested validation
  jsonDeepSchema?: JSONDeepSchema;
  hardLatencyBudgetMs?: number; // if exceeded -> fail even if status ok
  retries?: number; // retry attempts on failure (network or status mismatch)
  retryDelayMs?: number; // base delay for linear backoff
  slaMs?: number; // latency SLO target for breach counting
  circuitBreaker?: { failureThreshold: number; cooldownMs: number }; // open after N consecutive failures
}

type JSONPrimitiveType = 'string' | 'number' | 'boolean' | 'object' | 'array' | 'any';
interface JSONObjectSchema { type: 'object'; properties?: Record<string, JSONDeepSchema>; required?: string[]; }
interface JSONArraySchema { type: 'array'; items?: JSONDeepSchema; }
interface JSONLeafSchema { type: Exclude<JSONPrimitiveType, 'object' | 'array'>; }
export type JSONDeepSchema = JSONObjectSchema | JSONArraySchema | JSONLeafSchema;

export interface ContractTestResult {
  id: string;
  label: string;
  status: 'pass' | 'fail' | 'error' | 'skip';
  httpStatus?: number;
  latencyMs?: number;
  message?: string;
  missingKeys?: string[];
  timestamp: number;
}

interface RunOptions { parallel?: boolean; }

export const useServiceContractTests = (serviceId: string, baseUrl: string, specs: ContractTestSpec[], hookOptions?: { onAlert?: (payload: { serviceId: string; spec: ContractTestSpec; result: ContractTestResult; reason: string; }) => void }) => {
  const [results, setResults] = useState<ContractTestResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const historyRef = useRef<Record<string, number[]>>({});
  const failureStreakRef = useRef<Record<string, { streak: number; openedAt?: number }>>({});
  let prometheus: ReturnType<typeof usePrometheus> | null = null;
  try { prometheus = usePrometheus(); } catch { /* provider not mounted */ }

  // Hydrate from localStorage (latest snapshot only)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(`fks_contract-${serviceId}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed.results)) setResults(parsed.results);
        if (parsed.history && typeof parsed.history === 'object') historyRef.current = parsed.history;
      }
    } catch {}
  }, [serviceId]);

  const runSingle = useCallback(async (spec: ContractTestSpec): Promise<ContractTestResult> => {
    const enabled = typeof spec.enabled === 'function' ? spec.enabled() : (spec.enabled ?? true);
    if (!enabled) {
      return { id: spec.id, label: spec.label, status: 'skip', timestamp: Date.now(), message: 'disabled' };
    }
    const url = spec.endpoint.startsWith('http') ? spec.endpoint : baseUrl.replace(/\/$/, '') + spec.endpoint;
    const start = performance.now();
    try {
      const controller = new AbortController();
      controllerRef.current = controller;
      const timeout = setTimeout(() => controller.abort(), (spec.maxLatencyMs || 5000) * 2);
      // Circuit breaker check
      const cbState = spec.circuitBreaker ? failureStreakRef.current[spec.id] : undefined;
      if (spec.circuitBreaker && cbState?.openedAt && Date.now() - cbState.openedAt < spec.circuitBreaker.cooldownMs) {
        clearTimeout(timeout);
        return { id: spec.id, label: spec.label, status: 'skip', message: 'circuit-open', timestamp: Date.now() };
      }
      const attempts = (spec.retries || 0) + 1;
  let resp: Response | null = null;
  let lastError: unknown;
      for (let i=0;i<attempts;i++) {
        try {
          resp = await fetch(url, { method: spec.method || 'GET', credentials: spec.auth ? 'include' : 'same-origin', signal: controller.signal, headers: spec.headers });
          if (resp) break;
        } catch (e) {
          lastError = e;
          if (i < attempts -1) {
            const base = spec.retryDelayMs ?? 100;
            const delay = base * Math.pow(2, i) + Math.random()*base*0.3; // exponential + jitter
            await new Promise(r => setTimeout(r, delay));
            continue;
          } else {
            throw e;
          }
        }
      }
      if (!resp) throw lastError || new Error('no response');
      clearTimeout(timeout);
      const latencyMs = performance.now() - start;
      const expected = spec.expectedStatus || 200;
      const accepted = Array.isArray(expected) ? expected.includes(resp.status) : resp.status === expected;
      let status: ContractTestResult['status'] = accepted ? 'pass' : 'fail';
      let message = accepted ? 'ok' : `expected ${expected} got ${resp.status}`;
      let missingKeys: string[] | undefined;
      if (status === 'pass') {
        try {
          const data: unknown = await resp.clone().json();
          if (spec.requiredKeys && spec.requiredKeys.length > 0) {
            const rec = (data && typeof data === 'object' && !Array.isArray(data)) ? data as Record<string, unknown> : {};
            missingKeys = spec.requiredKeys.filter(k => !(k in rec));
            if (missingKeys.length > 0) {
              status = 'fail';
              message = 'missing keys';
            }
          }
          if (status === 'pass' && spec.jsonSchema) {
            const schemaIssues: string[] = [];
            Object.entries(spec.jsonSchema).forEach(([k, type]) => {
              if (type === 'any') return;
              const record = data as Record<string, unknown> | undefined;
              const v = record ? (record as Record<string, unknown>)[k] : undefined;
              if (v === undefined) {
                schemaIssues.push(`${k}:missing`);
              } else {
                const actual = Array.isArray(v) ? 'array' : typeof v;
                if (actual !== type) schemaIssues.push(`${k}:expected-${type}-got-${actual}`);
              }
            });
            if (schemaIssues.length > 0) {
              status = 'fail';
              message = `schema ${schemaIssues.slice(0,3).join(',')}${schemaIssues.length>3?'…':''}`;
            }
          }
          if (status === 'pass' && spec.jsonDeepSchema) {
            const deepIssues: string[] = [];
            const validateDeep = (schema: JSONDeepSchema, value: unknown, path: string, depth: number) => {
              if (depth > 6) return; // safeguard
              if (!schema) return;
              if ((schema as any).type === 'any') return;
              switch (schema.type) {
                case 'object': {
                  if (value === null || Array.isArray(value) || typeof value !== 'object') {
                    deepIssues.push(`${path || 'root'}:expected-object`);
                    return;
                  }
                  const req = schema.required || [];
                  req.forEach(k => { if (!(k in (value as Record<string, unknown>))) deepIssues.push(`${path ? path + '.' : ''}${k}:missing`); });
                  if (schema.properties) {
                    Object.entries(schema.properties).forEach(([k, sub]) => {
                      validateDeep(sub, (value as Record<string, unknown>)[k], path ? `${path}.${k}` : k, depth + 1);
                    });
                  }
                  break;
                }
                case 'array': {
                  if (!Array.isArray(value)) {
                    deepIssues.push(`${path || 'root'}:expected-array`);
                    return;
                  }
                  if (schema.items) {
                    (value as unknown[]).slice(0, 10).forEach((item: unknown, idx: number) => {
                      validateDeep(schema.items!, item, `${path || 'arr'}[${idx}]`, depth + 1);
                    });
                  }
                  break;
                }
                case 'string': case 'number': case 'boolean': {
                  const actual = typeof value;
                  if (schema.type !== actual) deepIssues.push(`${path || 'value'}:expected-${schema.type}-got-${actual}`);
                  break;
                }
              }
            };
            validateDeep(spec.jsonDeepSchema, data, '', 0);
            if (deepIssues.length > 0) {
              status = 'fail';
              message = `deep-schema ${deepIssues.slice(0,3).join(',')}${deepIssues.length>3?'…':''}`;
            }
          }
        } catch (e) {
          status = 'error';
          message = 'json parse error';
        }
      }
      if (status === 'pass' && spec.hardLatencyBudgetMs && latencyMs > spec.hardLatencyBudgetMs) {
        status = 'fail';
        message = `latency budget exceeded (${latencyMs.toFixed(0)}ms>${spec.hardLatencyBudgetMs}ms)`;
      } else if (status === 'pass' && spec.maxLatencyMs && latencyMs > spec.maxLatencyMs) {
        message = `slow (${latencyMs.toFixed(0)}ms>${spec.maxLatencyMs}ms)`; // soft warning
      }
      // Update circuit breaker streaks
      if (spec.circuitBreaker) {
        const rec = failureStreakRef.current[spec.id] || { streak: 0 };
        if (status === 'fail' || status === 'error') {
          rec.streak += 1;
          if (rec.streak >= spec.circuitBreaker.failureThreshold && !rec.openedAt) {
            rec.openedAt = Date.now();
          }
        } else if (status === 'pass') {
          rec.streak = 0; rec.openedAt = undefined;
        }
        failureStreakRef.current[spec.id] = rec;
      }
      return { id: spec.id, label: spec.label, status, httpStatus: resp.status, latencyMs, message, missingKeys, timestamp: Date.now() };
    } catch (e: unknown) {
      const latencyMs = performance.now() - start;
      const err = e as { name?: string; message?: string } | undefined;
      return { id: spec.id, label: spec.label, status: err?.name === 'AbortError' ? 'error' : 'fail', latencyMs, message: err?.message || 'error', timestamp: Date.now() };
    }
  }, [baseUrl]);

  const runAll = useCallback(async (opts: RunOptions = {}) => {
    if (isRunning) return;
    setIsRunning(true);
    try {
      let newResults: ContractTestResult[] = [];
      if (opts.parallel) {
        newResults = await Promise.all(specs.map(runSingle));
      } else {
        for (const spec of specs) {
          const r = await runSingle(spec);
            newResults.push(r);
        }
      }
  let alerted = false;
      setResults(prev => {
        const combined = [...prev.slice(-400), ...newResults];
        // update latency history per spec id for sparklines / trending
        newResults.forEach(r => {
          if (r.latencyMs != null) {
            const arr = historyRef.current[r.id] || [];
            arr.push(r.latencyMs);
            if (arr.length > 60) arr.splice(0, arr.length - 60); // cap
            historyRef.current[r.id] = arr;
          }
          if (prometheus && r.latencyMs != null) {
            const spec = specs.find(s => s.id === r.id)!;
            prometheus.observe('fks_contract_test_latency_ms', r.latencyMs, { service: serviceId, spec: r.id, status: r.status });
            if (r.status === 'fail' || r.status === 'error') {
              prometheus.inc('fks_contract_test_failures_total', { service: serviceId, spec: r.id, status: r.status });
            }
            if (spec.slaMs) {
              prometheus.inc('fks_contract_test_sla_breaches_total', { service: serviceId, spec: r.id }, r.latencyMs > spec.slaMs ? 1 : 0);
            }
            if (r.status === 'fail' && r.message?.startsWith('deep-schema')) {
              prometheus.inc('fks_contract_test_schema_failures_total', { service: serviceId, spec: r.id, kind: 'deep' });
            } else if (r.status === 'fail' && r.message?.startsWith('schema')) {
              prometheus.inc('fks_contract_test_schema_failures_total', { service: serviceId, spec: r.id, kind: 'shallow' });
            }
          }
          if (!alerted) {
            const spec = specs.find(s => s.id === r.id)!;
            if (r.status === 'fail') {
              hookOptions?.onAlert?.({ serviceId, spec, result: r, reason: 'status-fail' });
              alerted = true;
            } else if (spec.slaMs && r.latencyMs && r.latencyMs > spec.slaMs * 1.5) { // severe breach
              hookOptions?.onAlert?.({ serviceId, spec, result: r, reason: 'sla-severe-latency' });
              alerted = true;
            }
          }
        });
        // persist lightweight snapshot
        try { localStorage.setItem(`fks_contract-${serviceId}`, JSON.stringify({ results: combined.slice(-600), history: historyRef.current })); } catch {}
        return combined;
      });
      return newResults;
    } finally {
      setIsRunning(false);
    }
  }, [isRunning, specs, runSingle]);

  const abort = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  // Auto-run once when hook mounts (deferred for paint)
  useEffect(() => {
    const t = setTimeout(() => { runAll({ parallel: true }); }, 250);
    return () => clearTimeout(t);
  }, [runAll]);

  const summary = useMemo(() => {
    const latest = specs.reduce<Record<string, ContractTestResult | undefined>>((acc, s) => {
      acc[s.id] = [...results].reverse().find(r => r.id === s.id);
      return acc;
    }, {});
    const counts = Object.values(latest).reduce((acc, r) => {
      if (!r) return acc; acc[r.status] = (acc[r.status] || 0) + 1; return acc;
    }, {} as Record<string, number>);

    const latencySamples: number[] = [];
    Object.values(historyRef.current).forEach(arr => latencySamples.push(...arr));
    latencySamples.sort((a,b)=>a-b);
    const pick = (p: number) => latencySamples.length ? latencySamples[Math.min(latencySamples.length-1, Math.floor(latencySamples.length * p))] : undefined;
    const p50 = pick(0.50);
    const p95 = pick(0.95);
    const p99 = pick(0.99);

    let slaBreaches = 0;
    let totalSlaSamples = 0;
    specs.forEach(s => {
      if (s.slaMs) {
        const arr = historyRef.current[s.id];
        if (arr) {
          totalSlaSamples += arr.length;
          slaBreaches += arr.filter(v => v > s.slaMs!).length;
        }
      }
    });
    const slaBreachRate = totalSlaSamples ? slaBreaches / totalSlaSamples : 0;
    // Circuit breaker aggregated state
    const cbStates: Record<string, { streak: number; open: boolean; openedAt?: number; remainingMs?: number }> = {};
    let openCircuits = 0;
    let maxFailureStreak = 0;
    specs.forEach(s => {
      if (!s.circuitBreaker) return;
      const rec = failureStreakRef.current[s.id];
      if (!rec) return;
      const open = !!(rec.openedAt && (Date.now() - rec.openedAt) < s.circuitBreaker.cooldownMs);
      if (open) openCircuits += 1;
      if (rec.streak > maxFailureStreak) maxFailureStreak = rec.streak;
      cbStates[s.id] = {
        streak: rec.streak,
        open,
        openedAt: rec.openedAt,
        remainingMs: open && rec.openedAt ? Math.max(0, s.circuitBreaker.cooldownMs - (Date.now() - rec.openedAt)) : undefined
      };
    });
    return { latest, counts, p50, p95, p99, slaBreaches, slaBreachRate, cbStates, openCircuits, maxFailureStreak };
  }, [results, specs]);

  // Expose circuit breaker state as Prometheus gauges
  useEffect(() => {
    if (!prometheus) return;
    try {
      prometheus.set('fks_contract_open_circuits', summary.openCircuits || 0, { service: serviceId }, 'Number of currently open contract test circuit breakers');
      if (summary.cbStates) {
        Object.entries(summary.cbStates).forEach(([specId, s]) => {
          prometheus!.set('fks_contract_circuit_open', s.open ? 1 : 0, { service: serviceId, spec: specId }, 'Circuit breaker open (1=open,0=closed)');
          prometheus!.set('fks_contract_circuit_failure_streak', s.streak, { service: serviceId, spec: specId }, 'Current consecutive failure streak for circuit breaker');
        });
      }
    } catch { /* ignore metrics errors */ }
  }, [prometheus, summary.openCircuits, summary.cbStates, serviceId]);

  return { results, runAll, abort, isRunning, summary, history: historyRef.current };
};
