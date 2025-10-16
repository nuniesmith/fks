import React, { useEffect, useState } from 'react';

import type { ContractTestSpec } from '../../hooks/useServiceContractTests';

interface Props { serviceId: string; specs: ContractTestSpec[]; onUpdate: (updated: ContractTestSpec[]) => void; }

const keyFor = (serviceId: string) => `fks_contract-overrides-${serviceId}`;

const LatencyBudgetEditor: React.FC<Props> = ({ serviceId, specs, onUpdate }) => {
  const [open, setOpen] = useState(false);
  const [local, setLocal] = useState<Record<string, { maxLatencyMs?: number; hardLatencyBudgetMs?: number; slaMs?: number }>>({});

  useEffect(() => {
    try { const raw = localStorage.getItem(keyFor(serviceId)); if (raw) setLocal(JSON.parse(raw)); } catch {}
  }, [serviceId]);

  const apply = () => {
    const updated = specs.map(s => ({ ...s, ...local[s.id] }));
    onUpdate(updated);
    try { localStorage.setItem(keyFor(serviceId), JSON.stringify(local)); } catch {}
    setOpen(false);
  };

  const updateField = (id: string, field: keyof typeof local[string]) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value ? Number(e.target.value) : undefined;
    setLocal(prev => ({ ...prev, [id]: { ...prev[id], [field]: value } }));
  };

  return (
    <div className="relative">
      <button onClick={()=>setOpen(o=>!o)} className="text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20">Latency Budgets</button>
      {open && (
        <div className="absolute z-20 mt-2 w-[420px] right-0 bg-slate-900/95 border border-white/10 rounded shadow-xl p-3 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-white/70">Runtime Latency / SLA Overrides</h4>
            <button onClick={()=>setOpen(false)} className="text-white/40 hover:text-white/70 text-xs">✕</button>
          </div>
          <div className="max-h-72 overflow-auto space-y-2 pr-1">
            {specs.map(spec => {
              const ov = local[spec.id] || {};
              return (
                <div key={spec.id} className="bg-white/5 rounded p-2 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-white/60">
                    <span className="font-mono text-white/80">{spec.id}</span>
                    <span className="text-white/40">{spec.label}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[10px]">
                    <label className="flex flex-col gap-1">
                      <span className="text-white/40">Soft Max</span>
                      <input type="number" className="bg-slate-800/80 rounded px-2 py-1 focus:outline-none focus:ring ring-blue-500/40" value={ov.maxLatencyMs ?? ''} placeholder={spec.maxLatencyMs?.toString() || ''} onChange={updateField(spec.id, 'maxLatencyMs')} />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-white/40">Hard Budget</span>
                      <input type="number" className="bg-slate-800/80 rounded px-2 py-1 focus:outline-none focus:ring ring-blue-500/40" value={ov.hardLatencyBudgetMs ?? ''} placeholder={spec.hardLatencyBudgetMs?.toString() || ''} onChange={updateField(spec.id, 'hardLatencyBudgetMs')} />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-white/40">SLA</span>
                      <input type="number" className="bg-slate-800/80 rounded px-2 py-1 focus:outline-none focus:ring ring-blue-500/40" value={ov.slaMs ?? ''} placeholder={spec.slaMs?.toString() || ''} onChange={updateField(spec.id, 'slaMs')} />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-end gap-2 text-[11px]">
            <button onClick={()=>{ try { localStorage.removeItem(keyFor(serviceId)); } catch {}; setLocal({}); }} className="px-2 py-1 rounded bg-white/5 hover:bg-white/10">Reset</button>
            <button onClick={apply} className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium">Apply</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default LatencyBudgetEditor;
