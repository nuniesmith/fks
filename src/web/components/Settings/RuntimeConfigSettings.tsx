import React, { useEffect, useState } from 'react';

import { fetchMergedConfig, updateRuntimeOverrides, guessSensitive } from '../../services/configManager';

interface KVEdit { key: string; value: string; }

const RuntimeConfigSettings: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<any>(null);
  const [overrides, setOverrides] = useState<Record<string,string>>({});
  const [filter, setFilter] = useState('');
  const [entries, setEntries] = useState<KVEdit[]>([]);
  const [msg, setMsg] = useState<string|null>(null);
  const [err, setErr] = useState<string|null>(null);

  async function load() {
    setLoading(true); setErr(null);
    try {
      const data = await fetchMergedConfig();
      setConfig(data.config);
      setOverrides(data.overrides || {});
      const kv = Object.entries(data.overrides || {}).map(([k,v]) => ({ key: k, value: v }));
      setEntries(kv.sort((a,b)=>a.key.localeCompare(b.key)));
    } catch (e:any) { setErr(e.message||'Failed to load'); }
    finally { setLoading(false); }
  }

  useEffect(()=>{ load(); }, []);

  function updateEntry(idx: number, key: string, value: string) {
    setEntries(prev => prev.map((e,i)=> i===idx ? { key, value } : e));
  }

  function addRow() {
    setEntries(e => [...e, { key: '', value: '' }]);
  }

  async function save() {
    setSaving(true); setMsg(null); setErr(null);
    try {
      const payload: Record<string,string> = {};
      for (const row of entries) {
        if (!row.key.trim()) continue;
        payload[row.key.trim()] = row.value;
      }
      const res = await updateRuntimeOverrides(payload);
      setMsg(`Updated ${res.count} keys`);
      await load();
    } catch (e:any) {
      setErr(e.message||'Failed to save');
    } finally { setSaving(false); }
  }

  const shown = entries.filter(e => !filter || e.key.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Runtime Config & Environment Overrides</h3>
        <button onClick={load} disabled={loading} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">{loading ? 'Loading…' : 'Reload'}</button>
      </div>
      <p className="text-xs text-gray-400">Ephemeral overrides (process-level). Persist to real config / secrets separately. Sensitive values are not masked here; avoid storing production secrets in browser local storage.</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
        <div><span className="text-gray-400">Mode:</span> <span className="text-white">{config?.environment?.mode}</span></div>
        <div><span className="text-gray-400">Log Level:</span> <span className="text-white">{config?.logging}</span></div>
        <div><span className="text-gray-400">Services:</span> <span className="text-white">{(config?.services||[]).length}</span></div>
      </div>
      <div className="flex gap-3 items-center">
        <input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="Filter keys" className="px-3 py-2 bg-gray-900 border border-gray-700 rounded text-sm text-white" />
        <button onClick={addRow} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm">Add Row</button>
        <button onClick={save} disabled={saving} className="px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-white text-sm">{saving ? 'Saving…' : 'Save'}</button>
      </div>
      {msg && <div className="text-green-400 text-xs">{msg}</div>}
      {err && <div className="text-red-400 text-xs">{err}</div>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-300">
              <th className="text-left py-2 pr-4">Key</th>
              <th className="text-left py-2 pr-4">Value</th>
              <th className="text-left py-2 pr-4 w-20">Sensitive</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {shown.map((row, idx) => (
              <tr key={idx} className="text-white">
                <td className="py-1 pr-4">
                  <input value={row.key} onChange={e=>updateEntry(idx, e.target.value, row.value)} placeholder="KEY_NAME" className="w-full px-2 py-1 bg-gray-900 border border-gray-700 rounded" />
                </td>
                <td className="py-1 pr-4">
                  <input value={row.value} onChange={e=>updateEntry(idx, row.key, e.target.value)} placeholder="value" className="w-full px-2 py-1 bg-gray-900 border border-gray-700 rounded" type={guessSensitive(row.key)?'password':'text'} />
                </td>
                <td className="py-1 pr-4 text-xs text-gray-400">{guessSensitive(row.key)?'yes':'no'}</td>
              </tr>
            ))}
            {shown.length===0 && <tr><td colSpan={3} className="py-4 text-center text-gray-500">No keys</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RuntimeConfigSettings;
