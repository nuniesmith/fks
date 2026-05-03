<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Panel from '$components/ui/Panel.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface DataSourceResponse {
    source: 'kraken' | 'rithmic' | 'both';
    connected?: boolean;
  }

  interface HealthResponse {
    status: string;
    version?: string;
    uptime?: string;
    components?: Record<string, { status: string; latency?: string }>;
  }

  interface RiskSettings {
    daily_loss_limit: number;
    max_contracts: number;
    hard_stop: number;
  }

  interface AnalysisSettings {
    primary_tf: string;
    htf_bias: string;
    autorun_time: string;
    instruments: string[];
  }

  interface JanusConfig {
    optimize_assets: string;
    optimize_interval: string;
    optimize_trials: number;
    optimize_historical_days: number;
    data_kline_intervals: string;
    janus_auto_start: boolean;
    janus_bootstrap_days: number;
  }

  interface JanusConfigResponse {
    config: JanusConfig;
    assets_list: string[];
    source: 'redis' | 'env_defaults';
    valid_intervals: string[];
    redis_available: boolean;
  }

  interface BootstrapPushResponse {
    ok: boolean;
    pushed: number;
    failed: number;
    total: number;
    source: string;
    message: string;
  }

  // ─── Data Source State ──────────────────────────────────────────────
  let dsSource = $state<'kraken' | 'rithmic' | 'both'>('both');
  let dsConnected = $state<boolean | null>(null);
  let dsLoading = $state(true);
  let dsSaving = $state(false);
  let dsFeedback = $state('');

  // ─── Kraken Keys State ─────────────────────────────────────────────
  let krakenKey = $state('');
  let krakenSecret = $state('');
  let krakenSaving = $state(false);
  let krakenTesting = $state(false);
  let krakenFeedback = $state('');
  let krakenFeedbackVariant = $state<'green' | 'red' | 'default'>('default');

  // ─── Rithmic State ─────────────────────────────────────────────────
  let rithmicStatus = $state('Unknown');
  let rithmicTesting = $state(false);
  let rithmicFeedback = $state('');
  let rithmicFeedbackVariant = $state<'green' | 'red' | 'default'>('default');

  // ─── Risk Controls State ───────────────────────────────────────────
  let riskDailyLoss = $state(5000);
  let riskMaxContracts = $state(10);
  let riskHardStop = $state(2500);
  let riskSaving = $state(false);
  let riskFeedback = $state('');

  // ─── Analysis Preferences State ────────────────────────────────────
  let primaryTf = $state('5m');
  let htfBias = $state('1h');
  let autorunTime = $state('06:30');
  let selectedInstruments = $state<string[]>(['MES', 'MNQ', 'MGC']);
  let analysisSaving = $state(false);
  let analysisFeedback = $state('');

  const timeframes = ['1m', '5m', '15m', '1h', '4h', '1D'];
  const htfTimeframes = ['15m', '1h', '4h', '1D'];
  const allInstruments = ['MES', 'MNQ', 'MGC', 'MYM', 'M2K', 'BTC', 'ETH', 'SOL'];

  // ─── System Health State ───────────────────────────────────────────
  let healthData = $state<HealthResponse | null>(null);
  let healthLoading = $state(true);
  let healthTimer: ReturnType<typeof setInterval> | null = null;

  // ─── Observability Links ───────────────────────────────────────────
  const obsLinks = [
    { label: 'Grafana',       icon: '📊', url: 'http://localhost:3000',  color: 'var(--amber)' },
    { label: 'Prometheus',    icon: '🔥', url: 'http://localhost:9090',  color: 'var(--cyan)' },
    { label: 'Alertmanager',  icon: '🔔', url: 'http://localhost:9093',  color: 'var(--red)' },
    { label: 'Jaeger',        icon: '🔍', url: 'http://localhost:16686', color: 'var(--purple)' },
  ];

  // ─── Janus Config State ────────────────────────────────────────────
  let janusConfig = $state<JanusConfig>({
    optimize_assets: 'BTC,ETH,SOL',
    optimize_interval: '6h',
    optimize_trials: 100,
    optimize_historical_days: 30,
    data_kline_intervals: '1m,5m',
    janus_auto_start: false,
    janus_bootstrap_days: 30,
  });
  let janusConfigSource = $state<'redis' | 'env_defaults'>('env_defaults');
  let janusRedisAvailable = $state(false);
  let janusValidIntervals = $state<string[]>(['1h', '4h', '6h', '12h', '1D']);
  let janusLoading = $state(true);
  let janusSaving = $state(false);
  let janusFeedback = $state('');
  let janusFeedbackVariant = $state<'green' | 'red' | 'default'>('default');
  let janusPushing = $state(false);
  let janusPushFeedback = $state('');
  let janusPushVariant = $state<'green' | 'red' | 'default'>('default');

  // ─── Helpers ────────────────────────────────────────────────────────

  function clearFeedbackAfter(setter: (v: string) => void, ms = 3000) {
    setTimeout(() => setter(''), ms);
  }

  function componentVariant(status: string): 'green' | 'red' | 'amber' | 'default' {
    const s = status.toLowerCase();
    if (s === 'ok' || s === 'healthy' || s === 'up' || s === 'connected') return 'green';
    if (s === 'degraded' || s === 'warning' || s === 'slow') return 'amber';
    if (s === 'error' || s === 'down' || s === 'unhealthy' || s === 'disconnected') return 'red';
    return 'default';
  }

  function overallVariant(status: string): 'green' | 'red' | 'amber' | 'default' {
    const s = status.toLowerCase();
    if (s === 'ok' || s === 'healthy') return 'green';
    if (s === 'degraded') return 'amber';
    if (s === 'error' || s === 'unhealthy') return 'red';
    return 'default';
  }

  // ─── API: Data Sources ─────────────────────────────────────────────

  async function loadDataSource() {
    dsLoading = true;
    try {
      const res = await api.get<DataSourceResponse>('/api/settings/data-source');
      dsSource = res.source;
      dsConnected = res.connected ?? null;
    } catch {
      dsConnected = null;
    } finally {
      dsLoading = false;
    }
  }

  async function saveDataSource() {
    dsSaving = true;
    dsFeedback = '';
    try {
      await api.post('/api/settings/data-source', { source: dsSource });
      dsFeedback = 'Saved ✓';
      clearFeedbackAfter(v => dsFeedback = v);
    } catch (err: any) {
      dsFeedback = `Error: ${err.message ?? 'Failed to save'}`;
      clearFeedbackAfter(v => dsFeedback = v, 5000);
    } finally {
      dsSaving = false;
    }
  }

  // ─── API: Kraken Keys ─────────────────────────────────────────────

  async function saveKrakenKeys() {
    krakenSaving = true;
    krakenFeedback = '';
    try {
      await api.post('/api/settings/kraken-keys', { api_key: krakenKey, api_secret: krakenSecret });
      krakenFeedback = 'Keys saved ✓';
      krakenFeedbackVariant = 'green';
      clearFeedbackAfter(v => krakenFeedback = v);
    } catch (err: any) {
      krakenFeedback = `Error: ${err.message ?? 'Failed to save'}`;
      krakenFeedbackVariant = 'red';
      clearFeedbackAfter(v => krakenFeedback = v, 5000);
    } finally {
      krakenSaving = false;
    }
  }

  async function testKraken() {
    krakenTesting = true;
    krakenFeedback = '';
    try {
      const res = await api.get<{ status?: string; message?: string }>('/kraken/health');
      krakenFeedback = `✓ ${res.status ?? res.message ?? 'Connected'}`;
      krakenFeedbackVariant = 'green';
    } catch (err: any) {
      krakenFeedback = `✗ ${err.message ?? 'Connection failed'}`;
      krakenFeedbackVariant = 'red';
    } finally {
      krakenTesting = false;
      clearFeedbackAfter(v => krakenFeedback = v, 5000);
    }
  }

  // ─── API: Rithmic ──────────────────────────────────────────────────

  async function testRithmic() {
    rithmicTesting = true;
    rithmicFeedback = '';
    try {
      const res = await api.post<{ status?: string; message?: string; connected?: boolean }>('/api/rithmic/status');
      rithmicStatus = res.status ?? (res.connected ? 'Connected' : 'Disconnected');
      rithmicFeedback = `✓ ${res.status ?? res.message ?? 'OK'}`;
      rithmicFeedbackVariant = 'green';
    } catch (err: any) {
      rithmicStatus = 'Error';
      rithmicFeedback = `✗ ${err.message ?? 'Connection failed'}`;
      rithmicFeedbackVariant = 'red';
    } finally {
      rithmicTesting = false;
      clearFeedbackAfter(v => rithmicFeedback = v, 5000);
    }
  }

  // ─── API: Risk Controls ────────────────────────────────────────────

  async function saveRisk() {
    riskSaving = true;
    riskFeedback = '';
    try {
      await api.post('/api/settings/risk', {
        daily_loss_limit: riskDailyLoss,
        max_contracts: riskMaxContracts,
        hard_stop: riskHardStop,
      });
      riskFeedback = 'Saved ✓';
      clearFeedbackAfter(v => riskFeedback = v);
    } catch (err: any) {
      riskFeedback = `Error: ${err.message ?? 'Failed to save'}`;
      clearFeedbackAfter(v => riskFeedback = v, 5000);
    } finally {
      riskSaving = false;
    }
  }

  // ─── API: Analysis Preferences ─────────────────────────────────────

  async function saveAnalysis() {
    analysisSaving = true;
    analysisFeedback = '';
    try {
      await api.post('/api/settings/analysis', {
        primary_tf: primaryTf,
        htf_bias: htfBias,
        autorun_time: autorunTime,
        instruments: selectedInstruments,
      });
      analysisFeedback = 'Saved ✓';
      clearFeedbackAfter(v => analysisFeedback = v);
    } catch (err: any) {
      analysisFeedback = `Error: ${err.message ?? 'Failed to save'}`;
      clearFeedbackAfter(v => analysisFeedback = v, 5000);
    } finally {
      analysisSaving = false;
    }
  }

  function toggleInstrument(sym: string) {
    if (selectedInstruments.includes(sym)) {
      selectedInstruments = selectedInstruments.filter(s => s !== sym);
    } else {
      selectedInstruments = [...selectedInstruments, sym];
    }
  }

  // ─── API: Janus Config ────────────────────────────────────────────

  async function loadJanusConfig() {
    janusLoading = true;
    try {
      const res = await api.get<JanusConfigResponse>('/api/janus/config');
      janusConfig = res.config;
      janusConfigSource = res.source;
      janusRedisAvailable = res.redis_available;
      if (res.valid_intervals?.length) janusValidIntervals = res.valid_intervals;
    } catch {
      // Keep defaults
    } finally {
      janusLoading = false;
    }
  }

  async function saveJanusConfig() {
    janusSaving = true;
    janusFeedback = '';
    try {
      await api.put('/api/janus/config', {
        optimize_assets: janusConfig.optimize_assets,
        optimize_interval: janusConfig.optimize_interval,
        optimize_trials: janusConfig.optimize_trials,
        optimize_historical_days: janusConfig.optimize_historical_days,
        data_kline_intervals: janusConfig.data_kline_intervals,
        janus_auto_start: janusConfig.janus_auto_start,
        janus_bootstrap_days: janusConfig.janus_bootstrap_days,
      });
      janusFeedback = 'Saved ✓';
      janusFeedbackVariant = 'green';
      janusConfigSource = 'redis';
      clearFeedbackAfter(v => janusFeedback = v);
    } catch (err: any) {
      janusFeedback = `Error: ${err.message ?? 'Failed to save'}`;
      janusFeedbackVariant = 'red';
      clearFeedbackAfter(v => janusFeedback = v, 5000);
    } finally {
      janusSaving = false;
    }
  }

  async function pushBootstrapToJanus() {
    janusPushing = true;
    janusPushFeedback = '';
    janusPushVariant = 'default';
    try {
      const res = await api.post<BootstrapPushResponse>(
        `/api/janus/memories/bootstrap/push?days=${janusConfig.janus_bootstrap_days}&limit=500`,
        {}
      );
      janusPushFeedback = res.message ?? `Pushed ${res.pushed} memories ✓`;
      janusPushVariant = res.ok ? 'green' : 'red';
      clearFeedbackAfter(v => janusPushFeedback = v, 8000);
    } catch (err: any) {
      janusPushFeedback = `Error: ${err.message ?? 'Push failed'}`;
      janusPushVariant = 'red';
      clearFeedbackAfter(v => janusPushFeedback = v, 5000);
    } finally {
      janusPushing = false;
    }
  }

  // ─── API: System Health ────────────────────────────────────────────

  async function fetchHealth() {
    try {
      healthData = await api.get<HealthResponse>('/api/health');
    } catch {
      healthData = { status: 'error', components: {} };
    } finally {
      healthLoading = false;
    }
  }

  // ─── Lifecycle ─────────────────────────────────────────────────────

  onMount(() => {
    loadDataSource();
    fetchHealth();
    loadJanusConfig();
    healthTimer = setInterval(fetchHealth, 15_000);
  });

  onDestroy(() => {
    if (healthTimer) clearInterval(healthTimer);
  });
</script>

<svelte:head>
  <title>Settings — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ════════════════════════════════════════════════════════════════════
       LEFT PANE
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

    <!-- ── Panel 1: Data Sources ──────────────────────────────────── -->
    <Panel title="Data Sources">
      {#snippet header()}
        {#if dsConnected !== null}
          <span class="status-dot" class:dot-green={dsConnected} class:dot-red={!dsConnected}></span>
          <span class="status-text" class:connected={dsConnected} class:disconnected={!dsConnected}>
            {dsConnected ? 'Connected' : 'Disconnected'}
          </span>
        {/if}
      {/snippet}
      {#if dsLoading}
        <Skeleton lines={3} height="14px" />
      {:else}
        <div class="form-group">
          <span class="form-label">Active Source</span>
          <div class="radio-group">
            <label class="radio-option">
              <input type="radio" bind:group={dsSource} value="kraken" />
              <span class="radio-label">Kraken</span>
            </label>
            <label class="radio-option">
              <input type="radio" bind:group={dsSource} value="rithmic" />
              <span class="radio-label">Rithmic</span>
            </label>
            <label class="radio-option">
              <input type="radio" bind:group={dsSource} value="both" />
              <span class="radio-label">Both</span>
            </label>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-primary" onclick={saveDataSource} disabled={dsSaving}>
            {dsSaving ? 'Saving…' : 'Save'}
          </button>
          {#if dsFeedback}
            <span class="feedback" class:feedback-ok={dsFeedback.startsWith('Saved')} class:feedback-err={dsFeedback.startsWith('Error')}>
              {dsFeedback}
            </span>
          {/if}
        </div>
      {/if}
    </Panel>

    <!-- ── Panel 2: API Connections ───────────────────────────────── -->
    <Panel title="API Connections">
      <!-- Kraken -->
      <div class="connection-block">
        <div class="connection-title">Kraken</div>
        <div class="form-group">
          <label class="form-label" for="kraken-api-key">API Key</label>
          <input
            id="kraken-api-key"
            class="form-input"
            type="password"
            placeholder="Enter Kraken API key…"
            bind:value={krakenKey}
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label class="form-label" for="kraken-api-secret">API Secret</label>
          <input
            id="kraken-api-secret"
            class="form-input"
            type="password"
            placeholder="Enter Kraken API secret…"
            bind:value={krakenSecret}
            autocomplete="off"
          />
        </div>
        <div class="form-actions">
          <button class="btn-primary" onclick={saveKrakenKeys} disabled={krakenSaving || (!krakenKey && !krakenSecret)}>
            {krakenSaving ? 'Saving…' : 'Save Keys'}
          </button>
          <button class="btn-ghost" onclick={testKraken} disabled={krakenTesting}>
            {krakenTesting ? '⏳ Testing…' : '🔌 Test'}
          </button>
          {#if krakenFeedback}
            <span class="feedback" class:feedback-ok={krakenFeedbackVariant === 'green'} class:feedback-err={krakenFeedbackVariant === 'red'}>
              {krakenFeedback}
            </span>
          {/if}
        </div>
      </div>

      <div class="divider"></div>

      <!-- Rithmic -->
      <div class="connection-block">
        <div class="connection-title">Rithmic</div>
        <div class="form-group">
          <span class="form-label">Status</span>
          <div class="status-display">
            <span class="status-dot" class:dot-green={rithmicStatus === 'Connected'} class:dot-red={rithmicStatus !== 'Connected' && rithmicStatus !== 'Unknown'} class:dot-amber={rithmicStatus === 'Unknown'}></span>
            <span class="mono">{rithmicStatus}</span>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-ghost" onclick={testRithmic} disabled={rithmicTesting}>
            {rithmicTesting ? '⏳ Testing…' : '🔌 Test Connection'}
          </button>
          {#if rithmicFeedback}
            <span class="feedback" class:feedback-ok={rithmicFeedbackVariant === 'green'} class:feedback-err={rithmicFeedbackVariant === 'red'}>
              {rithmicFeedback}
            </span>
          {/if}
        </div>
      </div>
    </Panel>

    <!-- ── Panel 3: Risk Controls ─────────────────────────────────── -->
    <Panel title="Risk Controls">
      <div class="form-row">
        <div class="form-group form-grow">
          <label class="form-label" for="risk-daily-loss">Daily Loss Limit ($)</label>
          <input
            id="risk-daily-loss"
            class="form-input"
            type="number"
            min="0"
            step="100"
            bind:value={riskDailyLoss}
          />
        </div>
        <div class="form-group form-grow">
          <label class="form-label" for="risk-max-contracts">Max Contracts</label>
          <input
            id="risk-max-contracts"
            class="form-input"
            type="number"
            min="1"
            step="1"
            bind:value={riskMaxContracts}
          />
        </div>
        <div class="form-group form-grow">
          <label class="form-label" for="risk-hard-stop">Hard Stop ($)</label>
          <input
            id="risk-hard-stop"
            class="form-input"
            type="number"
            min="0"
            step="100"
            bind:value={riskHardStop}
          />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn-primary" onclick={saveRisk} disabled={riskSaving}>
          {riskSaving ? 'Saving…' : 'Save'}
        </button>
        {#if riskFeedback}
          <span class="feedback" class:feedback-ok={riskFeedback.startsWith('Saved')} class:feedback-err={riskFeedback.startsWith('Error')}>
            {riskFeedback}
          </span>
        {/if}
      </div>
    </Panel>
  </div>

  <!-- ════════════════════════════════════════════════════════════════════
       RIGHT PANE
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <!-- ── Panel 1: Analysis Preferences ──────────────────────────── -->
    <Panel title="Analysis Preferences">
      <div class="form-row">
        <div class="form-group form-grow">
          <label class="form-label" for="pref-primary-tf">Primary Timeframe</label>
          <select id="pref-primary-tf" class="form-select" bind:value={primaryTf}>
            {#each timeframes as tf}
              <option value={tf}>{tf}</option>
            {/each}
          </select>
        </div>
        <div class="form-group form-grow">
          <label class="form-label" for="pref-htf-bias">HTF Bias Timeframe</label>
          <select id="pref-htf-bias" class="form-select" bind:value={htfBias}>
            {#each htfTimeframes as tf}
              <option value={tf}>{tf}</option>
            {/each}
          </select>
        </div>
        <div class="form-group form-grow">
          <label class="form-label" for="pref-autorun-time">Auto-run Time</label>
          <input
            id="pref-autorun-time"
            class="form-input"
            type="time"
            bind:value={autorunTime}
          />
        </div>
      </div>

      <div class="form-group">
        <span class="form-label">Watched Instruments</span>
        <div class="chip-row">
          {#each allInstruments as sym}
            <button
              class="chip"
              class:chip-active={selectedInstruments.includes(sym)}
              onclick={() => toggleInstrument(sym)}
            >
              {sym}
            </button>
          {/each}
        </div>
      </div>

      <div class="form-actions">
        <button class="btn-primary" onclick={saveAnalysis} disabled={analysisSaving}>
          {analysisSaving ? 'Saving…' : 'Save'}
        </button>
        {#if analysisFeedback}
          <span class="feedback" class:feedback-ok={analysisFeedback.startsWith('Saved')} class:feedback-err={analysisFeedback.startsWith('Error')}>
            {analysisFeedback}
          </span>
        {/if}
      </div>
    </Panel>

    <!-- ── Panel 2: System Info ───────────────────────────────────── -->
    <Panel title="System Info" badge="15s">
      {#if healthLoading && !healthData}
        <Skeleton lines={4} height="14px" />
      {:else if healthData}
        <div class="sys-overview">
          <div class="sys-row">
            <span class="sys-key">Overall Status</span>
            <Badge variant={overallVariant(healthData.status)}>
              {healthData.status.toUpperCase()}
            </Badge>
          </div>
          {#if healthData.version}
            <div class="sys-row">
              <span class="sys-key">Version</span>
              <span class="sys-val mono">{healthData.version}</span>
            </div>
          {/if}
          {#if healthData.uptime}
            <div class="sys-row">
              <span class="sys-key">Uptime</span>
              <span class="sys-val mono">{healthData.uptime}</span>
            </div>
          {/if}
        </div>

        {#if healthData.components && Object.keys(healthData.components).length > 0}
          <div class="component-grid">
            {#each Object.entries(healthData.components) as [name, comp]}
              <div class="component-card">
                <span class="status-dot" class:dot-green={componentVariant(comp.status) === 'green'} class:dot-red={componentVariant(comp.status) === 'red'} class:dot-amber={componentVariant(comp.status) === 'amber'}></span>
                <div class="component-info">
                  <span class="component-name">{name}</span>
                  <span class="component-status">{comp.status}</span>
                  {#if comp.latency}
                    <span class="component-latency">{comp.latency}</span>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      {:else}
        <div class="empty-state">Unable to fetch system health</div>
      {/if}
    </Panel>

    <!-- ── Panel 3: Observability Links ───────────────────────────── -->
    <Panel title="Observability">
      <div class="obs-grid">
        {#each obsLinks as link}
          <a class="obs-link" href={link.url} target="_blank" rel="noopener noreferrer">
            <span class="obs-icon">{link.icon}</span>
            <span class="obs-label">{link.label}</span>
            <span class="obs-url">{link.url.replace('http://localhost', ':')}</span>
          </a>
        {/each}
      </div>
    </Panel>

    <!-- ── Panel 4: Janus Optimizer Config ──────────────────────────── -->
    <Panel title="Janus Optimizer">
      {#snippet header()}
        {#if !janusLoading}
          <span class="header-badge" title="Config source">{janusConfigSource === 'redis' ? '⬤ Redis' : '○ Env'}</span>
          {#if !janusRedisAvailable}
            <span class="header-badge" style="color: var(--red)">Redis unavailable</span>
          {/if}
        {/if}
      {/snippet}
      {#if janusLoading}
        <Skeleton lines={5} height="14px" />
      {:else}
        <!-- Optimize Assets -->
        <div class="form-group">
          <label class="form-label" for="janus-assets">Optimize Assets</label>
          <input
            id="janus-assets"
            class="form-input"
            type="text"
            placeholder="BTC,ETH,SOL"
            bind:value={janusConfig.optimize_assets}
            spellcheck="false"
          />
          <span class="form-hint">Comma-separated symbols for the optimizer to watch</span>
        </div>

        <div class="form-row">
          <!-- Interval -->
          <div class="form-group form-grow">
            <label class="form-label" for="janus-interval">Optimize Interval</label>
            <select id="janus-interval" class="form-select" bind:value={janusConfig.optimize_interval}>
              {#each janusValidIntervals as iv}
                <option value={iv}>{iv}</option>
              {/each}
            </select>
          </div>

          <!-- Trials -->
          <div class="form-group form-grow">
            <label class="form-label" for="janus-trials">Trials</label>
            <input
              id="janus-trials"
              class="form-input"
              type="number"
              min="1"
              max="1000"
              step="10"
              bind:value={janusConfig.optimize_trials}
            />
          </div>

          <!-- Historical Days -->
          <div class="form-group form-grow">
            <label class="form-label" for="janus-hist-days">Historical Days</label>
            <input
              id="janus-hist-days"
              class="form-input"
              type="number"
              min="1"
              max="365"
              step="1"
              bind:value={janusConfig.optimize_historical_days}
            />
          </div>
        </div>

        <!-- Kline Intervals -->
        <div class="form-group">
          <label class="form-label" for="janus-kline">Kline Intervals</label>
          <input
            id="janus-kline"
            class="form-input"
            type="text"
            placeholder="1m,5m,15m"
            bind:value={janusConfig.data_kline_intervals}
            spellcheck="false"
          />
        </div>

        <div class="form-row">
          <!-- Bootstrap Days -->
          <div class="form-group form-grow">
            <label class="form-label" for="janus-boot-days">Bootstrap History (days)</label>
            <input
              id="janus-boot-days"
              class="form-input"
              type="number"
              min="1"
              max="365"
              step="1"
              bind:value={janusConfig.janus_bootstrap_days}
            />
          </div>

          <!-- Auto-start -->
          <div class="form-group form-grow">
            <span class="form-label">Auto-start on Boot</span>
            <label class="toggle-label">
              <input
                type="checkbox"
                class="toggle-input"
                bind:checked={janusConfig.janus_auto_start}
              />
              <span class="toggle-track">
                <span class="toggle-thumb"></span>
              </span>
              <span class="toggle-text">{janusConfig.janus_auto_start ? 'Enabled' : 'Disabled'}</span>
            </label>
          </div>
        </div>

        <!-- Actions -->
        <div class="form-actions">
          <button
            class="btn-primary"
            onclick={saveJanusConfig}
            disabled={janusSaving || !janusRedisAvailable}
            title={janusRedisAvailable ? 'Save config to Redis' : 'Redis unavailable'}
          >
            {janusSaving ? 'Saving…' : 'Save Config'}
          </button>
          {#if janusFeedback}
            <span class="feedback" class:feedback-ok={janusFeedbackVariant === 'green'} class:feedback-err={janusFeedbackVariant === 'red'}>
              {janusFeedback}
            </span>
          {/if}
        </div>

        <div class="divider"></div>

        <!-- Memory Bootstrap -->
        <div class="janus-bootstrap">
          <div class="bootstrap-desc">
            Push the last <strong>{janusConfig.janus_bootstrap_days} days</strong> of
            <code>janus_memories</code> to the Janus affinity tracker.
            Use this after a fresh deployment to warm-start the brain without retraining.
          </div>
          <div class="form-actions">
            <button
              class="btn-ghost"
              onclick={pushBootstrapToJanus}
              disabled={janusPushing}
            >
              {janusPushing ? '⏳ Pushing…' : '🧠 Push Memories to Janus'}
            </button>
            {#if janusPushFeedback}
              <span class="feedback" class:feedback-ok={janusPushVariant === 'green'} class:feedback-err={janusPushVariant === 'red'}>
                {janusPushFeedback}
              </span>
            {/if}
          </div>
        </div>
      {/if}
    </Panel>
  </div>
</div>

<style>
  /* ═══════════════════════════════════════════════════════════════════
     Page Layout
     ═══════════════════════════════════════════════════════════════════ */
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
    min-width: 0;
  }

  .pane-left  { flex: 5; }
  .pane-right { flex: 5; }

  /* ═══════════════════════════════════════════════════════════════════
     Header Badges (inside Panel header snippet)
     ═══════════════════════════════════════════════════════════════════ */
  .header-badge {
    font-size: 8px;
    color: var(--t3);
    background: var(--bg3);
    padding: 1px 5px;
    border-radius: var(--r);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Status Indicators
     ═══════════════════════════════════════════════════════════════════ */
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
    background: var(--t3);
  }

  .dot-green  { background: var(--green);  box-shadow: 0 0 4px var(--green); }
  .dot-red    { background: var(--red);    box-shadow: 0 0 4px var(--red); }
  .dot-amber  { background: var(--amber);  box-shadow: 0 0 4px var(--amber); }

  .status-text {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .connected    { color: var(--green); }
  .disconnected { color: var(--red); }

  .status-display {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--t1);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Form Elements
     ═══════════════════════════════════════════════════════════════════ */
  .form-group {
    margin-bottom: 8px;
  }

  .form-grow {
    flex: 1;
    min-width: 0;
  }

  .form-label {
    display: block;
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .form-input,
  .form-select {
    width: 100%;
    padding: 6px 8px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    color: var(--t1);
    font-family: var(--font-mono, monospace);
    font-size: 12px;
    outline: none;
    transition: border-color 0.15s;
    box-sizing: border-box;
  }

  .form-input:focus,
  .form-select:focus {
    border-color: var(--accent, var(--cyan));
  }

  .form-input::placeholder {
    color: var(--t3);
  }

  .form-select {
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23888'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    padding-right: 24px;
  }

  .form-select option {
    background: var(--bg2);
    color: var(--t1);
  }

  .form-row {
    display: flex;
    gap: 8px;
  }

  .form-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Radio Group
     ═══════════════════════════════════════════════════════════════════ */
  .radio-group {
    display: flex;
    gap: 2px;
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 2px;
  }

  .radio-option {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .radio-option input[type="radio"] {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .radio-label {
    display: block;
    width: 100%;
    text-align: center;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    color: var(--t3);
    border-radius: var(--r);
    transition: background 0.15s, color 0.15s;
    user-select: none;
  }

  .radio-option input[type="radio"]:checked + .radio-label {
    background: var(--bg3);
    color: var(--t1);
  }

  .radio-option:hover .radio-label {
    color: var(--t2);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Buttons
     ═══════════════════════════════════════════════════════════════════ */
  .btn-primary {
    all: unset;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 600;
    color: var(--bg0);
    background: var(--accent, var(--cyan));
    border-radius: var(--r);
    cursor: pointer;
    transition: opacity 0.15s;
    white-space: nowrap;
  }

  .btn-primary:hover { opacity: 0.85; }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

  .btn-ghost {
    all: unset;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    color: var(--t2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
    white-space: nowrap;
  }

  .btn-ghost:hover {
    color: var(--t1);
    border-color: var(--t2);
  }

  .btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ═══════════════════════════════════════════════════════════════════
     Feedback
     ═══════════════════════════════════════════════════════════════════ */
  .feedback {
    font-size: 11px;
    font-weight: 600;
    color: var(--t2);
  }

  .feedback-ok  { color: var(--green); }
  .feedback-err { color: var(--red); }

  /* ═══════════════════════════════════════════════════════════════════
     Connection Blocks
     ═══════════════════════════════════════════════════════════════════ */
  .connection-block {
    margin-bottom: 4px;
  }

  .connection-title {
    font-size: 11px;
    font-weight: 700;
    color: var(--t1);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--b1);
  }

  .divider {
    height: 1px;
    background: var(--b1);
    margin: 8px 0;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Chips (Instrument Selection)
     ═══════════════════════════════════════════════════════════════════ */
  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .chip {
    all: unset;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    color: var(--t3);
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
  }

  .chip:hover {
    color: var(--t2);
    border-color: var(--t3);
  }

  .chip-active {
    color: var(--cyan);
    background: var(--bg3);
    border-color: var(--cyan);
  }

  .chip-active:hover {
    color: var(--cyan);
    border-color: var(--cyan);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Form Hints
     ═══════════════════════════════════════════════════════════════════ */
  .form-hint {
    font-size: 9px;
    color: var(--t3);
    margin-top: 2px;
    display: block;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Toggle Switch
     ═══════════════════════════════════════════════════════════════════ */
  .toggle-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    margin-top: 2px;
  }
  .toggle-input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }
  .toggle-track {
    width: 32px;
    height: 18px;
    background: var(--bg3);
    border: 1px solid var(--b2);
    border-radius: 9px;
    position: relative;
    transition: background .2s, border-color .2s;
    flex-shrink: 0;
  }
  .toggle-input:checked ~ .toggle-track {
    background: var(--accent, #6366f1);
    border-color: var(--accent, #6366f1);
  }
  .toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 12px;
    height: 12px;
    background: var(--t3);
    border-radius: 50%;
    transition: left .2s, background .2s;
  }
  .toggle-input:checked ~ .toggle-track .toggle-thumb {
    left: 16px;
    background: #fff;
  }
  .toggle-text {
    font-size: 11px;
    color: var(--t2);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Janus Bootstrap Block
     ═══════════════════════════════════════════════════════════════════ */
  .janus-bootstrap {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .bootstrap-desc {
    font-size: 11px;
    color: var(--t2);
    line-height: 1.5;
  }
  .bootstrap-desc code {
    font-family: 'SF Mono', 'Fira Code', monospace;
    color: var(--cyan, #00e5ff);
    font-size: 10px;
  }
  .bootstrap-desc strong {
    color: var(--t1);
  }

  /* ═══════════════════════════════════════════════════════════════════
     System Info
     ═══════════════════════════════════════════════════════════════════ */
  .sys-overview {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 10px;
  }

  .sys-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .sys-key {
    font-size: 11px;
    color: var(--t2);
    font-weight: 600;
  }

  .sys-val {
    font-size: 11px;
    color: var(--t1);
  }

  .component-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 6px;
  }

  .component-card {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 10px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
  }

  .component-card .status-dot {
    margin-top: 3px;
  }

  .component-info {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .component-name {
    font-size: 11px;
    font-weight: 700;
    color: var(--t1);
    text-transform: capitalize;
  }

  .component-status {
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .component-latency {
    font-size: 9px;
    color: var(--t3);
    font-family: var(--font-mono, monospace);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Observability Links
     ═══════════════════════════════════════════════════════════════════ */
  .obs-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }

  .obs-link {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    text-decoration: none;
    color: var(--t1);
    transition: border-color 0.15s, background 0.15s;
  }

  .obs-link:hover {
    border-color: var(--accent, var(--cyan));
    background: var(--bg3);
  }

  .obs-icon {
    font-size: 18px;
    flex-shrink: 0;
  }

  .obs-label {
    font-size: 12px;
    font-weight: 700;
    color: var(--t1);
  }

  .obs-url {
    font-size: 9px;
    color: var(--t3);
    font-family: var(--font-mono, monospace);
    margin-left: auto;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Utilities
     ═══════════════════════════════════════════════════════════════════ */
  .empty-state {
    color: var(--t3);
    font-size: 11px;
    text-align: center;
    padding: 24px 0;
  }

  .mono {
    font-family: var(--font-mono, monospace);
  }

  /* ── Number input spinner removal ───────────────────────── */
  .form-input[type="number"]::-webkit-inner-spin-button,
  .form-input[type="number"]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  .form-input[type="number"] {
    -moz-appearance: textfield;
    appearance: textfield;
  }
</style>
