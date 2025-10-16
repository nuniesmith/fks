import {
    BarChart3,
    Code,
    Folder,
    GitBranch,
    Monitor,
    Package,
    Settings,
    Terminal,
    TrendingUp,
    Zap
} from 'lucide-react';
import React from 'react';

import { isFeatureEnabled } from '../config/features';

interface NavigationTab {
  id: string;
  label: string;
  icon: React.ReactNode;
  description?: string;
  badge?: string | number;
}

interface ModernNavigationProps {
  activeTab: string;
  onTabChange: (tabId: string) => void;
  tabs?: NavigationTab[];
}

const defaultTabs: NavigationTab[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: <Monitor className="w-5 h-5" />,
    description: 'System overview and monitoring'
  },
  {
    id: 'trading',
    label: 'Trading',
    icon: <TrendingUp className="w-5 h-5" />,
    description: 'Live trading interface'
  },
  {
    id: 'charts',
    label: 'Charts',
    icon: <BarChart3 className="w-5 h-5" />,
    description: 'TradingView Lightweight Charts'
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: <BarChart3 className="w-5 h-5" />,
    description: 'Performance analytics'
  },
  ...(isFeatureEnabled('ninjaTrader') ? [{
    id: 'ninjatrader',
    label: 'NinjaTrader',
    icon: <Zap className="w-5 h-5" />,
    description: 'NinjaTrader integration'
  }] : []),
  {
    id: 'structure',
    label: 'Project',
    icon: <Folder className="w-5 h-5" />,
    description: 'Project structure'
  },
  {
    id: 'build',
    label: 'Build',
    icon: <Code className="w-5 h-5" />,
    description: 'Build & compile'
  },
  {
    id: 'package',
    label: 'Package',
    icon: <Package className="w-5 h-5" />,
    description: 'Package addon'
  },
  {
    id: 'logs',
    label: 'Logs',
    icon: <Terminal className="w-5 h-5" />,
    description: 'System logs'
  },
  {
    id: 'git',
    label: 'Git',
    icon: <GitBranch className="w-5 h-5" />,
    description: 'Version control'
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: <Settings className="w-5 h-5" />,
    description: 'Configuration'
  }
];

export const ModernNavigation: React.FC<ModernNavigationProps> = ({ 
  activeTab, 
  onTabChange, 
  tabs = defaultTabs 
}) => {
  return (
    <nav className="glass-card p-2 mb-8">
      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                tab-button flex items-center gap-3 px-4 py-3 rounded-xl font-semibold
                transition-all duration-300 relative group
                ${isActive 
                  ? 'bg-gradient-primary text-white shadow-lg shadow-primary-500/25 scale-105' 
                  : 'text-white/70 hover:text-white hover:bg-white/10 hover:scale-102'
                }
              `}
              title={tab.description}
            >
              {/* Icon */}
              <span className={`transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`}>
                {tab.icon}
              </span>
              
              {/* Label */}
              <span className="hidden sm:block">{tab.label}</span>
              
              {/* Badge */}
              {tab.badge && (
                <span className="bg-red-500 text-white text-xs rounded-full px-2 py-1 min-w-[1.5rem] h-6 flex items-center justify-center">
                  {tab.badge}
                </span>
              )}
              
              {/* Active indicator */}
              {isActive && (
                <div className="absolute inset-0 rounded-xl bg-gradient-primary opacity-20 animate-pulse-slow"></div>
              )}
              
              {/* Hover tooltip for mobile */}
              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-1 bg-gray-900 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none sm:hidden whitespace-nowrap z-10">
                {tab.description}
                <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
              </div>
            </button>
          );
        })}
      </div>
      
      {/* Mobile tab description */}
      <div className="sm:hidden mt-4 px-2">
        {tabs.find(tab => tab.id === activeTab)?.description && (
          <p className="text-white/70 text-sm text-center">
            {tabs.find(tab => tab.id === activeTab)?.description}
          </p>
        )}
      </div>
    </nav>
  );
};
