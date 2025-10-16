import type { RenderOptions } from '@testing-library/react';

// Import screen + waitFor from DOM package (types sometimes require explicit triple-slash or module augmentation in certain TS setups)
import { screen, waitFor } from '@testing-library/dom'
import { render } from '@testing-library/react'
import React from 'react'
// Fallback ambient declaration (harmless if real types exist)
 
declare module '@testing-library/dom' {}
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import { MilestoneProvider } from '../context/MilestoneContext'
import SecurityContext from '../context/SecurityContext'
import { TradingEnvProvider } from '../context/TradingEnvContext'
import { UserProvider } from '../context/UserContext'
import { UISettingsProvider } from '../context/UISettingsContext'

// Mock providers for testing
// Optionally wrap with real provider; for now keep a simple wrapper to avoid session side-effects.
const MockTradingEnvironmentProvider = ({ children }: { children: React.ReactNode }) => (
  <TradingEnvProvider>{children}</TradingEnvProvider>
)

const MockThemeProvider = ({ children }: { children: React.ReactNode }) => (
  <div data-testid="mock-theme-provider">{children}</div>
)

const MockNotificationProvider = ({ children }: { children: React.ReactNode }) => (
  <div data-testid="mock-notification-provider">{children}</div>
)

const MockApiProvider = ({ children }: { children: React.ReactNode }) => (
  <div data-testid="mock-api-provider">{children}</div>
)

// Minimal mock security context value
const mockSecurityValue = {
  initialized: true,
  vpnConnected: true,
  authenticated: true,
  user: { id: 'test', email: 'test@example.com', groups: ['developer'] },
  loading: false,
  error: null,
  securityLevel: 'secure' as const,
  initializeSecurity: vi.fn(),
  login: vi.fn(),
  completeLogin: vi.fn(),
  logout: vi.fn(),
  registerPasskey: vi.fn(),
  validateSecurity: vi.fn(),
  getSecurityDashboard: vi.fn(() => ({}))
}

// All the providers that wrap our app (with MemoryRouter + mocked security)
const AllTheProviders = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter initialEntries={['/']}>
    <SecurityContext.Provider value={mockSecurityValue}>
      <UserProvider>
        <MilestoneProvider>
          <MockTradingEnvironmentProvider>
            <MockThemeProvider>
              <MockNotificationProvider>
                <MockApiProvider>
                  <UISettingsProvider>
                    {children}
                  </UISettingsProvider>
                </MockApiProvider>
              </MockNotificationProvider>
            </MockThemeProvider>
          </MockTradingEnvironmentProvider>
        </MilestoneProvider>
      </UserProvider>
    </SecurityContext.Provider>
  </MemoryRouter>
)

// Custom render function with providers
const customRender = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) => render(ui, { wrapper: AllTheProviders, ...options })

// re-export everything
export * from '@testing-library/react'

// override render method
export { customRender as render, screen, waitFor }

// Mock trading environment context values
export const mockTradingEnvironment = {
  environment: 'SIMULATION' as const,
  tradingConfig: {
    mode: 'SIMULATION' as const,
    accounts: ['demo-account-1'],
    activeStrategies: ['momentum-scalp'],
    riskLimits: {
      maxDailyLoss: 1000,
      maxPositionSize: 10000,
      maxOpenPositions: 5
    },
    notifications: {
      enabled: true,
      email: false,
      push: true,
      discord: false
    }
  },
  updateEnvironment: vi.fn(),
  updateConfig: vi.fn(),
  isLive: false,
  isSimulation: true
}

// Mock API context values
export const mockApiContext = {
  baseURL: 'http://localhost:4000',
  isConnected: true,
  connectionStatus: 'connected' as const,
  lastHeartbeat: new Date().toISOString(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  request: vi.fn().mockResolvedValue({ data: {} })
}

// Common test data factories
export const createMockTradingAccount = (overrides = {}) => ({
  id: 'test-account-1',
  name: 'Test Account',
  type: 'prop' as const,
  balance: 50000,
  equity: 50235,
  enabled: true,
  environment: 'simulation' as const,
  ...overrides
})

export const createMockPosition = (overrides = {}) => ({
  symbol: 'EURUSD',
  side: 'long' as const,
  size: 1.0,
  entryPrice: 1.0950,
  currentPrice: 1.0975,
  pnl: 25.00,
  pnlPercentage: 0.23,
  accountId: 'test-account-1',
  timestamp: new Date().toISOString(),
  ...overrides
})

export const createMockStrategy = (overrides = {}) => ({
  id: 'test-strategy-1',
  name: 'Test Strategy',
  description: 'A test trading strategy',
  isActive: true,
  winRate: 68.5,
  avgReturn: 1.8,
  environment: 'simulation' as const,
  ...overrides
})
