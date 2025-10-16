import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '../../test/test-utils';
import { UISettingsProvider, useUISettings } from '../UISettingsContext';

const Consumer = () => {
  const { density, toggleDensity } = useUISettings();
  return (
    <div>
      <span data-testid="density">{density}</span>
      <button onClick={toggleDensity}>toggle</button>
    </div>
  );
};

describe('UISettingsContext', () => {
  beforeEach(() => { try { localStorage.removeItem('fks.ui.density'); } catch {} });
  it('toggles density via button', () => {
    render(<UISettingsProvider><Consumer /></UISettingsProvider>);
    const span = screen.getByTestId('density');
    expect(span.textContent).toBe('comfortable');
    fireEvent.click(screen.getByText('toggle'));
    expect(span.textContent).toBe('compact');
  });

  it('toggles density via keyboard shortcut Shift+D', () => {
    render(<UISettingsProvider><Consumer /></UISettingsProvider>);
    const span = screen.getByTestId('density');
    expect(span.textContent).toBe('comfortable');
    fireEvent.keyDown(window, { key: 'D', shiftKey: true });
    expect(span.textContent).toBe('compact');
  });
});
