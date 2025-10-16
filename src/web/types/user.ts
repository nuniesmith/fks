export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'user';
  avatar?: string;
  preferences: UserPreferences;
  createdAt: string;
  lastActive: string;
  status: 'active' | 'inactive' | 'suspended';
  tradingAccounts?: TradingAccount[];
  permissions: UserPermissions;
}

export interface UserPreferences {
  timezone: string;
  theme: 'dark' | 'light';
  notifications: {
    email: boolean;
    push: boolean;
    tradingAlerts: boolean;
    marketNews: boolean;
    developmentUpdates: boolean;
  };
  calendar: {
    showMarketEvents: boolean;
    showHolidays: boolean;
    showDevelopment: boolean;
    defaultView: 'day' | 'week' | 'month';
    workingHours: {
      start: string;
      end: string;
      timezone: string;
    };
  };
  trading: {
    defaultRiskPercent: number;
    preferredMarkets: string[];
    alertThresholds: {
      dailyLoss: number;
      weeklyLoss: number;
      monthlyLoss: number;
    };
  };
}

export interface UserPermissions {
  canAccessDevelopment: boolean;
  canManageUsers: boolean;
  canViewAnalytics: boolean;
  canModifySystem: boolean;
  canAccessMarketData: boolean;
  canManageCalendar: boolean;
  maxAccounts: number;
  features: {
    tradingDashboard: boolean;
    taxOptimization: boolean;
    milestoneSystem: boolean;
    calendar: boolean;
    advancedAnalytics: boolean;
  };
}

export interface TradingAccount {
  id: string;
  name: string;
  type: 'prop_firm' | 'tfsa' | 'rrsp' | 'margin' | 'cash';
  provider: string;
  balance: number;
  currency: 'CAD' | 'USD';
  status: 'active' | 'inactive' | 'pending';
  connectedAt: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  start: string;
  end: string;
  type: 'market' | 'holiday' | 'development' | 'trading' | 'news' | 'meeting';
  priority: 'low' | 'medium' | 'high' | 'critical';
  source: 'manual' | 'google_calendar' | 'market_api' | 'news_api' | 'auto_generated';
  attendees?: string[];
  location?: string;
  metadata?: {
    marketAffected?: string[];
    newsSource?: string;
    developmentPhase?: string;
    tradingImpact?: 'none' | 'low' | 'medium' | 'high';
  };
}

export interface MarketEvent {
  id: string;
  title: string;
  description: string;
  date: string;
  type: 'holiday' | 'early_close' | 'closure' | 'important_release';
  markets: string[]; // ['NYSE', 'TSX', 'FOREX', 'FUTURES']
  impact: 'none' | 'low' | 'medium' | 'high';
  source: string;
}

export interface DevelopmentTask {
  id: string;
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  estimatedHours: number;
  category: 'feature' | 'bugfix' | 'optimization' | 'research' | 'testing';
  dependencies?: string[];
  tags: string[];
  status: 'planned' | 'in_progress' | 'testing' | 'completed' | 'on_hold';
  assignedTo?: string;
  dueDate?: string;
  createdAt: string;
  updatedAt: string;
}
