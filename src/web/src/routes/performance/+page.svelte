<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtDollar, fmtPct, fmtFixed, fmtDateTime } from '$lib/utils/format';

  // ─── Types ──────────────────────────────────────────────────────────

  interface Performance {
    total_trades?: number;
    win_rate?: number;
    total_pnl?: number;
    profit_factor?: number;
    sharpe_ratio?: number;
    sortino_ratio?: number;
    max_drawdown?: number;
    recovery_factor?: number;
    avg_win?: number;
    avg_loss?: number;
    largest_win?: number;
    largest_loss?: number;
  }

  interface Trade {
    symbol: string;
    side?: string;
    entry_price?: number;
    exit_price?: number;
    size?: number;
    pnl?: number;
    pnl_percent?: number;
    open_time?: string;
    close_time?: string;
  }

  interface TradesResponse { trades: Trade[] }

  // ─── State ───────────────────────────────────────────────────────────

  let perf         = $state<Performance | null>(null);
  let perfLoading  = $state(true);
  let perfError    = $state('');

  let trades        = $state<Trade[]>([]);
  let tradesLoading = $state(true);
  let tradesError   = $state('');

  // ─── Fetch ───────────────────────────────────────────────────────────

  async function fetchPerformance() {
    perfError = '';
    try {
      perf = await api<Performance>('/api/performance');
    } catch (e: any) {
      perfError = e.message ?? 'Failed';
    } finally {
      perfLoading = false;
    }
  }

  async function fetchTrades() {
    tradesError = '';
    try {
      const data = await api<TradesResponse>('/api/trades');
      trades = data.trades ?? [];
    } catch (e: any) {
      tradesError = e.message ?? 'Failed';
    } finally {
      tradesLoading = false;
    }
  }

  function exportCSV() {
    window.location.href = '/api/trades/export';
  }

  // ─── Derived metric cards ─────────────────────────────────────────────

  interface MetricCard { label: string; value: string; sub?: string; color?: string }

  let metricCards = $derived<MetricCard[]>(() => {
    if (!perf) return [];
    const p = perf;
    const pnl = p.total_pnl ?? 0;
    return [
      { label: 'Total Trades',    value: String(p.total_trades ?? '—') },
      { label: 'Win Rate',        value: p.win_rate != null ? fmtPct(p.win_rate) : '—',        color: (p.win_rate ?? 0) >= 0.5 ? 'var(--green)' : 'var(--red)' },
      { label: 'Total P&L',       value: p.total_pnl != null ? fmtDollar(pnl) : '—',           color: pnl >= 0 ? 'var(--green)' : 'var(--red)' },
      { label: 'Profit Factor',   value: p.profit_factor != null ? fmtFixed(p.profit_factor, 2) : '—', color: (p.profit_factor ?? 0) >= 1 ? 'var(--green)' : 'var(--red)' },
      { label: 'Sharpe Ratio',    value: p.sharpe_ratio != null ? fmtFixed(p.sharpe_ratio, 2) : '—' },
      { label: 'Sortino Ratio',   value: p.sortino_ratio != null ? fmtFixed(p.sortino_ratio, 2) : '—' },
      { label: 'Max Drawdown',    value: p.max_drawdown != null ? fmtDollar(p.max_drawdown) : '—', color: 'var(--red)' },
      { label: 'Recovery Factor', value: p.recovery_factor != null ? fmtFixed(p.recovery_factor, 2) : '—' },
      { label: 'Avg Win',         value: p.avg_win != null ? fmtDollar(p.avg_win) : '—',       color: 'var(--green)' },
      { label: 'Avg Loss',        value: p.avg_loss != null ? fmtDollar(p.avg_loss) : '—',     color: 'var(--red)' },
      { label: 'Largest Win',     value: p.largest_win != null ? fmtDollar(p.largest_win) : '—', color: 'var(--green)' },
      { label: 'Largest Loss',    value: p.largest_loss != null ? fmtDollar(p.largest_loss) : '—', color: 'var(--red)' },
    ];
  });

  // ─── Polling ─────────────────────────────────────────────────────────

  let timer: ReturnType<typeof setInterval>;

  onMount(() => {
    fetchPerformance();
    fetchTrades();
    timer = setInterval(() => { fetchPerformance(); fetchTrades(); }, 10_000);
    return () => clearInterval(timer);
  });
</script>

<svelte:head>
  <title>Performance — FKS Terminal</title>
</svelte:head>

<div class="page">

  <!-- ─── Metrics grid ────────────────────────────────────────────────── -->
  <Panel title="Performance Metrics" badge="10s">
    {#snippet header()}
      <button class="export-btn" onclick={exportCSV}>⬇ Export CSV</button>
    {/snippet}

    {#if perfLoading}
      <div class="metrics-grid">
        {#each Array(12) as _}
          <Skeleton height="52px" />
        {/each}
      </div>
    {:else if perfError}
      <p class="err-text">{perfError}</p>
    {:else}
      <div class="metrics-grid">
        {#each metricCards as card}
          <StatCard label={card.label} value={card.value} valueColor={card.color} />
        {/each}
      </div>
    {/if}
  </Panel>

  <!-- ─── Trade history ───────────────────────────────────────────────── -->
  <Panel title="Trade History" fill>
    {#snippet header()}
      <span class="poll-badge">{trades.length > 50 ? `50 / ${trades.length}` : trades.length} trades · 10s</span>
    {/snippet}

    {#if tradesLoading}
      <div class="skeleton-rows">
        {#each Array(8) as _}
          <Skeleton height="28px" />
        {/each}
      </div>
    {:else if tradesError}
      <p class="err-text">{tradesError}</p>
    {:else if trades.length === 0}
      <p class="empty">No trades yet.</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>Size</th>
              <th>P&amp;L</th>
              <th>P&amp;L %</th>
            </tr>
          </thead>
          <tbody>
            {#each trades.slice(0, 50) as t}
              {@const pnl    = t.pnl ?? 0}
              {@const pnlPct = t.pnl_percent ?? 0}
              {@const side   = (t.side ?? '').toLowerCase()}
              <tr>
                <td class="dim mono">{t.close_time ? fmtDateTime(t.close_time) : (t.open_time ? fmtDateTime(t.open_time) : '—')}</td>
                <td class="symbol">{t.symbol}</td>
                <td>
                  <Badge variant={side === 'buy' ? 'green' : side === 'sell' ? 'red' : 'default'}>
                    {t.side ?? '—'}
                  </Badge>
                </td>
                <td class="mono">{t.entry_price != null ? fmtDollar(t.entry_price) : '—'}</td>
                <td class="mono">{t.exit_price  != null ? fmtDollar(t.exit_price)  : '—'}</td>
                <td class="mono">{t.size        != null ? fmtFixed(t.size, 4)       : '—'}</td>
                <td class="mono" style="color:{pnl >= 0 ? 'var(--green)' : 'var(--red)'}">{fmtDollar(pnl)}</td>
                <td class="mono" style="color:{pnlPct >= 0 ? 'var(--green)' : 'var(--red)'}">{fmtPct(pnlPct / 100)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        {#if trades.length > 50}
          <p class="overflow-note">Showing last 50 of {trades.length} trades</p>
        {/if}
      </div>
    {/if}
  </Panel>

</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 10px;
    gap: 10px;
  }

  /* ── Metrics grid ──────────────────────────────────────── */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 8px;
    padding: 6px 0;
  }

  /* ── Table ─────────────────────────────────────────────── */
  .table-wrap {
    overflow: auto;
    height: 100%;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }
  thead th {
    padding: 5px 8px;
    text-align: left;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--t3);
    border-bottom: 1px solid var(--b2);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--bg1);
  }
  tbody tr {
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s;
  }
  tbody tr:hover { background: var(--bg3); }
  td { padding: 5px 8px; color: var(--t1); white-space: nowrap; }
  .mono   { font-family: inherit; }
  .dim    { color: var(--t2); }
  .symbol { color: var(--cyan); font-weight: 600; }

  .overflow-note {
    padding: 8px;
    font-size: 10px;
    text-align: center;
    color: var(--t3);
  }

  /* ── Controls ──────────────────────────────────────────── */
  .export-btn {
    font-family: inherit;
    font-size: 10px;
    background: var(--cyan-dim);
    border: 1px solid var(--cyan-brd);
    border-radius: var(--r);
    color: var(--cyan);
    padding: 2px 8px;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .export-btn:hover { opacity: 0.8; }

  .poll-badge {
    font-size: 8px;
    color: var(--t3);
    background: var(--bg3);
    padding: 1px 5px;
    border-radius: var(--r);
  }

  .skeleton-rows {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px;
  }
  .empty    { padding: 20px; font-size: 11px; color: var(--t3); }
  .err-text { font-size: 11px; color: var(--red); padding: 12px; }
</style>
