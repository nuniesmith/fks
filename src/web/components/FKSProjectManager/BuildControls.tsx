import { Play, Package, Download, FilePlus } from 'lucide-react';
import React from 'react';

interface Props { canRun: boolean; isBuilding: boolean; isPackaging: boolean; onBuild: () => void; onPackage: () => void; onDownload: () => void; onOpenTemplate: () => void; }

const BuildControls: React.FC<Props> = ({ canRun, isBuilding, isPackaging, onBuild, onPackage, onDownload, onOpenTemplate }) => {
  const disabledBuild = !canRun || isBuilding;
  const disabledPackage = !canRun || isPackaging;
  return (
    <div className="glass-card p-6 space-y-4">
  <h3 className="text-lg font-semibold">Build & Package (Web)</h3>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <button onClick={onBuild} disabled={disabledBuild} className="btn-primary text-sm flex items-center justify-center gap-2 disabled:opacity-50"><Play className="w-4 h-4" /> {isBuilding ? 'Building…' : 'Build'}</button>
        <button onClick={onPackage} disabled={disabledPackage} className="btn-success text-sm flex items-center justify-center gap-2 disabled:opacity-50"><Package className="w-4 h-4" /> {isPackaging ? 'Packaging…' : 'Package'}</button>
        <button onClick={onDownload} disabled={!canRun} className="btn-secondary text-sm flex items-center justify-center gap-2 disabled:opacity-50"><Download className="w-4 h-4" /> Download</button>
        <button onClick={onOpenTemplate} disabled={!canRun} className="btn-warning text-sm flex items-center justify-center gap-2 disabled:opacity-50"><FilePlus className="w-4 h-4" /> Templates</button>
      </div>
      {!canRun && <div className="text-xs text-white/60">Actions disabled until Build API reachable.</div>}
    </div>
  );
};

export default BuildControls;
