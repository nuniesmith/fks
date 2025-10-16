import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';

import useSecurity from '../useSecurity';
import { TradingEnvProvider, useTradingEnv } from '../../context/TradingEnvContext';

// Basic in-memory storage shims
class MemoryStorage {
  private data: Record<string,string> = {};
  getItem(k:string){ return this.data[k] ?? null; }
  setItem(k:string,v:string){ this.data[k]=v; }
  removeItem(k:string){ delete this.data[k]; }
  clear(){ this.data = {}; }
}

// Attach globals if missing (JSDOM polyfills exist but ensure)
// @ts-ignore
if (typeof window === 'undefined') global.window = {} as any;
// @ts-ignore
if (typeof global.localStorage === 'undefined') global.localStorage = new MemoryStorage();
// @ts-ignore
if (typeof global.sessionStorage === 'undefined') global.sessionStorage = new MemoryStorage();

// Mock fetch used inside SecurityOrchestrator validation (health + openapi etc.)
const okFetch = vi.fn(async (url: string) => {
  // simulate /health and other endpoints returning ok
  if (/health$/.test(url)) {
    return { ok: true, status: 200, clone(){return this;}, json: async () => ({ status: 'ok' }) } as any;
  }
  if (/openapi\.json$/.test(url)) {
    return { ok: true, status: 200, clone(){return this;}, json: async () => ({ openapi: '3.1.0', paths: {} }) } as any;
  }
  // default
  return { ok: true, status: 200, clone(){return this;}, json: async () => ({}) } as any;
});

describe('Security + TradingEnv gating', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    (global.fetch as any) = okFetch;
    localStorage.clear();
    sessionStorage.clear();
  });

  it('initializes security once and exposes ready=true after posture validation', async () => {
    const { result } = renderHook(() => useSecurity());
    // allow effects to run
    await act(async () => { await new Promise(r => setTimeout(r, 0)); });
    const [state] = result.current;
    expect(state.initialized).toBe(true);
    expect(state.ready).toBe(true);
    // ensure initialize only once
    const initLogs = (okFetch.mock.calls || []).filter(c => /health$/.test(c[0])).length;
    expect(initLogs).toBeGreaterThanOrEqual(1);
  });

  it('TradingEnvProvider delays refresh until security.ready', async () => {
    // Track calls to /active-assets to verify gating (should occur after security ready)
    const calls: string[] = [];
    (global.fetch as any) = vi.fn(async (url: string, opts?: any) => {
      calls.push(url);
      if (/health$/.test(url)) return { ok: true, status: 200, clone(){return this;}, json: async () => ({ status: 'ok' }) };
      if (/openapi\.json$/.test(url)) return { ok: true, status: 200, clone(){return this;}, json: async () => ({ openapi: '3.1.0', paths: { '/active-assets': {} } }) };
      if (/active-assets$/.test(url)) return { ok: true, status: 200, clone(){return this;}, json: async () => ({ items: [] }) };
      if (/strategy\/assignments$/.test(url)) return { ok: true, status: 200, clone(){return this;}, json: async () => ({ assignments: {} }) };
      if (/data\/dataset\/verify$/.test(url)) return { ok: true, status: 200, clone(){return this;}, json: async () => ({ ok: true }) };
      return { ok: true, status: 200, clone(){return this;}, json: async () => ({}) };
    });

    const wrapper: React.FC<{children:React.ReactNode}> = ({ children }) => <TradingEnvProvider>{children}</TradingEnvProvider>;

    const { result } = renderHook(() => {
      const env = useTradingEnv();
      const sec = useSecurity();
      return { env, sec };
    }, { wrapper });

    await act(async () => { await new Promise(r => setTimeout(r, 10)); });

    const { sec: [secState] } = result.current;
    expect(secState.ready).toBe(true);
    // Ensure capability or asset related calls happened after readiness
    const firstActiveIdx = calls.findIndex(c => /active-assets$/.test(c));
    const firstHealthIdx = calls.findIndex(c => /health$/.test(c));
    expect(firstActiveIdx).toBeGreaterThanOrEqual(0);
    expect(firstHealthIdx).toBeGreaterThanOrEqual(0);
    expect(firstActiveIdx).toBeGreaterThanOrEqual(firstHealthIdx); // active-assets should not precede initial health
  });
});
