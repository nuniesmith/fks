// Lightweight client for the Training Service (v1)
import { config } from './config';
import { buildAuthHeaders, authFetch } from './authToken';

export type TrainRequest = {
  data_file: string;
  timeframe?: string; // e.g. '1m', '5m', '1h', '1d'
  date_column?: string; // default 'timestamp'
  models?: string[]; // e.g. ['ARIMA','Prophet','LSTM']
  forecast_horizon?: number; // default 5
  hyperparameters?: Record<string, any> | null;
};

export type TrainStartResponse = {
  job_id: string;
  status: string;
  message: string;
};

export type TrainStatus = {
  job_id: string;
  status: string; // queued|running|completed|failed|cancelled
  progress?: number;
  start_time?: number;
  models_completed?: string[];
  message?: string;
  version?: string;
};

export type ModelsResponse = { models: Array<Record<string, any>> };
export type JobsResponse = { jobs: Array<Record<string, any>> };

const API_BASE = (config.apiBaseUrl || (import.meta as any).env?.VITE_API_URL || '/api').replace(/\/$/, '');
const TRAINING_BASE = ((import.meta as any).env?.VITE_TRAINING_URL as string | undefined)?.replace(/\/$/, '') || `${API_BASE}/v1/training`;

function getApiKey(): string | undefined {
  try {
    const authTokensRaw = typeof window !== 'undefined' ? localStorage.getItem('auth_tokens') : null;
    const access = authTokensRaw ? (JSON.parse(authTokensRaw)?.access_token as string | undefined) : undefined;
    const lsToken = typeof window !== 'undefined' ? localStorage.getItem('fks_api_token') as string | null : null;
    const envToken = (import.meta as any).env?.VITE_API_TOKEN as string | undefined;
    return access || lsToken || envToken;
  } catch {
    return undefined;
  }
}

function buildHeaders(extra?: HeadersInit): HeadersInit { return buildAuthHeaders({ 'Content-Type': 'application/json', ...(extra || {}) }) }

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${TRAINING_BASE}${path}`;
  return authFetch<T>(url, { ...init, headers: buildHeaders(init?.headers) });
}

export async function startTraining(req: TrainRequest): Promise<TrainStartResponse> {
  const body: TrainRequest = {
    data_file: req.data_file,
    timeframe: req.timeframe || '1m',
    date_column: req.date_column || 'timestamp',
    models: req.models || ['ARIMA','Prophet','LSTM'],
    forecast_horizon: req.forecast_horizon ?? 5,
    hyperparameters: req.hyperparameters ?? null,
  };
  return http<TrainStartResponse>(`/train`, { method: 'POST', body: JSON.stringify(body) });
}

export async function getTrainingStatus(jobId: string): Promise<TrainStatus> {
  return http<TrainStatus>(`/train/${encodeURIComponent(jobId)}`, { method: 'GET' });
}

export async function cancelTraining(jobId: string): Promise<{ message: string }> {
  return http<{ message: string }>(`/train/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
}

export async function listModels(): Promise<ModelsResponse> {
  return http<ModelsResponse>(`/models`, { method: 'GET' });
}

export async function listTrainingJobs(): Promise<JobsResponse> {
  return http<JobsResponse>(`/jobs`, { method: 'GET' });
}

export async function downloadResults(jobId: string): Promise<Blob> {
  const url = `${TRAINING_BASE}/train/${encodeURIComponent(jobId)}/download`;
  const res = await fetch(url, { headers: buildHeaders(), method: 'GET' });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${text}`);
  }
  return res.blob();
}
