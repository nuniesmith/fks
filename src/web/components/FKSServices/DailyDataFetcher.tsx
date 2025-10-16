import React, { useState } from 'react'

type DailyResponse = {
  meta?: { symbol?: string }
  count: number
  data: Array<{ date: string; open?: number; high?: number; low?: number; close?: number; volume?: number }>
}

const DailyDataFetcher: React.FC = () => {
  const [symbol, setSymbol] = useState('')
  const [period, setPeriod] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resp, setResp] = useState<DailyResponse | null>(null)

  async function fetchDaily() {
    setLoading(true); setError(null)
    try {
      const qs = new URLSearchParams()
      qs.set('symbol', symbol)
      if (start || end) {
        if (start) qs.set('start', start)
        if (end) qs.set('end', end)
      } else if (period) {
        qs.set('period', period)
      }
      const res = await fetch(`/data/daily?${qs.toString()}`)
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const j = (await res.json()) as DailyResponse
      setResp(j)
    } catch (e: any) {
      setError(e?.message || 'Request failed')
    } finally { setLoading(false) }
  }

  const rows = resp?.data || []

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-white">Quick Daily Fetch</h3>
        <button onClick={fetchDaily} disabled={loading} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-60">
          {loading ? 'Loading…' : 'Fetch'}
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <label className="text-sm text-gray-300">
          <div>Symbol</div>
          <input value={symbol} onChange={e=>setSymbol(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
        </label>
        <label className="text-sm text-gray-300">
          <div>Period</div>
          <input value={period} onChange={e=>setPeriod(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
        </label>
        <label className="text-sm text-gray-300">
          <div>Start (YYYY-MM-DD)</div>
          <input value={start} onChange={e=>setStart(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
        </label>
        <label className="text-sm text-gray-300">
          <div>End (YYYY-MM-DD)</div>
          <input value={end} onChange={e=>setEnd(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
        </label>
      </div>
      {error && <div className="mt-3 text-red-400 text-sm">{error}</div>}
      {resp && (
        <div className="mt-4 text-sm text-gray-200">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <div>symbol: <b className="text-white">{resp.meta?.symbol || symbol}</b></div>
            <div>count: <b className="text-white">{resp.count}</b></div>
            <div>first: <b className="text-white">{rows[0]?.date || '—'}</b></div>
            <div>last: <b className="text-white">{rows[rows.length-1]?.date || '—'}</b></div>
          </div>
          {!!rows.length && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-gray-400">
                  <tr>
                    <th className="text-left">date</th>
                    <th className="text-right">open</th>
                    <th className="text-right">high</th>
                    <th className="text-right">low</th>
                    <th className="text-right">close</th>
                    <th className="text-right">volume</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 10).map((r, i) => (
                    <tr key={i} className="text-gray-200">
                      <td>{r.date}</td>
                      <td className="text-right">{r.open ?? ''}</td>
                      <td className="text-right">{r.high ?? ''}</td>
                      <td className="text-right">{r.low ?? ''}</td>
                      <td className="text-right">{r.close ?? ''}</td>
                      <td className="text-right">{r.volume ?? ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DailyDataFetcher
