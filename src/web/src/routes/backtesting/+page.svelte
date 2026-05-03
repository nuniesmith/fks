<script lang="ts">
  import { onMount, onDestroy, getContext } from 'svelte';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtDollar, fmtPct, fmtFixed, fmtDateTime } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ────────────────────────────────────────────────────────

  interface BacktestTrade {
    entry_time?: string;
    exit_time?: string;
    asset?: string;
    side?: string;
    entry_price?: number;
    exit_price?: number;
    pnl_usdt?: number;
    pnl_pct?: number;
    regime?: string;
    quality?: number;
  }

  interface BacktestStats {
    total_trades?: number;
    win_rate?: number;
    total_pnl?: number;
    profit_factor?: number;
    sharpe_ratio?: number;
    max_drawdown?: number;
    avg_win?: number;
    avg_loss?: number;
    expectancy?: number;
  }

  interface BacktestResult {
    status?: 'running' | 'done' | 'error';
    stats?: BacktestStats;
    trades?: BacktestTrade[];
    equity_curve?: Array<{ ts: number; equity: number }>;
    error?: string;
  }

  interface KnownAssets { assets: Array<{ key: string; base: string; enabled: boolean }> }

  // ─── Form state ───────────────────────────────────────────────────

  const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1D'];

  let selectedAsset = $state('');
  let selectedTf    = $state('5m');
  let dateFrom      = $state('');
  let dateTo        = $state('');
  let fastEma       = $state(9);
  let slowEma       = $state(21);
  let slPct         = $state(0.5);
  let tpPct         = $state(1.0);

  // ─── Assets ───────────────────────────────────────────────────────

  let knownAssets = $state<string[]>([]);

  async function loadAssets() {
    try {
      const data = await api.get<KnownAssets>(`${ws.apiBase}/assets`);
      knownAssets = data.assets.filter(a => a.enabled).map(a => a.key);
      if (knownAssets.length && !selectedAsset) selectedAsset = knownAssets[0];
    } catch { /* silent */ }
  }

  // ─── Task submission + SSE streaming ─────────────────────────────

  type RunState = 'idle' | 'running' | 'done' | 'error';

  let runState      = $state<RunState>('idle');
  let taskId        = $state<string | null>(null);
  let outputLines   = $state<string[]>([]);
  let result        = $state<BacktestResult | null>(null);
  let errorMsg      = $state('');
  let sseSource: EventSource | null = null;

  async function runBacktest() {
    if (!ws.tasksBase) {
      errorMsg = 'Task runner not configured for this workspace.';
      return;
    }
    if (!selectedAsset) {
      errorMsg = 'Select an asset first.';
      return;
    }

    runState    = 'running';
    errorMsg    = '';
    outputLines = [];
    result      = null;
    sseSource?.close();

    try {
      const res = await api.post<{ task_id: string }>(`${ws.tasksBase}/api/run`, {
        task_type: 'backtest',
        asset: selectedAsset,
        params: {
          timeframe: selectedTf,
          date_from: dateFrom || undefined,
          date_to:   dateTo   || undefined,
          fast_ema:  fastEma,
          slow_ema:  slowEma,
          sl_pct:    slPct,
          tp_pct:    tpPct,
        },
      });

      taskId    = res.task_id;
      sseSource = new EventSource(`${ws.tasksBase}/api/${res.task_id}/stream`);

      sseSource.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          if (parsed.done) {
            runState = 'done';
            sseSource?.close();
            loadResult(res.task_id);
          } else if (parsed.result) {
            result = parsed.result as BacktestResult;
          } else if (parsed.line) {
            outputLines = [...outputLines, parsed.line];
          }
        } catch { /* ignore */ }
      };
      sseSource.onerror = () => {
        runState = 'error';
        errorMsg = 'Lost connection to task stream.';
        sseSource?.close();
      };
    } catch (e: any) {
      runState = 'error';
      errorMsg = e?.message ?? 'Failed to submit backtest';
    }
  }

  async function loadResult(id: string) {
    try {
      const task = await api.get<{ status: string; result?: BacktestResult }>(`${ws.tasksBase}/api/${id}`);
      if (task.result) result = task.result;
      if (task.status === 'error') { runState = 'error'; errorMsg = 'Backtest failed.'; }
    } catch { /* ignore */ }
  }

  // ─── Helpers ─────────────────────────────────────────────────────

  function statColor(v: number | undefined, thresh: number): 'green' | 'amber' | 'red' | 'default' {
    if (v == null) return 'default';
    return v >= thresh ? 'green' : v >= thresh * 0.6 ? 'amber' : 'red';
  }

  function pnlCss(v: number | undefined) {
    if (!v) return 'var(--t1)';
    return v > 0 ? 'var(--green)' : 'var(--red)';
  }

  function sideBadge(s: string | undefined): 'green' | 'red' | 'default' {
    const u = (s ?? '').toUpperCase();
    return u === 'LONG' || u === 'BUY' ? 'green' : u === 'SHORT' || u === 'SELL' ? 'red' : 'default';
  }

  onMount(() => {
    loadAssets();
    // Default date range: last 90 days
    const to   = new Date();
    const from = new Date(to);
    from.setDate(from.getDate() - 90);
    dateFrom = from.toISOString().slice(0, 10);
    dateTo   = to.toISOString().slice(0, 10);
  });

  onDestroy(() => sseSource?.close());
</script>

<svelte:head>
  <title>Backtest — {ws.label} — FKS Terminal</title>
</svelte:head>

<div class="page">

  <!-- ── Config form ─────────────────────────────────────────────── -->
  <Panel title="Backtest Configuration">
    <div class="form">

      <div class="form-row">
        <label class="field">
          <span class="lbl">Asset</span>
          <select class="sel" bind:value={selectedAsset} disabled={runState === 'running'}>
            <option value="">— select —</option>
            {#each knownAssets as a}
              <option value={a}>{a.toUpperCase()}</option>
            {/each}
          </select>
        </label>

        <label class="field">
          <span class="lbl">Timeframe</span>
          <div class="tf-chips">
            {#each TIMEFRAMES as tf}
              <button
                class="tf-btn"
                class:active={selectedTf === tf}
                onclick={() => selectedTf = tf}
                disabled={runState === 'running'}
              >{tf}</button>
            {/each}
          </div>
        </label>
      </div>

      <div class="form-row">
        <label class="field">
          <span class="lbl">From</span>
          <input class="inp" type="date" bind:value={dateFrom} disabled={runState === 'running'} />
        </label>
        <label class="field">
          <span class="lbl">To</span>
          <input class="inp" type="date" bind:value={dateTo} disabled={runState === 'running'} />
        </label>
      </div>

      <div class="form-row">
        <label class="field">
          <span class="lbl">Fast EMA</span>
          <input class="inp num" type="number" min="2" max="50"  bind:value={fastEma} disabled={runState === 'running'} />
        </label>
        <label class="field">
          <span class="lbl">Slow EMA</span>
          <input class="inp num" type="number" min="5" max="200" bind:value={slowEma} disabled={runState === 'running'} />
        </label>
        <label class="field">
          <span class="lbl">SL %</span>
          <input class="inp num" type="number" min="0.1" max="5" step="0.1" bind:value={slPct} disabled={runState === 'running'} />
        </label>
        <label class="field">
          <span class="lbl">TP %</span>
          <input class="inp num" type="number" min="0.1" max="20" step="0.1" bind:value={tpPct} disabled={runState === 'running'} />
        </label>
      </div>

      <div class="form-actions">
        <button
          class="run-btn"
          onclick={runBacktest}
          disabled={runState === 'running' || !selectedAsset || !ws.tasksBase}
        >
          {#if runState === 'running'}
            <span class="spinner">⟳</span> Running…
          {:else}
            ▶ Run Backtest
          {/if}
        </button>

        {#if !ws.tasksBase}
          <span class="warn">Task runner not configured — add <code>tasksBase</code> to workspaces.ts</span>
        {/if}
        {#if errorMsg}
          <span class="err">{errorMsg}</span>
        {/if}
        {#if taskId}
          <span class="dim task-id">Task: {taskId.slice(0, 12)}…
            <Badge variant={runState === 'done' ? 'green' : runState === 'error' ? 'red' : 'cyan'}>
              {runState}
            </Badge>
          </span>
        {/if}
      </div>
    </div>
  </Panel>

  <!-- ── Results ─────────────────────────────────────────────────── -->
  {#if runState !== 'idle'}
    <div class="results-layout">

      <!-- Stats -->
      <div class="results-col">
        {#if result?.stats}
          {@const s = result.stats}
          <div class="stat-grid">
            <StatCard label="Total P&L"      value={fmtDollar(s.total_pnl)}         color={s.total_pnl && s.total_pnl > 0 ? 'green' : 'red'} />
            <StatCard label="Win Rate"        value={fmtPct(s.win_rate)}             color={statColor(s.win_rate, 0.55)} />
            <StatCard label="Total Trades"    value={String(s.total_trades ?? '—')} />
            <StatCard label="Profit Factor"   value={fmtFixed(s.profit_factor, 2)}   color={statColor(s.profit_factor, 1.5)} />
            <StatCard label="Sharpe"          value={fmtFixed(s.sharpe_ratio, 2)}    color={statColor(s.sharpe_ratio, 1.0)} />
            <StatCard label="Max Drawdown"    value={fmtPct(s.max_drawdown)}         color={s.max_drawdown && s.max_drawdown < 0.1 ? 'green' : 'red'} />
            <StatCard label="Avg Win"         value={fmtDollar(s.avg_win)}           color="green" />
            <StatCard label="Avg Loss"        value={fmtDollar(s.avg_loss)}          color="red" />
            <StatCard label="Expectancy"      value={fmtDollar(s.expectancy)}        color={s.expectancy && s.expectancy > 0 ? 'green' : 'red'} />
          </div>
        {:else if runState === 'running'}
          <!-- Live output while running -->
          <Panel title="Task Output" fill>
            {#snippet header()}
              <ProgressBar value={100} color="cyan" height="2px" />
            {/snippet}
            <div class="output">
              {#each outputLines.slice(-50) as line}
                <div class="output-line">{line}</div>
              {/each}
              {#if outputLines.length === 0}
                <p class="dim">Waiting for output…</p>
              {/if}
            </div>
          </Panel>
        {/if}

        <!-- Trade table -->
        {#if result?.trades && result.trades.length > 0}
          <Panel title="Trade Log ({result.trades.length})" fill noPad>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>P&L</th>
                    <th>Regime</th>
                  </tr>
                </thead>
                <tbody>
                  {#each result.trades as t}
                    <tr>
                      <td class="dim mono">{t.entry_time ? fmtDateTime(t.entry_time) : '—'}</td>
                      <td><Badge variant={sideBadge(t.side)}>{(t.side ?? '—').toUpperCase()}</Badge></td>
                      <td class="mono">{t.entry_price != null ? fmtFixed(t.entry_price, 2) : '—'}</td>
                      <td class="mono">{t.exit_price  != null ? fmtFixed(t.exit_price,  2) : '—'}</td>
                      <td class="mono" style="color:{pnlCss(t.pnl_usdt)}">{t.pnl_usdt != null ? fmtDollar(t.pnl_usdt) : '—'}</td>
                      <td><Badge variant="default">{t.regime ?? '—'}</Badge></td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </Panel>
        {/if}
      </div>

    </div>
  {/if}

</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    height: 100%;
    overflow: auto;
  }

  /* ── Form ─────────────────────────────────────── */
  .form       { display: flex; flex-direction: column; gap: 10px; }
  .form-row   { display: flex; gap: 12px; flex-wrap: wrap; }
  .field      { display: flex; flex-direction: column; gap: 3px; }
  .lbl        { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: 0.06em; }
  .sel, .inp  {
    background: var(--bg3); border: 1px solid var(--b3); border-radius: var(--r);
    color: var(--t1); font-family: inherit; font-size: 10px; padding: 3px 6px;
    outline: none; min-width: 80px;
  }
  .sel:focus, .inp:focus { border-color: var(--accent-brd); }
  .inp.num    { width: 70px; }

  .tf-chips   { display: flex; gap: 3px; flex-wrap: wrap; }
  .tf-btn {
    padding: 2px 8px; background: var(--bg3); border: 1px solid var(--b3);
    border-radius: var(--r); color: var(--t2); font-family: inherit; font-size: 10px;
    cursor: pointer; transition: all 0.1s;
  }
  .tf-btn:hover  { color: var(--t1); }
  .tf-btn.active { background: var(--accent-dim); border-color: var(--accent-brd); color: var(--t1); }
  .tf-btn:disabled { opacity: 0.4; cursor: default; }

  .form-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

  .run-btn {
    padding: 5px 18px; background: var(--accent-dim); border: 1px solid var(--accent-brd);
    border-radius: var(--r); color: var(--t1); font-family: inherit; font-size: 11px;
    font-weight: 600; cursor: pointer; transition: background 0.15s;
  }
  .run-btn:hover:not(:disabled) { background: var(--accent-glow); }
  .run-btn:disabled { opacity: 0.4; cursor: default; }

  .spinner { display: inline-block; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .warn    { font-size: 10px; color: var(--amber); }
  .err     { font-size: 10px; color: var(--red);   }
  .dim     { color: var(--t3); }
  .task-id { font-size: 9px; display: flex; align-items: center; gap: 6px; }

  /* ── Results ─────────────────────────────────── */
  .results-layout { display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0; }
  .results-col    { display: flex; flex-direction: column; gap: 8px; flex: 1; min-height: 0; }

  .stat-grid {
    display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0;
  }

  /* Output stream */
  .output {
    height: 200px; overflow: auto; font-size: 10px; display: flex;
    flex-direction: column; gap: 1px; padding: 4px;
  }
  .output-line { color: var(--t1); white-space: pre-wrap; word-break: break-all; line-height: 1.5; }

  /* Trade table */
  .table-wrap { overflow: auto; max-height: 320px; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  thead th {
    padding: 5px 8px; text-align: left; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--t3); border-bottom: 1px solid var(--b2);
    white-space: nowrap; position: sticky; top: 0; background: var(--bg1);
  }
  tbody tr { border-bottom: 1px solid var(--b1); transition: background 0.1s; }
  tbody tr:hover { background: var(--bg3); }
  td { padding: 5px 8px; color: var(--t1); white-space: nowrap; }
  .mono { font-size: 10px; }
</style>
