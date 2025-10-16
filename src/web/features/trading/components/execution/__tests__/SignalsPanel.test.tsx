import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import SignalsPanel from '../SignalsPanel';

vi.mock('@shared/hooks/useRealtime', () => ({
  useRealtime: () => ({ subscribe: () => () => {} })
}));

describe('SignalsPanel', () => {
  test('renders initial signals and adds demo', () => {
    render(<SignalsPanel />);
    const initialCount = parseInt(screen.getByTestId('signals-count').textContent!.split(' ')[0], 10);
    fireEvent.click(screen.getByTestId('add-signal'));
    const after = parseInt(screen.getByTestId('signals-count').textContent!.split(' ')[0], 10);
    expect(after).toBe(initialCount + 1);
  });

  test('filters signals by kind', () => {
    render(<SignalsPanel />);
    const select = screen.getByTestId('signals-filter') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'ENTRY' } });
    // Ensure list only contains ENTRY labels
    const rows = screen.getByTestId('signals-list').querySelectorAll('[data-signal-id]');
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach(r => {
      const kind = r.querySelector('span')!.textContent;
      expect(kind).toBe('ENTRY');
    });
  });
});
