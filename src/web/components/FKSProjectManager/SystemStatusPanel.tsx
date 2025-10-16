import { CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import React from 'react';

import type { SystemStatus } from '../../types/projectManager';

interface Props { status: SystemStatus; checking: boolean; onRefresh: () => void; }

const StatusItem: React.FC<{ label: string; ok: boolean | null }> = ({ label, ok }) => (
  <div className="flex items-center justify-between py-1 text-sm">
    <span className="text-white/80">{label}</span>
    {ok === null ? <span className="text-xs text-white/50">--</span> : ok ? <CheckCircle className="w-4 h-4 text-green-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
  </div>
);

const SystemStatusPanel: React.FC<Props> = ({ status, checking, onRefresh }) => (
  <div className="glass-card p-6 h-full flex flex-col">
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-lg font-semibold">System Status</h3>
      <button onClick={onRefresh} disabled={checking} className="btn-secondary flex items-center gap-1 text-sm px-3 py-1">
        <RefreshCw className={`w-4 h-4 ${checking ? 'animate-spin' : ''}`} />
        {checking ? 'Checking' : 'Refresh'}
      </button>
    </div>
    <div className="space-y-1">
      <StatusItem label="Build API" ok={status.buildApi} />
      <StatusItem label="Docker Services" ok={status.dockerServices} />
    </div>
    {!status.buildApi && (
      <div className="mt-4 text-xs text-amber-300/80">Build API offline. Start backend at port 4000 to enable actions.</div>
    )}
  </div>
);

export default SystemStatusPanel;
