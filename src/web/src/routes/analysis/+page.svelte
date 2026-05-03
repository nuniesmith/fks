<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createSSE } from '$stores/sse';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import FilterChips from '$components/ui/FilterChips.svelte';
  import InnerTabs from '$components/ui/InnerTabs.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import MiniChart from '$components/ui/MiniChart.svelte';
  import Panel from '$components/ui/Panel.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface ScoredAsset {
    symbol: string;
    name: string;
    exchange: string;
    asset_class: string;
    price: number | null;
    score: number | null;
    cnn_signal: string | null;
    ruby_signal: string | null;
    age: string;
    analyzed: boolean;
  }

  interface ScoresResponse {
    assets: ScoredAsset[];
    total: number;
  }

  interface RegimeEntry {
    symbol: string;
    regime: string;
    confidence: string;
    css_class: string;
    has_data: boolean;
  }

  interface RegimeResponse {
    regimes: RegimeEntry[];
    total: number;
    active: number;
    timestamp: string;
  }

  interface BriefingResponse {
    status: string;
    briefing: string;
    length: number;
    generated_at: string;
  }

  interface CorrelationResponse {
    symbols: string[];
    labels: string[];
    matrix: (number | null)[][];
    computed_at: string;
    days: number;
    errors: string[];
  }

  interface ScannerResult {
    symbol: string;
    score: number;
    direction: string;
    strategy: string;
    asset_class: string;
    tag: string;
    color_class: string;
  }

  interface ScannerResponse {
    results: ScannerResult[];
    total: number;
    threshold: number;
    scanned_at: string;
    status?: string;
  }

  interface ChecklistItem {
    id: string;
    text: string;
    category: string;
    checked: boolean;
  }

  interface ChecklistResponse {
    date: string;
    items: ChecklistItem[];
    completed: number;
    total: number;
  }

  // ─── Indicator Lab types ─────────────────────────────────────────
  interface IndicatorParam {
    name: string;
    label: string;
    type: 'int' | 'float';
    default: number;
    min: number;
    max: number;
    step?: number;
  }

  interface IndicatorEntry {
    key: string;
    display_name: string;
    short_name: string;
    category: string;
    output_keys: string[];
    output_labels?: Record<string, string>;
    is_overlay: boolean;
    description: string;
    params: IndicatorParam[];
    color: string;
    reference_lines?: { value: number; label: string; color: string }[];
  }

  interface IndicatorCategory {
    id: string;
    label: string;
    color: string;
    icon: string;
  }

  interface IndCatalogResponse {
    indicators: IndicatorEntry[];
    categories: IndicatorCategory[];
    defaults: { active_keys: string[]; interval: string; days_back: number };
  }

  interface IndComputeResult {
    symbol: string;
    interval: string;
    bars_count: number;
    indicators: Record<string, { time: number; value: number }[]>;
  }

  // ─── Strategy Lab types ──────────────────────────────────────────
  interface StrategyResult {
    symbol: string;
    score: number;
    direction: string;
    strategy: string;
    asset_class: string;
    tag: string;
    color_class: string;
  }

  interface RotationAsset {
    symbol: string;
    name: string;
    class: string;
    ret_7d: number | null;
    ret_30d: number | null;
    ret_90d: number | null;
    error?: string;
  }

  interface RotationResponse {
    assets: RotationAsset[];
    computed_at: string;
    errors: string[];
  }

  // ─── State ──────────────────────────────────────────────────────────

  // Left pane: scoring table
  let assetFilter = $state('all');
  const assetFilterOptions = [
    { value: 'all', label: 'All' },
    { value: 'futures', label: '⚡ Futures' },
    { value: 'crypto', label: '🔶 Crypto' },
  ];

  // Right pane tabs
  let activeRightTab = $state('briefing');
  const rightTabs = [
    { id: 'briefing', label: '📋 Briefing' },
    { id: 'correlation', label: '⬡ Correlation' },
    { id: 'scanner', label: '🔍 Scanner' },
    { id: 'checklist', label: '✅ Checklist' },
    { id: 'rotation', label: '🔄 Rotation' },
    { id: 'indicators', label: '🔬 Lab' },
    { id: 'strategy', label: '🎯 Strategy' },
  ];

  // ─── Indicator Lab state ─────────────────────────────────────────
  let indSymbol = $state('');
  let indInterval = $state('5m');
  let indCatalog = $state<IndicatorEntry[] | null>(null);
  let indCategories = $state<IndicatorCategory[]>([]);
  let indCatalogLoading = $state(false);
  let indActive = $state(new Set<string>(['ema9', 'ema21', 'rsi']));
  let indData = $state<IndComputeResult | null>(null);
  let indLoading = $state(false);
  let indLoaded = $state(false);

  // ─── Strategy Lab state ──────────────────────────────────────────
  let stratSymbol = $state('');
  let stratLoading = $state(false);
  let stratLoaded = $state(false);
  let stratResult = $state<StrategyResult | null>(null);
  let stratScoreAsset = $derived.by(() => {
    const sym = stratSymbol.toUpperCase();
    return assets.find(a => a.symbol === sym) ?? null;
  });

  // Briefing state
  let briefingText = $state('');
  let briefingLoading = $state(false);
  let briefingStreaming = $state(false);
  let briefingStreamText = $state('');
  let briefingSSE: ReturnType<typeof createSSE> | null = null;

  // Regime state
  let regimeData = $state<RegimeEntry[]>([]);
  let regimeLoading = $state(true);

  // Correlation state
  let corrSymbols = $state('MES,MNQ,MGC,MYM,M2K');
  let corrDays = $state(30);
  let corrData = $state<CorrelationResponse | null>(null);
  let corrLoading = $state(false);
  let corrLoaded = $state(false);

  // Scanner state
  let scannerFilter = $state('all');
  const scannerFilterOptions = [
    { value: 'all', label: 'All' },
    { value: 'futures', label: 'Futures' },
    { value: 'crypto', label: 'Crypto' },
    { value: 'bullish', label: 'Bull' },
    { value: 'bearish', label: 'Bear' },
  ];
  let scannerData = $state<ScannerResult[]>([]);
  let scannerLoading = $state(false);
  let scannerLoaded = $state(false);
  let scannerTimer: ReturnType<typeof setInterval> | null = null;

  // Checklist state
  let checklistData = $state<ChecklistResponse | null>(null);
  let checklistLoading = $state(false);
  let checklistLoaded = $state(false);

  // Rotation state
  let rotationFilter = $state('all');
  const rotationFilterOptions = [
    { value: 'all', label: 'All' },
    { value: 'equity', label: 'Equity' },
    { value: 'commodity', label: 'Cmdty' },
    { value: 'crypto', label: 'Crypto' },
  ];
  let rotationData = $state<RotationAsset[]>([]);
  let rotationLoading = $state(false);
  let rotationLoaded = $state(false);

  // ─── Polling stores ─────────────────────────────────────────────────
  const scoresStore = createPoll<ScoresResponse>('/api/pipeline/scores/json', 30_000);
  let scoresRaw = $derived($scoresStore);
  let assets = $derived(scoresRaw?.assets ?? []);

  let filteredAssets = $derived.by(() => {
    if (assetFilter === 'all') return assets;
    return assets.filter(a => a.asset_class === assetFilter);
  });

  let focusSymbol = $derived.by(() => {
    const analyzed = assets.filter(a => a.analyzed && a.score != null);
    if (!analyzed.length) return assets.length > 0 ? assets[0].symbol : 'MGC';
    analyzed.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    return analyzed[0].symbol;
  });

  // ─── Helpers ────────────────────────────────────────────────────────

  function fmtPrice(price: number | null): string {
    if (price == null) return '—';
    if (price >= 1000) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toFixed(4);
    return price.toFixed(6);
  }

  function scoreColor(score: number | null): string {
    if (score == null) return 'var(--t3)';
    if (score >= 60) return 'var(--green)';
    if (score >= 40) return 'var(--amber)';
    return 'var(--red)';
  }

  function signalVariant(signal: string | null): 'green' | 'red' | 'default' {
    if (!signal) return 'default';
    const s = signal.toUpperCase();
    if (['BULL', 'LONG', 'BUY'].includes(s)) return 'green';
    if (['BEAR', 'SHORT', 'SELL'].includes(s)) return 'red';
    return 'default';
  }

  function signalLabel(signal: string | null): string {
    if (!signal) return '—';
    const s = signal.toUpperCase();
    if (['BULL', 'LONG', 'BUY'].includes(s)) return '▲ BULL';
    if (['BEAR', 'SHORT', 'SELL'].includes(s)) return '▼ BEAR';
    return s;
  }

  function corrColor(v: number | null): string {
    if (v == null) return 'var(--t3)';
    if (v >= 0.7) return '#00c853';
    if (v >= 0.4) return '#66bb6a';
    if (v >= 0.1) return '#a5d6a7';
    if (v >= -0.1) return 'var(--t3)';
    if (v >= -0.4) return '#ef9a9a';
    if (v >= -0.7) return '#e53935';
    return '#b71c1c';
  }

  function retColor(v: number | null): string {
    if (v == null) return 'var(--t3)';
    if (v > 0.05) return 'var(--green)';
    if (v > 0.01) return '#66bb6a';
    if (v > 0) return '#a5d6a7';
    if (v > -0.01) return '#ef9a9a';
    if (v > -0.05) return '#e53935';
    return '#b71c1c';
  }

  function fmtReturn(v: number | null): string {
    if (v == null) return '—';
    const pct = (v * 100).toFixed(2);
    return (v >= 0 ? '+' : '') + pct + '%';
  }

  function regimeDotColor(cssClass: string): string {
    if (cssClass === 'info') return 'var(--green)';
    if (cssClass === 'warn') return 'var(--amber)';
    if (cssClass === 'neg') return 'var(--red)';
    return 'var(--t3)';
  }

  const categoryLabels: Record<string, string> = {
    macro: '🌍 Macro',
    levels: '📊 Levels',
    events: '📅 Events',
    risk: '🛡️ Risk',
    plan: '📋 Plan',
  };

  const classColors: Record<string, string> = {
    equity: 'var(--cyan)',
    commodity: 'var(--amber)',
    bonds: 'var(--purple)',
    fx: 'var(--t1)',
    crypto: 'var(--green)',
  };

  // ─── Data Fetching ──────────────────────────────────────────────────

  async function loadBriefing() {
    briefingLoading = true;
    try {
      const data = await api.get<BriefingResponse>('/api/grok/briefing');
      if (data.status === 'ok' && data.briefing) {
        briefingText = data.briefing;
      } else {
        briefingText = 'No briefing available yet. Run the morning pipeline or click Stream.';
      }
    } catch {
      briefingText = 'Failed to load briefing.';
    } finally {
      briefingLoading = false;
    }
  }

  function streamBriefing() {
    if (briefingSSE) {
      briefingSSE.disconnect();
      briefingSSE = null;
    }
    briefingStreaming = true;
    briefingStreamText = '';

    const source = new EventSource('/sse/grok/briefing');
    source.onmessage = (evt) => {
      if (evt.data === '[DONE]') {
        source.close();
        briefingStreaming = false;
        briefingText = briefingStreamText;
        return;
      }
      try {
        const parsed = JSON.parse(evt.data);
        if (parsed.text) briefingStreamText += parsed.text;
      } catch {
        briefingStreamText += evt.data;
      }
    };
    source.onerror = () => {
      source.close();
      briefingStreaming = false;
      if (briefingStreamText) {
        briefingText = briefingStreamText;
      }
    };
  }

  async function loadRegime() {
    regimeLoading = true;
    try {
      const data = await api.get<RegimeResponse>('/api/cnn/regime/json');
      regimeData = data.regimes ?? [];
    } catch {
      regimeData = [];
    } finally {
      regimeLoading = false;
    }
  }

  async function loadCorrelation(symbolsOverride?: string) {
    if (symbolsOverride) corrSymbols = symbolsOverride;
    corrLoading = true;
    corrLoaded = true;
    try {
      const data = await api.get<CorrelationResponse>(
        `/api/analysis/correlation?symbols=${encodeURIComponent(corrSymbols)}&days=${corrDays}`
      );
      corrData = data;
    } catch {
      corrData = null;
    } finally {
      corrLoading = false;
    }
  }

  async function loadScanner(filter?: string) {
    if (filter !== undefined) scannerFilter = filter;
    scannerLoading = true;
    scannerLoaded = true;
    try {
      const data = await api.get<ScannerResponse>(
        `/api/analysis/scanner?threshold=0.3&filter=${scannerFilter}&limit=20`
      );
      scannerData = data.results ?? [];
    } catch {
      scannerData = [];
    } finally {
      scannerLoading = false;
    }
  }

  async function loadChecklist() {
    checklistLoading = true;
    checklistLoaded = true;
    try {
      const data = await api.get<ChecklistResponse>('/api/analysis/checklist');
      checklistData = data;
    } catch {
      checklistData = null;
    } finally {
      checklistLoading = false;
    }
  }

  async function toggleChecklistItem(itemId: string) {
    try {
      await api.post(`/api/analysis/checklist/items/${itemId}/toggle`);
      await loadChecklist();
    } catch {
      console.warn('Checklist toggle failed');
    }
  }

  async function loadRotation() {
    rotationLoading = true;
    rotationLoaded = true;
    try {
      const data = await api.get<RotationResponse>('/api/analysis/rotation');
      rotationData = data.assets ?? [];
    } catch {
      rotationData = [];
    } finally {
      rotationLoading = false;
    }
  }

  let filteredRotation = $derived.by(() => {
    if (rotationFilter === 'all') return rotationData;
    return rotationData.filter(a => a.class === rotationFilter);
  });

  let sortedRotation = $derived.by(() => {
    return [...filteredRotation].sort((a, b) => {
      const ar = a.ret_30d ?? -Infinity;
      const br = b.ret_30d ?? -Infinity;
      return br - ar;
    });
  });

  // ─── Indicator Lab functions ─────────────────────────────────────
  async function loadIndicatorCatalog() {
    if (indCatalog !== null) return;
    indCatalogLoading = true;
    try {
      const data = await api.get<IndCatalogResponse>('/api/indicators/catalog');
      indCatalog = data.indicators ?? [];
      indCategories = data.categories ?? [];
      if (data.defaults?.active_keys?.length) {
        indActive = new Set(data.defaults.active_keys);
      }
      if (data.defaults?.interval) {
        indInterval = data.defaults.interval;
      }
    } catch {
      indCatalog = [];
    } finally {
      indCatalogLoading = false;
    }
  }

  function toggleIndicator(key: string) {
    const next = new Set(indActive);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    indActive = next;
  }

  async function computeIndicators() {
    if (!indSymbol) return;
    const keys = [...indActive].join(',');
    if (!keys) return;
    indLoading = true;
    indLoaded = true;
    try {
      const data = await api.get<IndComputeResult>(
        `/api/indicators/compute/${encodeURIComponent(indSymbol)}?interval=${indInterval}&days_back=5&keys=${encodeURIComponent(keys)}`
      );
      indData = data;
    } catch {
      indData = null;
    } finally {
      indLoading = false;
    }
  }

  function indLatestValue(key: string): number | null {
    const series = indData?.indicators?.[key];
    if (!series || series.length === 0) return null;
    return series[series.length - 1]?.value ?? null;
  }

  function indTrend(key: string): 'up' | 'down' | 'flat' {
    const series = indData?.indicators?.[key];
    if (!series || series.length < 2) return 'flat';
    const last = series[series.length - 1]?.value;
    const prev = series[series.length - 2]?.value;
    if (last == null || prev == null) return 'flat';
    if (last > prev) return 'up';
    if (last < prev) return 'down';
    return 'flat';
  }

  function fmtIndValue(key: string, v: number | null): string {
    if (v == null) return '—';
    if (['rsi', 'schaff', 'chop'].includes(key)) return v.toFixed(1);
    if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (Math.abs(v) >= 1) return v.toFixed(4);
    return v.toFixed(6);
  }

  function indTrendIcon(trend: 'up' | 'down' | 'flat'): string {
    if (trend === 'up') return '↑';
    if (trend === 'down') return '↓';
    return '–';
  }

  function indTrendColor(trend: 'up' | 'down' | 'flat'): string {
    if (trend === 'up') return 'var(--green)';
    if (trend === 'down') return 'var(--red)';
    return 'var(--t3)';
  }

  // ─── Strategy Lab functions ──────────────────────────────────────
  async function loadStrategyForSymbol() {
    const sym = stratSymbol.toUpperCase();
    if (!sym) return;
    stratLoading = true;
    stratLoaded = true;
    stratResult = null;
    try {
      const data = await api.get<{ results: StrategyResult[] }>(
        `/api/analysis/scanner?threshold=0&limit=50&filter=all`
      );
      stratResult = (data.results ?? []).find(r => r.symbol === sym) ?? null;
    } catch {
      stratResult = null;
    } finally {
      stratLoading = false;
    }
  }

  // ─── Tab switch handler (lazy loading) ──────────────────────────────
  function onRightTabChange(tabId: string) {
    activeRightTab = tabId;
    if (tabId === 'correlation' && !corrLoaded) loadCorrelation();
    if (tabId === 'scanner' && !scannerLoaded) loadScanner();
    if (tabId === 'checklist' && !checklistLoaded) loadChecklist();
    if (tabId === 'rotation' && !rotationLoaded) loadRotation();
    if (tabId === 'indicators') {
      if (!indCatalog) loadIndicatorCatalog();
      if (!indSymbol) indSymbol = focusSymbol;
    }
    if (tabId === 'strategy') {
      if (!stratSymbol) stratSymbol = focusSymbol;
      loadStrategyForSymbol();
    }
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  let regimeTimer: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    scoresStore.start();
    loadBriefing();
    loadRegime();
    regimeTimer = setInterval(loadRegime, 30_000);
  });

  onDestroy(() => {
    scoresStore.stop();
    if (regimeTimer) { clearInterval(regimeTimer); regimeTimer = null; }
    if (scannerTimer) { clearInterval(scannerTimer); scannerTimer = null; }
    if (briefingSSE) { briefingSSE.disconnect(); briefingSSE = null; }
  });

  // Auto-refresh scanner when active
  $effect(() => {
    if (activeRightTab === 'scanner' && scannerLoaded) {
      if (!scannerTimer) {
        scannerTimer = setInterval(() => loadScanner(), 30_000);
      }
    } else {
      if (scannerTimer) {
        clearInterval(scannerTimer);
        scannerTimer = null;
      }
    }
  });
</script>

<svelte:head>
  <title>Analysis — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ═══════════════════════════════════════════════════════════════
       LEFT PANE (60%) — context-sensitive (chart in lab modes, scoring otherwise)
       ═══════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

  {#if activeRightTab === 'indicators'}
    <!-- ── Indicator Lab: full-height chart ─────────────────────── -->
    <div style="flex:1; min-height:0; display:flex; flex-direction:column;">
      <Panel title="🔬 Preview — {indSymbol || 'select symbol'}" noPad fill>
        {#snippet header()}
          <span class="dim" style="font-size:9px;">{indInterval} · 5d</span>
        {/snippet}
        <div style="position:relative; flex:1; min-height:0;">
          {#if indSymbol}
            <MiniChart symbol={indSymbol} interval={indInterval} height="100%" showToolbar={false} />
          {:else}
            <div class="empty-state" style="margin-top:48px;">Enter a symbol in the Indicators tab →</div>
          {/if}
        </div>
      </Panel>
    </div>

  {:else if activeRightTab === 'strategy'}
    <!-- ── Strategy Lab: full-height chart ──────────────────────── -->
    <div style="flex:1; min-height:0; display:flex; flex-direction:column;">
      <Panel title="🎯 Strategy — {stratSymbol || focusSymbol}" noPad fill>
        {#snippet header()}
          <span class="dim" style="font-size:9px;">5m</span>
        {/snippet}
        <div style="position:relative; flex:1; min-height:0;">
          <MiniChart symbol={stratSymbol || focusSymbol} interval="5m" height="100%" showToolbar={false} />
        </div>
      </Panel>
    </div>

  {:else}
    <!-- ── Default: Asset Scoring Panel ─────────────────────────── -->
    <div style="flex:7; min-height:0; display:flex; flex-direction:column;">
      <Panel title="Asset Scoring" badge="30s" noPad fill>
        {#snippet header()}
          <FilterChips
            options={assetFilterOptions}
            active={assetFilter}
            onchange={(v) => assetFilter = v}
          />
        {/snippet}
        {#if !scoresRaw}
          <div style="padding:16px;">
            <Skeleton lines={8} height="18px" />
          </div>
        {:else if filteredAssets.length === 0}
          <div class="empty-state">
            No assets match the selected filter.
          </div>
        {:else}
          <table class="score-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Price</th>
                <th>Score</th>
                <th>CNN</th>
                <th>Signal</th>
                <th>Age</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredAssets as asset (asset.symbol)}
                <tr
                  class="score-row"
                  class:focused={asset.symbol === focusSymbol}
                >
                  <td>
                    <div class="asset-cell">
                      <span class="asset-sym">{asset.symbol}</span>
                      <span class="asset-name">{asset.name}</span>
                    </div>
                  </td>
                  <td class="mono">{fmtPrice(asset.price)}</td>
                  <td>
                    {#if asset.score != null}
                      <div class="score-cell">
                        <div class="score-bar-track">
                          <div
                            class="score-bar-fill"
                            style="width:{Math.min(100, Math.max(0, asset.score))}%; background:{scoreColor(asset.score)};"
                          ></div>
                        </div>
                        <span class="mono" style="color:{scoreColor(asset.score)}; font-size:10px;">
                          {asset.score.toFixed(0)}
                        </span>
                      </div>
                    {:else}
                      <span class="dim">—</span>
                    {/if}
                  </td>
                  <td>
                    <Badge variant={signalVariant(asset.cnn_signal)}>
                      {signalLabel(asset.cnn_signal)}
                    </Badge>
                  </td>
                  <td>
                    <Badge variant={signalVariant(asset.ruby_signal)}>
                      {signalLabel(asset.ruby_signal)}
                    </Badge>
                  </td>
                  <td>
                    <span class="dim" style="font-size:9px;">{asset.age || '—'}</span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </Panel>
    </div>

    <!-- ── Focus Banner ────────────────────────────────────────────── -->
    <div style="flex:0 0 auto;">
      <Panel title="Focus Asset" badge="auto">
        <div class="focus-row">
          <span class="focus-symbol">{focusSymbol}</span>
          <span class="dim" style="font-size:11px;">Current focus</span>
          <a href="/trading" class="btn-go-trading">▶ Go to Trading</a>
        </div>
      </Panel>
    </div>

  {/if}
  </div><!-- /.pane-left -->

  <!-- ═══════════════════════════════════════════════════════════════
       RIGHT PANE (40%) — Inner Tabs
       ═══════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <div style="padding:5px 10px 0;">
      <InnerTabs
        tabs={rightTabs}
        active={activeRightTab}
        onchange={onRightTabChange}
      />
    </div>

    <!-- ── Tab: Briefing ───────────────────────────────────────────── -->
    {#if activeRightTab === 'briefing'}
      <div class="tab-content" style="display:flex; flex-direction:column; gap:0;">

        <!-- AI Briefing sub-panel -->
        <div style="flex:6; min-height:0; display:flex; flex-direction:column;">
          <Panel title="AI Briefing" fill>
            {#snippet header()}
              <button class="btn-ghost" onclick={() => loadBriefing()}>📋 Cached</button>
              <button class="btn-primary" onclick={() => streamBriefing()}>▶ Stream</button>
            {/snippet}
            <div class="briefing-body">
              {#if briefingStreaming}
                <pre class="briefing-text">{briefingStreamText}<span class="cursor-blink">▌</span></pre>
              {:else if briefingLoading}
                <Skeleton lines={6} height="12px" />
              {:else}
                <pre class="briefing-text">{briefingText}</pre>
              {/if}
            </div>
          </Panel>
        </div>

        <!-- Regime Overview sub-panel -->
        <div style="flex:4; min-height:0; display:flex; flex-direction:column;">
          <Panel title="Regime Overview" badge="30s" fill>
            {#if regimeLoading && regimeData.length === 0}
              <Skeleton lines={3} height="24px" />
            {:else if regimeData.length === 0}
              <div class="empty-state">⏳ Waiting for HMM pipeline…</div>
            {:else}
              <div class="regime-header">
                <span class="dim" style="font-size:9px;">
                  {regimeData.filter(r => r.has_data).length}/{regimeData.length} symbols
                </span>
              </div>
              <div class="regime-grid">
                {#each regimeData as r (r.symbol)}
                  <div class="regime-card" class:regime-inactive={!r.has_data}>
                    {#if r.has_data}
                      <div class="regime-card-head">
                        <span class="regime-dot" style="color:{regimeDotColor(r.css_class)};">●</span>
                        <span class="mono dim" style="font-size:10px;">{r.symbol}</span>
                      </div>
                      <div class="regime-label {r.css_class}">{r.regime}</div>
                      <div class="dim" style="font-size:9px;">HMM {r.confidence}</div>
                    {:else}
                      <div class="mono dim" style="font-size:10px;">{r.symbol}</div>
                      <div class="dim" style="font-size:10px;">—</div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </Panel>
        </div>

      </div>
    {/if}

    <!-- ── Tab: Correlation ────────────────────────────────────────── -->
    {#if activeRightTab === 'correlation'}
      <div class="tab-content">
        <Panel title="Correlation Matrix" noPad fill>
          {#snippet header()}
            <div class="corr-presets">
              <button class="btn-ghost btn-xs" onclick={() => loadCorrelation('MES,MNQ,MGC,MYM,M2K')}>Futures</button>
              <button class="btn-ghost btn-xs" onclick={() => loadCorrelation('BTC,ETH,SOL,XRP,ADA,LINK')}>Crypto</button>
              <button class="btn-ghost btn-xs" onclick={() => loadCorrelation('MES,MNQ,MGC,BTC,ETH,SOL')}>Cross</button>
            </div>
            <select
              class="corr-days-select"
              bind:value={corrDays}
              onchange={() => { if (corrLoaded) loadCorrelation(); }}
            >
              <option value={14}>14d</option>
              <option value={30}>30d</option>
              <option value={60}>60d</option>
              <option value={90}>90d</option>
            </select>
            <button class="btn-ghost btn-xs" onclick={() => loadCorrelation()}>↻</button>
          {/snippet}
          {#if corrLoading}
            <div style="padding:16px;">
              <Skeleton lines={6} height="16px" />
            </div>
          {:else if !corrData || !corrData.matrix?.length}
            <div class="empty-state">
              {corrLoaded ? 'No data available — check yfinance connectivity' : 'Select a preset above or click ↻ to load'}
            </div>
          {:else}
            <div style="overflow:auto; padding:4px;">
              <table class="corr-table">
                <thead>
                  <tr>
                    <th></th>
                    {#each (corrData.labels ?? corrData.symbols) as sym}
                      <th>{sym}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each (corrData.labels ?? corrData.symbols) as rowSym, i}
                    <tr>
                      <td class="corr-row-label">{rowSym}</td>
                      {#each (corrData.labels ?? corrData.symbols) as _, j}
                        {@const v = corrData.matrix[i]?.[j] ?? null}
                        <td
                          class="corr-cell"
                          style="color:{corrColor(v)}; background:{i === j ? 'var(--bg2)' : 'transparent'};"
                        >
                          {v != null ? v.toFixed(2) : '—'}
                        </td>
                      {/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
              {#if corrData.errors?.length}
                <div class="corr-footnote">⚠ No data: {corrData.errors.join(', ')}</div>
              {/if}
              <div class="corr-footnote" style="text-align:right;">
                {corrData.days}d · {corrData.computed_at?.slice(0, 10) ?? ''}
              </div>
            </div>
          {/if}
        </Panel>
      </div>
    {/if}

    <!-- ── Tab: Scanner ────────────────────────────────────────────── -->
    {#if activeRightTab === 'scanner'}
      <div class="tab-content">
        <Panel title="Market Scanner" badge="30s" noPad fill>
          {#snippet header()}
            <FilterChips
              options={scannerFilterOptions}
              active={scannerFilter}
              onchange={(v) => loadScanner(v)}
            />
          {/snippet}
          {#if scannerLoading && scannerData.length === 0}
            <div style="padding:16px;">
              <Skeleton lines={5} height="16px" />
            </div>
          {:else if scannerData.length === 0}
            <div class="empty-state">No setups above threshold</div>
          {:else}
            <table class="scanner-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Score</th>
                  <th>Dir</th>
                  <th>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {#each scannerData as r (r.symbol)}
                  {@const color = r.color_class === 'text-green' ? 'var(--green)' : 'var(--red)'}
                  <tr>
                    <td style="font-weight:600;">{r.symbol || '—'}</td>
                    <td style="color:{color}; font-weight:600;">
                      {r.score >= 0 ? '+' : ''}{r.score.toFixed(3)}
                    </td>
                    <td style="color:{color};">{r.direction || '—'}</td>
                    <td class="dim">{r.strategy || '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </Panel>
      </div>
    {/if}

    <!-- ── Tab: Checklist ──────────────────────────────────────────── -->
    {#if activeRightTab === 'checklist'}
      <div class="tab-content">
        <Panel title="Pre-Market Checklist" badge={checklistData ? `${checklistData.completed}/${checklistData.total}` : undefined} noPad fill>
          {#snippet header()}
            <button class="btn-ghost btn-xs" onclick={() => loadChecklist()}>↻</button>
          {/snippet}
          {#if checklistLoading && !checklistData}
            <div style="padding:16px;">
              <Skeleton lines={6} height="16px" />
            </div>
          {:else if !checklistData?.items?.length}
            <div class="empty-state">No checklist items</div>
          {:else}
            {@const items = checklistData.items}
            {#each Object.keys(categoryLabels) as cat}
              {@const catItems = items.filter(i => i.category === cat)}
              {#if catItems.length > 0}
                <div class="checklist-cat">{categoryLabels[cat] ?? cat}</div>
                {#each catItems as item (item.id)}
                  <label
                    class="checklist-item"
                    style="opacity:{item.checked ? '0.55' : '1'};"
                  >
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onchange={() => toggleChecklistItem(item.id)}
                      class="checklist-cb"
                    />
                    <span
                      class="checklist-text"
                      style="text-decoration:{item.checked ? 'line-through' : 'none'};"
                    >
                      {item.text}
                    </span>
                  </label>
                {/each}
              {/if}
            {/each}
          {/if}
        </Panel>
      </div>
    {/if}

    <!-- ── Tab: Rotation ───────────────────────────────────────────── -->
    {#if activeRightTab === 'rotation'}
      <div class="tab-content">
        <Panel title="Sector Rotation" noPad fill>
          {#snippet header()}
            <FilterChips
              options={rotationFilterOptions}
              active={rotationFilter}
              onchange={(v) => rotationFilter = v}
            />
            <button class="btn-ghost btn-xs" onclick={() => loadRotation()}>↻</button>
          {/snippet}
          {#if rotationLoading && rotationData.length === 0}
            <div style="padding:16px;">
              <Skeleton lines={8} height="16px" />
            </div>
          {:else if sortedRotation.length === 0}
            <div class="empty-state">
              {rotationLoaded ? 'No data available' : 'Click ↻ to load rotation data'}
            </div>
          {:else}
            <table class="rotation-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th style="text-align:right;">7D</th>
                  <th style="text-align:right;">30D</th>
                  <th style="text-align:right;">90D</th>
                </tr>
              </thead>
              <tbody>
                {#each sortedRotation as asset (asset.symbol)}
                  <tr style="opacity:{asset.error ? '0.45' : '1'};">
                    <td>
                      <span style="font-weight:600;">{asset.symbol}</span>
                      {' '}
                      <span class="dim" style="font-size:9px; color:{classColors[asset.class] ?? 'var(--t3)'};">
                        {asset.name}
                      </span>
                    </td>
                    <td style="text-align:right; color:{retColor(asset.ret_7d)}; font-weight:600;">
                      {fmtReturn(asset.ret_7d)}
                    </td>
                    <td style="text-align:right; color:{retColor(asset.ret_30d)}; font-weight:600;">
                      {fmtReturn(asset.ret_30d)}
                    </td>
                    <td style="text-align:right; color:{retColor(asset.ret_90d)};">
                      {fmtReturn(asset.ret_90d)}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </Panel>
      </div>
    {/if}

    <!-- ── Tab: Indicator Lab ──────────────────────────────────────── -->
    {#if activeRightTab === 'indicators'}
      <div class="tab-content">
        <Panel title="🔬 Indicator Builder" fill>
          <div class="ind-body-layout">

            <!-- Controls row -->
            <div class="ind-controls">
              <input
                class="ind-sym-input"
                bind:value={indSymbol}
                placeholder="Symbol…"
                aria-label="Symbol"
                onkeydown={(e) => { if (e.key === 'Enter') computeIndicators(); }}
              />
              <select class="ind-interval-select" bind:value={indInterval}>
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1H</option>
                <option value="4h">4H</option>
                <option value="1d">1D</option>
              </select>
              <button
                class="btn-primary"
                onclick={() => computeIndicators()}
                disabled={!indSymbol || indActive.size === 0}
              >
                {indLoading ? '…' : '↻ Compute'}
              </button>
            </div>

            <!-- Indicator Catalog -->
            {#if indCatalogLoading}
              <Skeleton lines={3} height="24px" />
            {:else if indCatalog === null}
              <div class="empty-state">Loading catalog…</div>
            {:else}
              {#each indCategories as cat (cat.id)}
                {@const catItems = indCatalog.filter(i => i.category === cat.id)}
                {#if catItems.length > 0}
                  <div>
                    <div class="ind-cat-label" style="color:{cat.color};">{cat.icon} {cat.label}</div>
                    <div class="ind-chips">
                      {#each catItems as ind (ind.key)}
                        <button
                          class="ind-chip"
                          class:active={indActive.has(ind.key)}
                          style={indActive.has(ind.key)
                            ? `background:${ind.color}; border-color:${ind.color}; color:var(--bg0);`
                            : `border-color:var(--b2); color:var(--t2);`}
                          onclick={() => toggleIndicator(ind.key)}
                          title={ind.description}
                          aria-pressed={indActive.has(ind.key)}
                        >
                          {ind.short_name}
                        </button>
                      {/each}
                    </div>
                  </div>
                {/if}
              {/each}
            {/if}

            <!-- Results table -->
            <div class="ind-results-section">
              {#if !indLoaded}
                <div class="empty-state">Pick indicators then click ↻ Compute</div>
              {:else if indLoading}
                <Skeleton lines={4} height="20px" />
              {:else if !indData || indData.bars_count === 0}
                <div class="empty-state">No bar data for {indData?.symbol ?? indSymbol}</div>
              {:else}
                <div class="ind-results-header">
                  <span class="dim" style="font-size:9px;">{indData.symbol} · {indData.interval} · {indData.bars_count} bars</span>
                </div>
                <table class="ind-table">
                  <thead>
                    <tr>
                      <th>Indicator</th>
                      <th style="text-align:right;">Value</th>
                      <th style="text-align:center;">Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each (indCatalog ?? []).filter(i => indActive.has(i.key)) as ind (ind.key)}
                      {#if ind.output_keys.length === 1}
                        {@const key = ind.output_keys[0]}
                        {@const val = indLatestValue(key)}
                        {@const trend = indTrend(key)}
                        <tr>
                          <td>
                            <span class="ind-name-dot" style="color:{ind.color};">●</span>
                            {ind.short_name}
                          </td>
                          <td class="mono" style="text-align:right; color:{ind.color};">{fmtIndValue(key, val)}</td>
                          <td style="text-align:center; color:{indTrendColor(trend)}; font-weight:700;">{indTrendIcon(trend)}</td>
                        </tr>
                      {:else}
                        <!-- Multi-output indicator (MACD, BBands) -->
                        <tr class="ind-group-header">
                          <td colspan="3">
                            <span class="ind-name-dot" style="color:{ind.color};">●</span>
                            {ind.display_name}
                          </td>
                        </tr>
                        {#each ind.output_keys as key (key)}
                          {@const val = indLatestValue(key)}
                          {@const trend = indTrend(key)}
                          <tr class="ind-sub-row">
                            <td class="dim" style="padding-left:18px; font-size:9px;">
                              {ind.output_labels?.[key] ?? key}
                            </td>
                            <td class="mono" style="text-align:right; color:var(--t1); font-size:10px;">{fmtIndValue(key, val)}</td>
                            <td style="text-align:center; color:{indTrendColor(trend)}; font-size:10px;">{indTrendIcon(trend)}</td>
                          </tr>
                        {/each}
                      {/if}
                    {/each}
                  </tbody>
                </table>
              {/if}
            </div>

            <!-- Footer link -->
            {#if indSymbol}
              <div style="text-align:right; padding-top:4px;">
                <a href="/charts?symbol={encodeURIComponent(indSymbol)}" class="ind-chart-link">
                  🔗 View full chart →
                </a>
              </div>
            {/if}

          </div>
        </Panel>
      </div>
    {/if}

    <!-- ── Tab: Strategy Lab ───────────────────────────────────────── -->
    {#if activeRightTab === 'strategy'}
      <div class="tab-content">
        <Panel title="🎯 Strategy Lab" fill>
          <div class="strat-body-layout">

            <!-- Symbol + Analyze row -->
            <div class="ind-controls">
              <input
                class="ind-sym-input"
                bind:value={stratSymbol}
                placeholder="Symbol…"
                aria-label="Symbol for strategy analysis"
                onkeydown={(e) => { if (e.key === 'Enter') loadStrategyForSymbol(); }}
              />
              <button
                class="btn-primary"
                onclick={() => loadStrategyForSymbol()}
                disabled={!stratSymbol}
              >
                {stratLoading ? '…' : '⚡ Analyze'}
              </button>
            </div>

            {#if !stratLoaded}
              <div class="empty-state">Enter a symbol and click Analyze</div>
            {:else if stratLoading}
              <Skeleton lines={5} height="22px" />
            {:else}
              <!-- Score stats row -->
              {#if stratScoreAsset}
                <div class="strat-stat-row">
                  <div class="strat-stat">
                    <div class="dim" style="font-size:9px; margin-bottom:4px;">SCORE</div>
                    <div
                      class="mono"
                      style="font-size:18px; font-weight:700; color:{scoreColor(stratScoreAsset.score)};"
                    >
                      {stratScoreAsset.score?.toFixed(0) ?? '—'}
                    </div>
                  </div>
                  <div class="strat-stat">
                    <div class="dim" style="font-size:9px; margin-bottom:4px;">CNN</div>
                    <Badge variant={signalVariant(stratScoreAsset.cnn_signal)}>
                      {signalLabel(stratScoreAsset.cnn_signal)}
                    </Badge>
                  </div>
                  <div class="strat-stat">
                    <div class="dim" style="font-size:9px; margin-bottom:4px;">SIGNAL</div>
                    <Badge variant={signalVariant(stratScoreAsset.ruby_signal)}>
                      {signalLabel(stratScoreAsset.ruby_signal)}
                    </Badge>
                  </div>
                </div>

                <!-- Score bar -->
                {#if stratScoreAsset.score != null}
                  <div>
                    <div style="display:flex; justify-content:space-between; font-size:9px; margin-bottom:3px;">
                      <span class="dim">Score strength</span>
                      <span class="mono" style="color:{scoreColor(stratScoreAsset.score)};">
                        {stratScoreAsset.score.toFixed(1)} / 100
                      </span>
                    </div>
                    <div class="strat-score-bar">
                      <div
                        class="strat-score-fill"
                        style="width:{Math.min(100, Math.max(0, stratScoreAsset.score))}%; background:{scoreColor(stratScoreAsset.score)};"
                      ></div>
                    </div>
                  </div>
                {/if}
              {/if}

              <!-- Scanner result -->
              {#if stratResult}
                <div class="strat-detail-block">
                  <div class="strat-detail-row">
                    <span class="dim">Direction</span>
                    <span
                      class="mono"
                      style="color:{stratResult.color_class === 'text-green' ? 'var(--green)' : 'var(--red)'}; font-weight:600;"
                    >
                      {stratResult.direction || '—'}
                    </span>
                  </div>
                  <div class="strat-detail-row">
                    <span class="dim">Strategy</span>
                    <span class="mono" style="font-size:10px;">{stratResult.strategy || '—'}</span>
                  </div>
                  <div class="strat-detail-row">
                    <span class="dim">Scanner score</span>
                    <span
                      class="mono"
                      style="color:{stratResult.score >= 0 ? 'var(--green)' : 'var(--red)'};"
                    >
                      {stratResult.score >= 0 ? '+' : ''}{stratResult.score.toFixed(3)}
                    </span>
                  </div>
                  {#if stratResult.tag}
                    <div class="strat-detail-row">
                      <span class="dim">Tag</span>
                      <span class="mono dim" style="font-size:9px;">{stratResult.tag}</span>
                    </div>
                  {/if}
                </div>
              {:else if stratLoaded && !stratLoading}
                <div class="empty-state">
                  No scanner entry for <span class="mono">{stratSymbol.toUpperCase()}</span>.
                  <br /><span style="font-size:9px;">Run the pipeline or lower the threshold.</span>
                </div>
              {/if}

              {#if !stratScoreAsset && !stratResult && stratLoaded && !stratLoading}
                <div class="empty-state">
                  Symbol <span class="mono">{stratSymbol.toUpperCase()}</span> not found in scoring table.
                </div>
              {/if}

              <!-- Link to full analysis -->
              <div style="text-align:right; padding-top:4px;">
                <a href="/analysis" class="ind-chart-link">
                  📊 Full analysis view →
                </a>
              </div>
            {/if}

          </div>
        </Panel>
      </div>
    {/if}

  </div><!-- /.pane-right -->
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
  }

  .pane-left {
    flex: 6;
    border-right: 1px solid var(--b1);
    min-width: 0;
  }

  .pane-right {
    flex: 4;
    min-width: 300px;
    overflow-y: auto;
  }

  .tab-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    padding: 8px;
    gap: 0;
  }

  .empty-state {
    color: var(--t3);
    font-size: 11px;
    text-align: center;
    padding: 24px 0;
  }

  .dim { color: var(--t3); }
  .mono { font-family: var(--font-mono, monospace); }

  /* ═══════════════════════════════════════════════════════════════════
     Buttons
     ═══════════════════════════════════════════════════════════════════ */
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
  .btn-ghost:hover { background: var(--bg3); color: var(--t1); }

  .btn-xs { font-size: 9px; padding: 2px 6px; }

  .btn-primary {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--bg0);
    background: var(--accent);
    padding: 2px 10px;
    border-radius: var(--r);
    font-weight: 600;
    transition: opacity 0.12s;
  }
  .btn-primary:hover { opacity: 0.85; }

  .btn-go-trading {
    all: unset;
    cursor: pointer;
    font-size: 11px;
    font-family: inherit;
    color: var(--accent);
    margin-left: auto;
    padding: 2px 8px;
    border-radius: var(--r);
    transition: background 0.12s;
  }
  .btn-go-trading:hover { background: var(--bg3); }

  /* ═══════════════════════════════════════════════════════════════════
     Scoring Table
     ═══════════════════════════════════════════════════════════════════ */
  .score-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
  }

  .score-table thead th {
    padding: 4px 8px;
    text-align: left;
    color: var(--t3);
    font-weight: 500;
    font-size: 10px;
    text-transform: uppercase;
    border-bottom: 1px solid var(--b1);
    position: sticky;
    top: 0;
    background: var(--bg1);
    z-index: 1;
  }

  .score-table tbody td {
    padding: 6px 8px;
    border-bottom: 1px solid var(--b1);
  }

  .score-row { cursor: default; transition: background 0.1s; }
  .score-row:hover { background: var(--bg2); }
  .score-row.focused { background: rgba(0, 229, 255, 0.04); }

  .asset-cell {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .asset-sym { font-size: 12px; font-weight: 600; color: var(--t1); }
  .asset-name { font-size: 9px; color: var(--t3); }

  .score-cell {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .score-bar-track {
    width: 60px;
    height: 6px;
    background: var(--bg3);
    border-radius: 3px;
    overflow: hidden;
  }

  .score-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Focus Banner
     ═══════════════════════════════════════════════════════════════════ */
  .focus-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .focus-symbol {
    font-size: 18px;
    font-weight: 700;
    font-family: var(--font-mono, monospace);
    color: var(--accent);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Briefing
     ═══════════════════════════════════════════════════════════════════ */
  .briefing-body {
    overflow-y: auto;
    position: relative;
  }

  .briefing-text {
    white-space: pre-wrap;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    margin: 0;
    padding: 4px 0;
    color: var(--t1);
    line-height: 1.5;
  }

  .cursor-blink {
    animation: blink 0.8s step-end infinite;
    color: var(--accent);
  }

  @keyframes blink {
    50% { opacity: 0; }
  }

  /* ═══════════════════════════════════════════════════════════════════
     Regime
     ═══════════════════════════════════════════════════════════════════ */
  .regime-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  .regime-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .regime-card {
    background: var(--bg2);
    border-radius: 4px;
    padding: 6px 8px;
    border: 1px solid var(--b1);
  }

  .regime-inactive { opacity: 0.5; }

  .regime-card-head {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 2px;
  }

  .regime-dot { font-size: 8px; }

  .regime-label {
    font-family: var(--font-mono, monospace);
    font-size: 11px;
    font-weight: 600;
  }
  .regime-label.info { color: var(--green); }
  .regime-label.warn { color: var(--amber); }
  .regime-label.neg { color: var(--red); }

  /* ═══════════════════════════════════════════════════════════════════
     Correlation
     ═══════════════════════════════════════════════════════════════════ */
  .corr-presets {
    display: flex;
    gap: 4px;
    margin-left: 8px;
  }

  .corr-days-select {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    background: var(--bg2);
    border: 1px solid var(--b1);
    color: var(--t1);
    border-radius: 3px;
    padding: 2px 4px;
  }

  .corr-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono, monospace);
    font-size: 10px;
  }

  .corr-table thead th {
    padding: 4px 6px;
    text-align: center;
    color: var(--t3);
    font-size: 9px;
  }

  .corr-row-label {
    padding: 4px 6px;
    font-weight: 600;
    color: var(--t1);
  }

  .corr-cell {
    padding: 4px 6px;
    text-align: center;
    border-radius: 2px;
  }

  .corr-footnote {
    font-size: 9px;
    color: var(--t3);
    margin-top: 6px;
    padding: 0 4px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Scanner
     ═══════════════════════════════════════════════════════════════════ */
  .scanner-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono, monospace);
    font-size: 10px;
  }

  .scanner-table thead th {
    padding: 4px 8px;
    text-align: left;
    color: var(--t3);
    font-size: 9px;
    border-bottom: 1px solid var(--b1);
    position: sticky;
    top: 0;
    background: var(--bg1);
  }

  .scanner-table tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--b1);
    color: var(--t1);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Checklist
     ═══════════════════════════════════════════════════════════════════ */
  .checklist-cat {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 8px 12px 4px;
    margin-top: 4px;
  }

  .checklist-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 6px 12px;
    cursor: pointer;
    transition: opacity 0.15s;
    border-bottom: 1px solid var(--b1);
  }
  .checklist-item:hover { background: var(--bg2); }

  .checklist-cb {
    margin-top: 2px;
    accent-color: var(--green);
    cursor: pointer;
    flex-shrink: 0;
  }

  .checklist-text {
    font-family: var(--font-mono, monospace);
    font-size: 11px;
    color: var(--t1);
    line-height: 1.4;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Rotation
     ═══════════════════════════════════════════════════════════════════ */
  .rotation-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono, monospace);
    font-size: 10px;
  }

  .rotation-table thead th {
    padding: 4px 8px;
    text-align: left;
    color: var(--t3);
    font-size: 9px;
    border-bottom: 1px solid var(--b1);
    position: sticky;
    top: 0;
    background: var(--bg1);
  }

  .rotation-table tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--b1);
    color: var(--t1);
  }

  /* ═══════════════════════════════════════════════════════════════
     Indicator Lab
     ═══════════════════════════════════════════════════════════════ */
  .ind-body-layout {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .ind-controls {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .ind-sym-input {
    flex: 1;
    min-width: 70px;
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    color: var(--t1);
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r, 4px);
    outline: none;
    transition: border-color 0.15s;
  }
  .ind-sym-input:focus { border-color: var(--accent); }
  .ind-sym-input::placeholder { color: var(--t3); }

  .ind-interval-select {
    padding: 3px 6px;
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    background: var(--bg2);
    border: 1px solid var(--b1);
    color: var(--t1);
    border-radius: var(--r, 4px);
    cursor: pointer;
  }

  .ind-cat-label {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .ind-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }

  .ind-chip {
    all: unset;
    cursor: pointer;
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    padding: 2px 8px;
    border-radius: 3px;
    border: 1px solid var(--b2);
    color: var(--t2);
    transition: background 0.12s, color 0.12s, border-color 0.12s, transform 0.1s;
    user-select: none;
    font-weight: 500;
  }
  .ind-chip:hover { opacity: 0.85; transform: translateY(-1px); }
  .ind-chip:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .ind-results-section {
    flex: 1;
    min-height: 0;
  }

  .ind-results-header {
    margin-bottom: 6px;
  }

  .ind-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
    font-family: var(--font-mono, monospace);
  }
  .ind-table thead th {
    padding: 4px 6px;
    text-align: left;
    color: var(--t3);
    font-size: 9px;
    font-weight: 500;
    border-bottom: 1px solid var(--b1);
  }
  .ind-table tbody td {
    padding: 5px 6px;
    border-bottom: 1px solid var(--b1);
    color: var(--t1);
  }
  .ind-group-header td {
    padding: 6px 6px 2px;
    font-size: 9px;
    color: var(--t2);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background: var(--bg2);
  }
  .ind-sub-row td { background: transparent; }

  .ind-name-dot {
    font-size: 8px;
    margin-right: 3px;
  }

  .ind-chart-link {
    font-size: 9px;
    color: var(--accent);
    text-decoration: none;
    font-family: var(--font-mono, monospace);
  }
  .ind-chart-link:hover { text-decoration: underline; }

  /* ═══════════════════════════════════════════════════════════════
     Strategy Lab
     ═══════════════════════════════════════════════════════════════ */
  .strat-body-layout {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .strat-stat-row {
    display: flex;
    gap: 8px;
  }

  .strat-stat {
    flex: 1;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: 4px;
    padding: 8px 10px;
    min-width: 0;
  }

  .strat-score-bar {
    width: 100%;
    height: 6px;
    background: var(--bg3);
    border-radius: 3px;
    overflow: hidden;
  }

  .strat-score-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  .strat-detail-block {
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: 4px;
    overflow: hidden;
  }

  .strat-detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
    border-bottom: 1px solid var(--b1);
    font-size: 10px;
  }
  .strat-detail-row:last-child { border-bottom: none; }
</style>
