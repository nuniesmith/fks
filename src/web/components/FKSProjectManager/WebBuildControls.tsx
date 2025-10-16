import { Play, RefreshCw } from 'lucide-react';
import React, { useState } from 'react';

/**
 * Simulated web build starter; replace with real API call when backend is available.
 */
async function startWebBuild(): Promise<{ success: boolean; error?: string }> {
  try {
    // Simulate network/build delay
    await new Promise(res => setTimeout(res, 1200));
    return { success: true };
  } catch (e: any) {
    return { success: false, error: e.message || 'unexpected error' };
  }
}

interface Props { onLog: (msg: string, type?: 'info'|'success'|'error'|'warning') => void; }

const WebBuildControls: React.FC<Props> = ({ onLog }) => {
  const [isBuilding, setIsBuilding] = useState(false);
  const handleBuild = async () => {
    setIsBuilding(true); onLog('Starting web build…');
    try {
      const res = await startWebBuild();
      if (res.success) onLog('Web build completed', 'success'); else onLog('Web build failed: '+(res.error||'unknown'), 'error');
    } catch (e:any) { onLog('Web build error: '+e.message, 'error'); }
    finally { setIsBuilding(false); }
  };
  return (
    <div className="glass-card p-6 space-y-4">
      <h3 className="text-lg font-semibold">Web Build</h3>
      <div className="flex gap-3">
        <button onClick={handleBuild} disabled={isBuilding} className="btn-primary text-sm flex items-center justify-center gap-2 disabled:opacity-50">
          {isBuilding ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} {isBuilding ? 'Building…' : 'Build UI'}
        </button>
      </div>
      <p className="text-xs text-white/60">Triggers an on-demand production build (simulated stub). Integrate with CI trigger or internal build API endpoint when available.</p>
    </div>
  );
};

export default WebBuildControls;
