import '@testing-library/jest-dom'
import { vi, beforeEach } from 'vitest'

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as any

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
} as any

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// In-memory localStorage/sessionStorage implementations (stateful across calls in a test)
function createMemoryStorage() {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((k: string) => (k in store ? store[k] : null)),
    setItem: vi.fn((k: string, v: string) => { store[k] = String(v) }),
    removeItem: vi.fn((k: string) => { delete store[k] }),
    clear: vi.fn(() => { store = {} }),
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
    get length() { return Object.keys(store).length }
  } as unknown as Storage
}
global.localStorage = createMemoryStorage()
global.sessionStorage = createMemoryStorage()

// Mock console methods for cleaner test output
const consoleMock = {
  warn: vi.fn(),
  error: vi.fn(),
  log: vi.fn(),
}
global.console = { ...console, ...consoleMock }

// Reset all mocks before each test
beforeEach(() => {
  vi.clearAllMocks()
})

// Global mock for lightweight-charts (so individual tests need not redefine)
vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addSeries: (_kind: string, _opts: any) => ({ setData: () => {}, update: () => {} }),
    applyOptions: () => {},
    timeScale: () => ({ fitContent: () => {} }),
    remove: () => {}
  })
}))
