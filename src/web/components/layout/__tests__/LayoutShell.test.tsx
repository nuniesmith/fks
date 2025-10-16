import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import LayoutShell from '../LayoutShell';
import React from 'react';

describe('LayoutShell', () => {
  it('renders children', () => {
    render(<LayoutShell><div>Inner Content</div></LayoutShell>);
    expect(screen.getByText('Inner Content')).toBeInTheDocument();
  });

  it('optionally renders sidebar', () => {
    render(<LayoutShell sidebar={<div>Sidebar Area</div>}><div>Main</div></LayoutShell>);
    // Sidebar hidden on small screens due to lg:block; still present in DOM but with hidden class.
    expect(screen.getByText('Sidebar Area')).toBeInTheDocument();
    expect(screen.getByText('Main')).toBeInTheDocument();
  });
});
