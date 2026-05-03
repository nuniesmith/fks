<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtPrice, fmtPct, fmtDateTime, fmtFixed } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface Trade {
    timestamp?: number;
    date?: string;
    asset?: string;
    side?: string;
    entry_price?: number;
    exit_price?: number;
    size_lots?: number;
    notional_usdt?: number;
    pnl_usdt?: number;
    pnl_pct?: number;
    total_fees?: number;
    net_pnl?: number;
    regime?: string;
    quality?: number;
    duration_sec?: number;
    entry_type?: string;
    exit_type?: string;
  }

  interface TradesData {
    trades: Trade[];
    fee_summary: Record<string, number>;
    known_assets: string[];
    selected_asset: string;
    days: number;
  }

  // ─── Filter state ─────────────────────────────────────────────────────

  let days          = $state(7);
  let selectedAsset = $state('');

  function tradesUrl() {
    const p = new URLSearchParams({ days: String(days) });
    if (selectedAsset) p.set('asset', selectedAsset);
    return `${ws.apiBase}/trades?${p}`;
  }

  let poll = $state(createPoll<TradesData>(tradesUrl(), 30_000));

  $effect(() => {
    poll.stop();
    poll = createPoll<TradesData>(tradesUrl(), 30_000);
    poll.start();
  });

  let data        = $derived($poll);
  let trades      = $derived(data?.trades ?? []);
  let knownAssets = $derived(data?.known_assets ?? []);

  // ─── Helpers ─────────────────────────────────────────────────────────

  function sideBadge(side: string | undefined): 'green' | 'red' | 'default' {
    if (!side) return 'default';
    const s = side.toUpperCase();
    if (s === 'LONG' || s === 'BUY')   return 'green';
    if (s === 'SHORT' || s === 'SELL') return 'red';
    return 'default';
  }

  function fmtDuration(secs: number | undefined): string {
    if (secs == null) return '—';
    if (secs < 60)    return `${Math.round(secs)}s`;
    if (secs < 3600)  return `${Math.floor(secs / 60)}m ${Math.round(secs % 60)}s`;
    return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
  }

  function exportUrl(): string {
    const p = new URLSearchParams({ days: String(days) });
    if (selectedAsset) p.set('asset', selectedAsset);
    return `${ws.apiBase}/trades/export?${p}`;
  }

  onMount(() => {
    poll.start();
    return () => poll.stop();
  });
</script>

<div class="page">
  <Panel title="Trade History" fill>
    {#snippet header()}
      {#each [7, 30, 90] as d}
        <button class="period-btn" class:active={days === d} onclick={() => (days = d)}>{d}d</button>
      {/each}

      <select class="filter-select" bind:value={selectedAsset}>
        <option value="">All assets</option>
        {#each knownAssets as a}
          <option value={a}>{a.toUpperCase()}</option>
        {/each}
      </select>

      <a class="export-btn" href={exportUrl()} download>↓ CSV</a>
      <span class="poll-badge">{trades.length} trades · 30s</span>
    {/snippet}

    {#if !data}
      <div class="skeleton-rows">
        {#each Array(10) as _}
          <Skeleton height="26px" />
        {/each}
      </div>
    {:else if trades.length === 0}
      <p class="empty">No trades in the last {days} day{days > 1 ? 's' : ''}{selectedAsset ? ` for ${selectedAsset.toUpperCase()}` : ''}.</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Asset</th><th>Side</th><th>Entry</th><th>Exit</th>
              <th>Size</th><th>PnL</th><th>PnL%</th><th>Fees</th><th>Net</th>
              <th>Quality</th><th>Regime</th><th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {#each trades as t}
              {@const pnlPos = (t.pnl_usdt ?? 0) > 0}
              {@const pnlNeg = (t.pnl_usdt ?? 0) < 0}
              <tr>
                <td class="dim">{t.timestamp ? fmtDateTime(t.timestamp * 1000) : (t.date ?? '—')}</td>
                <td class="asset">{(t.asset ?? '—').toUpperCase()}</td>
                <td><Badge variant={sideBadge(t.side)}>{t.side ?? '—'}</Badge></td>
                <td>{fmtPrice(t.entry_price)}</td>
                <td>{fmtPrice(t.exit_price)}</td>
                <td class="dim">{t.size_lots != null ? fmtFixed(t.size_lots, 2) : '—'}</td>
                <td class:pos={pnlPos} class:neg={pnlNeg}>
                  {t.pnl_usdt != null ? `${pnlPos ? '+' : ''}$${fmtFixed(Math.abs(t.pnl_usdt), 4)}` : '—'}
                </td>
                <td class:pos={pnlPos} class:neg={pnlNeg}>
                  {t.pnl_pct != null ? fmtPct(t.pnl_pct) : '—'}
                </td>
                <td class="dim fees">
                  {t.total_fees != null ? `-$${fmtFixed(Math.abs(t.total_fees), 6)}` : '—'}
                </td>
                <td class:pos={(t.net_pnl ?? 0) > 0} class:neg={(t.net_pnl ?? 0) < 0}>
                  {t.net_pnl != null ? `${(t.net_pnl) > 0 ? '+' : ''}$${fmtFixed(Math.abs(t.net_pnl), 4)}` : '—'}
                </td>
                <td class="dim">{t.quality != null ? fmtFixed(t.quality, 1) : '—'}</td>
                <td class="dim">{t.regime ?? '—'}</td>
                <td class="dim">{fmtDuration(t.duration_sec)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </Panel>
</div>

<style>
  .page { display: flex; flex-direction: column; height: 100%; padding: 10px; }

  .period-btn {
    background: var(--bg3); border: 1px solid var(--b2); border-radius: var(--r);
    color: var(--t2); font-family: inherit; font-size: 9px; padding: 2px 7px; cursor: pointer; transition: background 0.15s;
  }
  .period-btn.active { background: var(--accent-dim); border-color: var(--accent-brd); color: var(--t1); }

  .filter-select {
    background: var(--bg3); border: 1px solid var(--b3); border-radius: var(--r);
    color: var(--t1); font-family: inherit; font-size: 10px; padding: 2px 6px; cursor: pointer;
  }

  .export-btn {
    font-size: 9px; padding: 2px 7px; background: var(--bg3); border: 1px solid var(--b3);
    border-radius: var(--r); color: var(--cyan); text-decoration: none; transition: background 0.15s;
  }
  .export-btn:hover { background: var(--cyan-dim); border-color: var(--cyan-brd); }

  .poll-badge { font-size: 8px; color: var(--t3); background: var(--bg3); padding: 1px 5px; border-radius: var(--r); }
  .table-wrap { overflow: auto; height: 100%; }

  table { width: 100%; border-collapse: collapse; font-size: 11px; }

  thead th {
    padding: 5px 8px; text-align: left; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--t3); border-bottom: 1px solid var(--b2);
    white-space: nowrap; position: sticky; top: 0; background: var(--bg1);
  }

  tbody tr { border-bottom: 1px solid var(--b1); transition: background 0.1s; }
  tbody tr:hover { background: var(--bg3); }

  td { padding: 5px 8px; color: var(--t1); white-space: nowrap; }

  .asset { color: var(--cyan); font-weight: 600; }
  .dim   { color: var(--t2); }
  .fees  { font-size: 10px; }
  .pos   { color: var(--green); }
  .neg   { color: var(--red); }

  .skeleton-rows { display: flex; flex-direction: column; gap: 4px; padding: 8px; }
  .empty { padding: 20px; font-size: 11px; color: var(--t3); }
</style>
