<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createSSE } from '$stores/sse';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import { POLL_INTERVAL_MS } from '$lib/config';
  import Badge from '$components/ui/Badge.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Panel from '$components/ui/Panel.svelte';
  import type { StripData } from '$lib/types';
  import {
    fmtPrice,
    fmtPct,
    fmtDollar,
    fmtConfidence,
    scoreColor,
    signalVariant,
    riskVariant,
    regimeVariant,
    directionVariant,
  } from '$lib/utils/format';
  import type { PageData } from './$types';

  // ─── Server data (SSR prefetch) ────────────────────────────────────
  // Populated by +page.server.ts before first paint; client-side poll
  // stores take over on their first tick and these become unreferenced.
  let { data }: { data: PageData } = $props();

  // ─── Types ──────────────────────────────────────────────────────────
  // StripData is imported from $lib/types

  interface MarketAsset {
    symbol: string;
    name: string;
    price: number;
    score: number;
    cnn_signal?: string;
    ruby_signal?: string;
    asset_class?: string;
    age?: number;
    change_pct?: number;
  }

  interface OpenTrade {
    id: number;
    asset: string;
    direction: string;
    entry: number;
    pnl: number;
    contracts?: number;
    strategy?: string;
  }

  interface RecentSignal {
    symbol?: string;
    direction?: string;
    strategy?: string;
    confidence?: number;
    timestamp?: string;
  }

  interface FactoryStatus {
    status?: string;
    healthy?: boolean;
    workers?: Record<string, string>;
    providers?: Record<string, { state?: string; failures?: number }>;
    gap_count?: number;
    last_gap_scan?: string;
    uptime_seconds?: number;
  }

  // ─── SSE: Strip Stats ───────────────────────────────────────────────
  const stripSSE = createSSE<StripData>('/sse/strip');
  let strip = $derived($stripSSE);

  // ─── Poll: Market Scores ────────────────────────────────────────────
  const scoresStore = createPoll<MarketAsset[]>('/api/pipeline/scores/json', 30_000, {
    transform(raw: unknown): MarketAsset[] {
      if (raw && typeof raw === 'object' && 'assets' in raw) {
        return (raw as any).assets ?? [];
      }
      if (Array.isArray(raw)) return raw;
      return [];
    },
  });
  // Fall back to SSR-prefetched scores until the poll fires for the first time.
  let assets = $derived($scoresStore ?? (data.initialScores as MarketAsset[] | null) ?? []);

  // ─── Poll: Active Trades ────────────────────────────────────────────
  const tradesStore = createPoll<OpenTrade[]>('/api/trades/open', 5_000, {
    transform(raw: unknown): OpenTrade[] {
      if (Array.isArray(raw)) return raw;
      if (raw && typeof raw === 'object' && 'trades' in raw) return (raw as any).trades ?? [];
      return [];
    },
  });
  // Fall back to SSR-prefetched trades until the poll fires for the first time.
  let trades = $derived($tradesStore ?? (data.initialTrades as OpenTrade[] | null) ?? []);

  // ─── Poll: Recent Signals ──────────────────────────────────────────
  const signalsStore = createPoll<RecentSignal[]>('/api/db/redis/get/fks:memories:new', 10_000, {
    transform(raw: unknown): RecentSignal[] {
      if (Array.isArray(raw)) return raw;
      if (raw && typeof raw === 'object') {
        if ('value' in raw) {
          const val = (raw as any).value;
          if (typeof val === 'string') {
            try { const p = JSON.parse(val); return Array.isArray(p) ? p : [p]; } catch { return []; }
          }
          return Array.isArray(val) ? val : [val];
        }
        return [raw as RecentSignal];
      }
      return [];
    },
  });
  let signals = $derived($signalsStore ?? []);

  // ─── Poll: Factory Status ──────────────────────────────────────────
  const factoryStore = createPoll<FactoryStatus>('/factory/status', POLL_INTERVAL_MS, {
    transform(raw: unknown): FactoryStatus {
      if (raw && typeof raw === 'object') return raw as FactoryStatus;
      return { status: 'unknown' };
    },
  });
  // Fall back to SSR-prefetched factory status until the poll fires for the first time.
  let factory = $derived(
    $factoryStore ??
    (data.initialFactory as FactoryStatus | null) ??
    ({ status: 'unknown' } as FactoryStatus)
  );

  function factoryColor(f: FactoryStatus): string {
    if (!f || f.status === 'unknown' || f.status === 'not_started') return 'var(--dim)';
    if (f.status === 'error' || f.healthy === false) return 'var(--red)';
    if (f.gap_count && f.gap_count > 0) return 'var(--yellow)';
    return 'var(--green)';
  }

  function factoryLabel(f: FactoryStatus): string {
    if (!f || f.status === 'unknown') return 'Offline';
    if (f.status === 'not_started') return 'Not Started';
    if (f.status === 'error' || f.healthy === false) return 'Error';
    if (f.gap_count && f.gap_count > 0) return `${f.gap_count} Gap${f.gap_count > 1 ? 's' : ''}`;
    return 'Healthy';
  }

  function factoryVariant(f: FactoryStatus): 'green' | 'amber' | 'red' | 'default' {
    if (!f || f.status === 'unknown' || f.status === 'not_started') return 'default';
    if (f.status === 'error' || f.healthy === false) return 'red';
    if (f.gap_count && f.gap_count > 0) return 'amber';
    return 'green';
  }

  // ─── AI Brief ──────────────────────────────────────────────────────
  let briefing = $state('');
  let briefingLoading = $state(false);
  let briefingError = $state('');

  async function fetchBriefing() {
    briefingLoading = true;
    briefingError = '';
    try {
      const data = await api.get<any>('/api/grok/briefing');
      briefing = typeof data === 'string'
        ? data
        : data?.briefing ?? data?.text ?? data?.content ?? JSON.stringify(data, null, 2);
    } catch (e: unknown) {
      briefingError = e instanceof Error ? e.message : 'Failed to load briefing';
      console.warn('[overview/briefing]', e);
    } finally {
      briefingLoading = false;
    }
  }

  // ─── Helpers ────────────────────────────────────────────────────────
  // ─── Helpers imported from $lib/utils/format ────────────────────────
  // fmtPrice, fmtPct, fmtDollar, fmtConfidence, scoreColor,
  // signalVariant, riskVariant, regimeVariant, directionVariant

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    stripSSE.connect();
    scoresStore.start();
    tradesStore.start();
    signalsStore.start();
    factoryStore.start();
    fetchBriefing();
  });

  onDestroy(() => {
    stripSSE.disconnect();
    scoresStore.stop();
    tradesStore.stop();
    signalsStore.stop();
    factoryStore.stop();
  });
</script>

<svelte:head>
  <title>Overview — FKS Terminal</title>
</svelte:head>

<div class="page">

  <!-- ═══════════════════════════════════════════════════════════════════
       TOP: Strip-style stat row
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="stat-strip">
    <StatCard
      label="Focus"
      value={strip?.focus?.symbol ?? '—'}
      color="cyan"
    />
    <StatCard
      label="Day P&L"
      value={fmtDollar(strip?.pnl?.daily)}
      color={(strip?.pnl?.daily ?? 0) >= 0 ? 'green' : 'red'}
    />
    <StatCard
      label="Equity"
      value={strip?.equity != null ? '$' + strip.equity.toLocaleString() : '—'}
      color="default"
    />
    <div class="stat-badge-card">
      <span class="stat-badge-label">Risk</span>
      <Badge variant={riskVariant(strip?.risk?.dd_pct)}>
        {strip?.risk?.dd_pct != null ? `DD ${strip.risk.dd_pct.toFixed(1)}%` : '—'}
      </Badge>
    </div>
    <div class="stat-badge-card">
      <span class="stat-badge-label">Regime</span>
      <Badge variant={regimeVariant(strip?.regime?.label)}>
        {strip?.regime?.label ?? '—'}
      </Badge>
    </div>
    <div class="stat-badge-card">
      <span class="stat-badge-label">Factory</span>
      <Badge variant={factoryVariant(factory)}>
        <span class="factory-dot" style="background:{factoryColor(factory)}"></span>
        {factoryLabel(factory)}
      </Badge>
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════════════════════════
       MIDDLE: Two-column content area
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="body">

    <!-- ─── LEFT (60%): Market Overview Table ──────────────────────── -->
    <div class="pane pane-left">
      <Panel title="Market Overview" badge="30s poll" noPad fill>
          {#if assets.length === 0}
            <Skeleton lines={6} />
          {:else}
            <table class="tbl">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Name</th>
                  <th>Price</th>
                  <th>Score</th>
                  <th>Signal</th>
                  <th>Age</th>
                </tr>
              </thead>
              <tbody>
                {#each assets as asset}
                  <tr
                    class="tbl-row-link"
                    tabindex="0"
                    role="button"
                    aria-label="View {asset.symbol} in Trading workspace"
                    onclick={() => { window.location.href = '/trading'; }}
                    onkeydown={(e: KeyboardEvent) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        window.location.href = '/trading';
                      }
                    }}
                  >
                    <td class="accent">{asset.symbol}</td>
                    <td class="muted name-cell">{asset.name ?? '—'}</td>
                    <td>{fmtPrice(asset.price)}</td>
                    <td class="score-cell">
                      <ProgressBar
                        value={asset.score ?? 0}
                        color={scoreColor(asset.score ?? 0)}
                        height="5px"
                        label={asset.score?.toFixed(0) ?? '—'}
                      />
                    </td>
                    <td>
                      {#if asset.ruby_signal || asset.cnn_signal}
                        <Badge variant={signalVariant(asset.ruby_signal ?? asset.cnn_signal)}>
                          {asset.ruby_signal ?? asset.cnn_signal}
                        </Badge>
                      {:else}
                        <span class="muted">—</span>
                      {/if}
                    </td>
                    <td class="muted">{asset.age != null ? asset.age + 'd' : '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
      </Panel>
    </div>

    <!-- ─── RIGHT (40%): Quick Panels ─────────────────────────────── -->
    <div class="pane pane-right">

      <!-- Panel 1: AI Brief -->
      <Panel title="AI Brief">
        {#snippet header()}
          <button class="btn-refresh" onclick={fetchBriefing} disabled={briefingLoading}>
            {briefingLoading ? '⟳' : '↻'} Refresh
          </button>
        {/snippet}
          {#if briefingLoading && !briefing}
            <Skeleton lines={4} />
          {:else if briefingError && !briefing}
            <p class="error-text">{briefingError}</p>
          {:else if briefing}
            <pre class="briefing-text">{briefing}</pre>
          {:else}
            <p class="muted empty-state">No briefing available.</p>
          {/if}
      </Panel>

      <!-- Panel 2: Active Trades -->
      <Panel title="Active Trades" badge="5s poll">
          {#if trades.length === 0}
            <p class="muted empty-state">No open trades.</p>
          {:else}
            <ul class="compact-list">
              {#each trades as trade}
                <li class="compact-item">
                  <span class="compact-symbol">{trade.asset}</span>
                  <Badge variant={directionVariant(trade.direction)}>
                    {trade.direction?.toUpperCase() ?? '—'}
                  </Badge>
                  <span class="compact-detail">@ {fmtPrice(trade.entry)}</span>
                  <span
                    class="compact-pnl"
                    class:green={(trade.pnl ?? 0) >= 0}
                    class:red={(trade.pnl ?? 0) < 0}
                  >
                    {fmtDollar(trade.pnl)}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}
      </Panel>

      <!-- Panel 3: Data Factory -->
      <Panel title="Data Factory" badge="30s poll">
          {#if factory.status === 'unknown'}
            <p class="muted empty-state">Factory status unavailable.</p>
          {:else}
            <ul class="compact-list">
              <li class="compact-item">
                <span class="compact-symbol">Status</span>
                <Badge variant={factoryVariant(factory)}>
                  {factoryLabel(factory)}
                </Badge>
              </li>
              {#if factory.gap_count != null}
                <li class="compact-item">
                  <span class="compact-symbol">Data Gaps</span>
                  <span class:red={factory.gap_count > 0} class:green={factory.gap_count === 0}>
                    {factory.gap_count}
                  </span>
                </li>
              {/if}
              {#if factory.last_gap_scan}
                <li class="compact-item">
                  <span class="compact-symbol">Last Scan</span>
                  <span class="muted">{factory.last_gap_scan}</span>
                </li>
              {/if}
              {#if factory.providers}
                {#each Object.entries(factory.providers) as [name, prov]}
                  <li class="compact-item">
                    <span class="compact-symbol">{name}</span>
                    <Badge variant={prov.state === 'closed' ? 'green' : prov.state === 'half_open' ? 'amber' : 'red'}>
                      {prov.state ?? '?'}
                    </Badge>
                  </li>
                {/each}
              {/if}
            </ul>
          {/if}
      </Panel>

      <!-- Panel 4: Recent Signals -->
      <Panel title="Recent Signals" badge="10s poll">
          {#if signals.length === 0}
            <p class="muted empty-state">No recent signals.</p>
          {:else}
            <ul class="compact-list">
              {#each signals as sig}
                <li class="compact-item">
                  <span class="compact-symbol">{sig.symbol ?? '—'}</span>
                  {#if sig.direction}
                    <Badge variant={directionVariant(sig.direction)}>
                      {sig.direction.toUpperCase()}
                    </Badge>
                  {/if}
                  {#if sig.strategy}
                    <span class="compact-detail">{sig.strategy}</span>
                  {/if}
                  <span class="compact-conf muted">
                    {fmtConfidence(sig.confidence)}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}
      </Panel>

    </div><!-- /.pane-right -->
  </div><!-- /.body -->
</div><!-- /.page -->

<style>
  /* ═══════════════════════════════════════════════════════════════════
     Layout
     ═══════════════════════════════════════════════════════════════════ */
  .page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .body {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .pane {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
    gap: 0;
  }

  .pane-left {
    flex: 6;
    border-right: 1px solid var(--b1);
    min-width: 0;
    overflow-y: auto;
    padding: 8px;
  }

  .pane-right {
    flex: 4;
    min-width: 240px;
    max-width: 480px;
    overflow-y: auto;
    padding: 8px;
    gap: 8px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Stat Strip (top row)
     ═══════════════════════════════════════════════════════════════════ */
  .stat-strip {
    display: flex;
    align-items: stretch;
    gap: 8px;
    padding: 8px 10px;
    background: var(--bg0);
    border-bottom: 1px solid var(--b1);
    flex-shrink: 0;
    overflow-x: auto;
  }

  .stat-badge-card {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    padding: 10px 14px;
    min-width: 100px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .stat-badge-label {
    font-size: 9px;
    font-weight: 600;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1;
  }

  .factory-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;
  }

  /* Panel chrome is now handled by the <Panel> component */

  /* ═══════════════════════════════════════════════════════════════════
     Market Overview Table
     ═══════════════════════════════════════════════════════════════════ */
  .tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  .tbl th {
    text-align: left;
    padding: 6px 8px;
    color: var(--t3);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--b2);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--bg2);
    z-index: 1;
  }

  .tbl td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
  }

  .tbl-row-link {
    cursor: pointer;
    transition: background 0.1s ease;
  }

  .tbl-row-link:hover {
    background: var(--bg3);
  }

  .name-cell {
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .score-cell {
    min-width: 100px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     AI Briefing
     ═══════════════════════════════════════════════════════════════════ */
  .btn-refresh {
    all: unset;
    cursor: pointer;
    font-size: 9px;
    color: var(--t3);
    padding: 2px 8px;
    border-radius: var(--r);
    background: var(--bg3);
    margin-left: auto;
    transition: color 0.12s, background 0.12s;
  }

  .btn-refresh:hover:not(:disabled) {
    color: var(--cyan);
    background: var(--bg0);
  }

  .btn-refresh:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .briefing-text {
    font-family: inherit;
    font-size: 11px;
    line-height: 1.6;
    color: var(--t2);
    white-space: pre-wrap;
    word-wrap: break-word;
    margin: 0;
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 8px 10px;
    max-height: 160px;
    overflow-y: auto;
  }

  .error-text {
    font-size: 11px;
    color: var(--red);
    padding: 8px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Compact Lists (trades, signals)
     ═══════════════════════════════════════════════════════════════════ */
  .compact-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .compact-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 4px;
    border-bottom: 1px solid var(--b1);
    font-size: 11px;
  }

  .compact-item:last-child {
    border-bottom: none;
  }

  .compact-symbol {
    font-weight: 700;
    color: var(--accent);
    min-width: 40px;
  }

  .compact-detail {
    color: var(--t3);
    font-size: 10px;
  }

  .compact-pnl {
    margin-left: auto;
    font-weight: 600;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .compact-conf {
    margin-left: auto;
    font-size: 10px;
    font-variant-numeric: tabular-nums;
  }

  .empty-state {
    padding: 12px 0;
    text-align: center;
    font-size: 11px;
    color: var(--t3);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Utility
     ═══════════════════════════════════════════════════════════════════ */
  .accent { color: var(--accent); }
  .muted  { color: var(--t3); }
  .green  { color: var(--green); }
  .red    { color: var(--red); }

</style>
<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtDollar, fmtPct, fmtFixed } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface WorkerStatus {
    quality?: number;
    daily_pnl?: number;
    daily_trades?: number;
    candles?: number;
    regime?: string;
    stack_dir?: string;
    stack_count?: number;
    params?: Record<string, number>;
    adl_level?: number;
    active_leverage?: number;
    target_leverage?: number;
    risk_per_trade_pct?: number;
    margin_used_usdt?: number;
    cnn_signal?: string;
    cnn_confidence?: number;
    master_risk_score?: number;
    master_halted?: boolean;
  }

  interface Worker {
    asset: string;
    alive: boolean;
    last_seen: number;
    age_str: string | null;
    dir_display: string;
    status: WorkerStatus;
  }

  interface GateStats {
    pass?: number;
    fail?: number;
    total?: number;
  }

  interface DashboardData {
    workers: Record<string, Worker>;
    stats: Record<string, unknown>;
    daily_pnl: number;
    bot_status: unknown;
    gate_stats: Record<string, GateStats>;
    timestamp: number;
  }

  // ─── Polling ─────────────────────────────────────────────────────────

  const dashPoll = createPoll<DashboardData>(`${ws.apiBase}/dashboard`, 5_000);

  let data     = $derived($dashPoll);
  let workers  = $derived(Object.values(data?.workers ?? {}));
  let stats    = $derived(data?.stats ?? {});
  let dailyPnl = $derived(data?.daily_pnl ?? 0);

  // ─── Worker helpers ───────────────────────────────────────────────────

  function qualityColor(q: number): 'green' | 'amber' | 'red' {
    if (q >= 65) return 'green';
    if (q >= 35) return 'amber';
    return 'red';
  }

  function dirBadge(dir: string): 'green' | 'red' | 'default' {
    if (dir === 'LONG')  return 'green';
    if (dir === 'SHORT') return 'red';
    return 'default';
  }

  function pnlColor(v: number) {
    return v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--t3)';
  }

  // ─── Bot control ──────────────────────────────────────────────────────

  let actionPending  = $state<string | null>(null);
  let actionFeedback = $state<{ msg: string; ok: boolean } | null>(null);

  async function workerAction(asset: string, action: 'start' | 'stop' | 'restart') {
    actionPending  = `${asset}:${action}`;
    actionFeedback = null;
    try {
      await api.post(`${ws.apiBase}/bot/worker/${asset}/${action}`);
      actionFeedback = { msg: `${asset} ${action} sent`, ok: true };
      dashPoll.refresh();
    } catch (e) {
      actionFeedback = { msg: `Failed: ${e}`, ok: false };
    } finally {
      actionPending = null;
      setTimeout(() => (actionFeedback = null), 3000);
    }
  }

  onMount(() => {
    dashPoll.start();
    return () => dashPoll.stop();
  });
</script>

<div class="page">
  <!-- Stats bar -->
  <div class="stats-row">
    {#if data}
      <StatCard label="Daily PnL" value={fmtDollar(dailyPnl)} color={dailyPnl >= 0 ? 'green' : 'red'} />
      <StatCard label="Total Trades" value={String((stats as any).total_trades ?? '—')} />
      <StatCard label="Win Rate" value={fmtPct((stats as any).win_rate)} />
      <StatCard label="Best Asset" value={String((stats as any).best_asset ?? '—')} color="green" />
      <StatCard label="Worst Asset" value={String((stats as any).worst_asset ?? '—')} color="red" />
    {:else}
      {#each Array(5) as _}
        <Skeleton width="110px" height="54px" />
      {/each}
    {/if}

    {#if actionFeedback}
      <span class="feedback" class:ok={actionFeedback.ok}>{actionFeedback.msg}</span>
    {/if}
  </div>

  <!-- Worker grid -->
  <div class="worker-grid">
    {#if !data}
      {#each Array(4) as _}
        <Skeleton height="240px" />
      {/each}
    {:else if workers.length === 0}
      <p class="empty">No workers connected.</p>
    {:else}
      {#each workers as w}
        {@const st = w.status}
        {@const quality = st.quality ?? 0}
        <Panel>
          {#snippet header()}
            <span class="worker-asset">{w.asset.toUpperCase()}</span>
            <span class="dot" class:alive={w.alive} class:dead={!w.alive}></span>
            {#if w.alive}
              <Badge variant="default">{(st.regime ?? 'unknown').toLowerCase().replace('_', ' ')}</Badge>
            {:else}
              <Badge variant="red">offline{w.age_str ? ` · ${w.age_str}` : ''}</Badge>
            {/if}
            <Badge variant={dirBadge(w.dir_display)}>{w.dir_display}</Badge>
          {/snippet}

          <div class="worker-body">
            <div class="metric-row">
              <span class="lbl">Quality</span>
              <ProgressBar value={quality} color={qualityColor(quality)} height="5px" />
              <span class="val">{quality}</span>
            </div>

            <div class="kv-grid">
              <span class="lbl">Daily PnL</span>
              <span class="val" style="color:{pnlColor(st.daily_pnl ?? 0)}">{fmtDollar(st.daily_pnl)}</span>

              <span class="lbl">Trades</span>
              <span class="val">{st.daily_trades ?? '—'}</span>

              <span class="lbl">Candles</span>
              <span class="val">{st.candles ?? '—'}</span>

              <span class="lbl">Stack</span>
              <span class="val">{st.stack_count ?? 0} pos</span>

              <span class="lbl">Leverage</span>
              <span class="val">{st.active_leverage ?? '—'}×</span>

              <span class="lbl">Risk/Trade</span>
              <span class="val">{fmtPct(st.risk_per_trade_pct ?? 0)}</span>

              {#if st.master_halted}
                <span class="lbl" style="color:var(--red)">HALTED</span>
                <span class="val" style="color:var(--red)">risk score {fmtFixed(st.master_risk_score ?? 0)}</span>
              {:else if (st.master_risk_score ?? 0) > 0}
                <span class="lbl">Risk Score</span>
                <span class="val">{fmtFixed(st.master_risk_score ?? 0)}</span>
              {/if}
            </div>

            <div class="ctrl-row">
              {#if w.alive}
                <button class="ctrl-btn ctrl-btn--stop"   disabled={!!actionPending} onclick={() => workerAction(w.asset, 'stop')}>stop</button>
                <button class="ctrl-btn ctrl-btn--restart" disabled={!!actionPending} onclick={() => workerAction(w.asset, 'restart')}>restart</button>
              {:else}
                <button class="ctrl-btn ctrl-btn--start"  disabled={!!actionPending} onclick={() => workerAction(w.asset, 'start')}>start</button>
              {/if}
            </div>
          </div>
        </Panel>
      {/each}
    {/if}
  </div>
</div>

<style>
  .page { display: flex; flex-direction: column; gap: 10px; padding: 10px; height: 100%; overflow: auto; }
  .stats-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; flex-shrink: 0; }

  .feedback { font-size: 10px; padding: 4px 10px; border-radius: var(--r); background: var(--red-dim); color: var(--red); }
  .feedback.ok { background: var(--green-dim); color: var(--green); }

  .worker-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 8px; }

  .worker-asset { font-size: 12px; font-weight: 700; color: var(--t1); letter-spacing: 0.06em; }

  .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .dot.alive { background: var(--green); animation: breathe 2.5s ease-in-out infinite; }
  .dot.dead  { background: var(--t3); }

  @keyframes breathe {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.45; }
  }

  .worker-body { display: flex; flex-direction: column; gap: 10px; padding: 4px 0; }
  .metric-row  { display: flex; align-items: center; gap: 8px; }
  .kv-grid     { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 12px; }

  .lbl { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: 0.05em; }
  .val { font-size: 11px; color: var(--t1); text-align: right; }

  .ctrl-row { display: flex; gap: 6px; padding-top: 4px; border-top: 1px solid var(--b1); }

  .ctrl-btn {
    flex: 1; background: var(--bg3); border: 1px solid var(--b3); border-radius: var(--r);
    color: var(--t2); font-family: inherit; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.06em; padding: 3px 6px; cursor: pointer; transition: background 0.15s, color 0.15s;
  }
  .ctrl-btn:disabled { opacity: 0.4; cursor: default; }
  .ctrl-btn--stop:hover:not(:disabled)    { background: var(--red-dim);   color: var(--red);   border-color: var(--red-brd);   }
  .ctrl-btn--start:hover:not(:disabled)   { background: var(--green-dim); color: var(--green); border-color: var(--green-brd); }
  .ctrl-btn--restart:hover:not(:disabled) { background: var(--amber-dim); color: var(--amber); border-color: var(--amber-brd); }

  .empty { font-size: 11px; color: var(--t3); padding: 20px; }
</style>
