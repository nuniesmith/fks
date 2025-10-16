import {
  Activity,
  AlertCircle,
  BarChart3,
  Brain,
  Building2,
  Code,
  Database,
  DollarSign,
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
  Calendar as CalendarIcon,
  Award,
  Lock,
  CheckCircle
} from 'lucide-react';
import React, { useState } from 'react';

import { isFeatureEnabled } from '../../config/features';
import { useGamification } from '../../context/GamificationContext';

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
  category: 'main' | 'trading' | 'development' | 'system' | 'docs';
  badge?: string;
  requiredLevel?: number;
  xpReward?: number;
}

interface MainNavigationProps {
  activeSection: string;
  onSectionChange: (section: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: (collapsed: boolean) => void;
}

const GamifiedNavigation: React.FC<MainNavigationProps> = ({ 
  activeSection, 
  onSectionChange,
  isCollapsed: externalIsCollapsed = false,
  onToggleCollapse
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState<string | null>('main');
  
  // Gamification context
  const { userProgress, getCurrentLevel, awardExperience } = useGamification();
  
  // Use external collapsed state if provided, otherwise manage internally
  const isCollapsed = externalIsCollapsed;
  const toggleCollapsed = () => {
    if (onToggleCollapse) {
      onToggleCollapse(!isCollapsed);
    }
  };

  const currentLevel = getCurrentLevel();
  const userLevel = currentLevel?.level || 1;

  const navigationItems: NavigationItem[] = [
    // Main Platform Categories (Core Navigation from Development Plan)
    { id: 'home', label: 'Home', icon: <Home className="w-5 h-5" />, description: 'Dashboard with real-time market updates', category: 'main' },
    { id: 'progress', label: 'Progress Dashboard', icon: <Trophy className="w-5 h-5" />, description: 'Track XP, achievements, and level progression', category: 'main', badge: 'XP', xpReward: 10 },
    { id: 'achievements', label: 'Achievements', icon: <Award className="w-5 h-5" />, description: 'View unlocked achievements and track progress', category: 'main', badge: 'New', xpReward: 5 },
    { id: 'phases', label: 'Phase Manager', icon: <Target className="w-5 h-5" />, description: 'Track Phase 1 & 2 progression towards financial independence', category: 'main', badge: 'Phases', requiredLevel: 2 },
    { id: 'prop-firms', label: 'Prop Firm Manager', icon: <Building2 className="w-5 h-5" />, description: 'Manage up to 30 prop firm accounts (Phase 1 goal)', category: 'main', badge: 'Phase 1', requiredLevel: 3 },
    { id: 'financial-targets', label: 'Financial Targets', icon: <DollarSign className="w-5 h-5" />, description: 'Set and track income targets to cover expenses', category: 'main', badge: 'Goals', requiredLevel: 2 },
    { id: 'trading', label: 'Trading Interface', icon: <TrendingUp className="w-5 h-5" />, description: 'Simulated and real-time trading interface', category: 'main', requiredLevel: 2 },
    { id: 'portfolio', label: 'Portfolio Manager', icon: <BarChart3 className="w-5 h-5" />, description: 'Asset allocation and performance metrics', category: 'main', requiredLevel: 3 },
    { id: 'profile', label: 'Profile & Preferences', icon: <Settings className="w-5 h-5" />, description: 'Strategy and risk management preferences', category: 'main' },
    { id: 'accounts', label: 'Account Manager', icon: <Package className="w-5 h-5" />, description: 'Manage trading accounts and strategies', category: 'main', requiredLevel: 2 },
    { id: 'canadian-accounts', label: 'Canadian Accounts', icon: <MapPin className="w-5 h-5" />, description: 'Guide to Canadian investment account types (Phase 2)', category: 'main', badge: 'CA', requiredLevel: 5 },
    { id: 'settings', label: 'System Settings', icon: <Settings className="w-5 h-5" />, description: 'App configurations and API settings', category: 'main' },
    { id: 'help', label: 'Help & Support', icon: <FileText className="w-5 h-5" />, description: 'Documentation and support resources', category: 'main' },

    // Development Planning & Management
    { id: 'calendar', label: 'Development Calendar', icon: <CalendarIcon className="w-5 h-5" />, description: '30-day development plan tracker', category: 'system', requiredLevel: 6 },
    { id: 'project-health', label: 'Project Health', icon: <Activity className="w-5 h-5" />, description: 'Monitor code quality and project issues', category: 'system', requiredLevel: 7 },

    // FKS Services (Core Intelligence) - High level requirements
    { id: 'fks_data', label: 'FKS Data Service', icon: <Database className="w-5 h-5" />, description: 'Data ETL pipelines and validation', category: 'trading', badge: 'GPU', requiredLevel: 5 },
    { id: 'fks_training', label: 'FKS Training Service', icon: <Brain className="w-5 h-5" />, description: 'ML model training and backtesting', category: 'trading', badge: 'GPU', requiredLevel: 6 },
    { id: 'fks_transformer', label: 'FKS Transformer Service', icon: <Zap className="w-5 h-5" />, description: 'NLP and sentiment analysis', category: 'trading', badge: 'GPU', requiredLevel: 7 },

    // Trading Tools & Features - Progressive unlock
    { id: 'strategy-library', label: 'Strategy Library', icon: <Database className="w-5 h-5" />, description: 'Build and manage trading strategies', category: 'trading', requiredLevel: 3 },
    { id: 'fks_intelligence', label: 'FKS Intelligence', icon: <Brain className="w-5 h-5" />, description: 'GPU-accelerated trading intelligence', category: 'trading', badge: 'AI', requiredLevel: 6 },
    { id: 'trading-mode', label: 'Trading Mode Control', icon: <Settings className="w-5 h-5" />, description: 'Simulation vs Live trading control', category: 'trading', requiredLevel: 2 },
    { id: 'market-insights', label: 'Market Insights', icon: <TrendingUp className="w-5 h-5" />, description: 'AI-powered market analysis', category: 'trading', badge: 'AI', requiredLevel: 4 },
    { id: 'live-charts', label: 'Live Charts', icon: <BarChart3 className="w-5 h-5" />, description: 'Real-time charting and technical analysis', category: 'trading', requiredLevel: 2 },
    { id: 'analytics', label: 'Trading Analytics', icon: <Activity className="w-5 h-5" />, description: 'Performance metrics and reports', category: 'trading', requiredLevel: 3 },
    { id: 'signals', label: 'Signals Panel', icon: <Zap className="w-5 h-5" />, description: 'Trading signals and alerts', category: 'trading', requiredLevel: 4 },
    { id: 'order-management', label: 'Order Management', icon: <Package className="w-5 h-5" />, description: 'Advanced order management and execution', category: 'trading', requiredLevel: 4 },
    { id: 'backtesting', label: 'Strategy Backtesting', icon: <TestTube className="w-5 h-5" />, description: 'Strategy backtesting and optimization', category: 'trading', requiredLevel: 3 },
    { id: 'strategy-development', label: 'Strategy Development', icon: <Code className="w-5 h-5" />, description: 'Create and test custom trading strategies', category: 'trading', requiredLevel: 5 },

    // Development & Testing Tools - Expert level
  ...(isFeatureEnabled('ninjaTrader') ? [{ id: 'ninjatrader', label: 'NinjaTrader 8', icon: <LineChart className="w-5 h-5" />, description: 'NT8 integration and management', category: 'development' as const, requiredLevel: 6 } as NavigationItem] : []),
    { id: 'api-testing', label: 'API Testing Suite', icon: <TestTube className="w-5 h-5" />, description: 'Test service endpoints and APIs', category: 'development', requiredLevel: 7 },
    { id: 'data-viewer', label: 'Database Viewer', icon: <Database className="w-5 h-5" />, description: 'Database inspection and queries', category: 'development', requiredLevel: 7 },
    { id: 'worker-status', label: 'Worker Status Monitor', icon: <Zap className="w-5 h-5" />, description: 'Background job monitoring', category: 'development', requiredLevel: 6 },
    { id: 'node-network', label: 'Node Network Monitor', icon: <Network className="w-5 h-5" />, description: 'Distributed system monitoring', category: 'development', badge: 'Beta', requiredLevel: 8 },
    { id: 'gamification-testing', label: 'Gamification Testing', icon: <Settings className="w-5 h-5" />, description: 'Test and validate gamification system', category: 'development', badge: 'Debug', requiredLevel: 1 },
    
    // System Administration - Master level
    { id: 'services-monitor', label: 'Services Monitor', icon: <Globe className="w-5 h-5" />, description: 'Service health and monitoring', category: 'system', requiredLevel: 6 },
    { id: 'system-logs', label: 'System Logs', icon: <FileText className="w-5 h-5" />, description: 'Real-time log viewer and analysis', category: 'system', requiredLevel: 7 },
    { id: 'git-status', label: 'Git Repository Status', icon: <GitBranch className="w-5 h-5" />, description: 'Repository status and deployment info', category: 'system', requiredLevel: 8 },
    
    // Documentation & Guidelines - Always available
    { id: 'documentation', label: 'Documentation', icon: <FileText className="w-5 h-5" />, description: 'Complete system documentation', category: 'docs' },
    { id: 'philosophy', label: 'Trading Philosophy', icon: <Brain className="w-5 h-5" />, description: 'Trading approach and methodology', category: 'docs' },
    { id: 'risk-management', label: 'Risk Management', icon: <Shield className="w-5 h-5" />, description: 'Risk guidelines and best practices', category: 'docs' },
    { id: 'crypto-guidelines', label: 'Crypto Guidelines', icon: <AlertCircle className="w-5 h-5" />, description: 'Cryptocurrency trading rules', category: 'docs' },
  ];

  const categories = [
    { id: 'main', label: 'Main Platform', color: 'blue', description: 'Core trading platform features' },
    { id: 'trading', label: 'Trading & AI', color: 'green', description: 'Advanced trading tools and AI features' },
    { id: 'development', label: 'Development Tools', color: 'purple', description: 'Developer and system tools' },
    { id: 'system', label: 'System Management', color: 'orange', description: 'System monitoring and administration' },
    { id: 'docs', label: 'Documentation', color: 'gray', description: 'Guides and documentation' },
  ];

  const getItemsByCategory = (category: string) => 
    navigationItems.filter(item => item.category === category);

  const isItemUnlocked = (item: NavigationItem) => {
    return !item.requiredLevel || userLevel >= item.requiredLevel;
  };

  const getUnlockedItemsCount = (category: string) => {
    return getItemsByCategory(category).filter(item => isItemUnlocked(item)).length;
  };

  const handleItemClick = (item: NavigationItem) => {
    if (!isItemUnlocked(item)) {
      // Could show a toast notification here
      return;
    }

    // Award XP for visiting new sections
    if (item.xpReward && activeSection !== item.id) {
      awardExperience('LESSON_COMPLETED');
    }

    onSectionChange(item.id);
    if (window.innerWidth < 1024) {
      setIsOpen(false);
    }
  };

  const getLevelProgress = () => {
    if (!userProgress) return { current: 0, required: 1000, percentage: 0 };
    
    const { totalXP, currentLevel } = userProgress;
    const nextLevelXP = currentLevel.level < 8 ? 
      (currentLevel.level === 1 ? 500 : currentLevel.requiredXP * 2) : 
      currentLevel.requiredXP;
    
    const currentLevelXP = currentLevel.requiredXP;
    const progressXP = totalXP - currentLevelXP;
    const requiredXP = nextLevelXP - currentLevelXP;
    
    return {
      current: Math.max(0, progressXP),
      required: requiredXP,
      percentage: Math.min((progressXP / requiredXP) * 100, 100)
    };
  };

  const levelProgress = getLevelProgress();

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
        {/* Header with Level Info */}
        <div className="p-6 border-b border-gray-800">
          <div className={`flex items-center justify-between ${isCollapsed ? 'hidden' : ''}`}>
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold">FKS Trading</h2>
                <p className="text-xs text-gray-400">v1.0.0 Gamified</p>
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
          </div>

          {/* User Level & Progress */}
          {!isCollapsed && userProgress && (
            <div className="mt-4 p-3 bg-gray-800 rounded-lg border border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">{currentLevel.icon}</span>
                  <div>
                    <div className="font-bold text-sm">{currentLevel.title}</div>
                    <div className="text-xs text-gray-400">Level {currentLevel.level}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400">XP</div>
                  <div className="text-sm font-bold text-blue-400">{userProgress.totalXP.toLocaleString()}</div>
                </div>
              </div>
              
              {currentLevel.level < 8 && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Progress to Level {currentLevel.level + 1}</span>
                    <span>{levelProgress.percentage.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${levelProgress.percentage}%` }}
                    ></div>
                  </div>
                  <div className="text-xs text-gray-500 text-center">
                    {levelProgress.current.toLocaleString()} / {levelProgress.required.toLocaleString()} XP
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Collapsed state icon */}
          {isCollapsed && (
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center mx-auto">
              <Brain className="w-6 h-6 text-white" />
            </div>
          )}
        </div>

        {/* Navigation items */}
        <div className="flex-1 overflow-y-auto py-4">
          {isCollapsed ? (
            // Collapsed view - show only icons with level indicators
            <div className="flex flex-col space-y-3 px-3">
              {navigationItems.map(item => {
                const unlocked = isItemUnlocked(item);
                return (
                  <button
                    key={item.id}
                    onClick={() => handleItemClick(item)}
                    disabled={!unlocked}
                    className={`p-3 rounded-lg transition-colors group relative ${
                      !unlocked 
                        ? 'opacity-50 cursor-not-allowed' 
                        : activeSection === item.id 
                          ? 'bg-gray-800 border-2 border-blue-500' 
                          : 'hover:bg-gray-800'
                    }`}
                    title={unlocked ? item.label : `Requires Level ${item.requiredLevel}`}
                  >
                    <div className={`${
                      !unlocked ? 'text-gray-600' :
                      activeSection === item.id ? 'text-blue-500' : 'text-gray-400 group-hover:text-white'
                    }`}>
                      {unlocked ? item.icon : <Lock className="w-5 h-5" />}
                    </div>
                    
                    {/* Enhanced tooltip with level info */}
                    <div className="absolute left-full ml-3 px-3 py-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-lg border border-gray-700 pointer-events-none">
                      <div className="flex items-center space-x-2">
                        <span>{item.label}</span>
                        {item.requiredLevel && (
                          <span className={`text-xs px-1 py-0.5 rounded ${
                            unlocked ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                          }`}>
                            Lv.{item.requiredLevel}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">{item.description}</div>
                      {!unlocked && (
                        <div className="text-xs text-red-400 mt-1">
                          🔒 Unlock at Level {item.requiredLevel}
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            // Expanded view - show categories with unlock progress
            categories.map(category => {
              const totalItems = getItemsByCategory(category.id).length;
              const unlockedItems = getUnlockedItemsCount(category.id);
              
              return (
                <div key={category.id} className="mb-2">
                  <button
                    onClick={() => setExpandedCategory(expandedCategory === category.id ? null : category.id)}
                    className="w-full px-6 py-2 flex items-center justify-between text-sm font-medium text-gray-400 hover:text-white transition-colors"
                  >
                    <div className="flex items-center space-x-2">
                      <span>{category.label}</span>
                      <div className="text-xs text-gray-500">({category.description})</div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs bg-gray-800 px-2 py-1 rounded">
                        {unlockedItems}/{totalItems}
                      </span>
                      {unlockedItems < totalItems && (
                        <Lock className="w-3 h-3 text-red-400" />
                      )}
                    </div>
                  </button>
                  
                  {expandedCategory === category.id && (
                    <div className="mt-1">
                      {getItemsByCategory(category.id).map(item => {
                        const unlocked = isItemUnlocked(item);
                        return (
                          <button
                            key={item.id}
                            onClick={() => handleItemClick(item)}
                            disabled={!unlocked}
                            className={`w-full px-6 py-3 flex items-start space-x-3 transition-colors group ${
                              !unlocked 
                                ? 'opacity-50 cursor-not-allowed' 
                                : activeSection === item.id 
                                  ? 'bg-gray-800 border-l-4 border-blue-500' 
                                  : 'hover:bg-gray-800'
                            }`}
                          >
                            <div className={`mt-0.5 flex-shrink-0 ${
                              !unlocked ? 'text-gray-600' :
                              activeSection === item.id ? 'text-blue-500' : 'text-gray-400 group-hover:text-white'
                            }`}>
                              {unlocked ? item.icon : <Lock className="w-5 h-5" />}
                            </div>
                            <div className="flex-1 text-left min-w-0">
                              <div className="flex items-center space-x-2">
                                <span className={`font-medium truncate ${
                                  !unlocked ? 'text-gray-500' :
                                  activeSection === item.id ? 'text-white' : 'text-gray-300'
                                }`}>
                                  {item.label}
                                </span>
                                
                                {/* Badges and level requirements */}
                                <div className="flex items-center space-x-1">
                                  {item.badge && unlocked && (
                                    <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded flex-shrink-0">
                                      {item.badge}
                                    </span>
                                  )}
                                  {item.requiredLevel && (
                                    <span className={`text-xs px-2 py-0.5 rounded flex-shrink-0 ${
                                      unlocked 
                                        ? 'bg-green-500/20 text-green-400' 
                                        : 'bg-red-500/20 text-red-400'
                                    }`}>
                                      Lv.{item.requiredLevel}
                                    </span>
                                  )}
                                  {unlocked && <CheckCircle className="w-3 h-3 text-green-400" />}
                                </div>
                              </div>
                              <p className={`text-xs mt-0.5 break-words ${
                                unlocked ? 'text-gray-500' : 'text-gray-600'
                              }`}>
                                {unlocked ? item.description : `🔒 Unlocks at Level ${item.requiredLevel}`}
                              </p>
                              {item.xpReward && unlocked && (
                                <div className="text-xs text-yellow-400 mt-1">
                                  +{item.xpReward} XP on first visit
                                </div>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer with Environment & Progress */}
        <div className={`p-4 border-t border-gray-800 ${isCollapsed ? 'hidden' : ''}`}>
          {userProgress && (
            <div className="mb-3 p-2 bg-gray-800 rounded text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-400">Recent Progress</span>
                <Award className="w-4 h-4 text-yellow-400" />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span>Phase 1 Progress:</span>
                  <span className="text-blue-400">
                    {userProgress.propFirmAccounts.length}/30 accounts
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Win Rate:</span>
                  <span className="text-green-400">{userProgress.stats.winRate.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          )}
          
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>Environment: development</span>
            <span>© 2025 FKS</span>
          </div>
        </div>
      </nav>
    </>
  );
};

export default GamifiedNavigation;
