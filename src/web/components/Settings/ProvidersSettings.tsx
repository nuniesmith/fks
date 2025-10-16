import React, { useEffect, useMemo, useState } from 'react'

import { getData, postData } from '../../services/dataClient'

interface ProviderInfo {
  id: string
  name: string
  asset_types: string[]
  requires_key: boolean
  enabled?: boolean
}

interface KeyStatus { provider: string; exists: boolean }

const providerQuickTests: Record<string, { label: string; run: (id: string) => Promise<{ ok: boolean; msg: string }> }> = {
  yfinance: {
    label: 'Test Daily (AAPL)',
    run: async () => {
  const r = await getData<any>(`/daily`, { provider: 'yfinance', symbol: 'AAPL', period: '5d' })
      const c = Array.isArray(r?.data) ? r.data.length : (r?.count || 0)
      return { ok: c > 0, msg: `Returned ${c} rows` }
    }
  },
  binance: {
    label: 'Test Klines (BTCUSDT)',
    run: async () => {
  const r = await getData<any>(`/crypto/binance/klines`, { symbol: 'BTCUSDT', interval: '1m', limit: 5 })
      const c = Array.isArray(r?.data) ? r.data.length : (r?.count || 0)
      return { ok: c > 0, msg: `Returned ${c} candles` }
    }
  },
  polygon: {
    label: 'Test Aggregates',
    run: async () => {
  const r = await getData<any>(`/providers/polygon/aggs`, { ticker: 'AAPL', timespan: 'day', range: 1 })
      const c = Array.isArray(r?.data) ? r.data.length : (r?.count || 0)
      return { ok: c > 0, msg: `Returned ${c} bars` }
    }
  },
  alpha_vantage: {
    label: 'Test News',
    run: async () => {
  const r = await getData<any>(`/providers/alpha/news`, { symbol: 'AAPL', limit: 3 })
      const c = Array.isArray(r?.data) ? r.data.length : (r?.count || 0)
      return { ok: c > 0, msg: `Returned ${c} items` }
    }
  },
  coinmarketcap: {
    label: 'Test Quotes',
    run: async () => {
  const r = await getData<any>(`/providers/cmc/quotes`, { symbol: 'BTC' })
      const ok = !!r?.raw
      return { ok, msg: ok ? 'Got quotes' : 'No data' }
    }
  },
  polygon_flatfiles: {
    label: 'Test Flat Files',
    run: async () => {
      // Try a tiny list under a common prefix and sample if any result
      const prefix = 'us_stocks_sip/minute_v1/2024/03/'
  const list = await getData<any>(`/providers/polygon/flatfiles/list`, { prefix, max: 5 })
      const c = Array.isArray(list?.items) ? list.items.length : 0
      if (c === 0) return { ok: false, msg: 'No files under prefix (or no access)' }
      const first = list.items[0]?.key
      if (!first) return { ok: true, msg: `Listed ${c} objects` }
  const sample = await getData<any>(`/providers/polygon/flatfiles/sample`, { key: first, n: 2 })
      const lines = Array.isArray(sample?.lines) ? sample.lines.length : 0
      return { ok: lines > 0, msg: `Listed ${c}, sampled ${lines} lines` }
    }
  },
  futures_beta: {
    label: 'Check Status',
    run: async () => {
  const r = await getData<any>(`/futures/beta/status`)
      const ok = !!(r?.rest || r?.ws || r?.api_key_masked)
      return { ok, msg: ok ? 'Configured' : 'Not configured' }
    }
  }
}

const ProvidersSettings: React.FC = () => {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [keys, setKeys] = useState<Record<string, KeyStatus>>({})
  const [provider, setProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [secret, setSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, string>>({})
  const [savedInfo, setSavedInfo] = useState<{ exists: boolean; masked?: string } | null>(null)

  useEffect(() => {
  getData<any>('/providers').then(j => setProviders(j.providers || [])).catch(() => setProviders([]))
  getData<any>('/providers/keys').then(j => {
      const rec: Record<string, KeyStatus> = {}
      ;(j.keys || []).forEach((k: any) => { rec[k.provider] = { provider: k.provider, exists: !!k.exists } })
      setKeys(rec)
    }).catch(() => setKeys({}))
  }, [])

  const requiresKey = useMemo(() => {
    const p = providers.find(p => p.id === provider)
    return !!p?.requires_key
  }, [providers, provider])

  useEffect(() => {
    async function loadSaved() {
      setSavedInfo(null)
      if (!provider) return
      try {
  const j = await getData<any>(`/providers/${encodeURIComponent(provider)}/key`)
        setSavedInfo({ exists: !!j?.exists, masked: j?.masked })
      } catch { setSavedInfo(null) }
    }
    loadSaved()
  }, [provider])

  async function save() {
    setSaving(true); setMsg(null); setErr(null)
    try {
      if (!provider || !apiKey) throw new Error('Provider and API key required')
      await postData(`/providers/${encodeURIComponent(provider)}/key`, { api_key: apiKey, secret: secret || undefined })
      setMsg('Saved')
      setKeys(k => ({ ...k, [provider]: { provider, exists: true } }))
      setApiKey(''); setSecret('')
      // Refresh saved info
      try {
        const j = await getData<any>(`/providers/${encodeURIComponent(provider)}/key`)
        setSavedInfo({ exists: !!j?.exists, masked: j?.masked })
      } catch {}
    } catch (e: any) {
      setErr(e?.message || 'Failed to save key')
    } finally { setSaving(false) }
  }

  async function runTest(p: ProviderInfo) {
    setTesting(p.id); setErr(null)
    try {
      const t = providerQuickTests[p.id]
      if (!t) throw new Error('No quick test implemented')
      const r = await t.run(p.id)
      setTestResult(s => ({ ...s, [p.id]: r.msg }))
      if (!r.ok) throw new Error(r.msg)
    } catch (e: any) {
      setErr(e?.message || 'Test failed')
    } finally { setTesting(null) }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h1 className="text-2xl font-bold text-white mb-1">Market Data Providers</h1>
        <p className="text-sm text-gray-400">Enter API keys securely; keys are stored server-side and can be encrypted-at-rest via env secret.</p>
      </div>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-4">
        <h3 className="text-lg font-semibold text-white">Add/Update Key</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="text-sm text-gray-300">
            <div>Provider</div>
            <select value={provider} onChange={e=>setProvider(e.target.value)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white">
              <option value="">Select provider…</option>
              {providers.map(p => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}
            </select>
          </label>
          <label className="text-sm text-gray-300">
            <div>API Key</div>
            <input value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="sk-…" className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
          </label>
          <label className="text-sm text-gray-300">
            <div>Secret (optional)</div>
            <input value={secret} onChange={e=>setSecret(e.target.value)} placeholder="secret" className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
          </label>
        </div>
        <button onClick={save} disabled={saving || !provider || !apiKey} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-60">{saving ? 'Saving…' : 'Save Key'}</button>
        {msg && <div className="text-green-400 text-sm mt-2">{msg}</div>}
        {err && <div className="text-red-400 text-sm mt-2">{err}</div>}
        {savedInfo && (
          <div className="text-xs text-gray-300 mt-2">
            Saved status: {savedInfo.exists ? 'present' : 'missing'}{savedInfo.masked ? ` (masked: ${savedInfo.masked})` : ''}
          </div>
        )}
      </div>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-3">Providers</h3>
        {providers.length === 0 && <div className="text-sm text-gray-400">No providers available.</div>}
        {providers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-300">
                <tr>
                  <th className="py-2 text-left">Provider</th>
                  <th className="py-2 text-left">Assets</th>
                  <th className="py-2 text-left">Key</th>
                  <th className="py-2 text-left">Quick Test</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {providers.map(p => (
                  <tr key={p.id} className="text-white">
                    <td className="py-2 pr-4">{p.name} <span className="text-xs text-gray-400">({p.id})</span></td>
                    <td className="py-2 pr-4">{(p.asset_types||[]).join(', ')}</td>
                    <td className="py-2 pr-4">{keys[p.id]?.exists ? '✅ stored' : (p.requires_key ? '—' : 'n/a')}</td>
                    <td className="py-2 pr-4">
                      {providerQuickTests[p.id] ? (
                        <button onClick={() => runTest(p)} disabled={!!testing} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded">
                          {testing === p.id ? 'Testing…' : providerQuickTests[p.id].label}
                        </button>
                      ) : <span className="text-gray-400">—</span>}
                      {testResult[p.id] && <div className="text-xs text-gray-300 mt-1">{testResult[p.id]}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default ProvidersSettings
