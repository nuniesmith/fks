import { Plus, Trash2, Play, Pause, RefreshCw, Search } from 'lucide-react'
import React, { useEffect, useState } from 'react'

import { addActiveAsset, listActiveAssets, removeActiveAsset, setActiveAssetEnabled, startBackfillScheduler, stopBackfillScheduler, type ActiveAsset } from '../../services/ActiveAssetsApi'
import { listSources, listSymbols, type SourceInfo } from '../../services/DataApi'

const KNOWN_INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d']
const ASSET_TYPES = [
  { id: 'futures', label: 'Futures' },
  { id: 'crypto', label: 'Crypto' },
  { id: 'equity', label: 'Equity' },
]

export default function ActiveAssetsManager() {
  const [items, setItems] = useState<ActiveAsset[]>([])
  const [sources, setSources] = useState<Record<string, SourceInfo>>({})
  const [symbols, setSymbols] = useState<Array<{ symbol: string; name?: string; exchange?: string; asset_type?: string }>>([])
  const [symbolQuery, setSymbolQuery] = useState('')
  const [form, setForm] = useState({ source: 'yfinance', asset_type: 'futures', exchange: '', symbol: '', intervals: ['1d'] as string[], years: 2, full_history: false })
  const [loading, setLoading] = useState(false)
  const [schedRunning, setSchedRunning] = useState(true) // optimistic

  async function reload() {
    setLoading(true)
    try {
      const res = await listActiveAssets()
      setItems(res.items)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { reload() }, [])

  useEffect(() => {
    // Load available sources to drive dynamic options
    ;(async () => {
      try {
        const res = await listSources()
        setSources(res.sources || {})
      } catch {
        // ignore; UI will fallback to manual input
      }
    })()
  }, [])

  async function refreshSymbols(q?: string) {
    if (!form.source) return setSymbols([])
    try {
      const res = await listSymbols(form.source, { query: q || symbolQuery, limit: 50 })
      setSymbols(res.symbols || [])
    } catch {
      setSymbols([])
    }
  }

  useEffect(() => {
    // whenever source changes, clear symbol and refresh list
    setForm(f => ({ ...f, symbol: '' }))
    setSymbols([])
    if (form.source) refreshSymbols('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.source])

  async function onAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!form.symbol.trim()) return
    setLoading(true)
    try {
      await addActiveAsset({
        source: form.source,
        symbol: form.symbol.trim(),
        intervals: form.intervals,
        years: form.full_history ? undefined : form.years,
        full_history: form.full_history,
        asset_type: form.asset_type,
        exchange: form.exchange || undefined,
      })
      setForm({ ...form, symbol: '' })
      await reload()
    } finally { setLoading(false) }
  }

  async function onRemove(id: number) {
    setLoading(true)
    try { await removeActiveAsset(id); await reload() } finally { setLoading(false) }
  }

  async function onToggleEnable(it: ActiveAsset) {
    setLoading(true)
    try { await setActiveAssetEnabled(it.id, !it.enabled); await reload() } finally { setLoading(false) }
  }

  async function onStartStop() {
    setLoading(true)
    try {
      if (schedRunning) await stopBackfillScheduler(); else await startBackfillScheduler()
      setSchedRunning(!schedRunning)
    } finally { setLoading(false) }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Active Assets</h3>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white flex items-center gap-2" onClick={reload} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          <button className={`px-3 py-1.5 rounded text-white flex items-center gap-2 ${schedRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'}`} onClick={onStartStop} disabled={loading}>
            {schedRunning ? (<><Pause className="w-4 h-4"/> Stop</>) : (<><Play className="w-4 h-4"/> Start</>)}
          </button>
        </div>
      </div>

      <form onSubmit={onAdd} className="grid grid-cols-1 md:grid-cols-7 gap-3">
        <select value={form.asset_type} onChange={e => setForm({ ...form, asset_type: e.target.value })} className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
          {ASSET_TYPES.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}
        </select>
        <select value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white">
          {Object.values(sources).length > 0 ? (
            Object.values(sources).filter(s => !form.asset_type || (s.asset_types || []).includes(form.asset_type)).map(s => (
              <option key={s.id} value={s.id}>{s.name || s.id}</option>
            ))
          ) : (
            <>
              <option value="yfinance">Yahoo Finance</option>
              <option value="binance">Binance</option>
            </>
          )}
        </select>
        <div className="relative">
          <input value={symbolQuery} onChange={e => setSymbolQuery(e.target.value)} placeholder="Search symbol" className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white w-full pr-8" />
          <button type="button" onClick={() => refreshSymbols()} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300 hover:text-white">
            <Search className="w-4 h-4" />
          </button>
          <select value={form.symbol} onChange={e => setForm({ ...form, symbol: e.target.value })} className="mt-2 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white w-full">
            <option value="">Select symbol…</option>
            {symbols.map(s => (
              <option key={`${s.symbol}-${s.exchange || ''}`} value={s.symbol}>
                {s.symbol}{s.exchange ? ` • ${s.exchange}` : ''}{s.name ? ` — ${s.name}` : ''}
              </option>
            ))}
          </select>
        </div>
        <input value={form.exchange} onChange={e => setForm({ ...form, exchange: e.target.value })} placeholder="Exchange (optional)" className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white" />
        <select multiple value={form.intervals} onChange={e => setForm({ ...form, intervals: Array.from(e.target.selectedOptions).map(o => o.value) })} className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white h-10 md:h-auto">
          {KNOWN_INTERVALS.map(i => <option key={i} value={i}>{i}</option>)}
        </select>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-white text-sm"><input type="checkbox" checked={form.full_history} onChange={e => setForm({ ...form, full_history: e.target.checked })}/> Full history</label>
          {!form.full_history && (
            <input type="number" min={1} max={30} value={form.years} onChange={e => setForm({ ...form, years: Number(e.target.value) })} className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white w-24" title="Years of history" />
          )}
        </div>
        <button type="submit" disabled={loading || !form.symbol} className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-3 py-2 flex items-center gap-2 justify-center">
          <Plus className="w-4 h-4"/> Add
        </button>
      </form>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-300">
              <th className="py-2">Source</th>
              <th className="py-2">Symbol</th>
              <th className="py-2">Intervals</th>
              <th className="py-2">Window</th>
              <th className="py-2">Enabled</th>
              <th className="py-2">Progress</th>
              <th></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {items.map(it => (
              <tr key={it.id} className="text-white">
                <td className="py-2 pr-4">{it.source}{it.asset_type ? ` · ${it.asset_type}` : ''}{it.exchange ? ` · ${it.exchange}` : ''}</td>
                <td className="py-2 pr-4 font-mono">{it.symbol}</td>
                <td className="py-2 pr-4">{it.intervals.join(', ')}</td>
                <td className="py-2 pr-4">{it.full_history ? 'max' : `${it.years ?? 1}y`}</td>
                <td className="py-2 pr-4">
                  <button onClick={() => onToggleEnable(it)} className={`px-2 py-0.5 rounded text-xs ${it.enabled ? 'bg-green-700' : 'bg-gray-600'}`}>{it.enabled ? 'Enabled' : 'Disabled'}</button>
                </td>
                <td className="py-2 pr-4">
                  <div className="space-y-1">
                    {(it.progress || []).map(p => (
                      <div key={p.interval} className="text-xs text-gray-300">
                        <span className="font-mono">{p.interval}</span>: last={p.last_run ? new Date(p.last_run).toLocaleString() : 'never'} rows={p.last_rows ?? 0}
                      </div>
                    ))}
                  </div>
                </td>
                <td className="py-2 text-right">
                  <button onClick={() => onRemove(it.id)} className="text-red-400 hover:text-red-300"><Trash2 className="w-4 h-4"/></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
