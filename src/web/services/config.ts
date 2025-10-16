export interface AppConfig {
  envName: string;
  apiBaseUrl: string;
  wsBaseUrl?: string;
  defaultTradingMode: 'SIMULATION' | 'LIVE';
  mockServices: boolean;
  defaultRealtimeChannels?: string[];
}

export const config: AppConfig = {
  envName: import.meta.env.VITE_ENV_NAME || (import.meta.env.PROD ? 'production' : 'development'),
  // Prefer an explicit API base URL; otherwise, if only VITE_API_URL is provided (host/root), append '/api' to match FastAPI prefix
  apiBaseUrl: (() => {
    const override = typeof window !== 'undefined' && localStorage.getItem('fks_api_base_url');
    if (override) return override;
    const explicitBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
    if (explicitBase) return explicitBase;
    const hostOnly = import.meta.env.VITE_API_URL as string | undefined;
    if (hostOnly) return `${hostOnly.replace(/\/$/, '')}/api`;
    return '/api';
  })(),
  wsBaseUrl: (typeof window !== 'undefined' && localStorage.getItem('fks_ws_base_url')) || import.meta.env.VITE_WS_BASE_URL,
  defaultTradingMode: (import.meta.env.VITE_DEFAULT_TRADING_MODE as 'SIMULATION' | 'LIVE') || 'SIMULATION',
  mockServices: (typeof window !== 'undefined' && localStorage.getItem('fks_mock_services') === 'true') || (import.meta.env.VITE_MOCK_SERVICES as any) === 'true' || import.meta.env.VITE_USE_MOCK_DATA === 'true',
  defaultRealtimeChannels:
    (typeof window !== 'undefined' && localStorage.getItem('fks_rt_channels')?.split(',').map(s => s.trim()).filter(Boolean)) ||
    ((import.meta.env.VITE_DEFAULT_RT_CHANNELS as string | undefined)?.split(',').map(s => s.trim()).filter(Boolean)) ||
    ['heartbeat','ticks:AAPL']
};
