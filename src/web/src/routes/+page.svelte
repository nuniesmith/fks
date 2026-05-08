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
