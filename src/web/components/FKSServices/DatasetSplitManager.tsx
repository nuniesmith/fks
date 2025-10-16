import React, { useState } from 'react'

type Split = { train: number; val: number; test: number }

async function postJson<T>(url: string, body?: any): Promise<T> {
  const res = await fetch(url, { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export default function DatasetSplitManager() {
  const [split, setSplit] = useState<Split>({ train: 80, val: 10, test: 10 })
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const total = split.train + split.val + split.test

  function setPart(key: keyof Split, value: number) {
    const v = Math.max(0, Math.min(100, Math.round(value)))
    setSplit(s => ({ ...s, [key]: v }))
  }

  async function applySplit() {
    setLoading(true); setError(null); setMessage(null)
    try {
      if (total !== 100) throw new Error('Split must equal 100%')
      // Attempt backend call if available; otherwise show informative message
  await postJson<{ ok: boolean }>(`/api/data/dataset/split`, { train: split.train, val: split.val, test: split.test })
      setMessage('Dataset split applied')
    } catch (e: any) {
      setError(e?.message || 'Failed to apply split (endpoint may be missing)')
    } finally { setLoading(false) }
  }

  async function verify() {
    setLoading(true); setError(null); setMessage(null)
    try {
  const res = await postJson<{ ok: boolean; stats?: any }>(`/api/data/dataset/verify`, {})
      setMessage(res?.ok ? 'Dataset verified' : 'Verification completed')
    } catch (e: any) {
      setError(e?.message || 'Failed to verify dataset (endpoint may be missing)')
    } finally { setLoading(false) }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Dataset Split (TimescaleDB)</h3>
        <div className="text-xs text-gray-400">Target: 80/10/10</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <label className="text-sm text-gray-300">
          <div>Train %</div>
          <input type="number" value={split.train} onChange={e=>setPart('train', Number(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
        </label>
        <label className="text-sm text-gray-300">
          <div>Validation %</div>
          <input type="number" value={split.val} onChange={e=>setPart('val', Number(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
        </label>
        <label className="text-sm text-gray-300">
          <div>Test %</div>
          <input type="number" value={split.test} onChange={e=>setPart('test', Number(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
        </label>
      </div>
      <div className="mt-3 text-sm text-gray-400">Total: <b className={`text-white ${total!==100?'text-red-300':''}`}>{total}%</b></div>
      <div className="mt-4 flex gap-2">
        <button onClick={applySplit} disabled={loading || total!==100} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-60">Apply Split</button>
        <button onClick={verify} disabled={loading} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded disabled:opacity-60">Verify Dataset</button>
      </div>
      {message && <div className="mt-3 text-green-400 text-sm">{message}</div>}
      {error && <div className="mt-3 text-red-400 text-sm">{error}</div>}
      <div className="mt-4 text-xs text-gray-400">Data is stored in TimescaleDB; Redis is used for caching and low-latency access by GPU services.</div>
    </div>
  )
}
