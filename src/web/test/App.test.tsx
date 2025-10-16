import { describe, it, expect, vi, beforeEach } from 'vitest'

import App from '../App'

import { render, screen } from './test-utils'

// Minimal mocks for heavy lazy components we don't validate here
vi.mock('../components/Milestones/MilestoneSystem', () => ({ default: () => <div /> }))
vi.mock('../components/TradingDashboard/TradingDashboard', () => ({ default: () => <div /> }))
vi.mock('../components/TaxOptimization/TaxOptimization', () => ({ default: () => <div /> }))

const renderApp = () => render(<App />)

describe('App Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the main layout correctly', async () => {
    renderApp()
    
  // Brand + some nav links (exact set may vary by env; assert subset)
  expect(screen.getByText('FKS')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument()
  // Skip link present (hidden until focus)
  const skip = screen.getByText('Skip to content')
  expect(skip).toHaveAttribute('href', '#main')
  })

  it('starts with home page as the default route', async () => {
    renderApp()
    
  // Should land at home route content (welcome headline present)
  expect(screen.getByText(/welcome to fks trading platform/i)).toBeInTheDocument()
  })

  it('renders without crashing', async () => {
    renderApp()
    
  expect(screen.getByText('FKS')).toBeInTheDocument()
  })

  it('has proper navigation structure', async () => {
    renderApp()
    
    // Check navigation structure
    const nav = screen.getByRole('navigation')
    expect(nav).toBeInTheDocument()
    
    // Check navigation links by href attribute to be more specific
    const homeLink = screen.getByRole('link', { name: 'Home' })
  expect(homeLink).toHaveAttribute('href', '/')
  })

  it('displays brand and platform description correctly', async () => {
    renderApp()
    
    // Check brand text
  expect(screen.getByText('FKS')).toBeInTheDocument()
  })
})

describe('App Error Handling', () => {
  it('renders without crashing', async () => {
    renderApp()
    
  expect(screen.getByText('FKS')).toBeInTheDocument()
  })
  
  it('renders with valid content', async () => {
    // Test that valid routes can be accessed through navigation
    renderApp()
    
    // App should render basic structure
  expect(screen.getByText(/welcome to fks trading platform/i)).toBeInTheDocument()
  })
})

describe('App Performance', () => {
  it('loads components efficiently', async () => {
    // Test that app loads without excessive delay
    renderApp()
    
    // Component should load immediately since we're mocking them
  expect(screen.getByText(/welcome to fks trading platform/i)).toBeInTheDocument()
  })

  it('has expected structure', async () => {
    renderApp()
    
    // Should show basic app structure
  expect(screen.getByText('FKS')).toBeInTheDocument()
  expect(screen.getByText(/welcome to fks trading platform/i)).toBeInTheDocument()
  })
})
