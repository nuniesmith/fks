import {
  Menu,
  X,
  Home,
  BarChart3,
  TrendingUp,
  Brain,
  Briefcase,
  Calculator,
  PieChart,
  Settings,
  Code2,
  Database
} from 'lucide-react';
import React, { useRef, useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useMilestones } from '../../context/MilestoneContext';
import { useSecurityContext } from '../../context/SecurityContext';
import { useTradingEnv } from '../../context/TradingEnvContext';
import { useUser } from '../../context/UserContext';

import type { AppSection } from '../../types/layout';

interface AppNavigationProps {
  sections: AppSection[];
  isDevelopment: boolean;
}

const AppNavigation: React.FC<AppNavigationProps> = ({ sections, isDevelopment }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout: userLogout } = useUser();
  const security = useSecurityContext();
  const { userProgress } = useMilestones();
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  const { focus, setFocus, readiness } = useTradingEnv();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  // Minimal inline Calendar icon
  function CalendarIcon(props: any) {
    return (
      <svg
        {...props}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`h-4 w-4 ${props.className || ''}`}
      >
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    );
  }

  const iconMap: Record<string, React.ComponentType<any>> = {
    home: Home,
  data: Database,
    trading: TrendingUp,
    strategy: Brain,
    accounts: Briefcase,
  tax_optimization: Calculator,
    analytics: PieChart,
    settings: Settings,
    services: Code2,
    calendar: CalendarIcon
  };

  const getIcon = (sectionId: string) => iconMap[sectionId] || BarChart3;

  const isActiveSection = (sectionPath: string, subSectionPaths?: string[]) => {
    if (location.pathname === sectionPath) return true;
    if (subSectionPaths && subSectionPaths.length > 0) {
      return subSectionPaths.some((p) => location.pathname === p);
    }
    return false;
  };

  // Dynamically determine how many items to show before collapsing into "More"
  const [visibleCount, setVisibleCount] = useState<number>(6);

  useEffect(() => {
    const computeVisible = () => {
      const w = window.innerWidth;
      // Conservative defaults for different breakpoints
      // md (>=768) -> 5, lg (>=1024) -> 6, xl (>=1280) -> 7, 2xl (>=1536) -> 8
      let n = 5;
      if (w >= 1024) n = 6;
      if (w >= 1280) n = 7;
      if (w >= 1536) n = 8;
      setVisibleCount(n);
    };
    computeVisible();
    window.addEventListener('resize', computeVisible);
    return () => window.removeEventListener('resize', computeVisible);
  }, []);

  return (
    <nav className="backdrop-blur bg-gray-900/80 shadow-sm border-b border-blue-900/40 fixed top-0 left-0 right-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Brand */}
          <div className="flex items-center">
            <Link to="/" className="flex items-center space-x-3">
              <div className="bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-2 rounded-lg border border-white/10">
                <BarChart3 className="h-6 w-6" />
              </div>
              <div>
                <span className="text-xl font-bold text-white">FKS</span>
                {isDevelopment && (
                  <span className="ml-2 px-2 py-1 bg-yellow-500/20 text-yellow-300 text-xs rounded-full border border-yellow-500/40">
                    DEV
                  </span>
                )}
              </div>
            </Link>
            {/* Global Env badge + quick toggle */}
            <button
              type="button"
              onClick={() => {
                if (focus === 'simulation') {
                  if (readiness.ok) setFocus('live');
                } else {
                  setFocus('simulation');
                }
              }}
              title={focus === 'simulation' ? (readiness.ok ? 'Switch to Live' : 'Complete dataset split + assign strategies to enable Live') : 'Switch to Simulation'}
              className={`ml-3 px-2 py-1 rounded-full text-[10px] uppercase tracking-wide border transition-opacity ${
                focus === 'simulation'
                  ? 'bg-green-500/20 text-green-300 border-green-500/40'
                  : 'bg-red-500/20 text-red-300 border-red-500/40'
              } ${focus === 'simulation' && !readiness.ok ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90'}`}
              disabled={focus === 'simulation' && !readiness.ok}
            >
              {focus === 'simulation' ? 'Sim' : 'Live'}
            </button>
          </div>

          {/* Desktop Navigation (collapses overflow into More) */}
          <div className="hidden md:flex items-center gap-x-1">
            <div className="flex items-center gap-x-1 max-w-[40vw] lg:max-w-[50vw] xl:max-w-[56vw] 2xl:max-w-[62vw] overflow-hidden">
              {sections.slice(0, visibleCount).map((section) => {
                const IconComponent = getIcon(section.id);
                const subPaths = section.subSections?.map((s) => s.path) || [];
                const active = isActiveSection(section.path, subPaths);
                return (
                  <div key={section.id} className="relative group">
                    <Link
                      to={section.path}
                      className={`flex items-center px-2.5 py-2 rounded-md text-sm font-medium transition-colors ${
                        active
                          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                          : 'text-gray-200 hover:text-blue-300 hover:bg-blue-500/10 border border-transparent'
                      }`}
                    >
                      <IconComponent className="h-4 w-4 mr-1.5" />
                      {section.title}
                    </Link>

                    {section.subSections && section.subSections.length > 0 && (
                      <div className="absolute left-0 mt-1 w-64 bg-gray-900/95 backdrop-blur rounded-md shadow-lg border border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                        <div className="py-2">
                          {section.subSections.map((sub) => (
                            <Link
                              key={sub.id}
                              to={sub.path}
                              className={`block px-4 py-2 text-sm transition-colors ${
                                location.pathname === sub.path
                                  ? 'bg-blue-500/10 text-blue-300'
                                  : 'text-gray-200 hover:bg-white/5 hover:text-white'
                              }`}
                            >
                              <div className="flex items-center">
                                <span className="text-lg mr-2">{sub.icon}</span>
                                <div>
                                  <div className="font-medium">{sub.title}</div>
                                  {sub.isDeveloperTool && (
                                    <div className="text-xs text-orange-400">Developer Tool</div>
                                  )}
                                </div>
                              </div>
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {sections.length > visibleCount && (
              <div className="relative group">
                <button className="flex items-center px-2.5 py-2 rounded-md text-sm font-medium text-gray-200 hover:text-blue-300 hover:bg-blue-500/10 border border-transparent">
                  More
                </button>
                <div className="absolute right-0 mt-1 w-56 bg-gray-900/95 backdrop-blur rounded-md shadow-lg border border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                  <div className="py-2">
                    {sections.slice(visibleCount).map((section) => (
                      <Link
                        key={section.id}
                        to={section.path}
                        className={`block px-4 py-2 text-sm transition-colors ${
                          isActiveSection(section.path, section.subSections?.map((s) => s.path))
                            ? 'bg-blue-500/10 text-blue-300'
                            : 'text-gray-200 hover:bg-white/5 hover:text-white'
                        }`}
                      >
                        {section.title}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Desktop auth controls */}
          <div className="hidden md:flex items-center gap-3">
            {!isAuthenticated ? (
              <Link
                to="/login"
                className="px-3 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
              >
                Login
              </Link>
            ) : (
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen((v) => !v)}
                  className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-white/5 border border-white/10"
                >
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center text-xs font-bold">
                    {(user?.name || user?.email || '?').slice(0, 1).toUpperCase()}
                  </div>
                  <span className="text-sm text-white/90 hidden lg:inline">{user?.name || user?.email}</span>
                </button>
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-72 bg-gray-900/95 backdrop-blur border border-gray-700 rounded-md shadow-lg z-50 p-3">
                    <div className="text-sm text-white mb-2">
                      Signed in as <span className="font-medium">{user?.email}</span>
                    </div>
                    <div className="mb-3">
                      <div className="flex items-center justify-between text-xs text-gray-300">
                        <span>XP</span>
                        <span className="font-mono">{userProgress.totalXP.toLocaleString()}</span>
                      </div>
                      <div className="h-1.5 bg-white/10 rounded mt-1 overflow-hidden">
                        <div
                          className="h-1.5 bg-blue-500 rounded"
                          style={{ width: `${Math.min(100, (userProgress.totalXP % 1000) / 10)}%` }}
                        />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Link to="/accounts" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">
                        Accounts
                      </Link>
                      <Link to="/ai/assistant" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">
                        AI Assistant
                      </Link>
                      <Link to="/chat/discord" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">
                        Chat
                      </Link>
                      <Link to="/milestones" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">
                        Milestones
                      </Link>
                      <Link to="/settings" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">
                        Settings
                      </Link>
                      <Link to="/calendar/plan" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">
                        Calendar
                      </Link>
                      {/* Dev-only: Architecture quick access */}
                      {isDevelopment && (
                        <Link to="/architecture" className="block text-sm text-orange-300 hover:text-white hover:bg-orange-500/10 rounded px-2 py-1">
                          Architecture (dev)
                        </Link>
                      )}
                    </div>
                    <div className="border-t border-gray-700 mt-2 pt-2">
                      <button
                        onClick={async () => {
                          try {
                            await security.logout();
                          } catch {}
                          userLogout();
                          navigate('/login');
                        }}
                        className="w-full text-left text-sm text-red-300 hover:text-red-200 hover:bg-red-500/10 rounded px-2 py-1"
                      >
                        Logout
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="text-gray-200 hover:text-blue-300 focus:outline-none"
            >
              {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden border-t border-gray-800 py-4">
            <div className="space-y-2">
              {sections.map((section) => {
                const IconComponent = getIcon(section.id);
                const subPaths = section.subSections?.map((s) => s.path) || [];
                const active = isActiveSection(section.path, subPaths);
                return (
                  <div key={section.id}>
                    <Link
                      to={section.path}
                      onClick={() => setIsMenuOpen(false)}
                      className={`flex items-center px-3 py-2 rounded-md text-base font-medium transition-colors ${
                        active
                          ? 'bg-blue-500/20 text-blue-300'
                          : 'text-gray-200 hover:text-blue-300 hover:bg-blue-500/10'
                      }`}
                    >
                      <IconComponent className="h-5 w-5 mr-3" />
                      {section.title}
                    </Link>

                    {section.subSections && section.subSections.length > 0 && (
                      <div className="ml-8 mt-2 space-y-1">
                        {section.subSections.map((sub) => (
                          <Link
                            key={sub.id}
                            to={sub.path}
                            onClick={() => setIsMenuOpen(false)}
                            className={`block px-3 py-2 rounded-md text-sm transition-colors ${
                              location.pathname === sub.path
                                ? 'bg-blue-500/10 text-blue-300'
                                : 'text-gray-300 hover:bg-white/5 hover:text-white'
                            }`}
                          >
                            <div className="flex items-center">
                              <span className="text-base mr-2">{sub.icon}</span>
                              <div>
                                <div>{sub.title}</div>
                                {sub.isDeveloperTool && (
                                  <div className="text-xs text-orange-400">Dev Tool</div>
                                )}
                              </div>
                            </div>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="pt-3 border-t border-gray-800">
                {!isAuthenticated ? (
                  <Link
                    to="/login"
                    onClick={() => setIsMenuOpen(false)}
                    className="block w-full text-center px-3 py-2 rounded-md text-base font-medium bg-blue-600 text-white hover:bg-blue-700"
                  >
                    Login
                  </Link>
                ) : (
                  <button
                    onClick={async () => {
                      setIsMenuOpen(false);
                      try {
                        await security.logout();
                      } catch {}
                      userLogout();
                      navigate('/login');
                    }}
                    className="block w-full text-center px-3 py-2 rounded-md text-base font-medium bg-gray-800 text-white hover:bg-gray-700"
                  >
                    Logout
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default AppNavigation;
