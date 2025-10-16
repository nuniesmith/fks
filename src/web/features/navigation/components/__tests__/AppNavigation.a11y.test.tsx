import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import React from 'react';
import AppNavigation from '../../components/AppNavigation';
import type { AppSection } from '../../../../types/layout';

// Mock heavy context hooks used in navigation
vi.mock('../../../../context/UserContext', () => ({ useUser: () => ({ isAuthenticated: true, user: { email: 'user@test.dev' }, logout: vi.fn() }) }));
vi.mock('../../../../context/SecurityContext', () => ({ useSecurityContext: () => ({ logout: vi.fn() }) }));
vi.mock('../../../../context/MilestoneContext', () => ({ useMilestones: () => ({ userProgress: { totalXP: 1234 } }) }));
vi.mock('../../../../context/TradingEnvContext', () => ({ useTradingEnv: () => ({ focus: 'simulation', setFocus: vi.fn(), readiness: { ok: false } }) }));

const sections: AppSection[] = [
  { id: 'home', title: 'Home', description: '', icon: '🏠', path: '/', category: 'overview', environment: 'both', isActive: true },
  { id: 'strategy', title: 'Strategy', description: '', icon: '🧠', path: '/strategy', category: 'strategy', environment: 'both', isActive: true },
  { id: 'trading', title: 'Trading', description: '', icon: '📈', path: '/trading', category: 'trading', environment: 'both', isActive: true }
];

describe('AppNavigation accessibility', () => {
  it('sets aria-current on active route', () => {
    render(
      <MemoryRouter initialEntries={['/strategy']}>
        <AppNavigation sections={sections} isDevelopment={false} />
      </MemoryRouter>
    );
    const activeLink = screen.getByRole('link', { name: /strategy/i });
    expect(activeLink).toHaveAttribute('aria-current', 'page');
  });
});

