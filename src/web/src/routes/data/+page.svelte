<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Panel from '$components/ui/Panel.svelte';

  // ─── Types ──────────────────────────────────────────────────────────

  interface IntervalInfo {
    status: string;
    pct: number;
    target_days: number;
    min_days: number;
  }

  interface CoverageAsset {
    name: string;
    asset_class: string;
    intervals: Record<string, IntervalInfo>;
    status: string;
  }

  interface CoverageResponse {
    assets: Record<string, CoverageAsset>;
    total: number;
    ok: number;
    partial: number;
    critical: number;
    empty: number;
  }

  interface WorkerInfo {
    running: boolean;
    last_run: string | null;
  }

  interface ProviderInfo {
    status: string;
    on_cooldown: boolean;
  }

  interface FactoryStatusResponse {
    status: string;
    enabled_assets: number;
    total_assets: number;
    workers: Record<string, WorkerInfo>;
    providers: Record<string, ProviderInfo>;
    last_gap_scan: string | null;
  }

  interface ProviderHealthEntry {
    status: string;
    latency_ms?: number;
    last_error?: string | null;
    requests_today?: number;
  }

  interface ProviderHealthResponse {
    providers: Record<string, ProviderHealthEntry>;
  }

  interface Dataset {
    symbol: string;
    type: string;
    interval: string;
    rows: number;
    size_bytes: number;
    date_range: string;
    path: string;
  }

  interface DatasetsResponse {
    count: number;
    datasets: Dataset[];
  }

  interface Gap {
    symbol: string;
    interval: string;
    start: string;
    end: string;
    missing_bars: number;
  }

  interface GapsResponse {
    gaps: Gap[];
    total_gaps: number;
    total_missing: number;
    scanned_at: string;
  }

  interface BackfillJob {
    symbol: string;
    interval: string;
    status: string;
    progress: number;
    total_chunks: number;
    done_chunks: number;
    failed_chunks: number;
    last_error: string | null;
  }

  interface BackfillStatusResponse {
    jobs: BackfillJob[];
    queue_length: number;
    active: number;
    done: number;
    failed: number;
  }

  // ─── Constants ──────────────────────────────────────────────────────

  const INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1D'];

  // ─── Polling Stores ─────────────────────────────────────────────────

  const coverageStore = createPoll<CoverageResponse>('/factory/coverage', 60_000);
  let coverageData = $derived($coverageStore);
  let coverageAssets = $derived.by(() => {
    if (!coverageData?.assets) return [];
    return Object.entries(coverageData.assets).map(([symbol, asset]) => ({
      symbol,
      ...asset,
    }));
  });

  const factoryStore = createPoll<FactoryStatusResponse>('/factory/status', 30_000);
  let factoryData = $derived($factoryStore);

  const providerHealthStore = createPoll<ProviderHealthResponse>('/factory/providers/health', 30_000);
  let providerHealthData = $derived($providerHealthStore);

  const gapsStore = createPoll<GapsResponse>('/factory/coverage/gaps/json', 120_000);
  let gapsData = $derived($gapsStore);
  let gaps = $derived(gapsData?.gaps ?? []);

  const backfillStore = createPoll<BackfillStatusResponse>('/factory/coverage/backfill-status/json', 30_000);
  let backfillData = $derived($backfillStore);
  let backfillJobs = $derived(backfillData?.jobs ?? []);

  // ─── Datasets (on-demand) ──────────────────────────────────────────

  let datasetsData = $state<DatasetsResponse | null>(null);
  let datasetsLoading = $state(false);
  let datasetsError = $state<string | null>(null);
  let generateLoading = $state(false);

  async function fetchDatasets(): Promise<void> {
    datasetsLoading = true;
    datasetsError = null;
    try {
      datasetsData = await api.get<DatasetsResponse>('/api/datasets');
    } catch (err: unknown) {
      datasetsError = err instanceof Error ? err.message : String(err);
    } finally {
      datasetsLoading = false;
    }
  }

  async function generateAll(): Promise<void> {
    generateLoading = true;
    try {
      await api.post('/api/datasets/generate');
      await fetchDatasets();
    } catch (err: unknown) {
      datasetsError = err instanceof Error ? err.message : String(err);
    } finally {
      generateLoading = false;
    }
  }

  // ─── Backfill trigger ──────────────────────────────────────────────

  let backfillTriggering = $state<string | null>(null);

  async function triggerBackfill(symbol: string, interval: string): Promise<void> {
    const key = `${symbol}:${interval}`;
    backfillTriggering = key;
    try {
      await api.post(`/factory/coverage/${encodeURIComponent(symbol)}/refresh?interval=${encodeURIComponent(interval)}`);
      await backfillStore.refresh();
    } catch (err: unknown) {
      console.warn('[backfill]', key, err);
    } finally {
      backfillTriggering = null;
    }
  }

  // ─── Helpers ────────────────────────────────────────────────────────

  function statusVariant(status: string): 'green' | 'amber' | 'red' | 'default' {
    const s = status.toUpperCase();
    if (s === 'OK' || s === 'HEALTHY' || s === 'RUNNING' || s === 'ONLINE') return 'green';
    if (s === 'PARTIAL' || s === 'DEGRADED' || s === 'WARNING') return 'amber';
    if (s === 'CRITICAL' || s === 'ERROR' || s === 'FAILED' || s === 'OFFLINE') return 'red';
    return 'default';
  }

  function pctColor(pct: number): 'green' | 'amber' | 'red' | 'cyan' {
    if (pct >= 95) return 'green';
    if (pct >= 60) return 'amber';
    if (pct > 0) return 'red';
    return 'cyan';
  }

  function gapSeverityColor(missing: number): 'red' | 'amber' | 'default' {
    if (missing > 500) return 'red';
    if (missing > 50) return 'amber';
    return 'default';
  }

  function backfillStatusVariant(status: string): 'cyan' | 'green' | 'red' | 'default' {
    const s = status.toUpperCase();
    if (s === 'RUNNING') return 'cyan';
    if (s === 'DONE') return 'green';
    if (s === 'FAILED') return 'red';
    return 'default';
  }

  function formatBytes(bytes: number): string {
    if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
    if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${bytes} B`;
  }

  function formatNumber(n: number): string {
    return n.toLocaleString();
  }

  function formatTime(iso: string | null | undefined): string {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  }

  function formatDateTime(iso: string | null | undefined): string {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  }

  function timeAgo(iso: string | null | undefined): string {
    if (!iso) return '—';
    try {
      const diff = Date.now() - new Date(iso).getTime();
      const mins = Math.floor(diff / 60_000);
      if (mins < 1) return 'just now';
      if (mins < 60) return `${mins}m ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h ago`;
      const days = Math.floor(hrs / 24);
      return `${days}d ago`;
    } catch {
      return '';
    }
  }

  function factoryStatusDot(status: string | undefined): string {
    if (!status) return 'dot-gray';
    const s = status.toUpperCase();
    if (s === 'OK' || s === 'HEALTHY' || s === 'RUNNING') return 'dot-green';
    if (s === 'DEGRADED' || s === 'PARTIAL' || s === 'WARNING') return 'dot-amber';
    return 'dot-red';
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────

  onMount(() => {
    coverageStore.start();
    factoryStore.start();
    providerHealthStore.start();
    gapsStore.start();
    backfillStore.start();
    fetchDatasets();
  });

  onDestroy(() => {
    coverageStore.stop();
    factoryStore.stop();
    providerHealthStore.stop();
    gapsStore.stop();
    backfillStore.stop();
  });
</script>

<svelte:head>
  <title>Data Factory — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ════════════════════════════════════════════════════════════════════
       LEFT PANE — Coverage + Factory Health + Datasets (50%)
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

    <!-- ── Panel 1: Coverage Table ─────────────────────────────────────── -->
    <div style="flex:5; min-height:0; display:flex; flex-direction:column;">
      <Panel title="Coverage" badge="60s" noPad fill>
        {#snippet header()}
          {#if coverageData}
            <span class="summary-text">
              {coverageData.total} assets
              <span class="sep">|</span>
              <span class="c-green">{coverageData.ok} ok</span>
              <span class="sep">|</span>
              <span class="c-amber">{coverageData.partial} partial</span>
              <span class="sep">|</span>
              <span class="c-red">{coverageData.critical} critical</span>
            </span>
          {/if}
        {/snippet}
        {#if !coverageData}
          <Skeleton lines={8} height="18px" />
        {:else if coverageAssets.length === 0}
          <div class="empty-state">No coverage data available</div>
        {:else}
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="col-sym">Symbol</th>
                  <th class="col-name">Name</th>
                  <th class="col-status">Status</th>
                  {#each INTERVALS as iv}
                    <th class="col-interval">{iv}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each coverageAssets as asset (asset.symbol)}
                  <tr>
                    <td class="cell-sym">{asset.symbol}</td>
                    <td class="cell-name">{asset.name}</td>
                    <td class="cell-status">
                      <Badge variant={statusVariant(asset.status)}>
                        {asset.status.toUpperCase()}
                      </Badge>
                    </td>
                    {#each INTERVALS as iv}
                      {@const info = asset.intervals[iv]}
                      <td class="cell-interval">
                        {#if info}
                          <div class="mini-progress">
                            <ProgressBar
                              value={info.pct}
                              color={pctColor(info.pct)}
                              height="4px"
                            />
                            <span class="mini-pct">{info.pct}%</span>
                          </div>
                        {:else}
                          <span class="no-data">—</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </Panel>
    </div>

    <!-- ── Panel 2: Factory Health ─────────────────────────────────────── -->
    <div style="flex:3; min-height:0; display:flex; flex-direction:column;">
      <Panel title="Factory Health" badge="30s" fill>
        {#snippet header()}
          {#if factoryData}
            <span class="status-dot {factoryStatusDot(factoryData.status)}"></span>
            <span class="status-label">{factoryData.status.toUpperCase()}</span>
          {/if}
        {/snippet}
        {#if !factoryData}
          <Skeleton lines={5} />
        {:else}
          <div class="health-grid">
            <!-- Overview -->
            <div class="health-section">
              <div class="health-section-title">Overview</div>
              <div class="health-row">
                <span class="health-key">Enabled Assets</span>
                <span class="health-val">{factoryData.enabled_assets} / {factoryData.total_assets}</span>
              </div>
              <div class="health-row">
                <span class="health-key">Last Gap Scan</span>
                <span class="health-val">{timeAgo(factoryData.last_gap_scan)}</span>
              </div>
            </div>

            <!-- Workers -->
            <div class="health-section">
              <div class="health-section-title">Workers</div>
              {#each Object.entries(factoryData.workers) as [name, worker]}
                <div class="health-row">
                  <span class="health-key">
                    <span class="status-dot {worker.running ? 'dot-green' : 'dot-gray'}"></span>
                    {name}
                  </span>
                  <span class="health-val">
                    {#if worker.running}
                      <Badge variant="green">RUNNING</Badge>
                    {:else}
                      <Badge variant="default">IDLE</Badge>
                    {/if}
                    {#if worker.last_run}
                      <span class="health-ago">{timeAgo(worker.last_run)}</span>
                    {/if}
                  </span>
                </div>
              {/each}
            </div>

            <!-- Providers -->
            <div class="health-section">
              <div class="health-section-title">Providers</div>
              {#each Object.entries(factoryData.providers) as [name, prov]}
                <div class="health-row">
                  <span class="health-key">
                    <span class="status-dot {statusVariant(prov.status) === 'green' ? 'dot-green' : statusVariant(prov.status) === 'amber' ? 'dot-amber' : statusVariant(prov.status) === 'red' ? 'dot-red' : 'dot-gray'}"></span>
                    {name}
                  </span>
                  <span class="health-val">
                    <Badge variant={statusVariant(prov.status)}>
                      {prov.status.toUpperCase()}
                    </Badge>
                    {#if prov.on_cooldown}
                      <Badge variant="amber">COOLDOWN</Badge>
                    {/if}
                    {#if providerHealthData?.providers?.[name]}
                      {@const ph = providerHealthData.providers[name]}
                      {#if ph.latency_ms != null}
                        <span class="health-ago">{ph.latency_ms}ms</span>
                      {/if}
                      {#if ph.requests_today != null}
                        <span class="health-ago">{ph.requests_today} req</span>
                      {/if}
                    {/if}
                  </span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </Panel>
    </div>

    <!-- ── Panel 3: Datasets ───────────────────────────────────────────── -->
    <div style="flex:4; min-height:0; display:flex; flex-direction:column;">
      <Panel title="Datasets" noPad fill>
        {#snippet header()}
          {#if datasetsData}
            <span class="summary-text">{datasetsData.count} datasets</span>
          {/if}
          <div style="display:flex; gap:4px;">
            <button class="btn-sm" onclick={fetchDatasets} disabled={datasetsLoading}>
              {datasetsLoading ? '⟳' : '↻'} Refresh
            </button>
            <button class="btn-sm btn-accent" onclick={generateAll} disabled={generateLoading}>
              {generateLoading ? '⟳ Generating…' : '⚡ Generate All'}
            </button>
          </div>
        {/snippet}
        {#if datasetsLoading && !datasetsData}
          <Skeleton lines={6} height="16px" />
        {:else if datasetsError}
          <div class="empty-state error-text">{datasetsError}</div>
        {:else if !datasetsData || datasetsData.datasets.length === 0}
          <div class="empty-state">No datasets found. Click "Generate All" to create them.</div>
        {:else}
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Interval</th>
                  <th class="col-num">Rows</th>
                  <th class="col-num">Size</th>
                  <th>Date Range</th>
                </tr>
              </thead>
              <tbody>
                {#each datasetsData.datasets as ds, i (ds.path)}
                  <tr>
                    <td class="cell-sym">{ds.symbol}</td>
                    <td>
                      <Badge variant="default">{ds.type}</Badge>
                    </td>
                    <td>{ds.interval}</td>
                    <td class="col-num cell-mono">{formatNumber(ds.rows)}</td>
                    <td class="col-num cell-mono">{formatBytes(ds.size_bytes)}</td>
                    <td class="cell-dim">{ds.date_range}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </Panel>
    </div>

  </div>

  <!-- ════════════════════════════════════════════════════════════════════
       RIGHT PANE — Gap Scanner + Backfill Status (50%)
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <!-- ── Panel 1: Gap Scanner ────────────────────────────────────────── -->
    <div style="flex:6; min-height:0; display:flex; flex-direction:column;">
      <Panel title="Gap Scanner" badge="120s" noPad fill>
        {#snippet header()}
          {#if gapsData}
            <span class="summary-text">
              {gapsData.total_gaps} gaps
              <span class="sep">|</span>
              {formatNumber(gapsData.total_missing)} missing bars
              <span class="sep">|</span>
              Scanned {formatTime(gapsData.scanned_at)}
            </span>
          {/if}
        {/snippet}
        {#if !gapsData}
          <Skeleton lines={8} height="16px" />
        {:else if gaps.length === 0}
          <div class="empty-state">✓ No gaps detected — coverage is complete</div>
        {:else}
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Interval</th>
                  <th>From</th>
                  <th>To</th>
                  <th class="col-num">Missing</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {#each gaps as gap, i (`${gap.symbol}:${gap.interval}:${gap.start}`)}
                  {@const severity = gapSeverityColor(gap.missing_bars)}
                  <tr class={severity === 'red' ? 'row-red' : severity === 'amber' ? 'row-amber' : ''}>
                    <td class="cell-sym">{gap.symbol}</td>
                    <td>{gap.interval}</td>
                    <td class="cell-dim">{formatDateTime(gap.start)}</td>
                    <td class="cell-dim">{formatDateTime(gap.end)}</td>
                    <td class="col-num">
                      <Badge variant={severity}>
                        {formatNumber(gap.missing_bars)}
                      </Badge>
                    </td>
                    <td>
                      <button
                        class="btn-sm btn-backfill"
                        onclick={() => triggerBackfill(gap.symbol, gap.interval)}
                        disabled={backfillTriggering === `${gap.symbol}:${gap.interval}`}
                      >
                        {backfillTriggering === `${gap.symbol}:${gap.interval}` ? '⟳' : '▶'} Backfill
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </Panel>
    </div>

    <!-- ── Panel 2: Backfill Status ────────────────────────────────────── -->
    <div style="flex:4; min-height:0; display:flex; flex-direction:column;">
      <Panel title="Backfill Status" badge="30s" noPad fill>
        {#snippet header()}
          {#if backfillData}
            <span class="summary-text">
              Queue: {backfillData.queue_length}
              <span class="sep">|</span>
              <span class="c-cyan">Active: {backfillData.active}</span>
              <span class="sep">|</span>
              <span class="c-green">Done: {backfillData.done}</span>
              <span class="sep">|</span>
              <span class="c-red">Failed: {backfillData.failed}</span>
            </span>
          {/if}
        {/snippet}
        {#if !backfillData}
          <Skeleton lines={5} height="16px" />
        {:else if backfillJobs.length === 0}
          <div class="empty-state">No backfill jobs in queue</div>
        {:else}
          <div class="backfill-list">
            {#each backfillJobs as job (`${job.symbol}:${job.interval}`)}
              {@const pct = job.total_chunks > 0 ? Math.round((job.done_chunks / job.total_chunks) * 100) : job.progress}
              <div class="backfill-job">
                <div class="job-header">
                  <span class="job-sym">{job.symbol}</span>
                  <span class="job-iv">{job.interval}</span>
                  <Badge variant={backfillStatusVariant(job.status)}>
                    {job.status.toUpperCase()}
                  </Badge>
                  <span class="job-chunks">
                    {job.done_chunks}/{job.total_chunks}
                    {#if job.failed_chunks > 0}
                      <span class="c-red">({job.failed_chunks} failed)</span>
                    {/if}
                  </span>
                </div>
                <ProgressBar
                  value={pct}
                  color={backfillStatusVariant(job.status) === 'red' ? 'red' : backfillStatusVariant(job.status) === 'green' ? 'green' : 'cyan'}
                  height="5px"
                  label="{pct}%"
                />
                {#if job.last_error}
                  <div class="job-error">{job.last_error}</div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </Panel>
    </div>

  </div>
</div>

<style>
  /* ═══════════════════════════════════════════════════════════════════
     Layout
     ═══════════════════════════════════════════════════════════════════ */
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
    gap: 0;
  }

  .pane {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
    gap: 0;
  }

  .pane-left {
    flex: 5;
    border-right: 1px solid var(--b1);
    min-width: 0;
  }

  .pane-right {
    flex: 5;
    min-width: 0;
  }

  .summary-text {
    font-size: 9px;
    color: var(--t3);
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }

  .sep {
    color: var(--b1);
    margin: 0 1px;
  }

  .c-green { color: var(--green); }
  .c-amber { color: var(--amber); }
  .c-red   { color: var(--red); }
  .c-cyan  { color: var(--cyan); }

  .empty-state {
    padding: 24px 16px;
    text-align: center;
    color: var(--t3);
    font-size: 12px;
  }

  .error-text {
    color: var(--red);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Tables
     ═══════════════════════════════════════════════════════════════════ */
  .table-scroll {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  .data-table thead {
    position: sticky;
    top: 0;
    z-index: 2;
  }

  .data-table th {
    background: var(--bg2);
    color: var(--t2);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 4px 8px;
    border-bottom: 1px solid var(--b1);
    text-align: left;
    white-space: nowrap;
  }

  .data-table td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--b1);
    color: var(--t1);
    white-space: nowrap;
  }

  .data-table tbody tr {
    transition: background 0.1s;
  }

  .data-table tbody tr:hover {
    background: var(--bg2);
  }

  .col-sym { width: 70px; }
  .col-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
  .col-status { width: 70px; }
  .col-interval { width: 90px; min-width: 80px; }
  .col-num { text-align: right; }

  .cell-sym {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 10px;
    color: var(--accent);
  }

  .cell-name {
    color: var(--t2);
    font-size: 10px;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .cell-status {
    text-align: center;
  }

  .cell-interval {
    padding: 4px 6px;
  }

  .cell-dim {
    color: var(--t3);
    font-size: 10px;
  }

  .cell-mono {
    font-family: var(--font-mono);
    font-size: 10px;
  }

  .mini-progress {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 60px;
  }

  .mini-pct {
    font-size: 9px;
    color: var(--t3);
    font-family: var(--font-mono);
    flex-shrink: 0;
    width: 28px;
    text-align: right;
  }

  .no-data {
    color: var(--t3);
    font-size: 10px;
  }

  /* Gap severity row tints */
  .row-red {
    background: color-mix(in srgb, var(--red) 4%, transparent);
  }

  .row-amber {
    background: color-mix(in srgb, var(--amber) 4%, transparent);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Buttons
     ═══════════════════════════════════════════════════════════════════ */
  .btn-sm {
    font-size: 9px;
    padding: 2px 8px;
    border-radius: var(--r);
    border: 1px solid var(--b1);
    background: var(--bg3);
    color: var(--t2);
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.12s, border-color 0.12s, color 0.12s;
  }

  .btn-sm:hover:not(:disabled) {
    background: var(--bg2);
    border-color: var(--accent);
    color: var(--t1);
  }

  .btn-sm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-accent {
    border-color: var(--accent);
    color: var(--accent);
  }

  .btn-accent:hover:not(:disabled) {
    background: color-mix(in srgb, var(--accent) 12%, var(--bg2));
  }

  .btn-backfill {
    font-size: 8px;
    padding: 1px 6px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Factory Health
     ═══════════════════════════════════════════════════════════════════ */
  .health-grid {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .health-section {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .health-section-title {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    padding-bottom: 2px;
    border-bottom: 1px solid var(--b1);
    margin-bottom: 2px;
  }

  .health-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 2px 0;
  }

  .health-key {
    font-size: 10px;
    color: var(--t2);
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .health-val {
    font-size: 10px;
    color: var(--t1);
    font-family: var(--font-mono);
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .health-ago {
    font-size: 9px;
    color: var(--t3);
  }

  .status-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .dot-green {
    background: var(--green);
    box-shadow: 0 0 4px var(--green);
  }

  .dot-amber {
    background: var(--amber);
    box-shadow: 0 0 4px var(--amber);
  }

  .dot-red {
    background: var(--red);
    box-shadow: 0 0 4px var(--red);
  }

  .dot-gray {
    background: var(--t3);
  }

  .status-label {
    font-size: 9px;
    color: var(--t2);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Backfill Status
     ═══════════════════════════════════════════════════════════════════ */
  .backfill-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .backfill-job {
    padding: 6px 10px;
    border-bottom: 1px solid var(--b1);
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: background 0.1s;
  }

  .backfill-job:hover {
    background: var(--bg2);
  }

  .job-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .job-sym {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    color: var(--accent);
  }

  .job-iv {
    font-size: 9px;
    color: var(--t3);
    background: var(--bg3);
    padding: 0 4px;
    border-radius: var(--r);
  }

  .job-chunks {
    margin-left: auto;
    font-size: 9px;
    color: var(--t3);
    font-family: var(--font-mono);
  }

  .job-error {
    font-size: 9px;
    color: var(--red);
    padding: 2px 0;
    word-break: break-all;
  }
</style>
