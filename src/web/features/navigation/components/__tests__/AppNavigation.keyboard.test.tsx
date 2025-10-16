import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import AppNavigation from '../../components/AppNavigation';
import type { AppSection } from '../../../../types/layout';

vi.mock('../../../../context/UserContext', () => ({ useUser: () => ({ isAuthenticated: true, user: { email: 'k@test' }, logout: vi.fn() }) }));
vi.mock('../../../../context/SecurityContext', () => ({ useSecurityContext: () => ({ logout: vi.fn() }) }));
vi.mock('../../../../context/MilestoneContext', () => ({ useMilestones: () => ({ userProgress: { totalXP: 500 } }) }));
vi.mock('../../../../context/TradingEnvContext', () => ({ useTradingEnv: () => ({ focus: 'simulation', setFocus: vi.fn(), readiness: { ok: true } }) }));

const sections: AppSection[] = [
  { id: 'home', title: 'Home', description: '', icon: '🏠', path: '/', category: 'overview', environment: 'both', isActive: true },
  { id: 'strategy', title: 'Strategy', description: '', icon: '🧠', path: '/strategy', category: 'strategy', environment: 'both', isActive: true },
  { id: 'trading', title: 'Trading', description: '', icon: '📈', path: '/trading', category: 'trading', environment: 'both', isActive: true }
];

describe('AppNavigation keyboard navigation (feature-flag)', () => {
  it('moves focus with arrow keys when enabled', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AppNavigation sections={sections} isDevelopment={false} enableKeyboardNav />
      </MemoryRouter>
    );
    const menubar = screen.getByLabelText('Primary top level');
    menubar.focus();
    await user.keyboard('{ArrowRight}');
    // First item focused
    const links = screen.getAllByRole('link');
    expect(document.activeElement).toBe(links.find(l => l.textContent?.includes('Home')));
    await user.keyboard('{ArrowRight}');
    expect(document.activeElement).toBe(links.find(l => l.textContent?.includes('Strategy')));
  });
});
