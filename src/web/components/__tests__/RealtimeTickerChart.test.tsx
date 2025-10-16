import React from 'react';
import { describe, it, expect } from 'vitest';

import { render, screen } from '@/test/test-utils';

vi.mock('@/hooks/useRealtime', () => ({
  useRealtime: () => ({ status: 'open', subscribe: () => () => {}, unsubscribe: () => {} })
}));

import RealtimeTickerChart from '../Realtime/RealtimeTickerChart';

describe('RealtimeTickerChart', () => {
  it('renders channel label and placeholder last price', () => {
    render(<RealtimeTickerChart channel="ticks:TEST" />);
    expect(screen.getByText('WS: open')).toBeInTheDocument();
    expect(screen.getByText('TEST')).toBeInTheDocument();
    expect(screen.getByText(/waiting/i)).toBeInTheDocument();
  });
});
