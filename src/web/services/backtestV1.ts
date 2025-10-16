import api from './apiClient';

// Types for v1 backtest lifecycle
export interface V1BacktestDataConfig {
  source: string;
  symbols: string[];
  start_date: string; // ISO date YYYY-MM-DD
  end_date: string;   // ISO date YYYY-MM-DD
  interval?: string;  // e.g., "1d"
}

export interface V1BacktestStrategyConfig {
  type: string;
  params?: Record<string, any>;
}

export interface V1BacktestRiskConfig {
  risk_per_trade?: number;
  max_daily_loss_pct?: number;
  max_position_size_pct?: number;
  sizing_mode?: 'fixed' | 'atr' | 'volatility' | string;
  atr_period?: number;
  atr_mult?: number;
}

export interface V1BacktestCreateConfig {
  name: string;
  description?: string;
  initial_capital?: number;
  commission?: number;
  slippage?: number;
  data: V1BacktestDataConfig;
  strategy: V1BacktestStrategyConfig;
  risk?: V1BacktestRiskConfig;
}

export interface V1BacktestCreateResponse {
  backtest_id: string;
  status: string;
  message: string;
  url?: string;
}

export interface V1BacktestStatus {
  backtest_id: string;
  name: string;
  status: 'initialized' | 'loading_data' | 'preparing_strategy' | 'running' | 'analyzing' | 'completed' | 'error' | 'canceling' | 'cancelled';
  progress: number; // 0-100
  message: string;
  created_at: string;
  updated_at: string;
  estimated_completion?: string | null;
}

export interface V1BacktestResultsResponse {
  backtest_id: string;
  name: string;
  description?: string;
  summary: Record<string, any>;
  metrics: Record<string, any>;
  charts?: any[];
  trades?: any[];
  trades_count?: number;
  trades_truncated?: boolean;
}

export async function getBacktestListV1(): Promise<V1BacktestStatus[]> {
  const res = await api.get<V1BacktestStatus[]>(`/v1/backtest/list`);
  return res.data;
}

export async function createBacktestV1(config: V1BacktestCreateConfig): Promise<V1BacktestCreateResponse> {
  const res = await api.post<V1BacktestCreateResponse>('/v1/backtest/create', config);
  return res.data;
}

export async function getBacktestStatusV1(backtestId: string): Promise<V1BacktestStatus> {
  const res = await api.get<V1BacktestStatus>(`/v1/backtest/${encodeURIComponent(backtestId)}/status`);
  return res.data;
}

export async function getBacktestResultsV1(backtestId: string, includeTrades = false, maxTrades = 1000): Promise<V1BacktestResultsResponse> {
  const res = await api.get<V1BacktestResultsResponse>(`/v1/backtest/${encodeURIComponent(backtestId)}/results`, {
    params: { include_trades: includeTrades, max_trades: maxTrades },
  });
  return res.data;
}

export async function cancelBacktestV1(backtestId: string): Promise<{ backtest_id: string; status: string; message: string }> {
  const res = await api.post<{ backtest_id: string; status: string; message: string }>(`/v1/backtest/${encodeURIComponent(backtestId)}/cancel`, {});
  return res.data;
}

// Helper to map v1 results into simple metrics used by the UI
export function mapV1ToSimpleMetrics(results: V1BacktestResultsResponse): { winRate: number; totalReturn: number; maxDrawdown: number; sharpeRatio: number } {
  const s = results.summary || {};
  const m = results.metrics || {};

  // Try a variety of likely keys in summary and metrics
  const getNum = (obj: any, keys: string[], fallback: number) => {
    for (const k of keys) {
      if (obj && obj[k] != null && !isNaN(Number(obj[k]))) return Number(obj[k]);
    }
    return fallback;
  };

  const winRate = getNum(m, ['win_rate', 'winRate', 'winning_rate', 'wins_pct'], getNum(s, ['win_rate', 'winRate'], 0));
  const totalReturn = getNum(s, ['total_return', 'totalReturn', 'return', 'strategy_return'], getNum(m, ['total_return', 'totalReturn'], 0));
  const maxDrawdown = getNum(m, ['max_drawdown', 'maxDrawdown', 'mdd'], getNum(s, ['max_drawdown', 'maxDrawdown'], 0));
  const sharpeRatio = getNum(m, ['sharpe_ratio', 'sharpe', 'sharpeRatio'], getNum(s, ['sharpe_ratio', 'sharpe'], 0));

  return {
    winRate: winRate,
    totalReturn: totalReturn,
    maxDrawdown: maxDrawdown,
    sharpeRatio: sharpeRatio,
  };
}
