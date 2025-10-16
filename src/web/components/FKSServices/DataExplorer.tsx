import React, { useEffect, useMemo, useState } from 'react'

import { getMarketDataPage, downloadMarketDataCsv, listSources, type MarketDataJsonResponse } from '../../services/DataApi'

type Props = {
  defaultSourceId?: string
  defaultSymbol?: string
  defaultInterval?: string
  pageSize?: number
}

const DataExplorer: React.FC<Props> = ({ defaultSourceId, defaultSymbol, defaultInterval = '1d', pageSize = 50 }) => {
  const [sourceId, setSourceId] = useState(defaultSourceId || '')
  const [symbol, setSymbol] = useState(defaultSymbol || '')
  const [interval, setInterval] = useState(defaultInterval)
  const [pageToken, setPageToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resp, setResp] = useState<MarketDataJsonResponse | null>(null)
  const [sources, setSources] = useState<Record<string, { id: string; name: string }>>({})

  useEffect(() => {
    listSources().then(r => {
      const mapped = Object.fromEntries(Object.values(r.sources).map(s => [s.id, { id: s.id, name: s.name } ]))
      setSources(mapped)
      // If no initial source provided, choose first
      if (!sourceId && Object.values(mapped)[0]) setSourceId(Object.values(mapped)[0].id)
    }).catch(() => {})
  }, [])

  const columns = useMemo(() => resp?.columns ?? [], [resp])
  const data = useMemo(() => resp?.data ?? [], [resp])

  async function loadPage(nextToken: string | null) {
    setLoading(true)
    setError(null)
    try {
      const r = await getMarketDataPage(sourceId, symbol, { interval, limit: pageSize, pageToken: nextToken })
      setResp(r)
      setPageToken(r.next_page_token ?? null)
    } catch (e: any) {
      setError(e?.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // reset and load first page when source/symbol/interval change
  setPageToken(null)
  if (sourceId && symbol) loadPage(null)
  }, [sourceId, symbol, interval])

  async function downloadCsv() {
    try {
      const { blob, filename } = await downloadMarketDataCsv(sourceId, symbol, { interval, limit: pageSize, pageToken: resp?.next_page_token ?? null })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 space-y-4">
      <div className="flex flex-col md:flex-row gap-3 items-start md:items-end">
        <div className="flex-1">
          <label className="text-xs text-gray-400">Source</label>
          <select value={sourceId} onChange={e => setSourceId(e.target.value)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white">
            {Object.values(sources).length === 0 && <option value="">—</option>}
            {Object.values(sources).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-400">Symbol</label>
          <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="" className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white" />
        </div>
        <div>
          <label className="text-xs text-gray-400">Interval</label>
          <select value={interval} onChange={e => setInterval(e.target.value)} className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white">
            {['1m','5m','15m','30m','1h','4h','1d','1w','1M'].map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div className="flex gap-2">
          <button onClick={() => loadPage(null)} disabled={!sourceId || !symbol} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50">Refresh</button>
          <button onClick={downloadCsv} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded">CSV</button>
        </div>
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      <div className="overflow-auto border border-gray-700 rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-700 text-gray-200">
            <tr>
              {columns.map(c => <th key={c} className="px-3 py-2 text-left whitespace-nowrap">{c}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-gray-800">
                {columns.map(c => <td key={c} className="px-3 py-2 whitespace-nowrap text-white/90">{String((row as any)[c] ?? '')}</td>)}
              </tr>
            ))}
            {loading && (
              <tr><td className="px-3 py-4 text-white/70" colSpan={columns.length}>Loading…</td></tr>
            )}
            {!loading && data.length === 0 && (
              <tr><td className="px-3 py-4 text-white/70" colSpan={columns.length}>No data</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="text-white/70">Showing {resp?.count ?? 0} of {resp?.total ?? 0}</div>
        <div className="flex gap-2">
          <button onClick={() => loadPage(resp?.next_page_token ?? null)} disabled={!resp?.next_page_token} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded">Next</button>
        </div>
      </div>
    </div>
  )
}

export default DataExplorer
