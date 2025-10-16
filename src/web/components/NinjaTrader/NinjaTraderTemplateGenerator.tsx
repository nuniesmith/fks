import { Plus, X } from 'lucide-react';
import React, { useState } from 'react';

import { generateTemplate } from '../../api/services';

interface LogEntry { timestamp: string; message: string; type: 'info' | 'error' | 'success' | 'warning'; }
interface Props { onLog: (e: LogEntry) => void; disabled?: boolean; }

const NT_TEMPLATE_TYPES = [
  { id: 'indicator', label: 'Indicator' },
  { id: 'strategy', label: 'Strategy' },
  { id: 'marketdata', label: 'Market Data' }
];

const NinjaTraderTemplateGenerator: React.FC<Props> = ({ onLog, disabled }) => {
  const [open, setOpen] = useState(false);
  const [fileName, setFileName] = useState('MyStrategy');
  const [type, setType] = useState(NT_TEMPLATE_TYPES[1].id);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!fileName) return;
    setLoading(true);
    onLog({ timestamp: new Date().toLocaleTimeString(), message: `Generating NinjaTrader ${type} template…`, type: 'info' });
    try {
      await generateTemplate(type, fileName);
      onLog({ timestamp: new Date().toLocaleTimeString(), message: `Template ${fileName} created`, type: 'success' });
      setOpen(false);
    } catch (e: any) {
      onLog({ timestamp: new Date().toLocaleTimeString(), message: `Template failed: ${e.message}`, type: 'error' });
    } finally { setLoading(false); }
  };

  if (!open) {
    return <button disabled={disabled} onClick={() => setOpen(true)} className="w-full btn-secondary flex items-center justify-center gap-2 disabled:opacity-50 text-sm"><Plus className="w-4 h-4" /> New NinjaTrader Template</button>;
  }

  return (
    <div className="mt-2 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold text-sm">Generate NinjaTrader Template</h4>
        <button onClick={() => setOpen(false)} className="text-white/50 hover:text-white/80"><X className="w-4 h-4" /></button>
      </div>
      <div className="space-y-2">
        <label className="block text-xs uppercase tracking-wide text-white/60">Type</label>
        <select value={type} onChange={e => setType(e.target.value)} className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-sm focus:outline-none">
          {NT_TEMPLATE_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
      </div>
      <div className="space-y-2">
        <label className="block text-xs uppercase tracking-wide text-white/60">File Name</label>
        <input value={fileName} onChange={e => setFileName(e.target.value)} placeholder="MyStrategy" className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-sm focus:outline-none" />
      </div>
      <button onClick={submit} disabled={loading || disabled} className="btn-primary w-full text-sm disabled:opacity-50">{loading ? 'Generating…' : 'Create'}</button>
    </div>
  );
};

export default NinjaTraderTemplateGenerator;
