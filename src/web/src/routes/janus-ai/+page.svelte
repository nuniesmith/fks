<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import InnerTabs from '$components/ui/InnerTabs.svelte';
  import Panel from '$components/ui/Panel.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Modal from '$components/ui/Modal.svelte';

  // ─── Types ──────────────────────────────────────────────────────────

  interface RegimeEntry {
    regime: string;
    confidence: number;
    symbol?: string;
  }

  interface AffinityEntry {
    symbol?: string;
    asset?: string;
  }

  interface RecentSignal {
    time?: string;
    timestamp?: string;
    symbol?: string;
    direction?: string;
    strategy?: string;
    confidence?: number;
    status?: string;
  }

  interface JanusStateResponse {
    janus: {
      status: string;
      uptime?: string;
      version?: string;
    };
    redis: {
      regime: Record<string, RegimeEntry>;
      affinity: Record<string, AffinityEntry>;
      signals_recent: RecentSignal[];
    };
  }

  interface AffinityResponse {
    status: string;
    weights: Record<string, Record<string, number>>;
  }

  interface Session {
    id: string;
    name: string;
    description?: string;
    assets: string[];
    execution_method: string;
    state: string;
    strategies?: string[];
    account_type?: string;
    pnl?: number;
    created_at?: string;
  }

  interface SessionsResponse {
    sessions: Session[];
    total: number;
    running: number;
    stopped: number;
  }

  interface LiveSignal {
    time?: string;
    timestamp?: string;
    symbol?: string;
    direction?: string;
    strategy?: string;
    confidence?: number;
    status?: string;
    price?: number;
  }

  interface Memory {
    time?: string;
    timestamp?: string;
    symbol?: string;
    strategy?: string;
    regime?: string;
    result?: string;
    pnl?: number;
    duration?: string;
  }

  interface MemoriesResponse {
    memories: Memory[];
    count: number;
  }

  // ─── Constants ──────────────────────────────────────────────────────

  const ALL_ASSETS = ['MES', 'MNQ', 'MGC', 'MYM', 'M2K', 'BTC', 'ETH', 'SOL'];
  const ALL_STRATEGIES = [
    'momentum', 'mean_reversion', 'breakout', 'scalp',
    'trend_follow', 'volatility', 'regime_adaptive',
  ];
  const ACCOUNT_TYPES = ['paper', 'live', 'sim'];
  const EXECUTION_METHODS = ['paper', 'live'];

  const RIGHT_TABS = [
    { id: 'sessions', label: 'Sessions' },
    { id: 'signals', label: 'Live Signals' },
    { id: 'memories', label: 'Memories' },
  ];

  // ─── State ──────────────────────────────────────────────────────────

  // Janus State (10s poll)
  let janusState = $state<JanusStateResponse | null>(null);
  let janusLoading = $state(true);
  let janusError = $state<string | null>(null);

  // Affinity (30s poll)
  let affinity = $state<AffinityResponse | null>(null);
  let affinityLoading = $state(true);
  let affinityError = $state<string | null>(null);

  // Sessions (15s poll)
  let sessionsData = $state<SessionsResponse | null>(null);
  let sessionsLoading = $state(true);
  let sessionsError = $state<string | null>(null);

  // Live signals (5s poll)
  let liveSignals = $state<LiveSignal[]>([]);
  let signalsLoading = $state(true);
  let signalsError = $state<string | null>(null);

  // Memories (on-demand)
  let memoriesData = $state<MemoriesResponse | null>(null);
  let memoriesLoading = $state(false);
  let memoriesError = $state<string | null>(null);
  let memoriesFilter = $state('all');

  // Right pane tab
  let activeTab = $state('sessions');

  // Modal
  let modalOpen = $state(false);
  let formSubmitting = $state(false);
  let formError = $state<string | null>(null);

  // New session form
  let formName = $state('');
  let formDescription = $state('');
  let formAssets = $state<Record<string, boolean>>(Object.fromEntries(ALL_ASSETS.map(a => [a, false])));
  let formAccountType = $state('paper');
  let formExecution = $state('paper');
  let formStrategies = $state<Record<string, boolean>>(Object.fromEntries(ALL_STRATEGIES.map(s => [s, false])));

  // Session action loading
  let actionLoading = $state<Record<string, boolean>>({});

  // Timers
  let timers: ReturnType<typeof setInterval>[] = [];

  // ─── Derived ────────────────────────────────────────────────────────

  let janusStatus = $derived(janusState?.janus?.status ?? 'UNKNOWN');
  let regimeEntries = $derived(
    janusState?.redis?.regime
      ? Object.entries(janusState.redis.regime)
      : []
  );
  let recentSignals = $derived(
    janusState?.redis?.signals_recent?.slice(0, 5) ?? []
  );

  let affinityStrategies = $derived(
    affinity?.weights ? Object.keys(affinity.weights) : []
  );
  let affinityAssets = $derived(() => {
    if (!affinity?.weights) return [] as string[];
    const assetSet = new Set<string>();
    for (const strat of Object.values(affinity.weights)) {
      for (const asset of Object.keys(strat)) {
        assetSet.add(asset);
      }
    }
    return Array.from(assetSet).sort();
  });

  let sessions = $derived(sessionsData?.sessions ?? []);
  let sessionRunning = $derived(sessionsData?.running ?? 0);
  let sessionTotal = $derived(sessionsData?.total ?? 0);

  let filteredMemories = $derived(() => {
    const mems = memoriesData?.memories ?? [];
    if (memoriesFilter === 'all') return mems;
    return mems.filter(m => m.strategy === memoriesFilter);
  });

  let memoryStrategies = $derived(() => {
    const mems = memoriesData?.memories ?? [];
    const set = new Set<string>();
    for (const m of mems) {
      if (m.strategy) set.add(m.strategy);
    }
    return Array.from(set).sort();
  });

  // ─── API Fetchers ──────────────────────────────────────────────────

  async function fetchJanusState() {
    try {
      const res = await api.get<JanusStateResponse>('/api/janus/state');
      janusState = res;
      janusError = null;
    } catch (e: unknown) {
      janusError = e instanceof Error ? e.message : String(e);
    } finally {
      janusLoading = false;
    }
  }

  async function fetchAffinity() {
    try {
      const res = await api.get<AffinityResponse>('/api/janus/affinity');
      affinity = res;
      affinityError = null;
    } catch (e: unknown) {
      affinityError = e instanceof Error ? e.message : String(e);
    } finally {
      affinityLoading = false;
    }
  }

  async function fetchSessions() {
    try {
      const res = await api.get<SessionsResponse>('/api/janus-ai/sessions');
      sessionsData = res;
      sessionsError = null;
    } catch (e: unknown) {
      sessionsError = e instanceof Error ? e.message : String(e);
    } finally {
      sessionsLoading = false;
    }
  }

  async function fetchLiveSignals() {
    try {
      const raw = await api.get<any>('/api/db/redis/get/fks:memories:new');
      if (Array.isArray(raw)) {
        liveSignals = raw;
      } else if (raw && typeof raw === 'object' && raw.value) {
        try {
          const parsed = typeof raw.value === 'string' ? JSON.parse(raw.value) : raw.value;
          liveSignals = Array.isArray(parsed) ? parsed : [parsed];
        } catch {
          liveSignals = [raw.value];
        }
      } else if (raw && typeof raw === 'object') {
        liveSignals = Array.isArray(raw.signals) ? raw.signals : (Array.isArray(raw.data) ? raw.data : []);
      } else {
        liveSignals = [];
      }
      signalsError = null;
    } catch (e: unknown) {
      signalsError = e instanceof Error ? e.message : String(e);
    } finally {
      signalsLoading = false;
    }
  }

  async function fetchMemories() {
    memoriesLoading = true;
    try {
      const res = await api.get<MemoriesResponse>('/api/janus/memories?limit=30');
      memoriesData = res;
      memoriesError = null;
    } catch (e: unknown) {
      memoriesError = e instanceof Error ? e.message : String(e);
    } finally {
      memoriesLoading = false;
    }
  }

  // ─── Session Actions ──────────────────────────────────────────────

  async function startSession(id: string) {
    actionLoading[id] = true;
    try {
      await api.post(`/api/janus-ai/sessions/${id}/start`);
      await fetchSessions();
    } catch (e: unknown) {
      console.error('Failed to start session:', e);
    } finally {
      actionLoading[id] = false;
    }
  }

  async function stopSession(id: string) {
    actionLoading[id] = true;
    try {
      await api.post(`/api/janus-ai/sessions/${id}/stop`);
      await fetchSessions();
    } catch (e: unknown) {
      console.error('Failed to stop session:', e);
    } finally {
      actionLoading[id] = false;
    }
  }

  // ─── New Session Modal ────────────────────────────────────────────

  function openModal() {
    formName = '';
    formDescription = '';
    formAssets = Object.fromEntries(ALL_ASSETS.map(a => [a, false]));
    formAccountType = 'paper';
    formExecution = 'paper';
    formStrategies = Object.fromEntries(ALL_STRATEGIES.map(s => [s, false]));
    formError = null;
    modalOpen = true;
  }

  function closeModal() {
    modalOpen = false;
  }

  async function submitSession() {
    if (!formName.trim()) {
      formError = 'Session name is required.';
      return;
    }

    const selectedAssets = Object.entries(formAssets).filter(([, v]) => v).map(([k]) => k);
    if (selectedAssets.length === 0) {
      formError = 'Select at least one asset.';
      return;
    }

    const selectedStrategies = Object.entries(formStrategies).filter(([, v]) => v).map(([k]) => k);

    formSubmitting = true;
    formError = null;

    try {
      await api.post('/api/janus-ai/sessions', {
        name: formName.trim(),
        description: formDescription.trim(),
        assets: selectedAssets,
        account_type: formAccountType,
        execution_method: formExecution,
        strategies: selectedStrategies,
      });
      closeModal();
      await fetchSessions();
    } catch (e: unknown) {
      formError = e instanceof Error ? e.message : String(e);
    } finally {
      formSubmitting = false;
    }
  }

  // ─── Helpers ──────────────────────────────────────────────────────

  function fmtTime(ts?: string): string {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  }

  function fmtDate(ts?: string): string {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
             d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
    } catch {
      return ts;
    }
  }

  function fmtPnl(pnl?: number): string {
    if (pnl == null) return '—';
    const sign = pnl >= 0 ? '+' : '';
    return `${sign}${pnl.toFixed(2)}`;
  }

  function pnlColor(pnl?: number): 'green' | 'red' | 'default' {
    if (pnl == null) return 'default';
    return pnl >= 0 ? 'green' : 'red';
  }

  function stateBadge(state: string): 'green' | 'red' | 'amber' | 'default' {
    const s = state.toLowerCase();
    if (s === 'running' || s === 'active') return 'green';
    if (s === 'stopped' || s === 'error') return 'red';
    if (s === 'paused') return 'amber';
    return 'default';
  }

  function directionBadge(dir?: string): 'green' | 'red' | 'default' {
    if (!dir) return 'default';
    const d = dir.toLowerCase();
    if (d === 'long' || d === 'buy') return 'green';
    if (d === 'short' || d === 'sell') return 'red';
    return 'default';
  }

  function resultBadge(result?: string): 'green' | 'red' | 'default' {
    if (!result) return 'default';
    const r = result.toLowerCase();
    if (r === 'win' || r === 'profit') return 'green';
    if (r === 'loss' || r === 'stopped') return 'red';
    return 'default';
  }

  function regimeColor(regime?: string): string {
    if (!regime) return 'var(--t3)';
    const r = regime.toLowerCase();
    if (r.includes('trend') || r.includes('bull')) return 'var(--green)';
    if (r.includes('bear') || r.includes('crash')) return 'var(--red)';
    if (r.includes('range') || r.includes('mean')) return 'var(--amber)';
    if (r.includes('volatile') || r.includes('breakout')) return 'var(--cyan)';
    return 'var(--purple)';
  }

  function weightColor(w: number): 'green' | 'red' | 'amber' | 'cyan' {
    if (w >= 0.7) return 'green';
    if (w >= 0.4) return 'cyan';
    if (w >= 0.2) return 'amber';
    return 'red';
  }

  function handleTabChange(id: string) {
    activeTab = id;
    if (id === 'memories' && !memoriesData && !memoriesLoading) {
      fetchMemories();
    }
  }

  // ─── Lifecycle ────────────────────────────────────────────────────

  onMount(() => {
    fetchJanusState();
    fetchAffinity();
    fetchSessions();
    fetchLiveSignals();

    timers.push(setInterval(fetchJanusState, 10_000));
    timers.push(setInterval(fetchAffinity, 30_000));
    timers.push(setInterval(fetchSessions, 15_000));
    timers.push(setInterval(fetchLiveSignals, 5_000));
  });

  onDestroy(() => {
    for (const t of timers) clearInterval(t);
    timers = [];
  });
</script>

<svelte:head>
  <title>Janus AI — FKS Terminal</title>
</svelte:head>

<!-- ─── HEADER ───────────────────────────────────────────────────────── -->

<div class="page-header">
  <div class="header-left">
    <span class="title-icon">◆</span>
    <h1 class="page-title">Janus AI</h1>
    <Badge variant="purple">
      {sessionRunning} / {sessionTotal} sessions
    </Badge>
  </div>
  <div class="header-right">
    <span class="poll-badge">auto-refresh</span>
    <button class="btn btn-accent" onclick={openModal}>+ New Session</button>
  </div>
</div>

<!-- ─── MAIN LAYOUT ──────────────────────────────────────────────────── -->

<div class="page">

  <!-- ─── LEFT PANE: Brain State ─────────────────────────────────────── -->
  <div class="pane pane-left">

    <!-- Panel 1: Janus State -->
    <Panel title="Janus State" badge="10s">
      {#snippet header()}
        {#if janusState}
          <Badge variant={janusStatus === 'UP' || janusStatus === 'ok' ? 'green' : 'red'}>
            {janusStatus}
          </Badge>
        {/if}
      {/snippet}
        {#if janusLoading && !janusState}
          <Skeleton lines={4} />
        {:else if janusError && !janusState}
          <p class="error-msg">⚠ {janusError}</p>
        {:else}
          <!-- Regime Grid -->
          <div class="sub-label">Regime Detection</div>
          {#if regimeEntries.length > 0}
            <div class="regime-grid">
              {#each regimeEntries as [symbol, entry] (symbol)}
                <div class="regime-card">
                  <span class="regime-symbol">{symbol}</span>
                  <span class="regime-label" style:color={regimeColor(entry.regime)}>
                    {entry.regime || '—'}
                  </span>
                  {#if entry.confidence != null}
                    <ProgressBar
                      value={entry.confidence * 100}
                      color={entry.confidence >= 0.7 ? 'green' : entry.confidence >= 0.4 ? 'cyan' : 'amber'}
                      height="4px"
                      label="{(entry.confidence * 100).toFixed(0)}%"
                    />
                  {/if}
                </div>
              {/each}
            </div>
          {:else}
            <p class="empty-msg">No regime data available</p>
          {/if}

          <!-- Recent Signals Feed -->
          <div class="sub-label" style="margin-top: 12px;">Recent Signals</div>
          {#if recentSignals.length > 0}
            <div class="signal-feed">
              {#each recentSignals as sig, i (i)}
                <div class="signal-row">
                  <span class="sig-time">{fmtTime(sig.time ?? sig.timestamp)}</span>
                  <span class="sig-symbol">{sig.symbol ?? '—'}</span>
                  <Badge variant={directionBadge(sig.direction)}>
                    {sig.direction ?? '—'}
                  </Badge>
                  <span class="sig-strat">{sig.strategy ?? '—'}</span>
                  {#if sig.confidence != null}
                    <span class="sig-conf">{(sig.confidence * 100).toFixed(0)}%</span>
                  {/if}
                </div>
              {/each}
            </div>
          {:else}
            <p class="empty-msg">No recent signals</p>
          {/if}
        {/if}
    </Panel>

    <!-- Panel 2: Strategy Affinity -->
    <Panel title="Strategy Affinity" badge="30s">
        {#if affinityLoading && !affinity}
          <Skeleton lines={5} />
        {:else if affinityError && !affinity}
          <p class="error-msg">⚠ {affinityError}</p>
        {:else if affinityStrategies.length > 0}
          <div class="affinity-table-wrap">
            <table class="affinity-table">
              <thead>
                <tr>
                  <th class="th-strat">Strategy</th>
                  {#each affinityAssets() as asset (asset)}
                    <th class="th-asset">{asset}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each affinityStrategies as strat (strat)}
                  <tr>
                    <td class="td-strat">{strat}</td>
                    {#each affinityAssets() as asset (asset)}
                      {@const w = affinity?.weights?.[strat]?.[asset] ?? 0}
                      <td class="td-weight">
                        <div class="weight-cell">
                          <ProgressBar
                            value={w * 100}
                            color={weightColor(w)}
                            height="5px"
                          />
                          <span class="weight-val">{(w * 100).toFixed(0)}</span>
                        </div>
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <p class="empty-msg">No affinity data available</p>
        {/if}
    </Panel>

  </div>

  <!-- ─── RIGHT PANE: Tabs ───────────────────────────────────────────── -->
  <div class="pane pane-right">
    <Panel fill>
      {#snippet header()}
        <InnerTabs tabs={RIGHT_TABS} active={activeTab} onchange={handleTabChange} />
      {/snippet}

        <!-- ═══ TAB: Sessions ═══════════════════════════════════════════ -->
        {#if activeTab === 'sessions'}
          {#if sessionsLoading && !sessionsData}
            <Skeleton lines={6} />
          {:else if sessionsError && !sessionsData}
            <p class="error-msg">⚠ {sessionsError}</p>
          {:else if sessions.length === 0}
            <div class="empty-state">
              <p class="empty-msg">No sessions found</p>
              <button class="btn btn-accent btn-sm" onclick={openModal}>+ Create Session</button>
            </div>
          {:else}
            <div class="sessions-list">
              {#each sessions as session (session.id)}
                <div class="session-card">
                  <div class="session-header">
                    <span class="session-name">{session.name}</span>
                    <Badge variant={stateBadge(session.state)}>
                      {session.state}
                    </Badge>
                  </div>

                  <div class="session-meta">
                    <div class="meta-row">
                      <span class="meta-label">Assets</span>
                      <span class="meta-value">
                        {#each session.assets as asset, i (asset)}
                          <span class="asset-chip">{asset}</span>
                        {/each}
                      </span>
                    </div>
                    <div class="meta-row">
                      <span class="meta-label">Execution</span>
                      <span class="meta-value">
                        <Badge variant={session.execution_method === 'live' ? 'amber' : 'cyan'}>
                          {session.execution_method}
                        </Badge>
                      </span>
                    </div>
                    {#if session.strategies && session.strategies.length > 0}
                      <div class="meta-row">
                        <span class="meta-label">Strategies</span>
                        <span class="meta-value strats-wrap">
                          {session.strategies.join(', ')}
                        </span>
                      </div>
                    {/if}
                    <div class="meta-row">
                      <span class="meta-label">P&L</span>
                      <span class="meta-value pnl" class:pnl-pos={session.pnl != null && session.pnl >= 0} class:pnl-neg={session.pnl != null && session.pnl < 0}>
                        {fmtPnl(session.pnl)}
                      </span>
                    </div>
                  </div>

                  <div class="session-actions">
                    {#if session.state.toLowerCase() === 'running' || session.state.toLowerCase() === 'active'}
                      <button
                        class="btn btn-red btn-sm"
                        onclick={() => stopSession(session.id)}
                        disabled={actionLoading[session.id]}
                      >
                        {actionLoading[session.id] ? '…' : '■ Stop'}
                      </button>
                    {:else}
                      <button
                        class="btn btn-green btn-sm"
                        onclick={() => startSession(session.id)}
                        disabled={actionLoading[session.id]}
                      >
                        {actionLoading[session.id] ? '…' : '▶ Start'}
                      </button>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          {/if}

        <!-- ═══ TAB: Live Signals ═══════════════════════════════════════ -->
        {:else if activeTab === 'signals'}
          {#if signalsLoading && liveSignals.length === 0}
            <Skeleton lines={6} />
          {:else if signalsError && liveSignals.length === 0}
            <p class="error-msg">⚠ {signalsError}</p>
          {:else if liveSignals.length === 0}
            <p class="empty-msg">No live signals</p>
          {:else}
            <div class="data-table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>Strategy</th>
                    <th>Confidence</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {#each liveSignals as sig, i (i)}
                    <tr>
                      <td class="col-time">{fmtTime(sig.time ?? sig.timestamp)}</td>
                      <td class="col-symbol">{sig.symbol ?? '—'}</td>
                      <td>
                        <Badge variant={directionBadge(sig.direction)}>
                          {sig.direction ?? '—'}
                        </Badge>
                      </td>
                      <td class="col-strat">{sig.strategy ?? '—'}</td>
                      <td class="col-conf">
                        {#if sig.confidence != null}
                          <ProgressBar
                            value={sig.confidence * 100}
                            color={sig.confidence >= 0.7 ? 'green' : sig.confidence >= 0.4 ? 'cyan' : 'amber'}
                            height="5px"
                            label="{(sig.confidence * 100).toFixed(0)}%"
                          />
                        {:else}
                          <span class="dim">—</span>
                        {/if}
                      </td>
                      <td>
                        <Badge variant={sig.status === 'active' || sig.status === 'filled' ? 'green' : sig.status === 'rejected' ? 'red' : 'default'}>
                          {sig.status ?? '—'}
                        </Badge>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}

        <!-- ═══ TAB: Memories ═══════════════════════════════════════════ -->
        {:else if activeTab === 'memories'}
          <div class="memories-controls">
            <select class="select-filter" bind:value={memoriesFilter}>
              <option value="all">All Strategies</option>
              {#each memoryStrategies() as strat (strat)}
                <option value={strat}>{strat}</option>
              {/each}
            </select>
            <button class="btn btn-sm" onclick={fetchMemories} disabled={memoriesLoading}>
              {memoriesLoading ? '…' : '↻ Refresh'}
            </button>
            {#if memoriesData}
              <span class="memories-count">{memoriesData.count} total</span>
            {/if}
          </div>

          {#if memoriesLoading && !memoriesData}
            <Skeleton lines={6} />
          {:else if memoriesError && !memoriesData}
            <p class="error-msg">⚠ {memoriesError}</p>
          {:else if filteredMemories().length === 0}
            <p class="empty-msg">No memories found</p>
          {:else}
            <div class="data-table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Strategy</th>
                    <th>Regime</th>
                    <th>Result</th>
                    <th>P&L</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {#each filteredMemories() as mem, i (i)}
                    <tr>
                      <td class="col-time">{fmtDate(mem.time ?? mem.timestamp)}</td>
                      <td class="col-symbol">{mem.symbol ?? '—'}</td>
                      <td class="col-strat">{mem.strategy ?? '—'}</td>
                      <td>
                        <span style:color={regimeColor(mem.regime)}>{mem.regime ?? '—'}</span>
                      </td>
                      <td>
                        <Badge variant={resultBadge(mem.result)}>
                          {mem.result ?? '—'}
                        </Badge>
                      </td>
                      <td class:pnl-pos={mem.pnl != null && mem.pnl >= 0} class:pnl-neg={mem.pnl != null && mem.pnl < 0}>
                        {fmtPnl(mem.pnl)}
                      </td>
                      <td class="dim">{mem.duration ?? '—'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {/if}

    </Panel>
  </div>

</div>

<!-- ─── NEW SESSION MODAL ────────────────────────────────────────────── -->

<Modal open={modalOpen} title="New Session" onclose={closeModal}>
  <div class="modal-form">
    {#if formError}
      <div class="form-error">{formError}</div>
    {/if}

    <label class="form-label">
      <span>Name <span class="required">*</span></span>
      <input class="form-input" type="text" bind:value={formName} placeholder="e.g. Asian Session Scalp" />
    </label>

    <label class="form-label">
      <span>Description</span>
      <input class="form-input" type="text" bind:value={formDescription} placeholder="Optional description" />
    </label>

    <fieldset class="form-fieldset">
      <legend>Assets <span class="required">*</span></legend>
      <div class="checkbox-grid">
        {#each ALL_ASSETS as asset (asset)}
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={formAssets[asset]} />
            <span>{asset}</span>
          </label>
        {/each}
      </div>
    </fieldset>

    <label class="form-label">
      <span>Account Type</span>
      <select class="form-input" bind:value={formAccountType}>
        {#each ACCOUNT_TYPES as at (at)}
          <option value={at}>{at}</option>
        {/each}
      </select>
    </label>

    <label class="form-label">
      <span>Execution Method</span>
      <select class="form-input" bind:value={formExecution}>
        {#each EXECUTION_METHODS as em (em)}
          <option value={em}>{em}</option>
        {/each}
      </select>
    </label>

    <fieldset class="form-fieldset">
      <legend>Strategies</legend>
      <div class="checkbox-grid">
        {#each ALL_STRATEGIES as strat (strat)}
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={formStrategies[strat]} />
            <span>{strat.replace(/_/g, ' ')}</span>
          </label>
        {/each}
      </div>
    </fieldset>
  </div>

  {#snippet actions()}
    <button class="btn" onclick={closeModal} disabled={formSubmitting}>Cancel</button>
    <button class="btn btn-accent" onclick={submitSession} disabled={formSubmitting}>
      {formSubmitting ? 'Creating…' : 'Create Session'}
    </button>
  {/snippet}
</Modal>

<!-- ─── STYLES ───────────────────────────────────────────────────────── -->

<style>
  /* ── Page Header ───────────────────────────────────────── */
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid var(--b1);
    background: var(--bg1);
    flex-shrink: 0;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .title-icon {
    color: var(--purple);
    font-size: 14px;
  }

  .page-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--purple);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0;
  }

  /* ── Main Layout ───────────────────────────────────────── */
  .page {
    display: flex;
    height: calc(100% - 42px);
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

  .pane-left {
    flex: 55;
  }

  .pane-right {
    flex: 45;
    border-left: 1px solid var(--b1);
  }

  /* ── Sub Labels ────────────────────────────────────────── */
  .sub-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 6px;
  }

  /* ── Regime Grid ───────────────────────────────────────── */
  .regime-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 6px;
  }

  .regime-card {
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 6px 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .regime-symbol {
    font-size: 11px;
    font-weight: 700;
    color: var(--t1);
  }

  .regime-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  /* ── Signal Feed ───────────────────────────────────────── */
  .signal-feed {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .signal-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 6px;
    background: var(--bg2);
    border-radius: var(--r);
    font-size: 10px;
  }

  .sig-time {
    color: var(--t3);
    min-width: 55px;
    font-size: 9px;
  }

  .sig-symbol {
    color: var(--t1);
    font-weight: 600;
    min-width: 35px;
  }

  .sig-strat {
    color: var(--t2);
    font-size: 9px;
  }

  .sig-conf {
    color: var(--cyan);
    font-size: 9px;
    margin-left: auto;
  }

  /* ── Affinity Table ────────────────────────────────────── */
  .affinity-table-wrap {
    overflow-x: auto;
  }

  .affinity-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
  }

  .affinity-table th,
  .affinity-table td {
    padding: 4px 6px;
    border-bottom: 1px solid var(--b1);
    text-align: left;
  }

  .affinity-table th {
    color: var(--t3);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    background: var(--bg2);
    position: sticky;
    top: 0;
  }

  .th-strat {
    min-width: 100px;
  }

  .th-asset {
    min-width: 70px;
    text-align: center !important;
  }

  .td-strat {
    color: var(--t2);
    font-weight: 600;
  }

  .td-weight {
    text-align: center;
  }

  .weight-cell {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .weight-val {
    font-size: 9px;
    color: var(--t3);
    min-width: 20px;
    text-align: right;
  }

  /* ── Sessions List ─────────────────────────────────────── */
  .sessions-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .session-card {
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .session-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .session-name {
    font-size: 11px;
    font-weight: 700;
    color: var(--t1);
  }

  .session-meta {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .meta-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
  }

  .meta-label {
    color: var(--t3);
    min-width: 65px;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .meta-value {
    color: var(--t2);
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }

  .strats-wrap {
    font-size: 9px;
  }

  .asset-chip {
    background: var(--bg3);
    color: var(--t2);
    padding: 0 4px;
    border-radius: var(--r);
    font-size: 9px;
    font-weight: 600;
  }

  .session-actions {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
    padding-top: 4px;
    border-top: 1px solid var(--b1);
  }

  .pnl {
    font-weight: 600;
  }

  .pnl-pos {
    color: var(--green);
  }

  .pnl-neg {
    color: var(--red);
  }

  /* ── Data Tables ───────────────────────────────────────── */
  .data-table-wrap {
    overflow-x: auto;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
  }

  .data-table th,
  .data-table td {
    padding: 4px 6px;
    border-bottom: 1px solid var(--b1);
    text-align: left;
    white-space: nowrap;
  }

  .data-table th {
    color: var(--t3);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    background: var(--bg2);
    position: sticky;
    top: 0;
  }

  .data-table tbody tr:hover {
    background: var(--bg3);
  }

  .col-time {
    color: var(--t3);
    font-size: 9px;
  }

  .col-symbol {
    color: var(--t1);
    font-weight: 600;
  }

  .col-strat {
    color: var(--t2);
  }

  .col-conf {
    min-width: 90px;
  }

  /* ── Memories Controls ─────────────────────────────────── */
  .memories-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }

  .select-filter {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t2);
    font-size: 10px;
    padding: 3px 8px;
    font-family: inherit;
    outline: none;
  }

  .select-filter:focus {
    border-color: var(--accent);
  }

  .memories-count {
    font-size: 9px;
    color: var(--t3);
    margin-left: auto;
  }

  /* ── Buttons ───────────────────────────────────────────── */
  .btn {
    all: unset;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    font-size: 10px;
    font-family: inherit;
    font-weight: 600;
    border-radius: var(--r);
    cursor: pointer;
    background: var(--bg3);
    color: var(--t2);
    border: 1px solid var(--b2);
    transition: background 0.12s, color 0.12s, border-color 0.12s;
    white-space: nowrap;
  }

  .btn:hover {
    background: var(--bg4, var(--bg3));
    color: var(--t1);
    border-color: var(--b3);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-sm {
    padding: 2px 8px;
    font-size: 9px;
  }

  .btn-accent {
    background: var(--accent-dim);
    color: var(--accent);
    border-color: var(--accent-brd);
  }

  .btn-accent:hover {
    background: var(--accent);
    color: #fff;
  }

  .btn-green {
    background: var(--green-dim);
    color: var(--green);
    border-color: var(--green-brd);
  }

  .btn-green:hover {
    background: var(--green);
    color: #fff;
  }

  .btn-red {
    background: var(--red-dim);
    color: var(--red);
    border-color: var(--red-brd);
  }

  .btn-red:hover {
    background: var(--red);
    color: #fff;
  }

  /* ── Empty / Error States ──────────────────────────────── */
  .empty-msg {
    font-size: 10px;
    color: var(--t3);
    padding: 12px;
    text-align: center;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 24px;
  }

  .error-msg {
    font-size: 10px;
    color: var(--red);
    padding: 8px;
  }

  .dim {
    color: var(--t3);
  }

  /* ── Modal Form ────────────────────────────────────────── */
  .modal-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .form-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .required {
    color: var(--red);
  }

  .form-input {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t1);
    font-size: 11px;
    padding: 6px 8px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.12s;
  }

  .form-input:focus {
    border-color: var(--accent);
  }

  .form-input::placeholder {
    color: var(--t3);
  }

  .form-fieldset {
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 8px;
  }

  .form-fieldset legend {
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    padding: 0 4px;
  }

  .checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 4px 8px;
    margin-top: 4px;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    color: var(--t2);
    cursor: pointer;
    text-transform: none;
    letter-spacing: normal;
    font-weight: 400;
  }

  .checkbox-label input[type="checkbox"] {
    accent-color: var(--accent);
    width: 12px;
    height: 12px;
    cursor: pointer;
  }

  .form-error {
    background: var(--red-dim);
    border: 1px solid var(--red-brd);
    border-radius: var(--r);
    color: var(--red);
    font-size: 10px;
    padding: 6px 8px;
  }
</style>
