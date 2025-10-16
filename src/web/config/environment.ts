// config/environment.ts
interface EnvironmentConfig {
  apiBaseUrl: string;
  isDevelopment: boolean;
  apiTimeout: number;
  useMockData: boolean;
  services: {
    api: string;
    database: string;
    cache: string;
    data: string;
    ninja: string;
    web: string;
  grafana?: string;
  prometheus?: string;
  };
}

const getEnvironmentConfig = (): EnvironmentConfig => {
  const isDev = import.meta.env.DEV || import.meta.env.MODE === 'development';
  const useMock = import.meta.env.VITE_USE_MOCK_DATA === 'true' || isDev;
  
  // Development URLs (localhost)
  const devServices = {
    api: 'http://localhost:8000',
    database: 'http://localhost:5432',
    cache: 'http://localhost:6379',
    data: 'http://localhost:9001',
    ninja: 'http://localhost:7496',
  web: 'http://localhost:3001',
  grafana: 'http://localhost:3001', // exposed from compose as 3001 -> 3000
  prometheus: 'http://localhost:9090',
  };
  
  // Production URLs
  const prodServices = {
    api: 'https://api.fkstrading.xyz',
    database: 'https://db.fkstrading.xyz',
    cache: 'https://cache.fkstrading.xyz',
    data: 'https://data.fkstrading.xyz',
    ninja: 'https://ninja.fkstrading.xyz',
  web: 'https://app.fkstrading.xyz',
  grafana: 'https://grafana.fkstrading.xyz',
  prometheus: 'https://prometheus.fkstrading.xyz',
  };

  return {
    apiBaseUrl: import.meta.env.VITE_API_URL || (isDev ? devServices.api : prodServices.api),
    isDevelopment: isDev,
    apiTimeout: parseInt(import.meta.env.VITE_API_TIMEOUT || '30000'),
    useMockData: useMock,
    services: isDev ? devServices : prodServices,
  };
};

export const config = getEnvironmentConfig();