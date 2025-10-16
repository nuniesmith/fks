import React, { createContext, useContext } from 'react';

interface PrometheusContextValue {
  metrics: Record<string, number | string>;
  refresh: () => void;
  loading: boolean;
}

const PrometheusContext = createContext<PrometheusContextValue>({ metrics: {}, refresh: () => {}, loading: false });

export const PrometheusMetricsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const value: PrometheusContextValue = { metrics: {}, refresh: () => {}, loading: false };
  return (
    <PrometheusContext.Provider value={value}>
      {children}
    </PrometheusContext.Provider>
  );
};

export const usePrometheus = () => useContext(PrometheusContext);
