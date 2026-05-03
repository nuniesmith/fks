<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Modal from '$components/ui/Modal.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface Holding {
    amount: number;
    value_usd: number;
    target_pct?: number;
    actual_pct?: number;
    drift_pct?: number;
  }

  interface PortfolioResponse {
    total_value_usd: number;
    holdings: Record<string, Holding>;
    stablecoin_usd: number;
    needs_rebalance: boolean;
  }

  interface RebalanceTrade {
    asset: string;
    side: string;
    amount: number;
    usd_value: number;
  }

  interface RebalanceResponse {
    status: 'dry_run' | 'executed';
    trades: RebalanceTrade[];
    summary?: string;
  }

  interface HistoryEntry {
    timestamp: string;
    num_trades: number;
    total_buy_usd: number;
    total_sell_usd: number;
    status: string;
  }

  interface HistoryResponse {
    history: HistoryEntry[];
  }

  interface PortfolioConfig {
    allocations: Record<string, number>;
    stablecoin_reserve: number;
    drift_threshold: number;
    min_trade_usd: number;
    max_single_trade_usd: number;
    confirm_above_usd: number;
    max_rebalances_per_hour: number;
    mode: string;
    dry_run: boolean;
  }

  // ─── State ──────────────────────────────────────────────────────────

  // Portfolio polling
  const portfolioStore = createPoll<PortfolioResponse>('/api/crypto/portfolio', 30_000);
  let portfolioRaw = $derived($portfolioStore);
  let holdings = $derived.by(() => {
    if (!portfolioRaw?.holdings) return [];
    return Object.entries(portfolioRaw.holdings)
      .map(([asset, h]) => ({ asset, ...h }))
      .sort((a, b) => b.value_usd - a.value_usd);
  });
  let totalValue = $derived(portfolioRaw?.total_value_usd ?? 0);
  let stablecoinUsd = $derived(portfolioRaw?.stablecoin_usd ?? 0);
  let needsRebalance = $derived(portfolioRaw?.needs_rebalance ?? false);
  let numAssets = $derived(holdings.length);

  // Rebalance state
  let dryRunLoading = $state(false);
  let executeLoading = $state(false);
  let rebalanceResult = $state<RebalanceResponse | null>(null);
  let rebalanceError = $state<string | null>(null);
  let dryRunSucceeded = $state(false);

  // Confirmation modal
  let showConfirmModal = $state(false);

  // History state
  let history = $state<HistoryEntry[]>([]);
  let historyLoading = $state(true);
  let historyError = $state<string | null>(null);

  // Config state
  let config = $state<PortfolioConfig | null>(null);
  let configLoading = $state(false);
  let configSaving = $state(false);
  let configError = $state<string | null>(null);
  let configSuccess = $state(false);
  // Editable copies (shown as percentages in UI, stored as decimals)
  let editDriftThreshold = $state('5.0');
  let editMinTradeUsd = $state('10');
  let editConfirmAboveUsd = $state('500');
  let editDryRun = $state(true);
  // Per-asset allocation editing (displayed as %, sent as decimal)
  let editAllocations = $state<Record<string, string>>({});
  let allocTotal = $derived(
    Object.values(editAllocations).reduce((s, v) => s + (parseFloat(v) || 0), 0)
  );
  let allocValid = $derived(Math.abs(allocTotal - 100.0) < 1.0);

  // ─── Helpers ────────────────────────────────────────────────────────

  function fmtUsd(value: number): string {
    return '$' + value.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function fmtAmount(value: number): string {
    if (value >= 1000) return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (value >= 1) return value.toFixed(4);
    if (value >= 0.0001) return value.toFixed(6);
    return value.toFixed(8);
  }

  function fmtPct(value: number | undefined): string {
    if (value == null) return '—';
    return value.toFixed(2) + '%';
  }

  function driftColor(drift: number | undefined): string {
    if (drift == null) return 'var(--t3)';
    const abs = Math.abs(drift);
    if (abs <= 2) return 'var(--green)';
    if (abs <= 5) return 'var(--amber)';
    return 'var(--red)';
  }

  function driftVariant(drift: number | undefined): 'green' | 'amber' | 'red' | 'default' {
    if (drift == null) return 'default';
    const abs = Math.abs(drift);
    if (abs <= 2) return 'green';
    if (abs <= 5) return 'amber';
    return 'red';
  }

  function progressColor(drift: number | undefined): 'green' | 'amber' | 'red' | 'cyan' {
    if (drift == null) return 'cyan';
    const abs = Math.abs(drift);
    if (abs <= 2) return 'green';
    if (abs <= 5) return 'amber';
    return 'red';
  }

  function sideVariant(side: string): 'green' | 'red' | 'default' {
    const s = side.toUpperCase();
    if (s === 'BUY') return 'green';
    if (s === 'SELL') return 'red';
    return 'default';
  }

  function statusVariant(status: string): 'green' | 'red' | 'amber' | 'cyan' | 'default' {
    const s = status.toLowerCase();
    if (s === 'executed' || s === 'success' || s === 'completed') return 'green';
    if (s === 'failed' || s === 'error') return 'red';
    if (s === 'partial' || s === 'pending') return 'amber';
    if (s === 'dry_run') return 'cyan';
    return 'default';
  }

  function fmtTimestamp(ts: string): string {
    try {
      const d = new Date(ts);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
        ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  }

  // ─── API Calls ──────────────────────────────────────────────────────

  async function doDryRun() {
    dryRunLoading = true;
    rebalanceError = null;
    rebalanceResult = null;
    dryRunSucceeded = false;
    try {
      const res = await api.post<RebalanceResponse>('/api/crypto/portfolio/rebalance', { dry_run: true });
      rebalanceResult = res;
      dryRunSucceeded = true;
    } catch (err: unknown) {
      rebalanceError = err instanceof Error ? err.message : String(err);
      dryRunSucceeded = false;
    } finally {
      dryRunLoading = false;
    }
  }

  function requestExecute() {
    showConfirmModal = true;
  }

  async function confirmExecute() {
    showConfirmModal = false;
    executeLoading = true;
    rebalanceError = null;
    try {
      const res = await api.post<RebalanceResponse>('/api/crypto/portfolio/rebalance', {
        dry_run: false,
        confirm: true,
      });
      rebalanceResult = res;
      dryRunSucceeded = false;
      // Refresh portfolio and history after execution
      portfolioStore.refresh();
      loadHistory();
    } catch (err: unknown) {
      rebalanceError = err instanceof Error ? err.message : String(err);
    } finally {
      executeLoading = false;
    }
  }

  async function loadHistory() {
    historyLoading = true;
    historyError = null;
    try {
      const res = await api.get<HistoryResponse>('/api/crypto/portfolio/history?limit=20');
      history = res.history ?? [];
    } catch (err: unknown) {
      historyError = err instanceof Error ? err.message : String(err);
    } finally {
      historyLoading = false;
    }
  }

  async function loadConfig() {
    configLoading = true;
    configError = null;
    try {
      const res = await api.get<PortfolioConfig>('/api/crypto/portfolio/config');
      config = res;
      // Populate editable fields
      editDriftThreshold = ((res.drift_threshold ?? 0.05) * 100).toFixed(1);
      editMinTradeUsd = String(res.min_trade_usd ?? 10);
      editConfirmAboveUsd = String(res.confirm_above_usd ?? 500);
      editDryRun = res.dry_run ?? true;
      // Allocations: decimal → percent display
      const allocs: Record<string, string> = {};
      for (const [asset, weight] of Object.entries(res.allocations ?? {})) {
        allocs[asset] = (weight * 100).toFixed(2);
      }
      editAllocations = allocs;
    } catch (err: unknown) {
      configError = err instanceof Error ? err.message : String(err);
    } finally {
      configLoading = false;
    }
  }

  async function saveConfig() {
    if (!allocValid) return;
    configSaving = true;
    configError = null;
    configSuccess = false;
    try {
      // Convert percent inputs back to decimals
      const allocations: Record<string, number> = {};
      for (const [asset, pctStr] of Object.entries(editAllocations)) {
        allocations[asset] = (parseFloat(pctStr) || 0) / 100;
      }
      const body = {
        drift_threshold: parseFloat(editDriftThreshold) / 100,
        min_trade_usd: parseFloat(editMinTradeUsd),
        confirm_above_usd: parseFloat(editConfirmAboveUsd),
        dry_run: editDryRun,
        allocations,
      };
      const res = await api.put<{ status: string; config: PortfolioConfig }>(
        '/api/crypto/portfolio/config',
        body
      );
      config = res.config;
      configSuccess = true;
      setTimeout(() => (configSuccess = false), 3000);
    } catch (err: unknown) {
      configError = err instanceof Error ? err.message : String(err);
    } finally {
      configSaving = false;
    }
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────

  onMount(() => {
    portfolioStore.start();
    loadHistory();
    loadConfig();
  });

  onDestroy(() => {
    portfolioStore.stop();
  });
</script>

<svelte:head>
  <title>Crypto Portfolio — FKS Terminal</title>
</svelte:head>

<div class="page">
  <div class="pane">

    <!-- ═══════════════════════════════════════════════════════════════
         Section 1: Portfolio Table
         ═══════════════════════════════════════════════════════════════ -->
    <div style="flex:5; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Crypto Portfolio" badge="30s" noPad fill>
      {#snippet header()}
        {#if needsRebalance}
          <Badge variant="amber">Needs Rebalance</Badge>
        {/if}
        <span class="total-value">{fmtUsd(totalValue)}</span>
      {/snippet}
        {#if !portfolioRaw}
          <div style="padding:16px;">
            <Skeleton lines={8} height="18px" />
          </div>
        {:else if holdings.length === 0}
          <div class="empty-state">No holdings found.</div>
        {:else}
          <table class="ptf-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th class="r">Amount</th>
                <th class="r">Value (USD)</th>
                <th class="r">Target %</th>
                <th class="r">Actual %</th>
                <th class="r">Drift %</th>
                <th style="min-width:100px;">Allocation</th>
              </tr>
            </thead>
            <tbody>
              {#each holdings as h (h.asset)}
                <tr class="ptf-row">
                  <td>
                    <span class="asset-sym">{h.asset}</span>
                  </td>
                  <td class="r mono">{fmtAmount(h.amount)}</td>
                  <td class="r mono usd">{fmtUsd(h.value_usd)}</td>
                  <td class="r mono">{fmtPct(h.target_pct)}</td>
                  <td class="r mono">{fmtPct(h.actual_pct)}</td>
                  <td class="r">
                    <span class="drift-val" style="color:{driftColor(h.drift_pct)};">
                      {fmtPct(h.drift_pct)}
                    </span>
                  </td>
                  <td>
                    <div class="alloc-cell">
                      <ProgressBar
                        value={h.actual_pct ?? 0}
                        color={progressColor(h.drift_pct)}
                        height="6px"
                      />
                      {#if h.target_pct != null}
                        <div
                          class="target-marker"
                          style="left:{Math.min(100, Math.max(0, h.target_pct))}%;"
                          title="Target: {h.target_pct.toFixed(1)}%"
                        ></div>
                      {/if}
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>

          <!-- Summary row -->
          <div class="summary-bar">
            <div class="summary-item">
              <span class="summary-label">Total Value</span>
              <span class="summary-val accent">{fmtUsd(totalValue)}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Stablecoin</span>
              <span class="summary-val">{fmtUsd(stablecoinUsd)}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Assets</span>
              <span class="summary-val">{numAssets}</span>
            </div>
          </div>
        {/if}
    </Panel>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════
         Section 2: Rebalance Controls
         ═══════════════════════════════════════════════════════════════ -->
    <div style="flex:3; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Rebalance" fill>
      {#snippet header()}
        <div class="btn-group">
          <button
            class="btn-primary"
            onclick={doDryRun}
            disabled={dryRunLoading}
          >
            {#if dryRunLoading}
              ⏳ Running…
            {:else}
              🔍 Dry Run
            {/if}
          </button>
          <button
            class="btn-danger"
            onclick={requestExecute}
            disabled={!dryRunSucceeded || executeLoading}
          >
            {#if executeLoading}
              ⏳ Executing…
            {:else}
              ⚡ Execute
            {/if}
          </button>
        </div>
      {/snippet}
        {#if rebalanceError}
          <div class="error-box">
            <span class="error-icon">✕</span>
            {rebalanceError}
          </div>
        {/if}

        {#if dryRunLoading || executeLoading}
          <Skeleton lines={4} height="14px" />
        {:else if rebalanceResult}
          <div class="result-header">
            <Badge variant={rebalanceResult.status === 'executed' ? 'green' : 'cyan'}>
              {rebalanceResult.status === 'executed' ? '✓ Executed' : '⦿ Dry Run'}
            </Badge>
            {#if rebalanceResult.summary}
              <span class="result-summary">{rebalanceResult.summary}</span>
            {/if}
          </div>

          {#if rebalanceResult.trades.length === 0}
            <div class="empty-state" style="padding:12px 0;">No trades needed — portfolio is balanced.</div>
          {:else}
            <table class="trade-table">
              <thead>
                <tr>
                  <th>Side</th>
                  <th>Asset</th>
                  <th class="r">Amount</th>
                  <th class="r">USD Value</th>
                </tr>
              </thead>
              <tbody>
                {#each rebalanceResult.trades as trade (trade.asset + trade.side)}
                  <tr class="trade-row">
                    <td>
                      <Badge variant={sideVariant(trade.side)}>
                        {trade.side.toUpperCase()}
                      </Badge>
                    </td>
                    <td class="mono asset-sym">{trade.asset}</td>
                    <td class="r mono">{fmtAmount(trade.amount)}</td>
                    <td class="r mono usd">{fmtUsd(trade.usd_value)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        {:else}
          <div class="empty-state">
            Run a <strong>Dry Run</strong> to preview rebalance trades before executing.
          </div>
        {/if}
    </Panel>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════
         Section 3: Rebalance History
         ═══════════════════════════════════════════════════════════════ -->
    <div style="flex:3; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Rebalance History" noPad fill>
      {#snippet header()}
        <button class="btn-ghost" onclick={loadHistory} disabled={historyLoading}>
          {historyLoading ? '⏳' : '↻'} Refresh
        </button>
      {/snippet}
        {#if historyLoading && history.length === 0}
          <div style="padding:16px;">
            <Skeleton lines={5} height="14px" />
          </div>
        {:else if historyError}
          <div class="error-box" style="margin:12px;">
            <span class="error-icon">✕</span>
            {historyError}
          </div>
        {:else if history.length === 0}
          <div class="empty-state">No rebalance history yet.</div>
        {:else}
          <table class="history-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th class="r">Trades</th>
                <th class="r">Buy Total</th>
                <th class="r">Sell Total</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {#each history as entry (entry.timestamp)}
                <tr class="history-row">
                  <td class="mono ts">{fmtTimestamp(entry.timestamp)}</td>
                  <td class="r mono">{entry.num_trades}</td>
                  <td class="r mono buy-val">{fmtUsd(entry.total_buy_usd)}</td>
                  <td class="r mono sell-val">{fmtUsd(entry.total_sell_usd)}</td>
                  <td>
                    <Badge variant={statusVariant(entry.status)}>
                      {entry.status}
                    </Badge>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
    </Panel>
    </div>

    <!-- ═══════════════════════════════════════════════════════════════
         Section 4: Portfolio Config
         ═══════════════════════════════════════════════════════════════ -->
    <div style="flex:4; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Portfolio Config" fill>
      {#snippet header()}
        <div class="btn-group">
          <button class="btn-ghost" onclick={loadConfig} disabled={configLoading}>
            {configLoading ? '⏳' : '↻'} Reload
          </button>
          <button
            class="btn-primary"
            onclick={saveConfig}
            disabled={configSaving || !allocValid}
            title={!allocValid ? `Allocations sum to ${allocTotal.toFixed(2)}% — must be 100%` : ''}
          >
            {configSaving ? '⏳ Saving…' : '💾 Save'}
          </button>
        </div>
      {/snippet}
      <div class="cfg-body">
        {#if configError}
          <div class="error-box">
            <span class="error-icon">✕</span>
            {configError}
          </div>
        {/if}
        {#if configSuccess}
          <div class="success-box">✓ Config saved successfully.</div>
        {/if}

        {#if configLoading && !config}
          <div style="padding:12px;"><span class="t3">Loading config…</span></div>
        {:else}
          <!-- ── Guard rows ── -->
          <div class="cfg-grid">
            <div class="cfg-row">
              <label class="cfg-label" for="cfg-drift-threshold">Drift Threshold</label>
              <div class="cfg-input-wrap">
                <input
                  id="cfg-drift-threshold"
                  class="cfg-input"
                  type="number"
                  min="0.1"
                  max="50"
                  step="0.1"
                  bind:value={editDriftThreshold}
                />
                <span class="cfg-unit">%</span>
              </div>
              <span class="cfg-hint">Rebalance when any asset drifts this far from target</span>
            </div>
            <div class="cfg-row">
              <label class="cfg-label" for="cfg-min-trade">Min Trade</label>
              <div class="cfg-input-wrap">
                <input
                  id="cfg-min-trade"
                  class="cfg-input"
                  type="number"
                  min="0"
                  step="1"
                  bind:value={editMinTradeUsd}
                />
                <span class="cfg-unit">USD</span>
              </div>
              <span class="cfg-hint">Skip trades smaller than this</span>
            </div>
            <div class="cfg-row">
              <label class="cfg-label" for="cfg-confirm-above">Confirm Above</label>
              <div class="cfg-input-wrap">
                <input
                  id="cfg-confirm-above"
                  class="cfg-input"
                  type="number"
                  min="0"
                  step="10"
                  bind:value={editConfirmAboveUsd}
                />
                <span class="cfg-unit">USD</span>
              </div>
              <span class="cfg-hint">Require confirmation when total trade exceeds this</span>
            </div>
            <div class="cfg-row">
              <label class="cfg-label" for="cfg-dry-run">Dry Run</label>
              <label class="toggle">
                <input id="cfg-dry-run" type="checkbox" bind:checked={editDryRun} />
                <span class="toggle-track">
                  <span class="toggle-thumb"></span>
                </span>
                <span class="toggle-lbl">{editDryRun ? 'Enabled (safe)' : 'DISABLED — live orders!'}</span>
              </label>
              <span class="cfg-hint">When on, no real orders are ever placed</span>
            </div>
          </div>

          <!-- ── Allocation weights ── -->
          <div class="cfg-section-hd">
            Target Allocations
            <span class="alloc-total" class:alloc-ok={allocValid} class:alloc-bad={!allocValid}>
              {allocTotal.toFixed(2)}% / 100%
            </span>
          </div>
          <div class="alloc-grid">
            {#each Object.entries(editAllocations) as [asset, pctStr] (asset)}
              <div class="alloc-row">
                <span class="alloc-asset">{asset}</span>
                <div class="cfg-input-wrap alloc-inp-wrap">
                  <input
                    class="cfg-input alloc-inp"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={pctStr}
                    oninput={(e) => {
                      editAllocations = { ...editAllocations, [asset]: (e.target as HTMLInputElement).value };
                    }}
                  />
                  <span class="cfg-unit">%</span>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </Panel>
    </div>

  </div><!-- /.pane -->
</div><!-- /.page -->

<!-- ═══════════════════════════════════════════════════════════════
     Confirmation Modal
     ═══════════════════════════════════════════════════════════════ -->
<Modal
  open={showConfirmModal}
  title="Confirm Live Rebalance"
  onclose={() => showConfirmModal = false}
>
  <div class="confirm-body">
    <div class="confirm-icon">⚠️</div>
    <p class="confirm-text">
      Are you sure? This will execute <strong>live trades</strong> on your crypto exchange account.
      This action cannot be undone.
    </p>
    {#if rebalanceResult?.trades?.length}
      <div class="confirm-trade-count">
        <Badge variant="amber">{rebalanceResult.trades.length} trade{rebalanceResult.trades.length === 1 ? '' : 's'} will be placed</Badge>
      </div>
    {/if}
  </div>

  {#snippet actions()}
    <button class="btn-ghost" onclick={() => showConfirmModal = false}>Cancel</button>
    <button class="btn-danger-solid" onclick={confirmExecute}>⚡ Execute Live Trades</button>
  {/snippet}
</Modal>

<style>
  /* ═══════════════════════════════════════════════════════════════════
     Layout
     ═══════════════════════════════════════════════════════════════════ */
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
  }

  .pane {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    flex: 1;
    min-width: 0;
    padding: 10px;
    gap: 8px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Total Value in Header
     ═══════════════════════════════════════════════════════════════════ */
  .total-value {
    margin-left: auto;
    font-size: 14px;
    font-weight: 700;
    font-family: var(--font-mono, monospace);
    color: var(--cyan, var(--accent));
    letter-spacing: -0.01em;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Shared table styles
     ═══════════════════════════════════════════════════════════════════ */
  .ptf-table,
  .trade-table,
  .history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
  }

  .ptf-table thead th,
  .trade-table thead th,
  .history-table thead th {
    padding: 4px 8px;
    text-align: left;
    color: var(--t3);
    font-weight: 500;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--b1);
    position: sticky;
    top: 0;
    background: var(--bg1);
    z-index: 1;
  }

  .ptf-table tbody td,
  .trade-table tbody td,
  .history-table tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--b1);
    vertical-align: middle;
  }

  .r { text-align: right !important; }
  .mono { font-family: var(--font-mono, monospace); }


  /* ═══════════════════════════════════════════════════════════════════
     Portfolio Table
     ═══════════════════════════════════════════════════════════════════ */
  .ptf-row {
    cursor: default;
    transition: background 0.1s;
  }
  .ptf-row:hover {
    background: var(--bg2);
  }

  .asset-sym {
    font-size: 11px;
    font-weight: 600;
    color: var(--t1);
  }

  .usd {
    color: var(--cyan, var(--accent));
  }

  .drift-val {
    font-family: var(--font-mono, monospace);
    font-size: 11px;
    font-weight: 600;
  }

  .alloc-cell {
    position: relative;
    min-width: 80px;
  }

  .target-marker {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 2px;
    height: 14px;
    background: var(--t1);
    opacity: 0.6;
    border-radius: 1px;
    pointer-events: none;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Summary Bar
     ═══════════════════════════════════════════════════════════════════ */
  .summary-bar {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 8px 12px;
    border-top: 1px solid var(--b1);
    background: var(--bg2);
  }

  .summary-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .summary-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .summary-val {
    font-size: 12px;
    font-weight: 600;
    font-family: var(--font-mono, monospace);
    color: var(--t1);
  }

  .summary-val.accent {
    color: var(--cyan, var(--accent));
  }

  /* ═══════════════════════════════════════════════════════════════════
     Buttons
     ═══════════════════════════════════════════════════════════════════ */
  .btn-group {
    display: flex;
    gap: 6px;
    margin-left: auto;
  }

  .btn-primary {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--bg0);
    background: var(--accent, var(--cyan));
    padding: 3px 12px;
    border-radius: var(--r);
    font-weight: 600;
    transition: opacity 0.12s;
  }
  .btn-primary:hover:not(:disabled) { opacity: 0.85; }
  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-danger {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--red);
    background: var(--red-dim, rgba(234, 57, 67, 0.12));
    border: 1px solid var(--red-brd, rgba(234, 57, 67, 0.25));
    padding: 3px 12px;
    border-radius: var(--r);
    font-weight: 600;
    transition: opacity 0.12s, background 0.12s;
  }
  .btn-danger:hover:not(:disabled) {
    background: rgba(234, 57, 67, 0.2);
  }
  .btn-danger:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .btn-danger-solid {
    all: unset;
    cursor: pointer;
    font-size: 11px;
    font-family: inherit;
    color: #fff;
    background: var(--red, #ea3943);
    padding: 6px 16px;
    border-radius: var(--r);
    font-weight: 600;
    transition: opacity 0.12s;
  }
  .btn-danger-solid:hover { opacity: 0.85; }

  .btn-ghost {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--t2);
    padding: 2px 8px;
    border-radius: var(--r);
    transition: background 0.12s, color 0.12s;
  }
  .btn-ghost:hover:not(:disabled) { background: var(--bg3); color: var(--t1); }
  .btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ═══════════════════════════════════════════════════════════════════
     Rebalance Results
     ═══════════════════════════════════════════════════════════════════ */
  .result-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .result-summary {
    font-size: 10px;
    color: var(--t2);
  }

  .trade-row {
    transition: background 0.1s;
  }
  .trade-row:hover {
    background: var(--bg2);
  }

  .buy-val { color: var(--green); }
  .sell-val { color: var(--red); }

  /* ═══════════════════════════════════════════════════════════════════
     History Table
     ═══════════════════════════════════════════════════════════════════ */
  .history-row {
    transition: background 0.1s;
  }
  .history-row:hover {
    background: var(--bg2);
  }

  .ts {
    font-size: 10px;
    color: var(--t2);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Error Box
     ═══════════════════════════════════════════════════════════════════ */
  .error-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--red-dim, rgba(234, 57, 67, 0.08));
    border: 1px solid var(--red-brd, rgba(234, 57, 67, 0.25));
    border-radius: var(--r);
    color: var(--red);
    font-size: 11px;
    margin-bottom: 8px;
  }

  .error-icon {
    font-weight: 700;
    font-size: 12px;
    flex-shrink: 0;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Empty state
     ═══════════════════════════════════════════════════════════════════ */
  .empty-state {
    color: var(--t3);
    font-size: 11px;
    text-align: center;
    padding: 24px 0;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Confirmation Modal
     ═══════════════════════════════════════════════════════════════════ */
  .confirm-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    text-align: center;
  }

  .confirm-icon {
    font-size: 28px;
    line-height: 1;
  }

  .confirm-text {
    font-size: 12px;
    color: var(--t2);
    line-height: 1.5;
    margin: 0;
    max-width: 360px;
  }

  .confirm-trade-count {
    margin-top: 4px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Portfolio Config Panel
     ═══════════════════════════════════════════════════════════════════ */
  .cfg-body {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .success-box {
    padding: 7px 10px;
    font-size: 10px;
    color: var(--green);
    background: rgba(0, 195, 105, 0.08);
    border: 1px solid rgba(0, 195, 105, 0.2);
    border-radius: var(--r);
  }

  .cfg-section-hd {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    font-weight: 600;
    color: var(--t2);
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding: 4px 0 2px;
    border-bottom: 1px solid var(--border);
  }

  .alloc-total {
    font-weight: 700;
    font-size: 10px;
    margin-left: auto;
  }
  .alloc-ok { color: var(--green); }
  .alloc-bad { color: var(--red); }

  .cfg-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .cfg-row {
    display: grid;
    grid-template-columns: 120px auto 1fr;
    align-items: center;
    gap: 8px;
  }

  .cfg-label {
    font-size: 10px;
    color: var(--t2);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
  }

  .cfg-input-wrap {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 2px 6px;
    width: 100px;
  }

  .cfg-input {
    all: unset;
    font-family: inherit;
    font-size: 11px;
    color: var(--t1);
    width: 70px;
    text-align: right;
  }

  .cfg-unit {
    font-size: 9px;
    color: var(--t3);
    white-space: nowrap;
  }

  .cfg-hint {
    font-size: 9px;
    color: var(--t3);
    padding-left: 4px;
  }

  /* Toggle */
  .toggle {
    display: flex;
    align-items: center;
    gap: 7px;
    cursor: pointer;
    user-select: none;
  }
  .toggle input { display: none; }
  .toggle-track {
    position: relative;
    width: 28px;
    height: 14px;
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 7px;
    transition: background 0.15s, border-color 0.15s;
  }
  .toggle input:checked ~ .toggle-track {
    background: rgba(0, 195, 105, 0.25);
    border-color: var(--green);
  }
  .toggle-thumb {
    position: absolute;
    top: 1px;
    left: 1px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--t3);
    transition: transform 0.15s, background 0.15s;
  }
  .toggle input:checked ~ .toggle-track .toggle-thumb {
    transform: translateX(14px);
    background: var(--green);
  }
  .toggle-lbl {
    font-size: 10px;
    color: var(--t2);
  }

  /* Allocation grid */
  .alloc-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 6px;
  }

  .alloc-row {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 8px;
  }

  .alloc-asset {
    font-size: 10px;
    font-weight: 700;
    color: var(--accent, var(--cyan));
    width: 60px;
    flex-shrink: 0;
  }

  .alloc-inp-wrap {
    width: auto;
    flex: 1;
    background: transparent;
    border: none;
    padding: 0;
  }

  .alloc-inp {
    width: 50px;
  }
</style>
