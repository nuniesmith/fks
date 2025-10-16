import { AlertTriangle, Play } from 'lucide-react'
import React, { useMemo, useState, Suspense } from 'react'
const MonteCarloPathsChart = React.lazy(() => import('./MonteCarloPathsChart'))

interface RunInputs {
  trials: number
  steps: number
  initialEquity: number
  drift: number // per step expected return
  vol: number   // per step volatility (stddev)
  feePerTrade: number // absolute fee per trade
  winRate: number // for simple Bernoulli payoff model (optional)
  rr: number // reward-to-risk ratio for Bernoulli model
  mode: 'gaussian' | 'bernoulli'
}

function simulateGaussian({ trials, steps, initialEquity, drift, vol, feePerTrade }: RunInputs): number[][] {
  const paths: number[][] = []
  for (let t = 0; t < trials; t++) {
    const path: number[] = [initialEquity]
    let eq = initialEquity
    for (let i = 1; i <= steps; i++) {
      const z = boxMuller()
      const r = drift + vol * z
      eq = Math.max(0, eq * (1 + r) - feePerTrade)
      path.push(eq)
    }
    paths.push(path)
  }
  return paths
}

function simulateBernoulli({ trials, steps, initialEquity, winRate, rr, feePerTrade }: RunInputs): number[][] {
  const paths: number[][] = []
  const loss = 1
  const gain = rr
  for (let t = 0; t < trials; t++) {
    const path: number[] = [initialEquity]
    let eq = initialEquity
    for (let i = 1; i <= steps; i++) {
      const win = Math.random() < winRate
      const r = win ? gain : -loss
      eq = Math.max(0, eq * (1 + r) - feePerTrade)
      path.push(eq)
    }
    paths.push(path)
  }
  return paths
}

function boxMuller(): number {
  // Standard normal random via Box-Muller
  let u = 0, v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v)
}

function quantile(arr: number[], q: number): number {
  if (arr.length === 0) return NaN
  const sorted = [...arr].sort((a, b) => a - b)
  const pos = (sorted.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  return sorted[base] + (sorted[base + 1] - sorted[base]) * rest || sorted[base]
}

function drawdown(series: number[]): { maxDD: number; avgDD: number } {
  let peak = series[0]
  let maxDD = 0
  let sumDD = 0
  let count = 0
  for (let i = 1; i < series.length; i++) {
    peak = Math.max(peak, series[i])
    const dd = (peak - series[i]) / peak
    if (dd > 0) { sumDD += dd; count++ }
    maxDD = Math.max(maxDD, dd)
  }
  return { maxDD, avgDD: count ? sumDD / count : 0 }
}

const MonteCarlo: React.FC = () => {
  const [inputs, setInputs] = useState<RunInputs>({
    trials: 500,
    steps: 250,
    initialEquity: 10000,
    drift: 0.0005,
    vol: 0.01,
    feePerTrade: 0,
    winRate: 0.55,
    rr: 0.8,
    mode: 'gaussian'
  })
  const [paths, setPaths] = useState<number[][]>([])

  const stats = useMemo(() => {
    if (paths.length === 0) return null
    const finals = paths.map(p => p[p.length - 1])
    const p5 = quantile(finals, 0.05)
    const p50 = quantile(finals, 0.50)
    const p95 = quantile(finals, 0.95)
    // Drawdown stats from median path
    const medIndex = finals.indexOf(p50)
    const dd = drawdown(paths[Math.max(0, medIndex)])
    return { p5, p50, p95, maxDD: dd.maxDD, avgDD: dd.avgDD }
  }, [paths])

  function run() {
    const sim = inputs.mode === 'gaussian' ? simulateGaussian(inputs) : simulateBernoulli(inputs)
    setPaths(sim)
  }

  // Prepare chart rows with percentile band and sample paths (lazy-loaded chart component)
  const chartData = useMemo(() => {
    if (paths.length === 0) return null
    const sampleCount = Math.min(8, paths.length)
    const sample = paths.slice(0, sampleCount)
    const stepsLen = sample[0].length
    // Precompute per-step percentiles across ALL paths (not just sample)
    const allLen = paths.length
    const rows: any[] = []
    for (let i = 0; i < stepsLen; i++) {
      const vals = new Array(allLen)
      for (let p = 0; p < allLen; p++) vals[p] = paths[p][i]
      vals.sort((a,b) => a-b)
      const q = (q: number) => {
        const pos = (vals.length - 1) * q
        const base = Math.floor(pos)
        const rest = pos - base
        return vals[base] + (vals[base + 1] - vals[base]) * rest || vals[base]
      }
      const p5 = q(0.05), p50 = q(0.5), p95 = q(0.95)
      const row: Record<string, number> = { step: i, p5, p50, p95, bandLow: p5, bandDiff: p95 - p5 }
      sample.forEach((path, idx) => { row[`p${idx}`] = path[i] })
      rows.push(row)
    }
    return { rows, count: sampleCount }
  }, [paths])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2"><span>🎲</span> Monte Carlo Simulator</h1>
          <p className="text-white/70">Run Monte Carlo scenarios for strategy equity and drawdown risk.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={run} className="px-3 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-1"><Play className="w-4 h-4"/> Run</button>
        </div>
      </div>

      <div className="glass-card p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="text-sm text-white/80">Trials
            <input type="number" min={10} max={10000} value={inputs.trials} onChange={e=>setInputs({ ...inputs, trials: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
          </label>
          <label className="text-sm text-white/80">Steps
            <input type="number" min={10} max={5000} value={inputs.steps} onChange={e=>setInputs({ ...inputs, steps: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
          </label>
          <label className="text-sm text-white/80">Initial Equity
            <input type="number" min={0} value={inputs.initialEquity} onChange={e=>setInputs({ ...inputs, initialEquity: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
          </label>
          <label className="text-sm text-white/80">Mode
            <select value={inputs.mode} onChange={e=>setInputs({ ...inputs, mode: e.target.value as any })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">
              <option value="gaussian">Gaussian (drift/vol)</option>
              <option value="bernoulli">Bernoulli (win rate / R:R)</option>
            </select>
          </label>
          {inputs.mode === 'gaussian' ? (
            <>
              <label className="text-sm text-white/80">Drift per step
                <input type="number" step="0.0001" value={inputs.drift} onChange={e=>setInputs({ ...inputs, drift: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
              </label>
              <label className="text-sm text-white/80">Volatility per step
                <input type="number" step="0.0001" value={inputs.vol} onChange={e=>setInputs({ ...inputs, vol: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
              </label>
            </>
          ) : (
            <>
              <label className="text-sm text-white/80">Win Rate
                <input type="number" step="0.01" min={0} max={1} value={inputs.winRate} onChange={e=>setInputs({ ...inputs, winRate: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
              </label>
              <label className="text-sm text-white/80">Reward:Risk Ratio
                <input type="number" step="0.01" min={0} value={inputs.rr} onChange={e=>setInputs({ ...inputs, rr: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
              </label>
            </>
          )}
          <label className="text-sm text-white/80">Fee per step
            <input type="number" step="0.01" min={0} value={inputs.feePerTrade} onChange={e=>setInputs({ ...inputs, feePerTrade: Number(e.target.value) })} className="mt-1 w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white"/>
          </label>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="glass-card p-4"><div className="text-white/70 text-sm">5th pct final equity</div><div className="text-white text-xl font-bold">${stats.p5.toFixed(2)}</div></div>
          <div className="glass-card p-4"><div className="text-white/70 text-sm">Median final equity</div><div className="text-white text-xl font-bold">${stats.p50.toFixed(2)}</div></div>
          <div className="glass-card p-4"><div className="text-white/70 text-sm">95th pct final equity</div><div className="text-white text-xl font-bold">${stats.p95.toFixed(2)}</div></div>
          <div className="glass-card p-4"><div className="text-white/70 text-sm">Median path Max DD</div><div className="text-white text-xl font-bold">{(stats.maxDD*100).toFixed(1)}%</div></div>
        </div>
      )}

      <div className="glass-card p-4">
        {chartData ? (
          <div style={{ width: '100%', height: 360 }}>
            <Suspense fallback={<div className="p-6 text-white/60 text-sm">Loading chart...</div>}>
              <MonteCarloPathsChart rows={chartData.rows as any} sampleCount={chartData.count} />
            </Suspense>
          </div>
        ) : <div className="p-6 text-white/70">Run a simulation to see equity paths.</div>}
        <div className="text-[10px] text-white/40 mt-2 flex flex-wrap gap-2">
          <span>Sampled paths: {chartData?.count ?? 0}</span>
          <span>Band: P5 – P95 (shaded)</span>
          <span>Median line highlighted</span>
        </div>
      </div>

      <div className="text-white/60 text-xs flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 mt-0.5"/>
        <span>Monte Carlo simulations are illustrative and rely on assumptions (iid returns, param choice). Validate with backtests/forward tests before going live.</span>
      </div>
    </div>
  )
}

export default MonteCarlo
