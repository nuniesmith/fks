import React, { useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { useUser } from '../../../context/UserContext';
import { APP_SECTIONS } from '../../../types/layout';

import type { AppSection } from '../../../types/layout';
const SectionSidebar: React.FC<{ isDevelopment: boolean }> = ({ isDevelopment }) => {
  const location = useLocation();
  const { isDeveloper } = useUser();
  const current = useMemo(() => {
    const path = location.pathname;
    const candidates = APP_SECTIONS.filter(s => s.isActive || s.id === 'overview_milestones');
    let match: AppSection | undefined = candidates.find(s => path === s.path || path.startsWith(s.path + '/'));
    if (!match) match = candidates.find(s => (s.subSections || []).some(sub => sub.path === path || path.startsWith(sub.path + '/')));
    if (!match) return undefined;
    const filteredSubs = (match.subSections || []).filter(sub => {
      const envOk = sub.environment === 'both' || (sub.environment === 'development' && isDevelopment);
      const roleOk = !sub.isDeveloperTool || isDeveloper;
      return envOk && roleOk;
    });
    return { ...match, subSections: filteredSubs } as AppSection;
  }, [location.pathname, isDeveloper, isDevelopment]);
  if (!current || !current.subSections || current.subSections.length === 0) return null;
  const activePath = location.pathname;
  return (
    <aside className="sticky top-20 space-y-3">
      <div className="bg-gray-900/70 border border-gray-800 rounded-lg p-4">
        <div className="text-sm uppercase tracking-wide text-gray-400 mb-2">{current.title}</div>
        <nav className="space-y-1">
          <Link to={current.path} className={`block px-3 py-2 rounded-md text-sm transition-colors ${activePath === current.path ? 'bg-blue-500/15 text-blue-300 border border-blue-500/30' : 'text-gray-200 hover:text-white hover:bg-white/5'}`}>Overview</Link>
          {current.subSections!.map(sub => (
            <Link key={sub.id} to={sub.path} className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${activePath === sub.path ? 'bg-blue-500/15 text-blue-300 border border-blue-500/30' : 'text-gray-200 hover:text-white hover:bg-white/5'}`}>
              <span className="text-base">{sub.icon}</span><span>{sub.title}</span>
            </Link>
          ))}
        </nav>
      </div>
    </aside>
  );
};
export default SectionSidebar;
