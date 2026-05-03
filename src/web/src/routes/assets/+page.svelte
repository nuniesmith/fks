<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtFixed, fmtPct } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface AssetSpec {
    contract_size?: number;
    tick_size?: number;
    tick_value?: number;
    exchange?: string;
    category?: string;
  }

  interface Asset {
    key: string;
    symbol: string;
    base: string;
    leverage: number;
    margin_pct: number;
    enabled: boolean;
    spec: AssetSpec | null;
  }

  interface AssetsData {
    assets: Asset[];
  }

  // ─── Poll ─────────────────────────────────────────────────────────────

  const assetsPoll = createPoll<AssetsData>(`${ws.apiBase}/assets`, 60_000);

  let data          = $derived($assetsPoll);
  let assets        = $derived(data?.assets ?? []);
  let enabledCount  = $derived(assets.filter((a) => a.enabled).length);
  let disabledCount = $derived(assets.length - enabledCount);

  onMount(() => {
    assetsPoll.start();
    return () => assetsPoll.stop();
  });
</script>

<div class="page">
  <Panel title="Asset Registry" fill>
    {#snippet header()}
      <span class="meta">
        <Badge variant="green">{enabledCount} enabled</Badge>
      </span>
      {#if disabledCount > 0}
        <Badge variant="default">{disabledCount} disabled</Badge>
      {/if}
      <span class="poll-badge">{assets.length} assets · 60s</span>
    {/snippet}

    {#if !data}
      <div class="skeleton-rows">
        {#each Array(6) as _}
          <Skeleton height="28px" />
        {/each}
      </div>
    {:else if assets.length === 0}
      <p class="empty">No assets configured.</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Key</th>
              <th>Symbol</th>
              <th>Base</th>
              <th>Status</th>
              <th>Leverage</th>
              <th>Margin</th>
              <th>Exchange</th>
              <th>Category</th>
              <th>Contract Size</th>
              <th>Tick Size</th>
              <th>Tick Value</th>
            </tr>
          </thead>
          <tbody>
            {#each assets as a}
              <tr class:disabled={!a.enabled}>
                <td class="key">{a.key}</td>
                <td class="symbol">{a.symbol}</td>
                <td class="dim">{a.base}</td>
                <td>
                  <Badge variant={a.enabled ? 'green' : 'default'}>
                    {a.enabled ? 'enabled' : 'disabled'}
                  </Badge>
                </td>
                <td>{a.leverage}×</td>
                <td>{fmtPct(a.margin_pct)}</td>
                <td class="dim">{a.spec?.exchange ?? '—'}</td>
                <td class="dim">{a.spec?.category ?? '—'}</td>
                <td class="dim">{a.spec?.contract_size != null ? fmtFixed(a.spec.contract_size, 2) : '—'}</td>
                <td class="dim">{a.spec?.tick_size    != null ? fmtFixed(a.spec.tick_size, 4)    : '—'}</td>
                <td class="dim">{a.spec?.tick_value   != null ? `$${fmtFixed(a.spec.tick_value, 4)}` : '—'}</td>
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

  .poll-badge { font-size: 8px; color: var(--t3); background: var(--bg3); padding: 1px 5px; border-radius: var(--r); }
  .meta { display: flex; align-items: center; gap: 4px; }
  .table-wrap { overflow: auto; height: 100%; }

  table { width: 100%; border-collapse: collapse; font-size: 11px; }

  thead th {
    padding: 5px 10px; text-align: left; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--t3); border-bottom: 1px solid var(--b2);
    white-space: nowrap; position: sticky; top: 0; background: var(--bg1);
  }

  tbody tr { border-bottom: 1px solid var(--b1); transition: background 0.1s; }
  tbody tr:hover { background: var(--bg3); }
  tbody tr.disabled { opacity: 0.45; }

  td { padding: 6px 10px; color: var(--t1); white-space: nowrap; }

  .key    { color: var(--amber); font-weight: 600; font-size: 12px; letter-spacing: 0.04em; }
  .symbol { color: var(--cyan);  font-weight: 600; }
  .dim    { color: var(--t2); }

  .skeleton-rows { display: flex; flex-direction: column; gap: 4px; padding: 8px; }
  .empty { padding: 20px; font-size: 11px; color: var(--t3); }
</style>
