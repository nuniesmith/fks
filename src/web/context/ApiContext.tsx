// context/ApiContext.tsx
import React, { createContext, useContext } from 'react';

import { config } from '../config/environment';
import { ApiService } from '../services/ApiService';

import type { ReactNode } from 'react';

interface ApiContextType {
  apiService: ApiService;
  config: typeof config;
}

const ApiContext = createContext<ApiContextType | undefined>(undefined);

interface ApiProviderProps {
  children: ReactNode;
}

export const ApiProvider: React.FC<ApiProviderProps> = ({ children }) => {
  const apiService = new ApiService(config.apiBaseUrl);

  return (
    <ApiContext.Provider value={{ apiService, config }}>
      {children}
    </ApiContext.Provider>
  );
};

export const useApi = (): ApiContextType => {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error('useApi must be used within an ApiProvider');
  }
  return context;
};