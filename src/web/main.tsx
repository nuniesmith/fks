import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import './styles/global.css'
import { ErrorBoundary } from './components/ErrorBoundary'
import { NotificationProvider } from './components/Notifications'
import { MilestoneProvider } from './context/MilestoneContext'
import { SecurityProvider } from './context/SecurityContext'
import { ThemeProvider } from './components/ThemeProvider'
import { UserProvider } from './context/UserContext'
import { PrometheusMetricsProvider, usePrometheusPushGateway } from '@shared';
import { UISettingsProvider } from './context/UISettingsContext';

const EnvMetricsWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const url = (import.meta as any).env?.VITE_PUSHGATEWAY_URL;
  if (url) {
    try { usePrometheusPushGateway({ url, job: 'frontend', instance: window.location.hostname, intervalMs: 15000 }); } catch {}
  }
  return <>{children}</>;
};

// Initialize the React app
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
  {/** Small component to conditionally enable pushgateway */}
  {/** Wrapped inside provider below */}
    
    <ThemeProvider>
      <SecurityProvider enforceVPN={false} requirePasskeys={false}>
        <UserProvider>
          <MilestoneProvider>
            <NotificationProvider>
              <BrowserRouter>
                <PrometheusMetricsProvider>
                  <EnvMetricsWrapper>
                    <ErrorBoundary>
                      <UISettingsProvider>
                        <App />
                      </UISettingsProvider>
                    </ErrorBoundary>
                  </EnvMetricsWrapper>
                </PrometheusMetricsProvider>
              </BrowserRouter>
            </NotificationProvider>
          </MilestoneProvider>
        </UserProvider>
      </SecurityProvider>
    </ThemeProvider>
  </React.StrictMode>,
)

