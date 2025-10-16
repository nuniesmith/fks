import { Home, BarChart3, TrendingUp, Brain, Briefcase, Calculator, PieChart, Settings, Code2, Database } from 'lucide-react';
import type { ComponentType } from 'react';

// Central icon map for tree-shaking clarity & single source
export const NAV_ICON_MAP: Record<string, ComponentType<any>> = {
  home: Home,
  data: Database,
  trading: TrendingUp,
  strategy: Brain,
  accounts: Briefcase,
  tax_optimization: Calculator,
  analytics: PieChart,
  settings: Settings,
  services: Code2,
  // calendar uses inline SVG in component (kept out intentionally)
};

export const getNavIcon = (id: string) => NAV_ICON_MAP[id] || BarChart3;
