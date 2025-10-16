// Minimal mock backtest service to enable end-to-end UI flow in dev
// Later this can be replaced with real API calls (REST/WS)

import api from './apiClient';
import { config } from './config';

export type StrategyLanguage = 'python' | 'javascript' | 'pinescript';

export interface BacktestInput {
  code: string;
  language: StrategyLanguage;
  parameters: Record<string, any>;
  asset?: string;
  exchange?: string;
  reducedParams?: boolean;
}

export interface BacktestResult {
  winRate: number; // percent 0-100
  totalReturn: number; // percent +/-
  maxDrawdown: number; // percent negative value expected
  sharpeRatio: number;
  startedAt: string;
  finishedAt: string;
}

// Simple deterministic hash for stable pseudo-random results per code string
function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function prng(seed: number) {
  let a = seed || 1;
  return () => {
    // xorshift32
    a ^= a << 13;
    a ^= a >>> 17;
    a ^= a << 5;
    return ((a >>> 0) % 10000) / 10000; // [0,1)
  };
}

export async function runBacktest(input: BacktestInput, signal?: AbortSignal): Promise<BacktestResult> {
  // If real API is enabled, call it; else fall back to mock
  if (!config.mockServices) {
    const res = await api.post<BacktestResult>('/backtests', input, { signal: signal as any });
    return res.data;
  }

  const startedAt = new Date().toISOString();
  const seed = hashString(
    input.code + JSON.stringify(input.parameters) + input.language + (input.asset || '') + (input.exchange || '') + String(!!input.reducedParams)
  );
  const rnd = prng(seed || 42);

  // Simulate work and allow cancellation
  const wait = (ms: number) => new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => resolve(), ms);
    if (signal) {
      const onAbort = () => {
        clearTimeout(t);
        signal.removeEventListener('abort', onAbort);
        reject(new DOMException('Aborted', 'AbortError'));
      };
      signal.addEventListener('abort', onAbort);
    }
  });

  // Simulate 600-1200ms backtest time
  await wait(600 + Math.floor(rnd() * 600));

  // Generate plausible metrics
  const winRate = 50 + Math.round(rnd() * 30 * 10) / 10; // 50.0 - 80.0
  const totalReturn = Math.round(((rnd() - 0.2) * 40) * 10) / 10; // -8.0 to +16.0 approx
  const maxDrawdown = -Math.round((5 + rnd() * 15) * 10) / 10; // -5.0% to -20.0%
  let sharpeRatio = Math.round((0.8 + rnd() * 2.0) * 100) / 100; // 0.8 - 2.8
  if (input.reducedParams) {
    // Slightly favor stability when reduced params is on
    sharpeRatio = Math.round((sharpeRatio + 0.2) * 100) / 100;
  }

  const finishedAt = new Date().toISOString();

  return { winRate, totalReturn, maxDrawdown, sharpeRatio, startedAt, finishedAt };
}
