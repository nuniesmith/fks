<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Modal from '$components/ui/Modal.svelte';
  import Panel from '$components/ui/Panel.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface Session {
    id: string;
    name: string;
    strategy: string;
    assets: string[];
    state: 'running' | 'stopped' | 'paused';
    initial_balance: number;
    current_equity: number;
    total_pnl: number;
    created_at?: string;
  }

  interface SessionMetrics {
    equity: number;
    day_pnl: number;
    total_pnl: number;
    win_rate: number;
    trades_count: number;
    max_drawdown: number;
  }

  interface Position {
    symbol: string;
    side: 'long' | 'short';
    entry_price: number;
    current_price: number;
    unrealized_pnl: number;
    size: number;
  }

  interface Signal {
    time: string;
    symbol: string;
    direction: 'buy' | 'sell';
    strategy: string;
    confidence: number;
    status: 'executed' | 'pending' | 'rejected';
  }

  interface NewSimForm {
    name: string;
    strategy: string;
    assets: string[];
    initial_balance: number;
    execution_mode: 'market' | 'limit';
    account_type: 'futures' | 'crypto';
  }

  // ─── State ──────────────────────────────────────────────────────────
  let sessions = $state<Session[]>([]);
  let sessionsLoading = $state(true);
  let selectedId = $state<string | null>(null);

  let metrics = $state<SessionMetrics | null>(null);
  let metricsLoading = $state(false);

  let positions = $state<Position[]>([]);
  let positionsLoading = $state(false);

  let signals = $state<Signal[]>([]);
  let signalsLoading = $state(false);

  let showModal = $state(false);
  let formSubmitting = $state(false);
  let formError = $state('');

  // ─── Compare Mode ────────────────────────────────────────────────────
  let compareMode = $state(false);
  let compareSelected = $state<Set<string>>(new Set());
  let compareMetrics = $state<Map<string, SessionMetrics>>(new Map());
  let compareLoading = $state<Set<string>>(new Set());

  let compareSessionList = $derived(
    sessions.filter(s => compareSelected.has(s.id))
  );

  let form = $state<NewSimForm>({
    name: '',
    strategy: 'momentum',
    assets: [],
    initial_balance: 10000,
    execution_mode: 'market',
    account_type: 'futures',
  });

  // ─── Derived ────────────────────────────────────────────────────────
  let selectedSession = $derived(sessions.find(s => s.id === selectedId) ?? null);

  // ─── Constants ──────────────────────────────────────────────────────
  const STRATEGIES = [
    'momentum',
    'mean_reversion',
    'breakout',
    'scalping',
    'trend_following',
    'pairs_trading',
    'grid',
    'dca',
  ];

  const AVAILABLE_ASSETS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT',
    'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT',
    'MATIC/USDT', 'DOT/USDT', 'LINK/USDT', 'UNI/USDT',
  ];

  // ─── Timers ─────────────────────────────────────────────────────────
  let timers: ReturnType<typeof setInterval>[] = [];

  // ─── Helpers ────────────────────────────────────────────────────────
  function stateVariant(state: string): 'green' | 'red' | 'amber' | 'default' {
    if (state === 'running') return 'green';
    if (state === 'stopped') return 'red';
    if (state === 'paused') return 'amber';
    return 'default';
  }

  function sideVariant(side: string): 'green' | 'red' | 'default' {
    if (side === 'long') return 'green';
    if (side === 'short') return 'red';
    return 'default';
  }

  function signalStatusVariant(status: string): 'green' | 'amber' | 'red' | 'default' {
    if (status === 'executed') return 'green';
    if (status === 'pending') return 'amber';
    if (status === 'rejected') return 'red';
    return 'default';
  }

  function directionVariant(dir: string): 'green' | 'red' | 'default' {
    if (dir === 'buy') return 'green';
    if (dir === 'sell') return 'red';
    return 'default';
  }

  function fmtUsd(v: number | null | undefined): string {
    if (v == null) return '—';
    return '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtPct(v: number | null | undefined): string {
    if (v == null) return '—';
    return v.toFixed(2) + '%';
  }

  function fmtNum(v: number | null | undefined): string {
    if (v == null) return '—';
    return v.toLocaleString('en-US');
  }

  function fmtPrice(v: number | null | undefined): string {
    if (v == null) return '—';
    if (Math.abs(v) >= 1) return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return v.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  }

  function fmtTime(t: string | null | undefined): string {
    if (!t) return '—';
    try {
      const d = new Date(t);
      return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
      });
    } catch {
      return t;
    }
  }

  function pnlColor(v: number | null | undefined): 'green' | 'red' | 'default' {
    if (v == null || v === 0) return 'default';
    return v > 0 ? 'green' : 'red';
  }

  function pnlSign(v: number): string {
    if (v > 0) return '+';
    return '';
  }

  // ─── Fetch Functions ────────────────────────────────────────────────
  async function fetchSessions(): Promise<void> {
    try {
      const raw = await api.get<{ sessions?: Session[] } | Session[]>(
        '/api/paper-trading/sessions'
      );
      if (Array.isArray(raw)) {
        sessions = raw;
      } else if (raw && Array.isArray(raw.sessions)) {
        sessions = raw.sessions;
      } else {
        sessions = [];
      }
    } catch {
      // keep previous on error
    } finally {
      sessionsLoading = false;
    }
  }

  async function fetchMetrics(id: string): Promise<void> {
    metricsLoading = true;
    try {
      const resp = await api.get<SessionMetrics>(
        `/api/paper-trading/sessions/${id}/metrics`
      );
      if (selectedId === id) {
        metrics = resp;
      }
    } catch {
      if (selectedId === id) metrics = null;
    } finally {
      if (selectedId === id) metricsLoading = false;
    }
  }

  async function fetchPositions(id: string): Promise<void> {
    positionsLoading = true;
    try {
      const raw = await api.get<{ positions?: Position[] } | Position[]>(
        `/api/paper-trading/sessions/${id}/positions`
      );
      if (selectedId === id) {
        if (Array.isArray(raw)) {
          positions = raw;
        } else if (raw && Array.isArray(raw.positions)) {
          positions = raw.positions;
        } else {
          positions = [];
        }
      }
    } catch {
      if (selectedId === id) positions = [];
    } finally {
      if (selectedId === id) positionsLoading = false;
    }
  }

  async function fetchSignals(id: string): Promise<void> {
    signalsLoading = true;
    try {
      const raw = await api.get<{ signals?: Signal[] } | Signal[]>(
        `/api/paper-trading/sessions/${id}/signals?limit=20`
      );
      if (selectedId === id) {
        if (Array.isArray(raw)) {
          signals = raw;
        } else if (raw && Array.isArray(raw.signals)) {
          signals = raw.signals;
        } else {
          signals = [];
        }
      }
    } catch {
      if (selectedId === id) signals = [];
    } finally {
      if (selectedId === id) signalsLoading = false;
    }
  }

  function fetchDetailData(id: string): void {
    fetchMetrics(id);
    fetchPositions(id);
    fetchSignals(id);
  }

  function selectSession(id: string): void {
    if (selectedId === id) return;
    selectedId = id;
    metrics = null;
    positions = [];
    signals = [];
    metricsLoading = true;
    positionsLoading = true;
    signalsLoading = true;
    fetchDetailData(id);
  }

  // ─── Session Actions ────────────────────────────────────────────────
  async function sessionAction(id: string, action: 'start' | 'stop' | 'pause' | 'resume', e: MouseEvent): Promise<void> {
    e.stopPropagation();
    try {
      await api.post(`/api/paper-trading/sessions/${id}/${action}`);
      await fetchSessions();
    } catch (err) {
      console.warn(`[simulations] ${action} failed:`, err);
    }
  }

  // ─── Modal / Form ──────────────────────────────────────────────────
  function openModal(): void {
    form = {
      name: '',
      strategy: 'momentum',
      assets: [],
      initial_balance: 10000,
      execution_mode: 'market',
      account_type: 'futures',
    };
    formError = '';
    formSubmitting = false;
    showModal = true;
  }

  function closeModal(): void {
    showModal = false;
  }

  function toggleAsset(asset: string): void {
    if (form.assets.includes(asset)) {
      form.assets = form.assets.filter(a => a !== asset);
    } else {
      form.assets = [...form.assets, asset];
    }
  }

  async function submitNewSimulation(): Promise<void> {
    if (!form.name.trim()) {
      formError = 'Name is required.';
      return;
    }
    if (form.assets.length === 0) {
      formError = 'Select at least one asset.';
      return;
    }
    if (form.initial_balance <= 0) {
      formError = 'Initial balance must be positive.';
      return;
    }

    formSubmitting = true;
    formError = '';

    try {
      const resp = await api.post<{ id?: string; session?: { id?: string } }>(
        '/api/paper-trading/sessions',
        {
          name: form.name.trim(),
          strategy: form.strategy,
          assets: form.assets,
          initial_balance: form.initial_balance,
          execution_mode: form.execution_mode,
          account_type: form.account_type,
        }
      );
      closeModal();
      await fetchSessions();
      // Select the newly created session
      const newId = resp?.id ?? resp?.session?.id;
      if (newId) {
        selectSession(newId);
      } else if (sessions.length > 0) {
        selectSession(sessions[sessions.length - 1].id);
      }
    } catch (err: unknown) {
      formError = err instanceof Error ? err.message : 'Failed to create simulation.';
    } finally {
      formSubmitting = false;
    }
  }

  // ─── Detail Polling ─────────────────────────────────────────────────
  let detailTimer: ReturnType<typeof setInterval> | null = null;

  function startDetailPoll(): void {
    stopDetailPoll();
    detailTimer = setInterval(() => {
      if (selectedId) {
        fetchMetrics(selectedId);
        fetchPositions(selectedId);
      }
    }, 5_000);
  }

  function stopDetailPoll(): void {
    if (detailTimer !== null) {
      clearInterval(detailTimer);
      detailTimer = null;
    }
  }

  // ─── Compare Mode Helpers ───────────────────────────────────────────
  function toggleCompareMode(): void {
    compareMode = !compareMode;
    if (!compareMode) {
      compareSelected = new Set();
      compareMetrics = new Map();
      compareLoading = new Set();
    }
  }

  function toggleCompareSession(id: string, e: MouseEvent): void {
    e.stopPropagation();
    const next = new Set(compareSelected);
    if (next.has(id)) {
      next.delete(id);
      const m = new Map(compareMetrics);
      m.delete(id);
      compareMetrics = m;
    } else {
      next.add(id);
      fetchCompareMetrics(id);
    }
    compareSelected = next;
  }

  async function fetchCompareMetrics(id: string): Promise<void> {
    compareLoading = new Set([...compareLoading, id]);
    try {
      const resp = await api.get<SessionMetrics>(
        `/api/paper-trading/sessions/${id}/metrics`
      );
      compareMetrics = new Map([...compareMetrics, [id, resp]]);
    } catch {
      // leave out of map — will show "—" in table
    } finally {
      const next = new Set(compareLoading);
      next.delete(id);
      compareLoading = next;
    }
  }

  async function refreshCompareAll(): Promise<void> {
    for (const id of compareSelected) {
      fetchCompareMetrics(id);
    }
  }

  function clearCompare(): void {
    compareSelected = new Set();
    compareMetrics = new Map();
    compareLoading = new Set();
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    fetchSessions();
    timers.push(setInterval(fetchSessions, 10_000));
    startDetailPoll();
  });

  onDestroy(() => {
    timers.forEach(clearInterval);
    timers = [];
    stopDetailPoll();
  });
</script>

<svelte:head>
  <title>Simulations — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ═══════════════════════════════════════════════════════════════════
       LEFT SIDEBAR — Session List
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title-row">
        <span class="sidebar-title">Simulations</span>
        <Badge variant="default">{sessions.length}</Badge>
        {#if compareMode}
          <Badge variant="cyan">Compare {compareSelected.size}</Badge>
        {/if}
      </div>
      <div class="sidebar-btn-row">
        <button
          class="btn-compare"
          class:active={compareMode}
          onclick={toggleCompareMode}
          title={compareMode ? 'Exit compare mode' : 'Compare sessions side-by-side'}
        >
          {compareMode ? '✕ Compare' : '⇄ Compare'}
        </button>
        {#if !compareMode}
          <button class="btn-primary" onclick={openModal}>+ New</button>
        {:else}
          <button class="btn-ghost-sm" onclick={clearCompare} disabled={compareSelected.size === 0}>
            Clear
          </button>
        {/if}
      </div>
    </div>

    <div class="session-list">
      {#if sessionsLoading && sessions.length === 0}
        <div class="sidebar-loading">
          <Skeleton lines={4} height="16px" />
        </div>
      {:else if sessions.length === 0}
        <div class="sidebar-empty">
          <span class="empty-icon">📊</span>
          <span class="empty-text">No simulations yet</span>
          <span class="empty-hint">Create one to get started</span>
        </div>
      {:else}
        {#each sessions as session (session.id)}
          <div
            class="session-card"
            class:selected={!compareMode && selectedId === session.id}
            class:compare-checked={compareMode && compareSelected.has(session.id)}
            role="button"
            tabindex="0"
            onclick={(e) => compareMode ? toggleCompareSession(session.id, e) : selectSession(session.id)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); compareMode ? toggleCompareSession(session.id, e as unknown as MouseEvent) : selectSession(session.id); } }}
          >
            <div class="card-top">
              {#if compareMode}
                <span class="compare-check" class:checked={compareSelected.has(session.id)}>
                  {compareSelected.has(session.id) ? '☑' : '☐'}
                </span>
              {/if}
              <span class="card-name">{session.name}</span>
              <Badge variant={stateVariant(session.state)}>{session.state}</Badge>
            </div>
            <div class="card-strategy">{session.strategy}</div>
            {#if session.assets && session.assets.length > 0}
              <div class="card-assets">
                {#each session.assets.slice(0, 4) as asset}
                  <span class="asset-chip">{asset}</span>
                {/each}
                {#if session.assets.length > 4}
                  <span class="asset-chip asset-more">+{session.assets.length - 4}</span>
                {/if}
              </div>
            {/if}
            <div class="card-pnl" class:green={session.total_pnl > 0} class:red={session.total_pnl < 0}>
              {pnlSign(session.total_pnl)}{fmtUsd(session.total_pnl)}
            </div>
            <div class="card-actions">
              {#if session.state === 'stopped'}
                <button class="action-btn action-start" onclick={(e) => sessionAction(session.id, 'start', e)} title="Start">▶</button>
              {/if}
              {#if session.state === 'running'}
                <button class="action-btn action-pause" onclick={(e) => sessionAction(session.id, 'pause', e)} title="Pause">⏸</button>
                <button class="action-btn action-stop" onclick={(e) => sessionAction(session.id, 'stop', e)} title="Stop">⏹</button>
              {/if}
              {#if session.state === 'paused'}
                <button class="action-btn action-resume" onclick={(e) => sessionAction(session.id, 'resume', e)} title="Resume">▶</button>
                <button class="action-btn action-stop" onclick={(e) => sessionAction(session.id, 'stop', e)} title="Stop">⏹</button>
              {/if}
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <div class="sidebar-footer">
      <span class="poll-badge">10s poll</span>
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════════════════════════
       RIGHT DETAIL PANEL
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="detail-pane">
    {#if compareMode}
      <!-- ═══════════════════════════════════════════════════════════════
           COMPARE PANEL
           ═══════════════════════════════════════════════════════════════ -->
      {#if compareSelected.size < 2}
        <div class="detail-placeholder">
          <span class="placeholder-icon">⇄</span>
          <span class="placeholder-text">Compare Mode</span>
          <span class="placeholder-hint">
            Select {2 - compareSelected.size} more session{compareSelected.size === 1 ? '' : 's'} from the sidebar to compare
          </span>
        </div>
      {:else}
        <div class="compare-header">
          <span class="compare-title">Comparing {compareSelected.size} sessions</span>
          <button class="btn-ghost-sm" onclick={refreshCompareAll}>↻ Refresh</button>
          <button class="btn-ghost-sm" onclick={clearCompare}>✕ Clear</button>
        </div>

        <!-- Comparison metrics table -->
        <Panel title="Side-by-Side Metrics" noPad fill>
            <table class="cmp-table">
              <thead>
                <tr>
                  <th class="cmp-metric-col">Metric</th>
                  {#each compareSessionList as s (s.id)}
                    <th class="cmp-session-col">
                      <div class="cmp-session-name">{s.name}</div>
                      <Badge variant={stateVariant(s.state)}>{s.state}</Badge>
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each [
                  { key: 'equity',       label: 'Equity',        fmt: fmtUsd,  color: true },
                  { key: 'total_pnl',    label: 'Total P&L',     fmt: (v: number) => pnlSign(v) + fmtUsd(v), color: true },
                  { key: 'day_pnl',      label: 'Day P&L',       fmt: (v: number) => pnlSign(v) + fmtUsd(v), color: true },
                  { key: 'win_rate',     label: 'Win Rate',      fmt: fmtPct,  color: false },
                  { key: 'trades_count', label: 'Trades',        fmt: fmtNum,  color: false },
                  { key: 'max_drawdown', label: 'Max Drawdown',  fmt: fmtPct,  color: false },
                ] as row (row.key)}
                  <tr class="cmp-row">
                    <td class="cmp-metric-lbl">{row.label}</td>
                    {#each compareSessionList as s (s.id)}
                      {@const m = compareMetrics.get(s.id)}
                      {@const loading = compareLoading.has(s.id)}
                      <td class="cmp-val"
                        class:cmp-green={row.color && m && (m as unknown as Record<string,number>)[row.key] > 0}
                        class:cmp-red={row.color && m && (m as unknown as Record<string,number>)[row.key] < 0}
                      >
                        {#if loading}
                          <span class="cmp-loading">…</span>
                        {:else if m}
                          {row.fmt((m as unknown as Record<string,number>)[row.key])}
                        {:else}
                          <span class="cmp-na">—</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
        </Panel>

        <!-- Per-session asset lists -->
        <Panel title="Assets">
            <div class="cmp-assets-row">
              {#each compareSessionList as s (s.id)}
                <div class="cmp-asset-col">
                  <span class="cmp-session-label">{s.name}</span>
                  <div class="cmp-chips">
                    {#each (s.assets ?? []) as asset}
                      <span class="asset-chip">{asset}</span>
                    {/each}
                    {#if !s.assets?.length}
                      <span class="cmp-na">—</span>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
        </Panel>
      {/if}
    {:else if !selectedSession}
      <div class="detail-placeholder">
        <span class="placeholder-icon">◎</span>
        <span class="placeholder-text">Select a session</span>
        <span class="placeholder-hint">Choose a simulation from the sidebar to view details</span>
      </div>
    {:else}
      <!-- Detail Header -->
      <div class="detail-header">
        <div class="detail-title-row">
          <span class="detail-title">{selectedSession.name}</span>
          <Badge variant={stateVariant(selectedSession.state)}>{selectedSession.state}</Badge>
          <span class="detail-strategy">{selectedSession.strategy}</span>
        </div>
        <span class="poll-badge">5s poll</span>
      </div>

      <!-- ═══════════════════════════════════════════════════════════════
           Section 1 — Session Metrics
           ═══════════════════════════════════════════════════════════════ -->
      <Panel title="Session Metrics" badge="5s">
          {#if metricsLoading && !metrics}
            <div class="stat-row">
              {#each Array(6) as _}
                <div class="stat-slot"><Skeleton lines={2} height="16px" /></div>
              {/each}
            </div>
          {:else if metrics}
            <div class="stat-row">
              <StatCard
                label="Equity"
                value={fmtUsd(metrics.equity)}
                color="cyan"
              />
              <StatCard
                label="Day P&L"
                value={pnlSign(metrics.day_pnl) + fmtUsd(metrics.day_pnl)}
                color={pnlColor(metrics.day_pnl)}
              />
              <StatCard
                label="Total P&L"
                value={pnlSign(metrics.total_pnl) + fmtUsd(metrics.total_pnl)}
                color={pnlColor(metrics.total_pnl)}
              />
              <StatCard
                label="Win Rate"
                value={fmtPct(metrics.win_rate)}
                color={metrics.win_rate >= 50 ? 'green' : 'amber'}
              />
              <StatCard
                label="Trades"
                value={fmtNum(metrics.trades_count)}
                color="default"
              />
              <StatCard
                label="Max Drawdown"
                value={fmtPct(metrics.max_drawdown)}
                color={metrics.max_drawdown > 10 ? 'red' : 'amber'}
              />
            </div>
          {:else}
            <p class="empty-msg">No metrics available</p>
          {/if}
      </Panel>

      <!-- ═══════════════════════════════════════════════════════════════
           Section 2 — Open Positions
           ═══════════════════════════════════════════════════════════════ -->
      <Panel title="Open Positions" badge="5s">
          {#if positionsLoading && positions.length === 0}
            <Skeleton lines={3} height="14px" />
          {:else if positions.length === 0}
            <p class="empty-msg">No open positions</p>
          {:else}
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th class="align-right">Entry</th>
                    <th class="align-right">Current</th>
                    <th class="align-right">Unreal. P&L</th>
                    <th class="align-right">Size</th>
                  </tr>
                </thead>
                <tbody>
                  {#each positions as pos}
                    <tr>
                      <td class="cell-symbol">{pos.symbol}</td>
                      <td>
                        <Badge variant={sideVariant(pos.side)}>{pos.side}</Badge>
                      </td>
                      <td class="align-right">{fmtPrice(pos.entry_price)}</td>
                      <td class="align-right">{fmtPrice(pos.current_price)}</td>
                      <td class="align-right" class:green={pos.unrealized_pnl > 0} class:red={pos.unrealized_pnl < 0}>
                        {pnlSign(pos.unrealized_pnl)}{fmtUsd(pos.unrealized_pnl)}
                      </td>
                      <td class="align-right">{fmtNum(pos.size)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
      </Panel>

      <!-- ═══════════════════════════════════════════════════════════════
           Section 3 — Signal History
           ═══════════════════════════════════════════════════════════════ -->
      <Panel title="Signal History">
        {#snippet header()}
          <Badge variant="default">Last 20</Badge>
        {/snippet}
          {#if signalsLoading && signals.length === 0}
            <Skeleton lines={4} height="14px" />
          {:else if signals.length === 0}
            <p class="empty-msg">No signals recorded</p>
          {:else}
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Direction</th>
                    <th>Strategy</th>
                    <th class="align-right">Confidence</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {#each signals as sig}
                    <tr>
                      <td class="cell-time">{fmtTime(sig.time)}</td>
                      <td class="cell-symbol">{sig.symbol}</td>
                      <td>
                        <Badge variant={directionVariant(sig.direction)}>{sig.direction}</Badge>
                      </td>
                      <td class="dim">{sig.strategy}</td>
                      <td class="align-right">{fmtPct(sig.confidence)}</td>
                      <td>
                        <Badge variant={signalStatusVariant(sig.status)}>{sig.status}</Badge>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
      </Panel>
    {/if}
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     NEW SIMULATION MODAL
     ═══════════════════════════════════════════════════════════════════ -->
<Modal open={showModal} title="New Simulation" onclose={closeModal}>
  <div class="form-grid">
    <!-- Name -->
    <label class="form-label">
      <span class="label-text">Name</span>
      <input
        class="form-input"
        type="text"
        placeholder="My Strategy Test"
        bind:value={form.name}
      />
    </label>

    <!-- Strategy -->
    <label class="form-label">
      <span class="label-text">Strategy</span>
      <select class="form-select" bind:value={form.strategy}>
        {#each STRATEGIES as strat}
          <option value={strat}>{strat.replace(/_/g, ' ')}</option>
        {/each}
      </select>
    </label>

    <!-- Assets -->
    <div class="form-label">
      <span class="label-text">Assets</span>
      <div class="asset-grid">
        {#each AVAILABLE_ASSETS as asset}
          <label class="asset-check">
            <input
              type="checkbox"
              checked={form.assets.includes(asset)}
              onchange={() => toggleAsset(asset)}
            />
            <span class="asset-check-label">{asset}</span>
          </label>
        {/each}
      </div>
    </div>

    <!-- Initial Balance -->
    <label class="form-label">
      <span class="label-text">Initial Balance ($)</span>
      <input
        class="form-input"
        type="number"
        min="100"
        step="100"
        bind:value={form.initial_balance}
      />
    </label>

    <!-- Execution Mode -->
    <label class="form-label">
      <span class="label-text">Execution Mode</span>
      <select class="form-select" bind:value={form.execution_mode}>
        <option value="market">Market</option>
        <option value="limit">Limit</option>
      </select>
    </label>

    <!-- Account Type -->
    <label class="form-label">
      <span class="label-text">Account Type</span>
      <select class="form-select" bind:value={form.account_type}>
        <option value="futures">Futures</option>
        <option value="crypto">Crypto</option>
      </select>
    </label>

    {#if formError}
      <div class="form-error">{formError}</div>
    {/if}
  </div>

  {#snippet actions()}
    <button class="btn-ghost" onclick={closeModal} disabled={formSubmitting}>Cancel</button>
    <button class="btn-primary" onclick={submitNewSimulation} disabled={formSubmitting}>
      {#if formSubmitting}
        Creating…
      {:else}
        Create Simulation
      {/if}
    </button>
  {/snippet}
</Modal>

<style>
  /* ── Page Layout ─────────────────────────────────────────── */
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
  }

  /* ── Sidebar ─────────────────────────────────────────────── */
  .sidebar {
    width: 280px;
    min-width: 280px;
    max-width: 280px;
    display: flex;
    flex-direction: column;
    background: var(--bg1);
    border-right: 1px solid var(--b2);
    overflow: hidden;
  }

  .sidebar-header {
    padding: 10px;
    border-bottom: 1px solid var(--b1);
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: var(--bg2);
  }

  .sidebar-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .sidebar-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--t1);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .sidebar-loading {
    padding: 12px 8px;
  }

  .sidebar-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 32px 16px;
    text-align: center;
  }

  .empty-icon {
    font-size: 24px;
    opacity: 0.5;
  }

  .empty-text {
    font-size: 11px;
    color: var(--t2);
    font-weight: 600;
  }

  .empty-hint {
    font-size: 10px;
    color: var(--t3);
  }

  .sidebar-footer {
    padding: 6px 10px;
    border-top: 1px solid var(--b1);
    display: flex;
    justify-content: flex-end;
    background: var(--bg2);
  }

  /* ── Session Card ────────────────────────────────────────── */
  .session-card {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    padding: 8px 10px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: border-color 0.15s, background 0.15s;
  }

  .session-card:hover {
    background: var(--bg3);
    border-color: var(--b3);
  }

  .session-card.selected {
    border-color: var(--accent-brd);
    border-left: 3px solid var(--accent);
    background: var(--accent-dim);
  }

  .card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }

  .card-name {
    font-size: 11px;
    font-weight: 600;
    color: var(--t1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }

  .card-strategy {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .card-assets {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }

  .asset-chip {
    font-size: 8px;
    font-weight: 600;
    color: var(--t2);
    background: var(--bg3);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 1px 4px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .asset-more {
    color: var(--t3);
    font-style: italic;
  }

  .card-pnl {
    font-size: 12px;
    font-weight: 700;
    color: var(--t1);
  }

  .card-pnl.green { color: var(--green); }
  .card-pnl.red   { color: var(--red); }

  .card-actions {
    display: flex;
    gap: 4px;
    margin-top: 2px;
  }

  .action-btn {
    background: var(--bg3);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t2);
    font-size: 10px;
    padding: 2px 8px;
    cursor: pointer;
    line-height: 1.2;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
  }

  .action-btn:hover {
    background: var(--bg4);
    border-color: var(--b3);
  }

  .action-start:hover,
  .action-resume:hover {
    color: var(--green);
    border-color: var(--green-brd);
  }

  .action-stop:hover {
    color: var(--red);
    border-color: var(--red-brd);
  }

  .action-pause:hover {
    color: var(--amber);
    border-color: var(--amber-brd);
  }

  /* ── Detail Pane ─────────────────────────────────────────── */
  .detail-pane {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .detail-placeholder {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .placeholder-icon {
    font-size: 32px;
    color: var(--t3);
    opacity: 0.4;
  }

  .placeholder-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--t2);
  }

  .placeholder-hint {
    font-size: 10px;
    color: var(--t3);
  }

  .detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    gap: 12px;
  }

  .detail-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .detail-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--t1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .detail-strategy {
    font-size: 10px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .poll-badge {
    font-size: 8px;
    font-weight: 600;
    color: var(--accent);
    background: var(--accent-dim);
    border: 1px solid var(--accent-brd);
    border-radius: var(--r);
    padding: 1px 5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-left: auto;
  }

  /* ── Stat Row ────────────────────────────────────────────── */
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

  /* ── Table ───────────────────────────────────────────────── */
  .table-wrap {
    width: 100%;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    color: var(--t1);
  }

  thead tr {
    border-bottom: 1px solid var(--b2);
  }

  th {
    padding: 6px 10px;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--t3);
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
    text-align: left;
  }

  tbody tr {
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s ease;
  }

  tbody tr:hover {
    background: var(--bg3);
  }

  tbody tr:last-child {
    border-bottom: none;
  }

  td {
    padding: 5px 10px;
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
  }

  .align-right {
    text-align: right;
  }

  .cell-symbol {
    font-weight: 600;
    color: var(--t1);
  }

  .cell-time {
    font-size: 10px;
    color: var(--t2);
  }

  .green { color: var(--green); }
  .red   { color: var(--red); }
  .dim   { color: var(--t3); }

  .empty-msg {
    font-size: 11px;
    color: var(--t3);
    padding: 16px;
    text-align: center;
  }

  /* ── Buttons ─────────────────────────────────────────────── */
  .btn-primary {
    background: var(--accent-dim);
    border: 1px solid var(--accent-brd);
    border-radius: var(--r);
    color: var(--accent);
    font-size: 10px;
    font-weight: 600;
    padding: 6px 12px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: inherit;
    transition: background 0.15s, color 0.15s;
    white-space: nowrap;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--accent);
    color: var(--bg0);
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-ghost {
    background: none;
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t2);
    font-size: 10px;
    font-weight: 600;
    padding: 6px 12px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: inherit;
    transition: color 0.15s, border-color 0.15s;
  }

  .btn-ghost:hover:not(:disabled) {
    color: var(--t1);
    border-color: var(--b3);
  }

  .btn-ghost:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* ── Form Styles ─────────────────────────────────────────── */
  .form-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .form-label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .label-text {
    font-size: 9px;
    font-weight: 600;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .form-input,
  .form-select {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t1);
    font-family: inherit;
    font-size: 11px;
    padding: 6px 8px;
    outline: none;
    transition: border-color 0.15s;
    width: 100%;
  }

  .form-input:focus,
  .form-select:focus {
    border-color: var(--accent-brd);
  }

  .form-input::placeholder {
    color: var(--t3);
  }

  .form-select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23454870'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    padding-right: 24px;
    cursor: pointer;
  }

  .form-select option {
    background: var(--bg1);
    color: var(--t1);
  }

  .asset-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
  }

  .asset-check {
    display: flex;
    align-items: center;
    gap: 5px;
    cursor: pointer;
    padding: 3px 4px;
    border-radius: var(--r);
    transition: background 0.1s;
  }

  .asset-check:hover {
    background: var(--bg3);
  }

  .asset-check input[type="checkbox"] {
    accent-color: var(--accent);
    width: 12px;
    height: 12px;
    cursor: pointer;
  }

  .asset-check-label {
    font-size: 10px;
    color: var(--t2);
    font-weight: 500;
  }

  .form-error {
    font-size: 11px;
    color: var(--red);
    padding: 6px 8px;
    background: var(--red-dim);
    border: 1px solid var(--red-brd);
    border-radius: var(--r);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Compare Mode
     ═══════════════════════════════════════════════════════════════════ */
  .sidebar-btn-row {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-top: 6px;
  }

  .btn-compare {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--t2);
    background: var(--bg2);
    border: 1px solid var(--border);
    padding: 3px 10px;
    border-radius: var(--r);
    font-weight: 600;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
    white-space: nowrap;
  }
  .btn-compare:hover { background: var(--bg3); color: var(--t1); }
  .btn-compare.active {
    color: var(--cyan);
    border-color: rgba(0, 212, 255, 0.35);
    background: rgba(0, 212, 255, 0.08);
  }

  .btn-ghost-sm {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--t3);
    padding: 2px 7px;
    border-radius: var(--r);
    border: 1px solid var(--border);
    transition: background 0.12s, color 0.12s;
    white-space: nowrap;
  }
  .btn-ghost-sm:hover:not(:disabled) { background: var(--bg3); color: var(--t1); }
  .btn-ghost-sm:disabled { opacity: 0.35; cursor: not-allowed; }

  .session-card.compare-checked {
    border-color: rgba(0, 212, 255, 0.45);
    background: rgba(0, 212, 255, 0.06);
  }

  .compare-check {
    font-size: 13px;
    line-height: 1;
    color: var(--t3);
    flex-shrink: 0;
    margin-right: 2px;
  }
  .compare-check.checked { color: var(--cyan); }

  /* Compare header */
  .compare-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .compare-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--cyan);
    flex: 1;
  }

  /* Comparison table */
  .cmp-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
  }

  .cmp-table thead tr {
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
  }

  .cmp-metric-col {
    text-align: left;
    padding: 8px 12px;
    font-size: 10px;
    color: var(--t3);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    width: 120px;
    white-space: nowrap;
  }

  .cmp-session-col {
    text-align: center;
    padding: 6px 12px;
    min-width: 140px;
    border-left: 1px solid var(--border);
  }

  .cmp-session-name {
    font-size: 11px;
    font-weight: 600;
    color: var(--t1);
    margin-bottom: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 180px;
  }

  .cmp-row {
    border-bottom: 1px solid var(--border);
    transition: background 0.1s;
  }
  .cmp-row:hover { background: var(--bg2); }

  .cmp-metric-lbl {
    padding: 7px 12px;
    font-size: 10px;
    color: var(--t2);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    white-space: nowrap;
    background: var(--bg1);
  }

  .cmp-val {
    padding: 7px 12px;
    text-align: right;
    color: var(--t1);
    border-left: 1px solid var(--border);
    font-variant-numeric: tabular-nums;
  }
  .cmp-val.cmp-green { color: var(--green); }
  .cmp-val.cmp-red   { color: var(--red); }

  .cmp-loading { color: var(--t3); font-style: italic; }
  .cmp-na      { color: var(--t3); }

  /* Asset columns in compare */
  .cmp-assets-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .cmp-asset-col {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 140px;
  }

  .cmp-session-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .cmp-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
</style>
