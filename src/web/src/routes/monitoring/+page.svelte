<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Panel from '$components/ui/Panel.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface MetricResult {
    metric: Record<string, string>;
    value: [number, string];
  }

  interface MetricResponse {
    status: string;
    data: {
      resultType: string;
      result: MetricResult[];
    };
  }

  interface RangeResult {
    metric: Record<string, string>;
    values: [number, string][];
  }

  interface RangeResponse {
    status: string;
    data: {
      resultType: string;
      result: RangeResult[];
    };
  }

  interface LayoutPanel {
    id: string;
    type: 'stat' | 'sparkline' | 'alert-feed' | 'targets';
    title: string;
    query?: string;
    unit?: string;
    warn?: number;
    crit?: number;
    color?: string;
  }

  interface LayoutResponse {
    panels: LayoutPanel[];
  }

  interface Alert {
    labels: {
      alertname: string;
      severity: string;
      instance: string;
      [key: string]: string;
    };
    age_str: string;
    severity_color: string;
  }

  interface AlertsResponse {
    data: Alert[];
  }

  interface ScrapeTarget {
    labels: {
      job: string;
      instance: string;
      [key: string]: string;
    };
    health: string;
    lastScrape: string;
    age_str: string;
    status_color: string;
  }

  interface TargetsResponse {
    status: string;
    data: {
      activeTargets: ScrapeTarget[];
    };
  }

  // ─── Health Stat Definitions ────────────────────────────────────────
  const healthStats = [
    {
      label: 'CPU %',
      query: "100 - avg(rate(node_cpu_seconds_total{mode='idle'}[5m]))*100",
      warn: 70,
      crit: 90,
      unit: '%',
    },
    {
      label: 'Memory %',
      query: '100*(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)',
      warn: 80,
      crit: 95,
      unit: '%',
    },
    {
      label: 'Redis ops/s',
      query: 'rate(redis_instantaneous_ops_per_sec[5m])',
      warn: 1000,
      crit: 5000,
      unit: '',
    },
    {
      label: 'HTTP req/s',
      query: 'rate(http_requests_total[5m])',
      warn: 100,
      crit: 500,
      unit: '',
    },
  ];

  // ─── Preset PromQL Chips ────────────────────────────────────────────
  const presetChips = [
    { label: 'CPU %', query: "100 - avg(rate(node_cpu_seconds_total{mode='idle'}[5m]))*100" },
    { label: 'Memory %', query: '100*(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)' },
    { label: 'Redis ops/s', query: 'rate(redis_instantaneous_ops_per_sec[5m])' },
    { label: 'HTTP req/s', query: 'rate(http_requests_total[5m])' },
    { label: 'Factory jobs', query: 'sum(factory_jobs_total)' },
    { label: 'Trade latency p95', query: 'histogram_quantile(0.95, rate(trade_latency_seconds_bucket[5m]))' },
  ];

  // ─── State ──────────────────────────────────────────────────────────
  let healthValues = $state<(number | null)[]>([null, null, null, null]);
  let healthLoading = $state(true);

  let layoutPanels = $state<LayoutPanel[]>([]);
  let panelData = $state<Record<string, any>>({});
  let layoutLoading = $state(true);

  let alerts = $state<Alert[]>([]);
  let alertsLoading = $state(true);

  let targets = $state<ScrapeTarget[]>([]);
  let targetsLoading = $state(true);

  let promqlInput = $state('');
  let promqlResults = $state<{ name: string; labels: string; value: string }[]>([]);
  let promqlRunning = $state(false);
  let promqlError = $state('');

  // ─── Timers ─────────────────────────────────────────────────────────
  let timers: ReturnType<typeof setInterval>[] = [];

  // ─── Helpers ────────────────────────────────────────────────────────
  function extractValue(resp: MetricResponse): number | null {
    if (resp?.data?.result?.length > 0) {
      const raw = resp.data.result[0].value[1];
      const n = parseFloat(raw);
      return isNaN(n) ? null : n;
    }
    return null;
  }

  function fmtNum(v: number | null, unit: string): string {
    if (v === null) return '—';
    if (unit === '%') return v.toFixed(1);
    if (v >= 10000) return (v / 1000).toFixed(1) + 'k';
    if (v >= 100) return v.toFixed(0);
    if (v >= 1) return v.toFixed(1);
    return v.toFixed(2);
  }

  function thresholdColor(v: number | null, warn: number, crit: number): 'green' | 'amber' | 'red' | 'default' {
    if (v === null) return 'default';
    if (v >= crit) return 'red';
    if (v >= warn) return 'amber';
    return 'green';
  }

  function severityVariant(severity: string): 'red' | 'amber' | 'cyan' | 'default' {
    const s = severity.toLowerCase();
    if (s === 'critical') return 'red';
    if (s === 'warning') return 'amber';
    if (s === 'info') return 'cyan';
    return 'default';
  }

  function healthVariant(health: string): 'green' | 'red' | 'default' {
    const h = health.toLowerCase();
    if (h === 'up') return 'green';
    if (h === 'down') return 'red';
    return 'default';
  }

  function buildSparklinePath(values: [number, string][], width: number, height: number): string {
    if (!values || values.length < 2) return '';
    const nums = values.map(v => parseFloat(v[1])).filter(n => !isNaN(n));
    if (nums.length < 2) return '';
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const range = max - min || 1;
    const stepX = width / (nums.length - 1);
    const pad = 2;
    const usableH = height - pad * 2;
    return nums
      .map((v, i) => {
        const x = i * stepX;
        const y = pad + usableH - ((v - min) / range) * usableH;
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }

  function labelsStr(metric: Record<string, string>): string {
    const entries = Object.entries(metric).filter(([k]) => k !== '__name__');
    if (entries.length === 0) return '';
    return '{' + entries.map(([k, v]) => `${k}="${v}"`).join(', ') + '}';
  }

  // ─── Fetch Functions ────────────────────────────────────────────────
  async function fetchHealthStats(): Promise<void> {
    try {
      const results = await Promise.all(
        healthStats.map((s) =>
          api.get<MetricResponse>(`/api/metrics/query?query=${encodeURIComponent(s.query)}`)
            .catch(() => null)
        )
      );
      healthValues = results.map((r) => (r ? extractValue(r) : null));
    } catch {
      // keep previous values
    } finally {
      healthLoading = false;
    }
  }

  async function fetchLayout(): Promise<void> {
    try {
      const resp = await api.get<LayoutResponse>('/api/metrics/layout');
      layoutPanels = resp.panels ?? [];
      await fetchAllPanelData();
    } catch {
      layoutPanels = [];
    } finally {
      layoutLoading = false;
    }
  }

  async function fetchAllPanelData(): Promise<void> {
    const fetches = layoutPanels.map(async (panel) => {
      try {
        if (panel.type === 'stat' && panel.query) {
          const resp = await api.get<MetricResponse>(
            `/api/metrics/query?query=${encodeURIComponent(panel.query)}`
          );
          panelData[panel.id] = extractValue(resp);
        } else if (panel.type === 'sparkline' && panel.query) {
          const now = Math.floor(Date.now() / 1000);
          const start = now - 3600;
          const resp = await api.get<RangeResponse>(
            `/api/metrics/query_range?query=${encodeURIComponent(panel.query)}&start=${start}&end=${now}&step=60`
          );
          panelData[panel.id] = resp?.data?.result?.[0]?.values ?? [];
        } else if (panel.type === 'alert-feed') {
          const resp = await api.get<AlertsResponse>('/api/metrics/alerts');
          panelData[panel.id] = resp?.data ?? [];
        } else if (panel.type === 'targets') {
          const resp = await api.get<TargetsResponse>('/api/metrics/targets');
          panelData[panel.id] = resp?.data?.activeTargets ?? [];
        }
      } catch {
        panelData[panel.id] = panelData[panel.id] ?? null;
      }
    });
    await Promise.all(fetches);
    panelData = { ...panelData };
  }

  async function fetchAlerts(): Promise<void> {
    try {
      const resp = await api.get<AlertsResponse>('/api/metrics/alerts');
      alerts = resp?.data ?? [];
    } catch {
      // keep previous
    } finally {
      alertsLoading = false;
    }
  }

  async function fetchTargets(): Promise<void> {
    try {
      const resp = await api.get<TargetsResponse>('/api/metrics/targets');
      targets = resp?.data?.activeTargets ?? [];
    } catch {
      // keep previous
    } finally {
      targetsLoading = false;
    }
  }

  async function runPromql(): Promise<void> {
    const q = promqlInput.trim();
    if (!q) return;
    promqlRunning = true;
    promqlError = '';
    promqlResults = [];
    try {
      const resp = await api.get<MetricResponse>(
        `/api/metrics/query?query=${encodeURIComponent(q)}`
      );
      if (resp?.data?.result) {
        promqlResults = resp.data.result.map((r) => ({
          name: r.metric['__name__'] ?? '',
          labels: labelsStr(r.metric),
          value: r.value[1],
        }));
      }
      if (promqlResults.length === 0) {
        promqlError = 'Query returned no results.';
      }
    } catch (e: unknown) {
      promqlError = e instanceof Error ? e.message : String(e);
    } finally {
      promqlRunning = false;
    }
  }

  function handlePromqlKeydown(e: KeyboardEvent): void {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      runPromql();
    }
  }

  function reloadLayout(): void {
    layoutLoading = true;
    fetchLayout();
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    fetchHealthStats();
    fetchLayout();
    fetchAlerts();
    fetchTargets();

    timers.push(setInterval(fetchHealthStats, 15_000));
    timers.push(setInterval(() => { if (layoutPanels.length) fetchAllPanelData(); }, 15_000));
    timers.push(setInterval(fetchAlerts, 30_000));
    timers.push(setInterval(fetchTargets, 60_000));
  });

  onDestroy(() => {
    timers.forEach(clearInterval);
    timers = [];
  });
</script>

<svelte:head>
  <title>Monitoring — FKS Terminal</title>
</svelte:head>

<div class="page">
  <div class="pane">
    <!-- ══════════════════════════════════════════════════════════════════
         Section 1 — System Health Stat Row
         ══════════════════════════════════════════════════════════════════ -->
    <Panel title="System Health" badge="15s">
      {#if healthLoading && healthValues.every(v => v === null)}
        <div class="stat-row">
          {#each healthStats as _}
            <div class="stat-slot"><Skeleton lines={2} height="16px" /></div>
          {/each}
        </div>
      {:else}
        <div class="stat-row">
          {#each healthStats as stat, i}
            <StatCard
              label={stat.label}
              value={healthValues[i] !== null ? Math.round(healthValues[i]! * 10) / 10 : '—'}
              unit={stat.unit}
              warn={stat.warn}
              crit={stat.crit}
            />
          {/each}
        </div>
      {/if}
    </Panel>

    <!-- ══════════════════════════════════════════════════════════════════
         Section 2 — Dynamic Panel Grid
         ══════════════════════════════════════════════════════════════════ -->
    <Panel title="Dashboard Panels" badge="15s">
      {#snippet header()}
        <button class="reload-btn" onclick={reloadLayout} title="Reload layout">↻</button>
      {/snippet}
      {#if layoutLoading && layoutPanels.length === 0}
        <Skeleton lines={4} height="20px" />
      {:else if layoutPanels.length === 0}
        <p class="empty-msg">No panels configured. Layout endpoint returned empty.</p>
      {:else}
        <div class="dynamic-grid">
          {#each layoutPanels as panel (panel.id)}
            <div class="grid-card">
              <div class="grid-card-head">
                <span class="grid-card-title">{panel.title}</span>
                <span class="grid-card-type">{panel.type}</span>
              </div>
              <div class="grid-card-body">
                {#if panel.type === 'stat'}
                  {@const val = panelData[panel.id] as number | null | undefined}
                  <span
                    class="big-number"
                    class:green={val != null && panel.warn != null && panel.crit != null && val < panel.warn}
                    class:amber={val != null && panel.warn != null && panel.crit != null && val >= panel.warn && val < panel.crit!}
                    class:red={val != null && panel.crit != null && val >= panel.crit}
                  >
                    {val != null ? fmtNum(val, panel.unit ?? '') : '—'}
                    {#if panel.unit}<span class="big-unit">{panel.unit}</span>{/if}
                  </span>
                {:else if panel.type === 'sparkline'}
                  {@const points = (panelData[panel.id] ?? []) as [number, string][]}
                  {#if points.length >= 2}
                    <svg class="sparkline-svg" viewBox="0 0 240 60" preserveAspectRatio="none">
                      <path
                        d={buildSparklinePath(points, 240, 60)}
                        fill="none"
                        stroke={panel.color ?? 'var(--accent)'}
                        stroke-width="1.5"
                        stroke-linejoin="round"
                        stroke-linecap="round"
                      />
                    </svg>
                  {:else}
                    <span class="empty-msg">No data</span>
                  {/if}
                {:else if panel.type === 'alert-feed'}
                  {@const panelAlerts = (panelData[panel.id] ?? []) as Alert[]}
                  {#if panelAlerts.length === 0}
                    <span class="ok-msg">✓ No active alerts</span>
                  {:else}
                    <ul class="mini-alert-list">
                      {#each panelAlerts.slice(0, 5) as a}
                        <li>
                          <Badge variant={severityVariant(a.labels.severity)}>{a.labels.severity}</Badge>
                          <span class="alert-name">{a.labels.alertname}</span>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                {:else if panel.type === 'targets'}
                  {@const panelTargets = (panelData[panel.id] ?? []) as ScrapeTarget[]}
                  {#if panelTargets.length === 0}
                    <span class="empty-msg">No targets</span>
                  {:else}
                    <ul class="mini-target-list">
                      {#each panelTargets.slice(0, 5) as t}
                        <li>
                          <Badge variant={healthVariant(t.health)}>{t.health}</Badge>
                          <span>{t.labels.job}</span>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </Panel>

    <!-- ══════════════════════════════════════════════════════════════════
         Section 3 — Alert Feed + Scrape Targets (side by side)
         ══════════════════════════════════════════════════════════════════ -->
    <div class="dual-row">
      <!-- Alert Feed -->
      <Panel title="Alert Feed" badge="30s" fill>
        {#if alertsLoading && alerts.length === 0}
          <Skeleton lines={3} height="14px" />
        {:else if alerts.length === 0}
          <span class="ok-msg">✓ No active alerts</span>
        {:else}
          <div class="alert-list">
            {#each alerts as alert}
              <div class="alert-row">
                <Badge variant={severityVariant(alert.labels.severity)}>
                  {alert.labels.severity}
                </Badge>
                <span class="alert-name">{alert.labels.alertname}</span>
                <span class="alert-instance dim">{alert.labels.instance}</span>
                <span class="alert-age dim">{alert.age_str}</span>
              </div>
            {/each}
          </div>
        {/if}
      </Panel>

      <!-- Scrape Targets -->
      <Panel title="Scrape Targets" badge="60s" fill noPad>
        {#if targetsLoading && targets.length === 0}
          <div class="targets-loading-pad">
            <Skeleton lines={3} height="14px" />
          </div>
        {:else if targets.length === 0}
          <span class="empty-msg">No active targets</span>
        {:else}
          <table class="target-table">
            <thead>
              <tr>
                <th>Health</th>
                <th>Job</th>
                <th>Instance</th>
                <th>Last Scrape</th>
              </tr>
            </thead>
            <tbody>
              {#each targets as t}
                <tr>
                  <td>
                    <Badge variant={healthVariant(t.health)}>
                      {t.health}
                    </Badge>
                  </td>
                  <td>{t.labels.job}</td>
                  <td class="dim">{t.labels.instance}</td>
                  <td class="dim">{t.age_str ?? t.lastScrape}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </Panel>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════
         Section 4 — Ad-hoc PromQL Runner
         ══════════════════════════════════════════════════════════════════ -->
    <Panel title="PromQL Runner">
      <div class="promql-section">
        <div class="chip-row">
          {#each presetChips as chip}
            <button
              class="chip"
              class:chip-active={promqlInput === chip.query}
              onclick={() => { promqlInput = chip.query; }}
            >
              {chip.label}
            </button>
          {/each}
        </div>

        <div class="promql-input-row">
          <textarea
            class="promql-textarea"
            rows="3"
            placeholder="Enter PromQL query…"
            bind:value={promqlInput}
            onkeydown={handlePromqlKeydown}
          ></textarea>
          <button
            class="run-btn"
            disabled={promqlRunning || !promqlInput.trim()}
            onclick={runPromql}
          >
            {promqlRunning ? '⏳' : '▶'} Run
          </button>
        </div>

        <div class="promql-hint dim">Ctrl+Enter to execute</div>

        {#if promqlError}
          <div class="promql-error">{promqlError}</div>
        {/if}

        {#if promqlResults.length > 0}
          <div class="promql-output">
            {#each promqlResults as r}
              <div class="promql-result-row">
                <span class="promql-metric">{r.name}{r.labels}</span>
                <span class="promql-value">{r.value}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </Panel>
  </div>
</div>

<style>
  /* ── Page Layout ─────────────────────────────────────────── */
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
  }

  .pane {
    overflow: auto;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }

  /* ── Reload Button ───────────────────────────────────────── */
  .reload-btn {
    background: none;
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t2);
    font-size: 12px;
    padding: 1px 6px;
    cursor: pointer;
    line-height: 1;
    transition: color 0.15s, border-color 0.15s;
  }

  .reload-btn:hover {
    color: var(--accent);
    border-color: var(--accent-brd);
  }

  /* ── Section 1 — Health Stats ────────────────────────────── */
  .stat-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .stat-slot {
    flex: 1;
    min-width: 100px;
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    padding: 10px 14px;
  }

  /* ── Section 2 — Dynamic Panel Grid ──────────────────────── */
  .dynamic-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 8px;
  }

  .grid-card {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .grid-card-head {
    padding: 5px 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--b1);
  }

  .grid-card-title {
    font-size: 9px;
    font-weight: 600;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .grid-card-type {
    font-size: 8px;
    color: var(--t3);
    text-transform: uppercase;
  }

  .grid-card-body {
    padding: 10px 8px;
    min-height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .big-number {
    font-size: 22px;
    font-weight: 700;
    color: var(--t1);
    line-height: 1.2;
  }

  .big-number.green { color: var(--green); }
  .big-number.amber { color: var(--amber); }
  .big-number.red   { color: var(--red); }

  .big-unit {
    font-size: 11px;
    font-weight: 500;
    color: var(--t2);
    margin-left: 2px;
  }

  .sparkline-svg {
    width: 100%;
    height: 50px;
  }

  .mini-alert-list,
  .mini-target-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
  }

  .mini-alert-list li,
  .mini-target-list li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    color: var(--t2);
  }

  /* ── Section 3 — Dual Row ────────────────────────────────── */
  .dual-row {
    display: flex;
    gap: 8px;
  }

  .alert-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .alert-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    padding: 3px 0;
    border-bottom: 1px solid var(--b1);
  }

  .alert-row:last-child {
    border-bottom: none;
  }

  .alert-name {
    color: var(--t1);
    font-weight: 500;
  }

  .alert-instance {
    margin-left: auto;
    font-size: 10px;
  }

  .alert-age {
    font-size: 10px;
    white-space: nowrap;
  }

  .targets-loading-pad {
    padding: 8px;
  }

  .target-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  .target-table th {
    text-align: left;
    font-size: 9px;
    font-weight: 600;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 4px 6px;
    border-bottom: 1px solid var(--b1);
  }

  .target-table td {
    padding: 4px 6px;
    border-bottom: 1px solid var(--b1);
    color: var(--t1);
  }

  .target-table tr:last-child td {
    border-bottom: none;
  }

  /* ── Section 4 — PromQL Runner ───────────────────────────── */
  .promql-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .chip {
    font-size: 9px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: var(--r);
    border: 1px solid var(--b2);
    background: var(--bg2);
    color: var(--t2);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
  }

  .chip:hover {
    color: var(--t1);
    border-color: var(--b3);
    background: var(--bg3);
  }

  .chip-active {
    color: var(--accent);
    border-color: var(--accent-brd);
    background: var(--accent-dim);
  }

  .promql-input-row {
    display: flex;
    gap: 6px;
    align-items: stretch;
  }

  .promql-textarea {
    flex: 1;
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t1);
    font-family: inherit;
    font-size: 11px;
    padding: 6px 8px;
    resize: vertical;
    min-height: 36px;
    outline: none;
    transition: border-color 0.15s;
  }

  .promql-textarea:focus {
    border-color: var(--accent-brd);
  }

  .promql-textarea::placeholder {
    color: var(--t3);
  }

  .run-btn {
    background: var(--accent-dim);
    border: 1px solid var(--accent-brd);
    border-radius: var(--r);
    color: var(--accent);
    font-size: 10px;
    font-weight: 600;
    padding: 6px 14px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
    transition: background 0.15s, color 0.15s;
  }

  .run-btn:hover:not(:disabled) {
    background: var(--accent);
    color: var(--bg0);
  }

  .run-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .promql-hint {
    font-size: 9px;
    letter-spacing: 0.04em;
  }

  .promql-error {
    font-size: 11px;
    color: var(--red);
    padding: 6px 8px;
    background: var(--red-dim);
    border: 1px solid var(--red-brd);
    border-radius: var(--r);
  }

  .promql-output {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    padding: 6px 8px;
    max-height: 240px;
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .promql-result-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 11px;
    padding: 2px 0;
    border-bottom: 1px solid var(--b1);
  }

  .promql-result-row:last-child {
    border-bottom: none;
  }

  .promql-metric {
    color: var(--t2);
    word-break: break-all;
    min-width: 0;
  }

  .promql-value {
    color: var(--cyan);
    font-weight: 600;
    white-space: nowrap;
    flex-shrink: 0;
  }

  /* ── Shared Helpers ──────────────────────────────────────── */
  .dim {
    color: var(--t3);
  }

  .empty-msg {
    font-size: 11px;
    color: var(--t3);
    padding: 12px 0;
    text-align: center;
  }

  .ok-msg {
    font-size: 11px;
    color: var(--green);
    padding: 12px 0;
    text-align: center;
    display: block;
    width: 100%;
  }

  /* ── Responsive ──────────────────────────────────────────── */
  @media (max-width: 720px) {
    .dual-row {
      flex-direction: column;
    }

    .stat-row {
      flex-direction: column;
    }

    .dynamic-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
