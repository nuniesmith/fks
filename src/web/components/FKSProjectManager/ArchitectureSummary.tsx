import { RefreshCw } from 'lucide-react';
import React from 'react';

import type { SystemHealth } from '../../hooks/useServiceMonitoring';

const statusColor: Record<string,string> = {
  healthy: 'text-green-400',
  degraded: 'text-amber-400',
  critical: 'text-red-400'
};

interface Props { systemHealth: SystemHealth; isLoading: boolean; onRefresh: () => void; }

export const ArchitectureSummary: React.FC<Props> = ({ systemHealth, isLoading, onRefresh }) => {
  const { overallStatus, healthyServices, warningServices, errorServices, offlineServices, totalServices, lastUpdate } = systemHealth;
  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Architecture Snapshot</h3>
        <button onClick={onRefresh} disabled={isLoading} className="btn-secondary flex items-center gap-1 px-3 py-1 text-sm">
          <RefreshCw className={`w-4 h-4 ${isLoading? 'animate-spin':''}`} /> {isLoading? 'Refreshing':'Refresh'}
        </button>
      </div>
      <div className="flex flex-wrap gap-4 text-sm">
        <div><span className="text-white/50">Overall: </span><span className={`font-semibold ${statusColor[overallStatus]}`}>{overallStatus}</span></div>
        <div><span className="text-white/50">Services: </span>{healthyServices}/{totalServices} healthy</div>
        <div className="text-amber-300/80">Warnings: {warningServices}</div>
        <div className="text-red-300/80">Errors: {errorServices}</div>
        <div className="text-red-400/90">Offline: {offlineServices}</div>
      </div>
      <div className="text-xs text-white/40">Updated {lastUpdate.toLocaleTimeString()}</div>
    </div>
  );
};

export default ArchitectureSummary;
