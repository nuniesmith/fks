import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import StatTile from '../StatTile';
import React from 'react';

describe('StatTile', () => {
  it('renders label and value', () => {
    render(<StatTile label="Net PnL" value="$12,345" />);
    expect(screen.getByText('Net PnL')).toBeInTheDocument();
    expect(screen.getByText('$12,345')).toBeInTheDocument();
  });

  it('handles click when onClick provided', () => {
    const onClick = vi.fn();
    render(<StatTile label="Trades" value={42} onClick={onClick} />);
    screen.getByText('Trades');
    screen.getByText('42').click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
