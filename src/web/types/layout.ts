// Application Layout Types for Clean Organization
export interface AppSection {
  id: string;
  title: string;
  description: string;
  icon: string;
  path: string;
  category: SectionCategory;
  environment: 'production' | 'development' | 'both';
  requiredMilestones?: string[];
  isActive: boolean;
  subSections?: AppSubSection[];
}

export type SectionCategory = 
  | 'overview'               // Home and dashboard overview
  | 'trading'                // Live trading and market analysis
  | 'strategy'               // Strategy development and testing
  | 'accounts'               // Account management and tracking
  | 'tax_optimization'       // Canadian tax planning
  | 'analytics'              // Performance analytics
  | 'settings';              // Configuration and preferences

export interface AppSubSection {
  id: string;
  title: string;
  description: string;
  icon: string;
  path: string;
  component: string;
  environment: 'production' | 'development' | 'both';
  isDeveloperTool?: boolean;
}

export const APP_SECTIONS: AppSection[] = [
  // Overview Section
  {
    id: 'home',
    title: 'Home',
    description: 'Clean overview of your trading progress and milestones',
    icon: '🏠',
    path: '/',
    category: 'overview',
    environment: 'both',
    isActive: true
  },
  // Data Section (promoted out of Services)
  {
    id: 'data',
    title: 'Data',
    description: 'Fetch and explore market data',
    icon: '🗄️',
    path: '/services/data',
    category: 'analytics',
    environment: 'both',
    isActive: true
  },
  // Move former Home options to Analytics for cleaner top-nav
  {
    id: 'overview_milestones',
    title: 'Milestones',
    description: 'Track progress toward your Canadian trading goals',
    icon: '🎯',
    path: '/milestones',
    category: 'analytics',
    environment: 'both',
  isActive: false
  },

  // Strategy Section (moved ahead of Trading per requested order)
  {
    id: 'strategy',
    title: 'Strategy',
    description: 'Generate, validate, and deploy trading strategies',
    icon: '🧠',
    path: '/strategy',
    category: 'strategy',
    environment: 'both',
    isActive: true,
    subSections: [
      {
        id: 'backtesting',
        title: 'Backtesting',
        description: 'Test strategies against historical data',
        icon: '⏮️',
        path: '/strategy/backtesting',
        component: 'StrategyBacktesting',
        environment: 'both'
      },
      {
        id: 'forward_testing',
        title: 'Forward Testing',
        description: 'Test strategies in staging environment',
        icon: '⏭️',
  path: '/strategy/forward-test',
        component: 'ForwardTesting',
        environment: 'both'
      },
      {
        id: 'strategy_builder',
        title: 'Strategy Builder',
        description: 'Create and configure trading strategies',
        icon: '🏗️',
        path: '/strategy/builder',
        component: 'StrategyBuilder',
        environment: 'both'
      },
      {
        id: 'monte_carlo',
        title: 'Monte Carlo',
        description: 'Simulate equity paths and drawdown risk',
        icon: '🎲',
  path: '/strategy/monte-carlo',
        component: 'MonteCarlo',
        environment: 'both'
      },
      {
        id: 'strategy_validation',
        title: 'Strategy Validation',
        description: 'Validate strategies for live deployment',
        icon: '✅',
        path: '/strategy/validation',
        component: 'StrategyValidation',
        environment: 'production'
      },
      {
        id: 'strategy_debug',
        title: 'Strategy Debug Console',
        description: 'Advanced debugging and performance analysis',
        icon: '🐛',
        path: '/strategy/debug',
        component: 'StrategyDebugConsole',
        environment: 'development',
        isDeveloperTool: true
      }
    ]
  },

  // Trading Section (now after Strategy)
  {
    id: 'trading',
    title: 'Trading',
    description: 'Live trading interface with market analysis',
    icon: '📈',
    path: '/trading',
    category: 'trading',
    environment: 'both',
    isActive: true,
    subSections: [
      {
        id: 'live_trading',
        title: 'Live Trading',
        description: 'Real-time trading interface',
        icon: '⚡',
        path: '/trading/live',
        component: 'LiveTradingInterface',
        environment: 'production'
      },
      {
        id: 'market_analysis',
        title: 'Market Analysis',
        description: 'Technical and fundamental analysis tools',
        icon: '🔍',
        path: '/trading/analysis',
        component: 'MarketAnalysis',
        environment: 'both'
      },
      {
        id: 'paper_trading',
        title: 'Paper Trading',
        description: 'Practice trading with virtual funds',
        icon: '📝',
        path: '/trading/paper',
        component: 'PaperTrading',
        environment: 'both'
      },
      {
        id: 'trading_debug',
        title: 'Trading Debug Tools',
        description: 'Developer tools for trading system debugging',
    icon: '🧪',
        path: '/trading/debug',
        component: 'TradingDebugTools',
        environment: 'development',
        isDeveloperTool: true
      }
    ]
  },

  

  // Accounts Section
  {
    id: 'accounts',
    title: 'Accounts',
    description: 'Manage all trading accounts and track performance',
    icon: '💼',
    path: '/accounts',
    category: 'accounts',
    environment: 'both',
    isActive: true,
    subSections: [
      {
        id: 'prop_firms',
        title: 'Prop Firm Accounts',
        description: 'Manage prop firm accounts and payouts',
        icon: '🏢',
        path: '/accounts/prop-firms',
        component: 'PropFirmManager',
        environment: 'both'
      },
      {
        id: 'personal_accounts',
        title: 'Personal Accounts',
        description: 'TFSA, RRSP, and personal trading accounts',
        icon: '👤',
        path: '/accounts/personal',
        component: 'PersonalAccountManager',
        environment: 'both'
      },
      {
        id: 'account_analytics',
        title: 'Account Analytics',
        description: 'Performance analysis across all accounts',
        icon: '📊',
        path: '/accounts/analytics',
        component: 'AccountAnalytics',
        environment: 'both'
      },
      {
        id: 'profit_tracking',
        title: 'Profit Tracking',
        description: 'Track profits from all accounts including closed ones',
        icon: '💰',
        path: '/accounts/profits',
        component: 'ProfitTracker',
        environment: 'both'
      }
    ]
  },

  // Tax Optimization Section
  {
    id: 'tax_optimization',
    title: 'Taxes',
    description: 'Optimize your trading for Canadian tax efficiency',
    icon: '🇨🇦',
    path: '/tax',
    category: 'tax_optimization',
    environment: 'both',
  // Hide from top nav; accessible via Analytics -> Taxes
  isActive: false,
    subSections: [
      {
        id: 'tax_dashboard',
        title: 'Tax Dashboard',
        description: 'Overview of tax situation and savings',
        icon: '🏛️',
  path: '/tax/dashboard',
        component: 'TaxDashboard',
        environment: 'both'
      },
      {
        id: 'contribution_tracker',
        title: 'Contribution Tracker',
        description: 'Track TFSA, RRSP, and RESP contributions',
        icon: '💡',
        path: '/tax/contributions',
        component: 'ContributionTracker',
        environment: 'both'
      },
      {
        id: 'tax_reporting',
        title: 'Tax Reporting',
        description: 'Generate reports for tax filing',
        icon: '📋',
        path: '/tax/reporting',
        component: 'TaxReporting',
        environment: 'both'
      },
    ]
  },

  // Analytics Section
  {
    id: 'analytics',
    title: 'Analytics',
    description: 'Deep analytics and performance insights',
    icon: '📈',
    path: '/analytics',
    category: 'analytics',
    environment: 'both',
    isActive: true,
    subSections: [
      {
        id: 'taxes',
        title: 'Taxes',
        description: 'Tax dashboard and tools',
        icon: '🏛️',
        path: '/tax/dashboard',
        component: 'TaxDashboard',
        environment: 'both'
      },
      {
        id: 'performance_analytics',
        title: 'Performance Analytics',
        description: 'Detailed performance analysis and metrics',
        icon: '⚡',
        path: '/analytics/performance',
        component: 'PerformanceAnalytics',
        environment: 'both'
      },
      {
        id: 'risk_analytics',
        title: 'Risk Analytics',
        description: 'Risk assessment and management tools',
        icon: '⚠️',
        path: '/analytics/risk',
        component: 'RiskAnalytics',
        environment: 'both'
      },
      {
        id: 'market_insights',
        title: 'Market Insights',
        description: 'Market analysis and insights',
        icon: '🌍',
        path: '/analytics/market',
        component: 'MarketInsights',
        environment: 'both'
      },
      {
        id: 'data_explorer',
        title: 'Data Explorer',
        description: 'Advanced data exploration and custom queries',
        icon: '🔍',
        path: '/analytics/explorer',
        component: 'DataExplorer',
        environment: 'development',
        isDeveloperTool: true
      }
    ]
  },

  // Services Section (links to Data, Engine, Transformer)
  {
    id: 'services',
    title: 'Services',
    description: 'Data, Engine, and Transformer service consoles',
    icon: '🧩',
  path: '/services/engine',
    category: 'analytics',
    environment: 'both',
    isActive: true,
    subSections: [
      {
        id: 'services_engine',
        title: 'FKS Engine',
        description: 'Backtesting and HMM+Transformer forecasts',
        icon: '🧠',
        path: '/services/engine',
        component: 'FKSEngine',
  environment: 'both'
      },
      {
        id: 'services_transformer',
        title: 'FKS Transformer',
        description: 'Transformer service dashboard',
        icon: '⚡',
        path: '/services/transformer',
        component: 'FKSTransformer',
  environment: 'both'
      },
      {
        id: 'services_training',
        title: 'GPU Training',
        description: 'GPU training jobs and monitoring',
        icon: '🏋️',
        path: '/services/training',
        component: 'FKSTraining',
  environment: 'both'
      }
    ]
  },

  // Project Manager (developer only helper)
  {
    id: 'project_manager',
    title: 'Project Manager',
    description: 'Build, package, and manage addon artifacts',
    icon: '🛠️',
    path: '/project-manager',
    category: 'settings',
    environment: 'development',
    isActive: false
  },

  // Settings Section
  {
    id: 'settings',
    title: 'Settings',
    description: 'Configure application preferences and integrations',
    icon: '⚙️',
    path: '/settings',
    category: 'settings',
    environment: 'both',
  isActive: false,
    subSections: [
      {
        id: 'user_preferences',
        title: 'User Preferences',
        description: 'Personal preferences and configuration',
        icon: '👤',
        path: '/settings/preferences',
        component: 'UserPreferences',
        environment: 'both'
      },
      {
        id: 'oauth_setup',
        title: 'OAuth & Authentication',
  description: 'Authentication and OAuth configuration',
        icon: '🔐',
        path: '/settings/oauth',
        component: 'OAuthSettings',
        environment: 'both'
      },
      {
        id: 'calendar_integration',
        title: 'Calendar Integration',
        description: 'Google Calendar API integration',
        icon: '📅',
  path: '/settings/calendar',
        component: 'CalendarIntegration',
        environment: 'both'
      },
      {
        id: 'notifications',
        title: 'Notifications',
        description: 'Configure notification preferences',
        icon: '🔔',
        path: '/settings/notifications',
        component: 'NotificationSettings',
        environment: 'both'
      },
      {
        id: 'developer_tools',
        title: 'Developer Tools',
        description: 'Advanced configuration and debugging tools',
        icon: '🛠️',
        path: '/settings/developer',
        component: 'DeveloperSettings',
        environment: 'development',
        isDeveloperTool: true
      }
      ,
      {
        id: 'providers_settings',
        title: 'Market Data Providers',
        description: 'Manage API keys and verify external data providers',
        icon: '🔑',
        path: '/settings/providers',
        component: 'ProvidersSettings',
        environment: 'both'
      }
    ]
  },

  // Calendar quick access
  {
    id: 'calendar',
    title: 'Calendar',
    description: 'Trading events and development planning',
    icon: '📅',
    path: '/calendar/plan',
    category: 'overview',
    environment: 'both',
  isActive: false
  },

  // Chat Section
  {
    id: 'chat',
    title: 'Chat',
    description: 'Integrations for collaboration and notifications',
    icon: '💬',
    path: '/chat/discord',
    category: 'overview',
    environment: 'both',
  // Move to user dropdown menu; hide from top nav
  isActive: false,
    subSections: [
      {
        id: 'discord_chat',
        title: 'Discord',
        description: 'Post messages to your Discord server via Webhooks',
        icon: '💬',
        path: '/chat/discord',
        component: 'DiscordChat',
        environment: 'both'
      }
    ]
  },

  // Architecture Section
  {
    id: 'architecture',
    title: 'Architecture',
    description: 'Interactive system architecture and service monitoring',
    icon: '🏗️',
    path: '/architecture',
    category: 'analytics',
    environment: 'both',
  isActive: true,
    subSections: [
      {
        id: 'architecture_overview',
        title: 'Architecture Overview',
        description: 'Interactive system architecture diagram',
        icon: '🗺️',
        path: '/architecture',
        component: 'ArchitectureDashboard',
        environment: 'both'
      },
      {
        id: 'master_orchestration',
        title: 'Master Orchestration',
        description: 'Central service orchestration & compose actions',
        icon: '🧩',
        path: '/master',
        component: 'MasterDashboard',
        environment: 'development',
        isDeveloperTool: true
      },
      {
        id: 'service_monitoring',
        title: 'Service Monitoring',
        description: 'Real-time service health and metrics',
        icon: '📊',
        path: '/architecture/monitoring',
        component: 'ServiceMonitoring',
        environment: 'both'
      },
      {
        id: 'service_health',
        title: 'Health Checks',
        description: 'Aggregated service & external dependency health',
        icon: '🩺',
        path: '/architecture/health',
        component: 'ServiceHealth',
        environment: 'both'
      },
      {
        id: 'diagnostics',
        title: 'Diagnostics',
        description: 'Latency tests & network throughput benchmarks',
        icon: '🧪',
        path: '/architecture/diagnostics',
        component: 'Diagnostics',
        environment: 'development',
        isDeveloperTool: true
      },
      {
        id: 'development_guide',
        title: 'Development Guide',
        description: 'Guide for extending and developing the system',
        icon: '📚',
        path: '/architecture/guide',
        component: 'DevelopmentGuide',
        environment: 'development',
        isDeveloperTool: true
      }
    ]
  }
];

// Environment configuration
export interface EnvironmentConfig {
  name: 'production' | 'development';
  features: EnvironmentFeature[];
  debugLevel: 'none' | 'basic' | 'verbose';
  showDeveloperTools: boolean;
  enableExperimentalFeatures: boolean;
}

export interface EnvironmentFeature {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  category: 'core' | 'experimental' | 'debug';
}

export const ENVIRONMENT_CONFIGS: Record<string, EnvironmentConfig> = {
  production: {
    name: 'production',
    features: [
      { id: 'live_trading', name: 'Live Trading', description: 'Real money trading', enabled: true, category: 'core' },
      { id: 'strategy_validation', name: 'Strategy Validation', description: 'Production strategy validation', enabled: true, category: 'core' },
      { id: 'tax_reporting', name: 'Tax Reporting', description: 'Official tax report generation', enabled: true, category: 'core' }
    ],
    debugLevel: 'none',
    showDeveloperTools: false,
    enableExperimentalFeatures: false
  },
  development: {
    name: 'development',
    features: [
      { id: 'paper_trading', name: 'Paper Trading', description: 'Simulated trading', enabled: true, category: 'core' },
      { id: 'debug_console', name: 'Debug Console', description: 'Advanced debugging tools', enabled: true, category: 'debug' },
      { id: 'data_explorer', name: 'Data Explorer', description: 'Advanced data analysis', enabled: true, category: 'experimental' },
      { id: 'verbose_logging', name: 'Verbose Logging', description: 'Detailed system logging', enabled: true, category: 'debug' }
    ],
    debugLevel: 'verbose',
    showDeveloperTools: true,
    enableExperimentalFeatures: true
  }
};
