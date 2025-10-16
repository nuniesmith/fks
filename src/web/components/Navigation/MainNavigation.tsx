import {
  Activity,
  AlertCircle,
  BarChart3,
  Brain,
  Building2,
  Code,
  Database,
  FileText,
  GitBranch,
  Globe,
  Home,
  LineChart,
  MapPin,
  Menu,
  Network,
  Package,
  Settings,
  Shield,
  Target,
  TestTube,
  TrendingUp,
  Trophy,
  X,
  Zap,
  Calendar as CalendarIcon
} from 'lucide-react';
import React, { useState } from 'react';

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
  category: 'main' | 'trading' | 'development' | 'system' | 'docs';
  badge?: string;
}

interface MainNavigationProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: (collapsed: boolean) => void;
}

const MainNavigation: React.FC<MainNavigationProps> = ({ 
  activeSection, 
  onSectionChange,
  isCollapsed: externalIsCollapsed = false,
  onToggleCollapse
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState<string | null>('main');
  
  // Use external collapsed state if provided, otherwise manage internally
  const isCollapsed = externalIsCollapsed;
  const toggleCollapsed = () => {
    if (onToggleCollapse) {
      onToggleCollapse(!isCollapsed);
    }
  };

  const navigationItems: NavigationItem[] = [
    // Main Platform Categories (Core Navigation from Development Plan)
    { id: 'home', label: 'Home', icon: <Home className="w-5 h-5" />, description: 'Dashboard with real-time market updates', category: 'main' },
    { id: 'progress', label: 'Progress', icon: <Trophy className="w-5 h-5" />, description: 'Gamified progress tracking and achievements', category: 'main', badge: 'XP' },
    { id: 'phases', label: 'Phase Manager', icon: <Target className="w-5 h-5" />, description: 'Track Phase 1 & 2 progression towards financial independence', category: 'main', badge: 'Phases' },
    { id: 'trading', label: 'Trading', icon: <TrendingUp className="w-5 h-5" />, description: 'Simulated and real-time trading interface', category: 'main' },
    { id: 'portfolio', label: 'Portfolio', icon: <BarChart3 className="w-5 h-5" />, description: 'Asset allocation and performance metrics', category: 'main' },
    { id: 'prop-firms', label: 'Prop Firms', icon: <Building2 className="w-5 h-5" />, description: 'Manage prop firm accounts and track progress to 30 accounts', category: 'main', badge: 'Phase 1' },
    { id: 'financial-targets', label: 'Financial Targets', icon: <Target className="w-5 h-5" />, description: 'Set and track income targets to cover expenses', category: 'main', badge: 'NEW' },
    { id: 'profile', label: 'Profile', icon: <Settings className="w-5 h-5" />, description: 'Strategy and risk management preferences', category: 'main' },
    { id: 'accounts', label: 'Accounts', icon: <Package className="w-5 h-5" />, description: 'Manage trading accounts and strategies', category: 'main' },
    { id: 'canadian-accounts', label: 'Canadian Accounts Guide', icon: <MapPin className="w-5 h-5" />, description: 'Guide to Canadian investment account types', category: 'main', badge: 'CA' },
    { id: 'settings', label: 'Settings', icon: <Settings className="w-5 h-5" />, description: 'App configurations and API settings', category: 'main' },
    { id: 'help', label: 'Help', icon: <FileText className="w-5 h-5" />, description: 'Documentation and support', category: 'main' },

    // Development Planning & Management
    { id: 'calendar', label: 'Development Calendar', icon: <CalendarIcon className="w-5 h-5" />, description: '30-day development plan tracker', category: 'system' },
    { id: 'project-health', label: 'Project Health', icon: <Activity className="w-5 h-5" />, description: 'Monitor code quality and project issues', category: 'system' },

    // FKS Services (Core Intelligence)
    { id: 'fks_data', label: 'FKS Data Service', icon: <Database className="w-5 h-5" />, description: 'Data ETL pipelines and validation', category: 'trading', badge: 'GPU' },
    { id: 'fks_training', label: 'FKS Training Service', icon: <Brain className="w-5 h-5" />, description: 'ML model training and backtesting', category: 'trading', badge: 'GPU' },
    { id: 'fks_transformer', label: 'FKS Transformer Service', icon: <Zap className="w-5 h-5" />, description: 'NLP and sentiment analysis', category: 'trading', badge: 'GPU' },

    // Trading Tools & Features
    { id: 'strategy-library', label: 'Strategy Library', icon: <Database className="w-5 h-5" />, description: 'Build and manage trading strategies', category: 'trading' },
    { id: 'fks_intelligence', label: 'FKS Intelligence', icon: <Brain className="w-5 h-5" />, description: 'GPU-accelerated trading intelligence', category: 'trading', badge: 'AI' },
    { id: 'trading-mode', label: 'Trading Mode', icon: <Settings className="w-5 h-5" />, description: 'Simulation vs Live trading control', category: 'trading' },
    { id: 'market-insights', label: 'Market Insights', icon: <TrendingUp className="w-5 h-5" />, description: 'AI-powered market analysis', category: 'trading', badge: 'AI' },
    { id: 'live-charts', label: 'Live Charts', icon: <BarChart3 className="w-5 h-5" />, description: 'Real-time charting and technical analysis', category: 'trading' },
    { id: 'analytics', label: 'Trading Analytics', icon: <Activity className="w-5 h-5" />, description: 'Performance metrics and reports', category: 'trading' },
    { id: 'signals', label: 'Signals Panel', icon: <Zap className="w-5 h-5" />, description: 'Trading signals and alerts', category: 'trading' },
    { id: 'order-management', label: 'Orders', icon: <Package className="w-5 h-5" />, description: 'Order management and execution', category: 'trading' },
    { id: 'backtesting', label: 'Backtesting', icon: <TestTube className="w-5 h-5" />, description: 'Strategy backtesting and optimization', category: 'trading' },
    { id: 'strategy-development', label: 'Strategy Development', icon: <Code className="w-5 h-5" />, description: 'Create and test trading strategies', category: 'trading' },

    // Development & Testing Tools
    { id: 'ninjatrader', label: 'NinjaTrader 8', icon: <LineChart className="w-5 h-5" />, description: 'NT8 integration and management', category: 'development' },
    { id: 'api-testing', label: 'API Testing', icon: <TestTube className="w-5 h-5" />, description: 'Test service endpoints and APIs', category: 'development' },
    { id: 'data-viewer', label: 'Data Viewer', icon: <Database className="w-5 h-5" />, description: 'Database inspection and queries', category: 'development' },
    { id: 'worker-status', label: 'Worker Status', icon: <Zap className="w-5 h-5" />, description: 'Background job monitoring', category: 'development' },
    { id: 'node-network', label: 'Node Network', icon: <Network className="w-5 h-5" />, description: 'Distributed system monitoring', category: 'development', badge: 'Beta' },
    
    // System Administration
    { id: 'services-monitor', label: 'Services Monitor', icon: <Globe className="w-5 h-5" />, description: 'Service health and monitoring', category: 'system' },
    { id: 'system-logs', label: 'System Logs', icon: <FileText className="w-5 h-5" />, description: 'Real-time log viewer and analysis', category: 'system' },
    { id: 'git-status', label: 'Git Status', icon: <GitBranch className="w-5 h-5" />, description: 'Repository status and deployment info', category: 'system' },
    
    // Documentation & Guidelines
    { id: 'documentation', label: 'Documentation', icon: <FileText className="w-5 h-5" />, description: 'Complete system documentation', category: 'docs' },
    { id: 'philosophy', label: 'Trading Philosophy', icon: <Brain className="w-5 h-5" />, description: 'Trading approach and methodology', category: 'docs' },
    { id: 'risk-management', label: 'Risk Management', icon: <Shield className="w-5 h-5" />, description: 'Risk guidelines and best practices', category: 'docs' },
    { id: 'crypto-guidelines', label: 'Crypto Guidelines', icon: <AlertCircle className="w-5 h-5" />, description: 'Cryptocurrency trading rules', category: 'docs' },
  ];

  const categories = [
    { id: 'main', label: 'Main Platform', color: 'blue' },
    { id: 'trading', label: 'Trading & AI', color: 'green' },
    { id: 'development', label: 'Development', color: 'purple' },
    { id: 'system', label: 'System', color: 'orange' },
    { id: 'docs', label: 'Documentation', color: 'gray' },
  ];

  const getItemsByCategory = (category: string) => 
    navigationItems.filter(item => item.category === category);

  const handleItemClick = (itemId: string) => {
    onSectionChange(itemId);
    if (window.innerWidth < 1024) {
      setIsOpen(false);
    }
  };

  return (
    <>
      {/* Mobile menu toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-gray-900 rounded-lg text-white hover:bg-gray-800 transition-colors"
      >
        {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Navigation sidebar */}
      <nav
        className={`fixed left-0 top-0 h-full bg-gray-900 text-white transform transition-all duration-300 z-40 overflow-x-hidden overflow-y-auto flex flex-col ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        } ${isCollapsed ? 'lg:w-20' : 'w-80'}`}
      >
        {/* Header */}
        <div className="p-6 border-b border-gray-800 flex items-center justify-between">
          <div className={`flex items-center space-x-3 ${isCollapsed ? 'hidden' : ''}`}>
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold">FKS Trading Systems</h2>
              <p className="text-xs text-gray-400">v1.0.0</p>
            </div>
          </div>
          
          {/* Collapse toggle button (desktop only) */}
          <button
            onClick={toggleCollapsed}
            className="hidden lg:flex p-2 hover:bg-gray-800 rounded-lg transition-colors"
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? <Menu className="w-5 h-5" /> : <X className="w-5 h-5" />}
          </button>
          
          {/* Collapsed state icon */}
          {isCollapsed && (
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center mx-auto absolute left-1/2 transform -translate-x-1/2">
              <Brain className="w-6 h-6 text-white" />
            </div>
          )}
        </div>

        {/* Navigation items */}
        <div className="flex-1 overflow-y-auto py-4">
          {isCollapsed ? (
            // Collapsed view - show only icons
            <div className="flex flex-col space-y-3 px-3">
              {navigationItems.map(item => (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item.id)}
                  className={`p-3 rounded-lg hover:bg-gray-800 transition-colors group relative ${
                    activeSection === item.id ? 'bg-gray-800 border-2 border-blue-500' : ''
                  }`}
                  title={item.label}
                >
                  <div className={`${activeSection === item.id ? 'text-blue-500' : 'text-gray-400 group-hover:text-white'}`}>
                    {item.icon}
                  </div>
                  {/* Tooltip */}
                  <div className="absolute left-full ml-3 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-lg border border-gray-700 pointer-events-none">
                    {item.label}
                    <div className="text-xs text-gray-400 mt-1">{item.description}</div>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            // Expanded view - show categories and full items
            categories.map(category => (
              <div key={category.id} className="mb-2">
                <button
                  onClick={() => setExpandedCategory(expandedCategory === category.id ? null : category.id)}
                  className="w-full px-6 py-2 flex items-center justify-between text-sm font-medium text-gray-400 hover:text-white transition-colors"
                >
                  <span>{category.label}</span>
                  <span className="text-xs bg-gray-800 px-2 py-1 rounded">
                    {getItemsByCategory(category.id).length}
                  </span>
                </button>
                
                {expandedCategory === category.id && (
                  <div className="mt-1">
                    {getItemsByCategory(category.id).map(item => (
                      <button
                        key={item.id}
                        onClick={() => handleItemClick(item.id)}
                        className={`w-full px-6 py-3 flex items-start space-x-3 hover:bg-gray-800 transition-colors group ${
                          activeSection === item.id ? 'bg-gray-800 border-l-4 border-blue-500' : ''
                        }`}
                      >
                        <div className={`mt-0.5 flex-shrink-0 ${activeSection === item.id ? 'text-blue-500' : 'text-gray-400 group-hover:text-white'}`}>
                          {item.icon}
                        </div>
                        <div className="flex-1 text-left min-w-0">
                          <div className="flex items-center space-x-2">
                            <span className={`font-medium truncate ${activeSection === item.id ? 'text-white' : 'text-gray-300'}`}>
                              {item.label}
                            </span>
                            {item.badge && (
                              <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded flex-shrink-0">
                                {item.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-0.5 break-words">{item.description}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className={`p-4 border-t border-gray-800 ${isCollapsed ? 'hidden' : ''}`}>
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>Environment: development</span>
            <span>© 2025 FKS</span>
          </div>
        </div>
      </nav>
    </>
  );
};

export default MainNavigation;
