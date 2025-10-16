// Feature slice copy of legacy AppNavigation
import { Menu, X, BarChart3, ChevronDown } from 'lucide-react';
import React, { useRef, useState, useEffect, useLayoutEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useMilestones } from '../../../context/MilestoneContext';
import useAuthSession from '../../../hooks/useAuthSession';
import { useSecurityContext } from '../../../context/SecurityContext';
import { useTradingEnv } from '../../../context/TradingEnvContext';
import { useUser } from '../../../context/UserContext';

import type { AppSection } from '../../../types/layout';
import { getNavIcon } from '../config/icons';
import { useHorizontalScrollIndicators } from '../hooks/useHorizontalScrollIndicators';

interface AppNavigationProps { sections: AppSection[]; isDevelopment: boolean; enableKeyboardNav?: boolean; }
const AppNavigation: React.FC<AppNavigationProps> = ({ sections, isDevelopment, enableKeyboardNav }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [openMobile, setOpenMobile] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  // Local persistent keyboard navigation flag (used only if prop not supplied)
  const [internalKB, setInternalKB] = useState<boolean>(() => {
    try { const stored = localStorage.getItem('nav-keyboard'); return stored ? stored === '1' : false; } catch { return false; }
  });
  const effectiveKB = enableKeyboardNav !== undefined ? enableKeyboardNav : internalKB;
  // Persist which mobile section was last expanded
  useEffect(() => {
    const stored = sessionStorage.getItem('nav-mobile-open');
    if (stored) setOpenMobile(stored);
  }, []);
  useEffect(() => {
    if (openMobile) sessionStorage.setItem('nav-mobile-open', openMobile); else sessionStorage.removeItem('nav-mobile-open');
  }, [openMobile]);

  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user, logout: userLogout } = useUser();
  const security = useSecurityContext();
  const { userProgress } = useMilestones();
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  const { focus, setFocus, readiness } = useTradingEnv();
  const sessionInfo = useAuthSession(1000);
  // Auto-logout if token expired
  useEffect(() => {
    if (isAuthenticated && sessionInfo.valid === false && sessionInfo.accessToken) {
      // Grace period of 2s to allow silent refresh if in flight
      const t = setTimeout(async () => { try { await security.logout(); } catch {} userLogout(); navigate('/login'); }, 2000);
      return () => clearTimeout(t);
    }
  }, [isAuthenticated, sessionInfo.valid, sessionInfo.accessToken, security, userLogout, navigate]);
  useEffect(() => { const handler = (e: MouseEvent) => { if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) setUserMenuOpen(false); }; document.addEventListener('click', handler); return () => document.removeEventListener('click', handler); }, []);
  function CalendarIcon(props: any) { return (<svg {...props} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`h-4 w-4 ${props.className || ''}`}><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>); }
  const getIcon = (id: string) => (id === 'calendar' ? CalendarIcon : getNavIcon(id));
  const isActiveSection = (sectionPath: string, subPaths?: string[]) => location.pathname === sectionPath || (subPaths||[]).some(p => location.pathname === p);
  const [visibleCount, setVisibleCount] = useState(6);
  useEffect(() => { const compute = () => { const w = window.innerWidth; let n = 5; if (w >= 1024) n = 6; if (w >= 1280) n = 7; if (w >= 1536) n = 8; setVisibleCount(n); }; compute(); window.addEventListener('resize', compute); return () => window.removeEventListener('resize', compute); }, []);
  const navRef = useRef<HTMLElement | null>(null);
  const { containerRef: scrollStripRef, indicators } = useHorizontalScrollIndicators<HTMLDivElement>({ persistKey: 'nav-scroll-x' });
  // Optional keyboard roving focus (feature flag)
  const [focusIndex, setFocusIndex] = useState(-1);
  const visibleSections = sections.slice(0, visibleCount);
  useEffect(() => { if (!effectiveKB) return; if (focusIndex >= visibleSections.length) setFocusIndex(visibleSections.length - 1); }, [focusIndex, visibleSections, effectiveKB]);
  useEffect(() => { if (!effectiveKB) return; if (focusIndex >= 0) { const el = scrollStripRef.current?.querySelectorAll('[data-nav-item]')[focusIndex] as HTMLElement | undefined; el?.focus(); } }, [focusIndex, effectiveKB]);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!effectiveKB) return;
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
    e.preventDefault();
    if (e.key === 'Home') { setFocusIndex(0); return; }
    if (e.key === 'End') { setFocusIndex(visibleSections.length -1); return; }
    setFocusIndex(i => {
      if (i === -1) return 0;
      if (e.key === 'ArrowLeft') return (i - 1 + visibleSections.length) % visibleSections.length;
      if (e.key === 'ArrowRight') return (i + 1) % visibleSections.length;
      return i;
    });
  };

  // Dynamically keep CSS var --nav-height in sync if navigation grows (e.g., wrapping / responsive changes)
  useLayoutEffect(() => {
    const update = () => {
      if (navRef.current) {
        const h = navRef.current.offsetHeight;
        document.documentElement.style.setProperty('--nav-height', h + 'px');
      }
    };
    update();
    window.addEventListener('resize', update);
    let ro: any = null;
    try {
      const R = (window as any).ResizeObserver;
      if (typeof R === 'function') {
        ro = new R(update);
        if (navRef.current) ro.observe(navRef.current);
      }
    } catch {}
    return () => { window.removeEventListener('resize', update); try { ro && ro.disconnect && ro.disconnect(); } catch {} };
  }, []);

  useEffect(() => {
    // Prevent background scroll when mobile menu open
    if (isMenuOpen) { document.body.style.overflow = 'hidden'; } else { document.body.style.overflow = ''; }
    return () => { document.body.style.overflow = ''; };
  }, [isMenuOpen]);

  // Auto-scroll expanded mobile section into view
  useEffect(() => {
    if (!isMenuOpen || !openMobile) return;
    const el = document.getElementById(`mobile-sec-${openMobile}`);
    if (el) requestAnimationFrame(() => { el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); });
  }, [openMobile, isMenuOpen]);

  // Filter logic (mobile only currently)
  const filteredSections = sections.filter(sec => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    if (sec.title.toLowerCase().includes(q)) return true;
    return sec.subSections?.some(s => s.title.toLowerCase().includes(q));
  });

  return (
  <>
    <nav ref={navRef} className="fixed top-0 left-0 right-0 z-50 bg-gray-950/85 supports-[backdrop-filter]:backdrop-blur-xl border-b border-blue-900/40 shadow-[0_2px_6px_rgba(0,0,0,0.6)]" aria-label="Primary Navigation">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center min-h-16 py-2">
          <div className="flex items-center">
            <Link to="/" className="flex items-center space-x-3">
              <div className="bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-2 rounded-lg border border-white/10"><BarChart3 className="h-6 w-6" /></div>
              <div><span className="text-xl font-bold text-white">FKS</span>{isDevelopment && (<span className="ml-2 px-2 py-1 bg-yellow-500/20 text-yellow-300 text-xs rounded-full border border-yellow-500/40">DEV</span>)}</div>
            </Link>
            <button type="button" onClick={() => { if (focus === 'simulation') { if (readiness.ok) setFocus('live'); } else setFocus('simulation'); }} title={focus === 'simulation' ? (readiness.ok ? 'Switch to Live' : 'Complete dataset split + assign strategies to enable Live') : 'Switch to Simulation'} className={`ml-3 px-2 py-1 rounded-full text-[10px] uppercase tracking-wide border transition-opacity ${focus === 'simulation' ? 'bg-green-500/20 text-green-300 border-green-500/40' : 'bg-red-500/20 text-red-300 border-red-500/40'} ${focus === 'simulation' && !readiness.ok ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90'}`} disabled={focus === 'simulation' && !readiness.ok}>{focus === 'simulation' ? 'Sim' : 'Live'}</button>
          </div>
          <div className="hidden md:flex items-center gap-x-1 flex-1 relative" onKeyDown={handleKeyDown}>
            {indicators.left && <div className="pointer-events-none absolute left-0 top-0 h-full w-6 bg-gradient-to-r from-gray-900/90 to-transparent" aria-hidden="true" />}
            <div ref={scrollStripRef} className="flex items-center gap-x-1 flex-nowrap overflow-x-auto no-scrollbar pr-2" aria-label="Primary top level" tabIndex={effectiveKB ? 0 : undefined}>
              {visibleSections.map((section, idx) => { const Icon = getIcon(section.id); const sub = section.subSections?.map(s=>s.path)||[]; const active = isActiveSection(section.path, sub); return (
                <div key={section.id} className="relative group">
                  <Link
                    to={section.path}
                    data-nav-item
                    aria-current={active ? 'page' : undefined}
                    className={`focus:outline-none ${effectiveKB ? 'focus-visible:ring-2 focus-visible:ring-blue-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900' : ''} flex items-center px-2.5 py-2 rounded-md text-sm font-medium transition-colors ${active ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'text-gray-200 hover:text-blue-300 hover:bg-blue-500/10 border border-transparent'}`}
                    tabIndex={effectiveKB ? (focusIndex === idx ? 0 : -1) : undefined}
                    onFocus={() => { if (effectiveKB) setFocusIndex(idx); }}
                  >
                    <Icon className="h-4 w-4 mr-1.5" /> {section.title}
                  </Link>
                  {section.subSections && section.subSections.length>0 && (
        <div className="absolute left-0 mt-1 w-64 bg-gray-900/95 backdrop-blur rounded-md shadow-lg border border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50" aria-label={`${section.title} submenu`}>
                      <div className="py-2">
                        {section.subSections.map(subItem => (
          <Link key={subItem.id} to={subItem.path} className={`block px-4 py-2 text-sm transition-colors ${location.pathname === subItem.path ? 'bg-blue-500/10 text-blue-300' : 'text-gray-200 hover:bg-white/5 hover:text-white'}`}>
                            <div className="flex items-center"><span className="text-lg mr-2">{subItem.icon}</span><div><div className="font-medium">{subItem.title}</div>{subItem.isDeveloperTool && (<div className="text-xs text-orange-400">Developer Tool</div>)}</div></div>
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ); })}
            </div>
            {indicators.right && <div className="pointer-events-none absolute right-0 top-0 h-full w-6 bg-gradient-to-l from-gray-900/90 to-transparent" aria-hidden="true" />}
            {sections.length > visibleCount && (
              <div className="relative group ml-1">
        <button className="flex items-center px-2.5 py-2 rounded-md text-sm font-medium text-gray-200 hover:text-blue-300 hover:bg-blue-500/10 border border-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/70 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900" aria-haspopup="true" aria-expanded="false">More</button>
        <div className="absolute right-0 mt-1 w-56 bg-gray-900/95 backdrop-blur rounded-md shadow-lg border border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50" aria-label="Overflow sections">
                  <div className="py-2">
                    {sections.slice(visibleCount).map(section => (
          <Link key={section.id} to={section.path} className={`block px-4 py-2 text-sm transition-colors ${isActiveSection(section.path, section.subSections?.map(s=>s.path)) ? 'bg-blue-500/10 text-blue-300' : 'text-gray-200 hover:bg-white/5 hover:text-white'}`}>
                        {section.title}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            )}
            <button
              type="button"
              aria-pressed={effectiveKB}
              onClick={() => { if (enableKeyboardNav === undefined) { setInternalKB(v=>{ const nv=!v; try{ localStorage.setItem('nav-keyboard', nv?'1':'0'); }catch{} return nv; }); } }}
              className="ml-2 hidden md:inline-flex items-center px-2 py-1 text-[11px] rounded-md border border-white/10 text-gray-300 hover:text-white hover:bg-white/5"
              title="Toggle enhanced keyboard navigation (persists locally)"
            >KB</button>
          </div>
          <div className="hidden md:flex items-center gap-3">
            {!isAuthenticated ? (
              <Link to="/login" className="px-3 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700">Login</Link>
            ) : (
              <div className="relative" ref={userMenuRef}>
                <button onClick={()=>setUserMenuOpen(v=>!v)} className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-white/5 border border-white/10">
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center text-xs font-bold">
                    {(user?.name || user?.email || '?').slice(0,1).toUpperCase()}
                  </div>
                  <span className="text-sm text-white/90 hidden lg:inline">{user?.name || user?.email}</span>
                  {sessionInfo.expiresAt && (
                    <span className={`ml-1 text-[10px] font-mono px-1.5 py-0.5 rounded ${sessionInfo.remainingSec < 60 ? 'bg-red-600/40 text-red-200' : 'bg-white/10 text-white/70'}`} title="Access token remaining (seconds)">{sessionInfo.remainingSec}s</span>
                  )}
                </button>
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-72 bg-gray-900/95 backdrop-blur border border-gray-700 rounded-md shadow-lg z-50 p-3">
                    <div className="text-sm text-white mb-2">Signed in as <span className="font-medium">{user?.email}</span></div>
                    <div className="mb-3">
                      <div className="flex items-center justify-between text-xs text-gray-300"><span>XP</span><span className="font-mono">{userProgress.totalXP.toLocaleString()}</span></div>
                      <div className="h-1.5 bg-white/10 rounded mt-1 overflow-hidden">
                        <div className="h-1.5 bg-blue-500 rounded" style={{width: `${Math.min(100,(userProgress.totalXP % 1000)/10)}%`}} />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Link to="/accounts" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">Accounts</Link>
                      <Link to="/assistant" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">AI Assistant</Link>
                      <Link to="/discord" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">Chat</Link>
                      <Link to="/milestones" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">Milestones</Link>
                      <Link to="/settings" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">Settings</Link>
                      <Link to="/calendar/dev" className="block text-sm text-gray-200 hover:text-white hover:bg-white/5 rounded px-2 py-1">Calendar</Link>
                      {isDevelopment && (
                        <Link to="/architecture" className="block text-sm text-orange-300 hover:text-white hover:bg-orange-500/10 rounded px-2 py-1">Architecture (dev)</Link>
                      )}
                    </div>
                    <div className="mt-2 text-[10px] text-gray-400 flex items-center justify-between">
                      {sessionInfo.expiresAt && <span>Expires {new Date(sessionInfo.expiresAt).toLocaleTimeString()}</span>}
                      {sessionInfo.refreshing && <span className="text-blue-300">refreshing…</span>}
                    </div>
                    <div className="border-t border-gray-700 mt-2 pt-2">
                      <button onClick={async()=>{try{await security.logout();}catch{} userLogout(); navigate('/login');}} className="w-full text-left text-sm text-red-300 hover:text-red-200 hover:bg-red-500/10 rounded px-2 py-1">Logout</button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="md:hidden"><button aria-label={isMenuOpen ? 'Close menu' : 'Open menu'} onClick={()=>setIsMenuOpen(!isMenuOpen)} className="text-gray-200 hover:text-blue-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/70 rounded">
            {isMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button></div>
        </div>
      </div>
    </nav>
    {/* Gradient fade below nav (desktop) */}
    <div className="hidden md:block fixed top-[var(--nav-height)] left-0 right-0 pointer-events-none z-40 bg-gradient-to-b from-gray-950/70 to-transparent" style={{height:'clamp(1.25rem,4vh,2.75rem)'}} aria-hidden="true" />
    {isMenuOpen && (
      <>
        <div className="fixed inset-0 top-[var(--nav-height)] bg-gray-950/70 backdrop-blur-sm z-40" onClick={()=>setIsMenuOpen(false)} aria-hidden="true" />
        <div className="fixed inset-x-0 top-[var(--nav-height)] z-50 md:hidden overflow-y-auto max-h-[calc(100vh-var(--nav-height))] p-4 pb-24 space-y-4 bg-gradient-to-b from-gray-950/95 to-gray-900/90 border-t border-blue-900/40 shadow-[0_8px_24px_-4px_rgba(0,0,0,0.6)]">
          <div className="sticky top-0 -mt-2 -mx-4 px-4 pb-3 pt-1 backdrop-blur-sm bg-gray-950/60 border-b border-white/5">
            <label className="block text-xs uppercase tracking-wide text-gray-400 mb-1">Search</label>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter sections" className="w-full px-3 py-2 rounded-md bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50" />
          </div>
          <nav aria-label="Mobile primary" className="space-y-3">
            {filteredSections.length === 0 && (<div className="text-center text-sm text-gray-400 py-4">No matches</div>)}
            {filteredSections.map(section=>{ const Icon=getIcon(section.id); const subSections=section.subSections||[]; const subPaths=subSections.map(s=>s.path); const active=isActiveSection(section.path,subPaths); const hasSubs=subSections.length>0; const expanded = openMobile===section.id; return (
              <div key={section.id} id={`mobile-sec-${section.id}`} className="border border-white/5 rounded-lg bg-white/2.5 backdrop-blur-sm transition-colors">
                <div className="flex items-center">
                  <Link to={section.path} onClick={()=>{ if(!hasSubs) setIsMenuOpen(false); }} className={`flex-1 flex items-center px-3 py-2 rounded-l-lg text-[15px] font-medium tracking-wide transition-colors ${active?'bg-blue-600/25 text-blue-300 ring-1 ring-inset ring-blue-500/40':'text-gray-200 hover:text-white hover:bg-white/5'}`}>
                    <Icon className="h-5 w-5 mr-3 opacity-90" /> {section.title}
                  </Link>
                  {hasSubs && (
                    <button aria-label={expanded?`Collapse ${section.title}`:`Expand ${section.title}`} onClick={()=> setOpenMobile(expanded?null:section.id)} className={`px-2 py-2 rounded-r-lg text-gray-300 hover:text-white hover:bg-white/10 transition-colors focus:outline-none`}>{<ChevronDown className={`h-4 w-4 transition-transform ${expanded?'rotate-180':''}`} />}</button>
                  )}
                </div>
                {hasSubs && (
                  <div style={{ maxHeight: expanded ? 400 : 0, transition: 'max-height 0.4s ease', overflow: 'hidden' }} aria-hidden={!expanded} className="border-t border-white/5">
                    <div className="px-2 pt-1 pb-2 space-y-1">
                      {subSections.filter(subItem => { if (!search.trim()) return true; return subItem.title.toLowerCase().includes(search.toLowerCase()); }).map(subItem => (
                        <Link key={subItem.id} to={subItem.path} onClick={()=>setIsMenuOpen(false)} className={`block px-3 py-1.5 rounded-md text-sm transition-colors ${location.pathname === subItem.path ? 'bg-blue-500/20 text-blue-300' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'}`}>
                          <span className="mr-2 text-base leading-none">{subItem.icon}</span>{subItem.title}{subItem.isDeveloperTool && (<span className="ml-2 text-xs text-orange-400">Dev</span>)}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ); })}
          </nav>
          <div className="pt-3 border-t border-gray-800/60">
            {!isAuthenticated ? (
              <Link to="/login" onClick={()=>setIsMenuOpen(false)} className="block w-full text-center px-4 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-500">Login</Link>
            ) : (
              <button onClick={async()=>{ setIsMenuOpen(false); try{ await security.logout(); }catch{} userLogout(); navigate('/login'); }} className="block w-full text-center px-4 py-2 rounded-md text-sm font-medium bg-gray-800/80 text-white hover:bg-gray-700/80 border border-gray-700">Logout</button>
            )}
          </div>
        </div>
      </>
    )}
    </>
  );
};
export default AppNavigation;
