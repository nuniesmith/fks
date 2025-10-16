import React, { createContext, useContext } from 'react';

import { useServiceMonitoring, serviceEndpoints } from '../../hooks/useServiceMonitoring';

import type { ServiceStatus, SystemHealth} from '../../hooks/useServiceMonitoring';

interface ServiceHealthContextValue {
  services: ServiceStatus[];
  systemHealth: SystemHealth;
  isLoading: boolean;
  refresh: () => void;
  registry: typeof serviceEndpoints;
}

const ServiceHealthContext = createContext<ServiceHealthContextValue | undefined>(undefined);

export const ServiceHealthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { services, systemHealth, isLoading, refreshServices } = useServiceMonitoring();
  return (
    <ServiceHealthContext.Provider value={{ services, systemHealth, isLoading, refresh: refreshServices, registry: serviceEndpoints }}>
      {children}
    </ServiceHealthContext.Provider>
  );
};

export const useServiceHealth = () => {
  const ctx = useContext(ServiceHealthContext);
  if (!ctx) throw new Error('useServiceHealth must be used within ServiceHealthProvider');
  return ctx;
};

export const useSingleService = (id: string) => {
  const { services } = useServiceHealth();
  return services.find(s => s.id === id);
};
