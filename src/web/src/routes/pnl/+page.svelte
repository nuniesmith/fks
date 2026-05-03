<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import Panel from '$components/ui/Panel.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtDollar, fmtPct, fmtFixed } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface PerAsset { total_pnl?: number; total_trades?: number; win_rate?: number; }
  interface DailyEntry { date?: string; pnl?: number; trades?: number; }

  interface Stats {
    total_pnl?: number;
    total_trades?: number;
    win_rate?: number;
    best_asset?: string;
    worst_asset?: string;
    daily_breakdown?: DailyEntry[];
    per_asset?: Record<string, PerAsset>;
  }

  interface FeeSummary {
    total_fees?: number;
    total_maker_fees?: number;
    total_taker_fees?: number;
    avg_fee_per_trade?: number;
    total_gross_pnl?: number;
    total_net_pnl?: number;
  }

  interface PnlData {
    stats: Stats;
    history: unknown[];
    daily_pnl: number;
    fee_summary: FeeSummary;
    days: number;
  }

  // ─── Period selector ─────────────────────────────────────────────────

  let days = $state(7);

  function pnlUrl() { return `${ws.apiBase}/pnl?days=${days}`; }

  let poll = $state(createPoll<PnlData>(pnlUrl(), 30_000));

  $effect(() => {
    poll.stop();
    poll = createPoll<PnlData>(pnlUrl(), 30_000);
    poll.start();
  });

  let data     = $derived($poll);
  let stats    = $derived(data?.stats ?? {} as Stats);
  let fees     = $derived(data?.fee_summary ?? {} as FeeSummary);
  let perAsset = $derived(Object.entries(stats.per_asset ?? {}));

  function pnlColor(v: number | undefined): 'green' | 'red' | 'default' {
    if (v == null) return 'default';
    return v > 0 ? 'green' : v < 0 ? 'red' : 'default';
  }

  function pnlCss(v: number | undefined) {
    const c = pnlColor(v);
    if (c === 'green') return 'var(--green)';
    if (c === 'red')   return 'var(--red)';
    return 'var(--t1)';
  }

  onMount(() => {
    poll.start();
    return () => poll.stop();
  });
</script>

<div class="page">
  <div class="toolbar">
    <span class="toolbar-lbl">Period</span>
    {#each [1, 7, 30] as d}
      <button class="period-btn" class:active={days === d} onclick={() => (days = d)}>{d}d</button>
    {/each}
  </div>

  {#if !data}
    <div class="skel-row">
      {#each Array(5) as _}
        <Skeleton width="130px" height="54px" />
      {/each}
    </div>
  {:else}
    <div class="stats-row">
      <StatCard label="Total PnL ({days}d)"     value={fmtDollar(stats.total_pnl)}   color={pnlColor(stats.total_pnl)} />
      <StatCard label="Net PnL (after fees)"     value={fmtDollar(fees.total_net_pnl)} color={pnlColor(fees.total_net_pnl)} />
      <StatCard label="Total Trades"             value={String(stats.total_trades ?? '—')} />
      <StatCard label="Win Rate"                 value={fmtPct(stats.win_rate)} />
      <StatCard label="Best Asset"               value={stats.best_asset ?? '—'}  color="green" />
      <StatCard label="Worst Asset"              value={stats.worst_asset ?? '—'} color="red" />
      <StatCard label="Total Fees"               value={fees.total_fees != null ? `-$${fmtFixed(Math.abs(fees.total_fees), 4)}` : '—'} color="amber" />
    </div>

    <div class="panels-row">
      <Panel title="Per-Asset Breakdown" fill>
        {#if perAsset.length === 0}
          <p class="empty">No data for this period.</p>
        {:else}
          <table>
            <thead>
              <tr><th>Asset</th><th>PnL</th><th>Trades</th><th>Win Rate</th></tr>
            </thead>
            <tbody>
              {#each perAsset as [asset, row]}
                <tr>
                  <td class="asset">{asset.toUpperCase()}</td>
                  <td><span style="color:{pnlCss(row.total_pnl)}">{fmtDollar(row.total_pnl)}</span></td>
                  <td>{row.total_trades ?? '—'}</td>
                  <td>{row.win_rate != null ? fmtPct(row.win_rate) : '—'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </Panel>

      <Panel title="Fee Breakdown">
        <div class="fee-grid">
          <span class="lbl">Maker Fees</span>
          <span class="val neg">-${fmtFixed(Math.abs(fees.total_maker_fees ?? 0), 6)}</span>

          <span class="lbl">Taker Fees</span>
          <span class="val neg">-${fmtFixed(Math.abs(fees.total_taker_fees ?? 0), 6)}</span>

          <span class="lbl">Total Fees</span>
          <span class="val neg">-${fmtFixed(Math.abs(fees.total_fees ?? 0), 6)}</span>

          <span class="lbl">Avg Fee/Trade</span>
          <span class="val">{fees.avg_fee_per_trade != null ? `-$${fmtFixed(Math.abs(fees.avg_fee_per_trade), 6)}` : '—'}</span>

          <span class="lbl sep">Gross PnL</span>
          <span class="val" style="color:{pnlCss(fees.total_gross_pnl)}">{fmtDollar(fees.total_gross_pnl)}</span>

          <span class="lbl">Net PnL</span>
          <span class="val" style="color:{pnlCss(fees.total_net_pnl)}">{fmtDollar(fees.total_net_pnl)}</span>
        </div>
      </Panel>
    </div>
  {/if}
</div>

<style>
  .page { display: flex; flex-direction: column; gap: 10px; padding: 10px; height: 100%; overflow: auto; }

  .toolbar { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .toolbar-lbl { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: 0.06em; }

  .period-btn {
    background: var(--bg3); border: 1px solid var(--b2); border-radius: var(--r);
    color: var(--t2); font-family: inherit; font-size: 10px; padding: 2px 8px;
    cursor: pointer; transition: background 0.15s, color 0.15s;
  }
  .period-btn.active { background: var(--accent-dim); border-color: var(--accent-brd); color: var(--t1); }

  .skel-row, .stats-row { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }

  .panels-row { display: grid; grid-template-columns: 1fr 280px; gap: 8px; flex: 1; min-height: 0; }

  table { width: 100%; border-collapse: collapse; font-size: 11px; }

  thead th {
    padding: 5px 8px; text-align: left; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--t3); border-bottom: 1px solid var(--b2);
    white-space: nowrap; position: sticky; top: 0; background: var(--bg1);
  }

  tbody tr { border-bottom: 1px solid var(--b1); transition: background 0.1s; }
  tbody tr:hover { background: var(--bg3); }
  td { padding: 5px 8px; color: var(--t1); }

  .asset { color: var(--cyan); font-weight: 600; }

  .fee-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; padding: 4px 0; }

  .lbl { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: 0.05em; align-self: center; }
  .val { font-size: 11px; color: var(--t1); text-align: right; }
  .neg { color: var(--red); }
  .lbl.sep { border-top: 1px solid var(--b1); padding-top: 4px; margin-top: 2px; }

  .empty { padding: 20px; font-size: 11px; color: var(--t3); }
</style>
