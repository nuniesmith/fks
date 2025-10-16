import api from './apiClient';
import { config } from './config';

import type { StrategyLanguage } from './backtest';

export interface OptimizationInput {
  code: string;
  language: StrategyLanguage;
  parameters: Record<string, any>;
}

export interface OptimizationResult {
  parameters: Record<string, any>;
  trials: number;
  bestScore: number;
}

// Mock optimization; in production, call backend service using Optuna
export async function optimizeStrategy(input: OptimizationInput): Promise<OptimizationResult> {
  if (!config.mockServices) {
    const res = await api.post<OptimizationResult>('/optimize', input);
    return res.data;
  }
  // Deterministic suggestion: nudge numeric params
  const out: Record<string, any> = { ...input.parameters };
  Object.keys(out).forEach((k) => {
    const v = out[k];
    if (typeof v === 'number') out[k] = Number((v * 1.05).toFixed(4));
  });
  return { parameters: out, trials: 30, bestScore: Math.round(Math.random() * 100) / 10 };
}
