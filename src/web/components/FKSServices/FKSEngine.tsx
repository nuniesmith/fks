import { Cpu } from 'lucide-react'
import React, { useState } from 'react'

import { forecast as engineForecast, backtest as engineBacktest, type EngineForecastResponse, type EngineBacktestResponse } from '../../services/EngineApi'

const FKSEngine: React.FC = () => {
  const [symbol, setSymbol] = useState('GC=F')
  const [period, setPeriod] = useState('6mo')
  const [window, setWindow] = useState(64)
  const [loading, setLoading] = useState<'forecast' | 'backtest' | null>(null)
  const [forecast, setForecast] = useState<EngineForecastResponse | null>(null)
  const [backtest, setBacktest] = useState<EngineBacktestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [withLLM, setWithLLM] = useState<boolean>(false)

  async function runForecast() {
    setLoading('forecast'); setError(null)
    try {
  const res = await engineForecast({ symbol, period, window, withLLM })
      setForecast(res)
    } catch (e: any) {
      setError(e?.message || 'Forecast failed')
    } finally { setLoading(null) }
  }

  async function runBacktest() {
    setLoading('backtest'); setError(null)
    try {
  const res = await engineBacktest({ symbol, period, withLLM })
      setBacktest(res)
    } catch (e: any) {
      setError(e?.message || 'Backtest failed')
    } finally { setLoading(null) }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3"><Cpu className="w-7 h-7 text-blue-400"/> FKS Engine</h1>
        <p className="text-gray-400">Run backtests and view HMM+Transformer forecasts</p>
      </div>

      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
  <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <label className="text-sm text-gray-300">
            <div>Symbol</div>
            <input value={symbol} onChange={e=>setSymbol(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
          </label>
          <label className="text-sm text-gray-300">
            <div>Period</div>
            <input value={period} onChange={e=>setPeriod(e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
          </label>
          <label className="text-sm text-gray-300">
            <div>Window</div>
            <input type="number" value={window} onChange={e=>setWindow(Number(e.target.value)||64)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded"/>
          </label>
          <div className="flex items-end gap-2">
            <button onClick={runForecast} disabled={loading==='forecast'} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded disabled:opacity-60">Forecast</button>
            <button onClick={runBacktest} disabled={loading==='backtest'} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-60">Backtest</button>
          </div>
          <label className="text-sm text-gray-300 flex items-end gap-2">
            <input type="checkbox" checked={withLLM} onChange={e=>setWithLLM(e.target.checked)} className="w-4 h-4"/>
            <span>with LLM notes</span>
          </label>
        </div>
        {error && <div className="mt-3 text-red-400 text-sm">{error}</div>}
      </div>

      {forecast && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold text-white">Forecast</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm text-gray-200 mt-2">
            <div>ok: <b className="text-white">{String(forecast.ok)}</b></div>
            <div>tf_ok: <b className="text-white">{String(forecast.tf_ok)}</b></div>
            <div>window_used: <b className="text-white">{forecast.transformer?.window_used ?? forecast.window}</b></div>
            <div>horizon_pred: <b className="text-white">{forecast.transformer?.horizon_pred?.toFixed?.(6) ?? 'n/a'}</b></div>
            <div>device: <b className="text-white">{forecast.transformer?.device ?? 'n/a'}</b></div>
            <div>regime_last: <b className="text-white">{forecast.transformer?.regime_last ?? 'n/a'}</b></div>
            <div>confidence: <b className="text-white">{forecast.transformer?.confidence?.toFixed?.(3) ?? 'n/a'}</b></div>
            <div>n: <b className="text-white">{forecast.n}</b></div>
          </div>
          {forecast.llm_comment && (
            <div className="mt-3 text-sm text-gray-100">
              <div className="text-gray-300 mb-1">LLM note</div>
              <div className="p-3 rounded border border-gray-700 bg-gray-900/60 whitespace-pre-wrap">{forecast.llm_comment}</div>
            </div>
          )}
        </div>
      )}

      {backtest && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="text-lg font-semibold text-white">Backtest</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm text-gray-200 mt-2">
            <div>ok: <b className="text-white">{String(backtest.ok)}</b></div>
            <div>trades: <b className="text-white">{backtest.trades}</b></div>
            <div>equity: <b className="text-white">{backtest.equity.toFixed(4)}</b></div>
            <div>tf_ok: <b className="text-white">{String(backtest.tf_ok)}</b></div>
            <div>horizon_pred: <b className="text-white">{backtest.transformer?.horizon_pred?.toFixed?.(6) ?? 'n/a'}</b></div>
            <div>device: <b className="text-white">{backtest.transformer?.device ?? 'n/a'}</b></div>
            <div>regime_last: <b className="text-white">{backtest.transformer?.regime_last ?? 'n/a'}</b></div>
            <div>confidence: <b className="text-white">{backtest.transformer?.confidence?.toFixed?.(3) ?? 'n/a'}</b></div>
          </div>
          {!!backtest.signals_tail?.length && (
            <div className="mt-3">
              <div className="text-sm text-gray-300 mb-1">Signals (tail)</div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-400">
                      <th className="text-left">date</th>
                      <th className="text-left">action</th>
                      <th className="text-right">price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backtest.signals_tail.map((s, i) => (
                      <tr key={i} className="text-gray-200">
                        <td>{s.date}</td>
                        <td>{s.action}</td>
                        <td className="text-right">{s.price}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {backtest.llm_comment && (
            <div className="mt-3 text-sm text-gray-100">
              <div className="text-gray-300 mb-1">LLM note</div>
              <div className="p-3 rounded border border-gray-700 bg-gray-900/60 whitespace-pre-wrap">{backtest.llm_comment}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default FKSEngine
