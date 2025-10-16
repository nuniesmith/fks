import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import OrderManagement from '../OrderManagement';

// Mock realtime hook to avoid actual websocket usage
vi.mock('@shared/hooks/useRealtime', () => ({
  useRealtime: () => ({ subscribe: () => () => {} })
}));

describe('OrderManagement', () => {
  test('renders initial orders and adds a new one', () => {
    render(<OrderManagement />);
    const countEl = screen.getByTestId('order-count');
    const initial = parseInt(countEl.textContent!.split('total')[0].split('/')[1].trim(), 10);
    fireEvent.click(screen.getByTestId('add-order'));
    const after = parseInt(screen.getByTestId('order-count').textContent!.split('total')[0].split('/')[1].trim(), 10);
    expect(after).toBe(initial + 1);
  });

  test('can transition order statuses (work -> cancel)', () => {
    render(<OrderManagement />);
    // Find a NEW order row
    const newRow = Array.from(document.querySelectorAll('tr[data-order-id]')).find(r => r.querySelector('[data-status]')?.getAttribute('data-status') === 'NEW');
    expect(newRow).toBeTruthy();
    const id = newRow!.getAttribute('data-order-id')!;
    const workBtn = screen.getByTestId(`work-${id}`);
    fireEvent.click(workBtn);
    const workingRow = document.querySelector(`tr[data-order-id='${id}'] [data-status='WORKING']`);
    expect(workingRow).toBeTruthy();
    const cancelBtn = screen.getByTestId(`cancel-${id}`);
    fireEvent.click(cancelBtn);
    const cancelled = document.querySelector(`tr[data-order-id='${id}'] [data-status='CANCELLED']`);
    expect(cancelled).toBeTruthy();
  });
});
