import { useCallback, useEffect, useRef, useState } from 'react';

import { serviceEndpoints } from './useServiceMonitoring';

export interface EndpointTestResult {
  id: string; // service id
  timestamp: string;
  duration: number; // ms
  ok: boolean;
  statusCode?: number;
  size?: number;
  error?: string;
}

export const useServiceDiagnostics = (serviceId: string) => {
  const endpoint = serviceEndpoints.find(e => e.id === serviceId);
  const storageKey = `fks_service_tests_${serviceId}`;
  const [results, setResults] = useState<EndpointTestResult[]>([]);
  const loadingRef = useRef(false);

  // hydrate
  useEffect(() => {
    try { const raw = localStorage.getItem(storageKey); if (raw) { const parsed = JSON.parse(raw); if (Array.isArray(parsed)) setResults(parsed); } } catch {}
  }, [storageKey]);

  // persist
  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(results.slice(-100))); } catch {}
  }, [results, storageKey]);

  const runTest = useCallback(async () => {
    if (!endpoint || loadingRef.current) return;
    loadingRef.current = true;
    const start = performance.now();
    const record: EndpointTestResult = { id: serviceId, timestamp: new Date().toISOString(), duration: 0, ok: false };
    try {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 8000);
      const resp = await fetch(endpoint.url, { signal: controller.signal, mode: 'cors' }).catch(e => { throw e; });
      clearTimeout(t);
      const blob = await resp.blob().catch(() => new Blob());
      record.statusCode = resp.status;
      record.ok = resp.ok;
      record.size = blob.size;
    } catch (e: any) {
      record.error = e?.message || String(e);
    } finally {
      record.duration = Math.round(performance.now() - start);
      setResults(prev => [...prev.slice(-99), record]);
      loadingRef.current = false;
    }
  }, [endpoint, serviceId]);

  const clear = () => setResults([]);

  const average = results.length ? results.reduce((a, b) => a + b.duration, 0) / results.length : 0;
  const last = results[results.length - 1];
  const last5 = results.slice(-5);
  const last5Avg = last5.length ? last5.reduce((a, b) => a + b.duration, 0) / last5.length : 0;
  const prev5 = results.slice(-10, -5);
  const prev5Avg = prev5.length ? prev5.reduce((a, b) => a + b.duration, 0) / prev5.length : 0;
  const trendDelta5 = last5Avg && prev5Avg ? last5Avg - prev5Avg : 0;

  return { endpoint, results, runTest, clear, average, last, last5Avg, prev5Avg, trendDelta5 };
};
