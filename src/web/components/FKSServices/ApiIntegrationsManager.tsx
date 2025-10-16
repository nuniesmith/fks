import React, { useEffect, useState } from 'react'

type Provider = {
  id: string
  name: string
  asset_types: string[]
  requires_key: boolean
}

type SavedKey = { provider: string; exists: boolean }

export default function ApiIntegrationsManager() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [keys, setKeys] = useState<Record<string, SavedKey>>({})
  const [form, setForm] = useState<{ provider: string; apiKey: string; secret?: string }>({ provider: '', apiKey: '' })
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    // Attempt to load from backend; otherwise show empty state
    fetch('/data/providers').then(async r => {
      if (!r.ok) throw new Error('providers endpoint missing')
      const j = await r.json()
      setProviders(j.providers || [])
    }).catch(() => setProviders([]))

    fetch('/data/providers/keys').then(async r => {
      if (!r.ok) throw new Error('keys endpoint missing')
      const j = await r.json()
      const rec: Record<string, SavedKey> = {}
      ;(j.keys || []).forEach((k: any) => { rec[k.provider] = { provider: k.provider, exists: !!k.exists } })
      setKeys(rec)
    }).catch(() => setKeys({}))
  }, [])

  async function saveKey() {
    setLoading(true); setErr(null); setMsg(null)
    try {
      if (!form.provider || !form.apiKey) throw new Error('Provider and API key required')
      const res = await fetch(`/data/providers/${encodeURIComponent(form.provider)}/key`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: form.apiKey, secret: form.secret || null })
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setMsg('API key saved')
      setKeys(k => ({ ...k, [form.provider]: { provider: form.provider, exists: true } }))
      setForm({ provider: form.provider, apiKey: '' })
    } catch (e: any) {
      setErr(e?.message || 'Failed to save API key (endpoint may be missing)')
    } finally { setLoading(false) }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">API Integrations</h3>
        <div className="text-xs text-gray-400">Store keys securely; sources power assets by type</div>
      </div>

      {providers.length === 0 && (
        <div className="text-sm text-gray-400">No providers loaded (backend endpoint not implemented). Add once available.</div>
      )}

      {providers.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-gray-300">
              <tr>
                <th className="py-2 text-left">Provider</th>
                <th className="py-2 text-left">Asset Types</th>
                <th className="py-2 text-left">Key</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {providers.map(p => (
                <tr key={p.id} className="text-white">
                  <td className="py-2 pr-4">{p.name}</td>
                  <td className="py-2 pr-4">{p.asset_types.join(', ')}</td>
                  <td className="py-2 pr-4">{keys[p.id]?.exists ? '✅ stored' : (p.requires_key ? '—' : 'n/a')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <label className="text-sm text-gray-300">
          <div>Provider ID</div>
          <input value={form.provider} onChange={e=>setForm({ ...form, provider: e.target.value })} placeholder="binance" className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
        </label>
        <label className="text-sm text-gray-300">
          <div>API Key</div>
          <input value={form.apiKey} onChange={e=>setForm({ ...form, apiKey: e.target.value })} placeholder="sk-..." className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
        </label>
        <label className="text-sm text-gray-300">
          <div>Secret (optional)</div>
          <input value={form.secret || ''} onChange={e=>setForm({ ...form, secret: e.target.value })} placeholder="secret" className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
        </label>
      </div>
      <div>
        <button onClick={saveKey} disabled={loading} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-60">Save Key</button>
      </div>
      {msg && <div className="text-green-400 text-sm">{msg}</div>}
      {err && <div className="text-red-400 text-sm">{err}</div>}
    </div>
  )
}
