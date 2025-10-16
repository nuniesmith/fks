// (Removed duplicated corrupted header block)
// CLEAN IMPLEMENTATION (reset after corruption)
import FeatureBoundary from '@features/core/FeatureBoundary';
import AppNavigation from '@features/navigation/components/AppNavigation';
import SectionSidebar from '@features/navigation/components/SectionSidebar';
import LayoutShell from '@layout/LayoutShell';
import React, { useMemo } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';

import { ServiceHealthProvider } from './components/ServiceMonitoring/ServiceHealthProvider';
import { TradingEnvProvider } from './context/TradingEnvContext';
import { useUser } from './context/UserContext';
import { useFrontendMetrics, useWebVitals } from '@shared';
import HomePage from './pages/Home/HomePage';
import { APP_SECTIONS } from './types/layout';
import { buildAuthLoginUrl } from './utils/authUtils';

// Lazily loaded route components
const ArchitectureDashboard = React.lazy(() => import('./components/ArchitectureDashboard/ArchitectureDashboard'));
const ServiceHealthPage = React.lazy(() => import('./components/ArchitectureDashboard/ServiceHealthPage'));
const DiagnosticsPage = React.lazy(() => import('./components/ArchitectureDashboard/DiagnosticsPage'));
const DocumentationViewer = React.lazy(() => import('./components/DocumentationViewer'));
const MilestoneSystem = React.lazy(() => import('./components/MilestoneSystem/System'));
const MilestoneTracker = React.lazy(() => import('./components/MilestoneSystem/Tracker'));
const TradingDashboard = React.lazy(() => import('@features/trading/components/dashboard/TradingDashboard'));
const StrategyLibrary = React.lazy(() => import('@features/trading/components/strategy/StrategyLibrary'));
const StrategyDevelopment = React.lazy(() => import('@features/trading/components/strategy/StrategyDevelopment'));
const BacktestsHistory = React.lazy(() => import('@features/trading/components/backtests/BacktestsHistory'));
const BacktestRunner = React.lazy(() => import('./components/Trading/BacktestRunner'));
const StrategyOverview = React.lazy(() => import('./components/Trading/StrategyOverview'));
const StrategyBuilder = React.lazy(() => import('./components/Trading/StrategyBuilder'));
const StrategyBacktesting = React.lazy(() => import('./components/Trading/StrategyBacktesting'));
const ForwardTesting = React.lazy(() => import('./components/Trading/ForwardTesting'));
const MonteCarlo = React.lazy(() => import('./components/Trading/MonteCarlo'));
const AnalyticsOverview = React.lazy(() => import('@features/analytics/components/Overview'));
const AnalyticsPerformance = React.lazy(() => import('@features/analytics/components/Performance'));
const AnalyticsRisk = React.lazy(() => import('@features/analytics/components/Risk'));
const AnalyticsMarket = React.lazy(() => import('@features/analytics/components/Market'));
const AccountsPage = React.lazy(() => import('./components/Accounts/AccountsPage'));
const PortfolioPage = React.lazy(() => import('@features/portfolio/components/PortfolioPage'));
const TaxOptimization = React.lazy(() => import('./components/TaxOptimization/TaxOptimization'));
const DevCalendar = React.lazy(() => import('./components/Calendar/DevCalendar'));
const IcsCalendar = React.lazy(() => import('./components/Calendar/IcsCalendar'));
const SettingsPage = React.lazy(() => import('./components/Settings/SettingsPage'));
const ProvidersSettings = React.lazy(() => import('./components/Settings/ProvidersSettings'));
const RuntimeConfigSettings = React.lazy(() => import('./components/Settings/RuntimeConfigSettings'));
const LoginPage = React.lazy(() => import('@features/auth/components/LoginPage'));
const AuthCallback = React.lazy(() => import('@features/auth/components/AuthCallback'));
const DiscordChat = React.lazy(() => import('./components/Discord/DiscordChat'));
const AIAssistant = React.lazy(() => import('./components/AI/AIAssistant'));
const ApiServicePage = React.lazy(() => import('@features/services/pages/ApiServicePage'));
const DataServicePage = React.lazy(() => import('@features/services/pages/DataServicePage'));
const EngineServicePage = React.lazy(() => import('@features/services/pages/EngineServicePage'));
const TransformerServicePage = React.lazy(() => import('@features/services/pages/TransformerServicePage'));
const WebServicePage = React.lazy(() => import('@features/services/pages/WebServicePage'));
const TrainingServicePage = React.lazy(() => import('@features/services/pages/TrainingServicePage'));
const WorkerServicePage = React.lazy(() => import('@features/services/pages/WorkerServicePage'));
const MetricsPage = React.lazy(() => import('./pages/Metrics/MetricsPage'));
const MasterDashboard = React.lazy(() => import('./pages/Master/MasterDashboard'));

// Placeholder page
const PlaceholderPage: React.FC<{ title: string; description: string; icon: string }> = ({ title, description, icon }) => (
  <div className="p-6">
    <h1 className="text-3xl font-bold text-white mb-6 flex items-center gap-3"><span>{icon}</span>{title}</h1>
    <div className="glass-card p-6">
      <p className="text-white/90 mb-4">{description}</p>
      <p className="text-xs text-white/60">Coming soon</p>
    </div>
  </div>
);

const LoadingSpinner: React.FC = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white/30 border-t-white"></div>
    <span className="ml-3 text-lg text-white/90">Loading...</span>
  </div>
);

const ProtectedRoute: React.FC<{ children: React.ReactElement; requireDeveloper?: boolean }> = ({ children, requireDeveloper = false }) => {
  const { isAuthenticated, isDeveloper } = useUser();
  if (!isAuthenticated) {
    const returnTo = window.location.pathname + window.location.search + window.location.hash;
    const authLogin = buildAuthLoginUrl(returnTo);
    if (authLogin.startsWith('http')) { window.location.replace(authLogin); return null; }
    return <Navigate to={authLogin} replace />;
  }
  if (requireDeveloper && !isDeveloper) return <Navigate to="/" replace />;
  return children;
};

const App: React.FC = () => {
  try { useFrontendMetrics(); useWebVitals(); } catch { /* ignore metrics errors */ }
  const { isDeveloper } = useUser();
  const isDevelopment = import.meta?.env?.DEV === true;
  const location = useLocation();

  const navSections = useMemo(() => APP_SECTIONS
    .filter(s => s.isActive)
    .filter(s => s.environment === 'both' || (s.environment === 'development' && isDevelopment))
    .map(s => ({
      ...s,
      subSections: (s.subSections || []).filter(sub => {
        const envOk = sub.environment === 'both' || (sub.environment === 'development' && isDevelopment);
        const roleOk = !sub.isDeveloperTool || isDeveloper; return envOk && roleOk; })
    })), [isDeveloper, isDevelopment]);

  const hasSidebar = useMemo(() => {
    const path = location.pathname;
    const candidates = APP_SECTIONS.filter(s => s.isActive);
    let match = candidates.find(s => path === s.path || path.startsWith(s.path + '/'));
    if (!match) match = candidates.find(s => (s.subSections || []).some(sub => path === sub.path || path.startsWith(sub.path + '/')));
    if (!match) return false;
    const filtered = (match.subSections || []).filter(sub => {
      const envOk = sub.environment === 'both' || (sub.environment === 'development' && isDevelopment);
      const roleOk = !sub.isDeveloperTool || isDeveloper; return envOk && roleOk; });
    return filtered.length > 0;
  }, [location.pathname, isDevelopment, isDeveloper]);

  return (
    <TradingEnvProvider>
      <ServiceHealthProvider>
  {/* Body already supplies the primary gradient; avoid double-stacking to reduce banding & over-saturation */}
  <div className="min-h-screen">
          {/* Auth Disabled Banner (when Authentik / auth intentionally disabled) */}
          {(() => { try { return localStorage.getItem('fks.disable.auth') === 'true' || (import.meta as any).env?.VITE_DISABLE_AUTH === 'true'; } catch { return false } })() && (
            <div className="w-full bg-amber-600/80 backdrop-blur-sm text-white text-sm py-2 px-4 flex items-center gap-2 shadow-lg">
              <span className="font-semibold">Auth Disabled</span>
              <span className="text-white/80">Running in unsecured local mode – enable authentication for production.</span>
            </div>
          )}
          <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 bg-blue-600 text-white px-4 py-2 rounded z-50">Skip to content</a>
          <AppNavigation sections={navSections} isDevelopment={isDevelopment} />
          {/* Main application shell */}
          <main id="main" className="app-shell px-4" role="main" aria-label="Main content">
            <LayoutShell sidebar={hasSidebar ? <SectionSidebar isDevelopment={isDevelopment} /> : undefined}>
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/login" element={<React.Suspense fallback={<LoadingSpinner />}><LoginPage /></React.Suspense>} />
                  <Route path="/auth/callback" element={<React.Suspense fallback={<LoadingSpinner />}><AuthCallback /></React.Suspense>} />
                  <Route path="/oauth/callback" element={<React.Suspense fallback={<LoadingSpinner />}><AuthCallback /></React.Suspense>} />

                  {/* Architecture */}
                  <Route path="/architecture" element={<React.Suspense fallback={<LoadingSpinner />}><ArchitectureDashboard /></React.Suspense>} />
                  <Route path="/architecture/health" element={<React.Suspense fallback={<LoadingSpinner />}><ServiceHealthPage /></React.Suspense>} />
                  {/* Legacy alias */}
                  <Route path="/architecture/monitoring" element={<Navigate to="/architecture/health" replace />} />
                  <Route path="/architecture/diagnostics" element={<ProtectedRoute requireDeveloper><React.Suspense fallback={<LoadingSpinner />}><DiagnosticsPage /></React.Suspense></ProtectedRoute>} />
                  <Route path="/architecture/guide" element={<ProtectedRoute requireDeveloper><PlaceholderPage title="Development Guide" description="📚 Guidance for extending and developing the system (dev only)." icon="📚" /></ProtectedRoute>} />

                  {/* Docs */}
                  <Route path="/docs" element={<React.Suspense fallback={<LoadingSpinner />}><DocumentationViewer className="min-h-[calc(100vh-7rem)]" /></React.Suspense>} />

                  {/* Accounts */}
                  <Route path="/accounts" element={<React.Suspense fallback={<LoadingSpinner />}><AccountsPage /></React.Suspense>} />
                  <Route path="/accounts/prop-firms" element={<PlaceholderPage title="Prop Firm Accounts" description="🏢 Manage prop firm accounts and payouts (coming soon)." icon="🏢" />} />
                  <Route path="/accounts/personal" element={<PlaceholderPage title="Personal Accounts" description="👤 TFSA, RRSP, and personal trading accounts (coming soon)." icon="👤" />} />
                  <Route path="/accounts/analytics" element={<PlaceholderPage title="Account Analytics" description="📊 Performance analysis across accounts (coming soon)." icon="📊" />} />
                  <Route path="/accounts/profits" element={<PlaceholderPage title="Profit Tracking" description="💰 Track profits from all accounts (coming soon)." icon="💰" />} />

                  {/* Services (wrapped with FeatureBoundary) */}
                  <Route path="/services/api" element={<ProtectedRoute requireDeveloper><FeatureBoundary><ApiServicePage /></FeatureBoundary></ProtectedRoute>} />
                  <Route path="/services/data" element={<FeatureBoundary><DataServicePage /></FeatureBoundary>} />
                  <Route path="/services/engine" element={<ProtectedRoute requireDeveloper><FeatureBoundary><EngineServicePage /></FeatureBoundary></ProtectedRoute>} />
                  <Route path="/services/transformer" element={<ProtectedRoute requireDeveloper><FeatureBoundary><TransformerServicePage /></FeatureBoundary></ProtectedRoute>} />
                  <Route path="/services/web" element={<ProtectedRoute requireDeveloper><FeatureBoundary><WebServicePage /></FeatureBoundary></ProtectedRoute>} />
                  <Route path="/services/training" element={<ProtectedRoute requireDeveloper><FeatureBoundary><TrainingServicePage /></FeatureBoundary></ProtectedRoute>} />
                  <Route path="/services/worker" element={<ProtectedRoute requireDeveloper><FeatureBoundary><WorkerServicePage /></FeatureBoundary></ProtectedRoute>} />

                  {/* Settings */}
                  <Route path="/settings" element={<React.Suspense fallback={<LoadingSpinner />}><SettingsPage /></React.Suspense>} />
                  <Route path="/settings/providers" element={<React.Suspense fallback={<LoadingSpinner />}><ProvidersSettings /></React.Suspense>} />
                  <Route path="/settings/config" element={<React.Suspense fallback={<LoadingSpinner />}><RuntimeConfigSettings /></React.Suspense>} />
                  <Route path="/settings/preferences" element={<PlaceholderPage title="User Preferences" description="👤 Personal preferences and configuration (coming soon)." icon="👤" />} />
                  <Route path="/settings/oauth" element={<PlaceholderPage title="OAuth & Authentication" description="🔐 Configure Google OAuth and Authentik (coming soon)." icon="🔐" />} />
                  <Route path="/settings/calendar" element={<PlaceholderPage title="Calendar Integration" description="📅 Google Calendar API integration (coming soon)." icon="📅" />} />
                  <Route path="/settings/notifications" element={<PlaceholderPage title="Notifications" description="🔔 Configure notification preferences (coming soon)." icon="🔔" />} />
                  <Route path="/settings/developer" element={<ProtectedRoute requireDeveloper><PlaceholderPage title="Developer Tools" description="🛠️ Advanced configuration and debugging tools (dev only)." icon="🛠️" /></ProtectedRoute>} />

                  {/* Trading core + history */}
                  <Route path="/trading/dashboard" element={<React.Suspense fallback={<LoadingSpinner />}><TradingDashboard /></React.Suspense>} />
                  {/* Live/paper/analysis placeholders to avoid 404s */}
                  <Route path="/trading/live" element={<PlaceholderPage title="Live Trading" description="⚡ Real-time trading interface (coming soon)." icon="⚡" />} />
                  <Route path="/trading/analysis" element={<PlaceholderPage title="Market Analysis" description="🔍 Technical & fundamental analysis tools (coming soon)." icon="🔍" />} />
                  <Route path="/trading/paper" element={<PlaceholderPage title="Paper Trading" description="📝 Practice with virtual funds (coming soon)." icon="📝" />} />
                  <Route path="/trading/debug" element={<ProtectedRoute requireDeveloper><PlaceholderPage title="Trading Debug Tools" description="🧪 Developer diagnostics for trading engine (dev only)." icon="🧪" /></ProtectedRoute>} />
                  <Route path="/trading/backtests" element={<React.Suspense fallback={<LoadingSpinner />}><BacktestsHistory /></React.Suspense>} />
                  <Route path="/trading/backtests/run" element={<ProtectedRoute requireDeveloper><React.Suspense fallback={<LoadingSpinner />}><BacktestRunner /></React.Suspense></ProtectedRoute>} />
                  {/* Strategy research & tooling (corrected paths) */}
                  <Route path="/strategy" element={<StrategyOverview />} />
                  <Route path="/strategy/builder" element={<React.Suspense fallback={<LoadingSpinner />}><StrategyBuilder /></React.Suspense>} />
                  <Route path="/strategy/backtesting" element={<React.Suspense fallback={<LoadingSpinner />}><StrategyBacktesting /></React.Suspense>} />
                  <Route path="/strategy/forward-test" element={<React.Suspense fallback={<LoadingSpinner />}><ForwardTesting /></React.Suspense>} />
                  <Route path="/strategy/monte-carlo" element={<React.Suspense fallback={<LoadingSpinner />}><MonteCarlo /></React.Suspense>} />
                  <Route path="/strategy/validation" element={<PlaceholderPage title="Strategy Validation" description="✅ Production readiness validation (coming soon)." icon="✅" />} />
                  <Route path="/strategy/debug" element={<ProtectedRoute requireDeveloper><PlaceholderPage title="Strategy Debug Console" description="🐛 Advanced performance & debugging (dev only)." icon="🐛" /></ProtectedRoute>} />
                  {/* Backwards compatibility redirects */}
                  <Route path="/trading/forward-testing" element={<Navigate to="/strategy/forward-test" replace />} />
                  <Route path="/trading/monte-carlo" element={<Navigate to="/strategy/monte-carlo" replace />} />

                  {/* Analytics (wrapped with FeatureBoundary) */}
                  <Route path="/analytics" element={<FeatureBoundary><AnalyticsOverview /></FeatureBoundary>} />
                  <Route path="/analytics/performance" element={<FeatureBoundary><AnalyticsPerformance /></FeatureBoundary>} />
                  <Route path="/analytics/risk" element={<FeatureBoundary><AnalyticsRisk /></FeatureBoundary>} />
                  <Route path="/analytics/market" element={<FeatureBoundary><AnalyticsMarket /></FeatureBoundary>} />
                  <Route path="/analytics/explorer" element={<ProtectedRoute requireDeveloper><PlaceholderPage title="Data Explorer" description="🔍 Advanced data exploration and custom queries (dev only)." icon="🔍" /></ProtectedRoute>} />

                  {/* Portfolio & Tax (wrapped with FeatureBoundary) */}
                  <Route path="/portfolio" element={<FeatureBoundary><PortfolioPage /></FeatureBoundary>} />
                  <Route path="/tax" element={<React.Suspense fallback={<LoadingSpinner />}><TaxOptimization /></React.Suspense>} />
                  {/* Tax subsection placeholders / redirects */}
                  <Route path="/tax/dashboard" element={<Navigate to="/tax" replace />} />
                  <Route path="/tax/contributions" element={<PlaceholderPage title="Contribution Tracker" description="💡 Track TFSA / RRSP contributions (coming soon)." icon="💡" />} />
                  <Route path="/tax/reporting" element={<PlaceholderPage title="Tax Reporting" description="📋 Generate Canada-focused tax reports (coming soon)." icon="📋" />} />

                  {/* Calendars */}
                  <Route path="/calendar/dev" element={<React.Suspense fallback={<LoadingSpinner />}><DevCalendar /></React.Suspense>} />
                  <Route path="/calendar/plan" element={<Navigate to="/calendar/dev" replace />} />
                  <Route path="/calendar" element={<Navigate to="/calendar/dev" replace />} />
                  <Route path="/calendar/ics" element={<React.Suspense fallback={<LoadingSpinner />}><IcsCalendar /></React.Suspense>} />

                  {/* Communication & AI */}
                  <Route path="/discord" element={<React.Suspense fallback={<LoadingSpinner />}><DiscordChat /></React.Suspense>} />
                  <Route path="/assistant" element={<React.Suspense fallback={<LoadingSpinner />}><AIAssistant /></React.Suspense>} />
                  <Route path="/chat/discord" element={<Navigate to="/discord" replace />} />
                  <Route path="/ai/assistant" element={<Navigate to="/assistant" replace />} />

                  {/* Milestones & Metrics */}
                  <Route path="/milestones" element={<React.Suspense fallback={<LoadingSpinner />}><MilestoneSystem /></React.Suspense>} />
                  <Route path="/milestones-old" element={<React.Suspense fallback={<LoadingSpinner />}><MilestoneTracker /></React.Suspense>} />
                  <Route path="/metrics" element={<React.Suspense fallback={<LoadingSpinner />}><MetricsPage /></React.Suspense>} />
                  <Route path="/master" element={<ProtectedRoute requireDeveloper><React.Suspense fallback={<LoadingSpinner />}><MasterDashboard /></React.Suspense></ProtectedRoute>} />

                  <Route path="*" element={<div className="flex items-center justify-center min-h-screen"><div className="text-center glass-card p-8 max-w-md mx-4"><h1 className="text-4xl font-bold text-white mb-4">404 - Page Not Found</h1><p className="text-white/80 mb-8">The page you're looking for doesn't exist.</p><a href="/" className="btn-primary inline-block">Go Home</a></div></div>} />
                </Routes>
            </LayoutShell>
          </main>
        </div>
      </ServiceHealthProvider>
    </TradingEnvProvider>
  );
};

export default App;
