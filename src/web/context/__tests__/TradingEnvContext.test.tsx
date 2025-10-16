import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Use unified test-utils re-export to avoid mixing DOM vs react entrypoints
import { TradingEnvProvider, useTradingEnv } from '../TradingEnvContext'
import { render, act, screen, waitFor } from '../../test/test-utils'

// Helper component to surface context values in the DOM for assertions
const Probe: React.FC = () => {
  const ctx = useTradingEnv()
  return (
    <div>
      <div data-testid="focus">{ctx.focus}</div>
      <div data-testid="environment">{ctx.environment}</div>
      <div data-testid="sim-status">{ctx.sim.status}</div>
      <div data-testid="live-status">{ctx.live.status}</div>
      <div data-testid="sim-strategies">{ctx.sim.strategiesAssigned}</div>
      <div data-testid="active-assets">{ctx.sim.activeAssets}</div>
      <div data-testid="readiness-ok">{String(ctx.readiness.ok)}</div>
      <button onClick={() => ctx.start('simulation')} data-testid="start-sim" />
      <button onClick={() => ctx.pause('simulation')} data-testid="pause-sim" />
      <button onClick={() => ctx.stop('simulation')} data-testid="stop-sim" />
      <button onClick={() => ctx.updateEnvironment('LIVE')} data-testid="go-live" />
    </div>
  )
}

const Wrapper: React.FC = () => (
  <TradingEnvProvider>
    <Probe />
  </TradingEnvProvider>
)

// Mock fetch responses used by provider readiness logic
function installFetchMock() {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()
    if (url.includes('/data/dataset/verify')) {
      return new Response(JSON.stringify({ ok: true }), { status: 200 }) as any
    }
    if (url.includes('/active-assets')) {
      return new Response(JSON.stringify({ items: [{ id: 1 }, { id: 2 }] }), { status: 200 }) as any
    }
    if (url.includes('/strategy/assignments')) {
      return new Response(JSON.stringify({ assignments: { '1': ['s1'], '2': ['s2', 's3'] } }), { status: 200 }) as any
    }
    if (url.includes('/trading/sessions/start')) {
      return new Response('{}', { status: 200 }) as any
    }
    if (url.includes('/trading/sessions/pause')) {
      return new Response('{}', { status: 200 }) as any
    }
    if (url.includes('/trading/sessions/stop')) {
      return new Response('{}', { status: 200 }) as any
    }
    return new Response('{}', { status: 200 }) as any
  }) as any
}

describe('TradingEnvContext (unified)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    installFetchMock()
  })

  it('initializes readiness and counts strategies/assets', async () => {
  render(<Wrapper />)
  await waitFor(() => expect(screen.getByTestId('readiness-ok').textContent).toBe('true'))
  expect(screen.getByTestId('sim-strategies').textContent).toBe('3')
  expect(screen.getByTestId('active-assets').textContent).toBe('2')
  })

  it('handles start -> pause -> stop lifecycle for simulation', async () => {
  render(<Wrapper />)
    // Start
  await act(async () => { screen.getByTestId('start-sim').click() })
  await waitFor(() => expect(screen.getByTestId('sim-status').textContent).toBe('active'))
    // Pause
  await act(async () => { screen.getByTestId('pause-sim').click() })
  expect(screen.getByTestId('sim-status').textContent).toBe('paused')
    // Stop
  await act(async () => { screen.getByTestId('stop-sim').click() })
  expect(screen.getByTestId('sim-status').textContent).toBe('stopped')
  })

  it('updates environment (legacy mode) and syncs focus', async () => {
  render(<Wrapper />)
  expect(screen.getByTestId('environment').textContent).toBe('SIMULATION')
  expect(screen.getByTestId('focus').textContent).toBe('simulation')
  act(() => { screen.getByTestId('go-live').click() })
  await waitFor(() => expect(screen.getByTestId('environment').textContent).toBe('LIVE'))
  expect(screen.getByTestId('focus').textContent).toBe('live')
  })
})
