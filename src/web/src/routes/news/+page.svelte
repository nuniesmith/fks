<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import Panel from '$components/ui/Panel.svelte';
  import FilterChips from '$components/ui/FilterChips.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';

  // SSE reconnect interval (ms)
  const SSE_RECONNECT_MS = 5_000;

  // ─── Types ──────────────────────────────────────────────────────────
  interface NewsArticle {
    id: number;
    headline: string;
    published_at: string;
    source: string;
    sentiment: string | null;
    compound: number | null;
    body_preview: string | null;
    assets: { symbol: string; score: number; match: string }[];
  }

  interface NewsResponse {
    articles: NewsArticle[];
    total?: number;
    limit?: number;
    offset?: number;
  }

  interface WhaleAlert {
    hash?: string;
    chain?: string;
    from_owner?: string;
    to_owner?: string;
    symbol?: string;
    amount?: number;
    usd_value?: number;
    timestamp?: string;
    transaction_type?: string;
    from_address?: string;
    to_address?: string;
  }

  interface WhaleResponse {
    alerts: WhaleAlert[];
    total: number;
  }

  interface SymbolSentiment {
    symbol: string;
    positive: number;
    negative: number;
    neutral: number;
    total: number;
  }

  // ─── State ──────────────────────────────────────────────────────────
  let sentimentFilter = $state('all');

  // ─── Live SSE State ─────────────────────────────────────────────────
  let liveEnabled    = $state(false);
  let liveSymbol     = $state('MGC');
  let liveConnected  = $state(false);
  let liveError      = $state('');
  let liveArticles   = $state<NewsArticle[]>([]);

  let _liveEs: EventSource | null = null;
  let _liveTimer: ReturnType<typeof setTimeout> | null = null;

  function _connectSSE() {
    _disconnectSSE();
    liveError = '';
    const sym = liveSymbol.trim().toUpperCase() || 'MGC';
    const url = `/factory/news/sse/${encodeURIComponent(sym)}`;
    _liveEs = new EventSource(url);

    _liveEs.onopen = () => { liveConnected = true; liveError = ''; };

    _liveEs.addEventListener('connected', () => { liveConnected = true; });

    _liveEs.addEventListener('news', (evt: MessageEvent) => {
      try {
        const raw = JSON.parse(evt.data) as Partial<NewsArticle>;
        // Normalise — SSE event omits the assets array
        const article: NewsArticle = {
          id:           raw.id ?? Date.now(),
          headline:     raw.headline ?? '',
          published_at: raw.published_at ?? new Date().toISOString(),
          source:       raw.source ?? '',
          sentiment:    raw.sentiment ?? null,
          compound:     raw.compound ?? null,
          body_preview: raw.body_preview ?? null,
          assets:       raw.assets ?? [],
        };
        // Prepend, cap at 30 live items; deduplicate by id
        liveArticles = [article, ...liveArticles.filter(a => a.id !== article.id)].slice(0, 30);
      } catch (e) {
        console.warn('[news/sse] parse error', e);
      }
    });

    _liveEs.onerror = () => {
      liveConnected = false;
      _liveEs?.close();
      _liveEs = null;
      if (liveEnabled) {
        liveError = 'Disconnected — retrying…';
        _liveTimer = setTimeout(_connectSSE, SSE_RECONNECT_MS);
      }
    };
  }

  function _disconnectSSE() {
    if (_liveTimer) { clearTimeout(_liveTimer); _liveTimer = null; }
    _liveEs?.close();
    _liveEs = null;
    liveConnected = false;
  }

  function toggleLive() {
    liveEnabled = !liveEnabled;
    if (liveEnabled) {
      liveArticles = [];
      _connectSSE();
    } else {
      _disconnectSSE();
      liveError = '';
    }
  }

  function handleSymbolKey(e: KeyboardEvent) {
    if (e.key === 'Enter' && liveEnabled) {
      liveArticles = [];
      _connectSSE();
    }
  }

  const filterOptions = [
    { value: 'all', label: 'All' },
    { value: 'positive', label: '🟢 Positive' },
    { value: 'negative', label: '🔴 Negative' },
    { value: 'neutral', label: '🟡 Neutral' },
  ];

  // ─── Polling Stores ─────────────────────────────────────────────────
  const newsStore = createPoll<NewsResponse>('/factory/news/recent?limit=40', 60_000);
  let newsData = $derived($newsStore);
  let allArticles = $derived(newsData?.articles ?? []);

  // Merge: live articles (top, deduplicated against polled) + polled
  let mergedArticles = $derived.by(() => {
    if (liveArticles.length === 0) return allArticles;
    const polledIds = new Set(allArticles.map(a => a.id));
    const freshOnly = liveArticles.filter(a => !polledIds.has(a.id));
    return [...freshOnly, ...allArticles];
  });

  // Filtered articles based on sentiment chip
  let filteredArticles = $derived.by(() => {
    const base = mergedArticles;
    if (sentimentFilter === 'all') return base;
    return base.filter(a => (a.sentiment ?? 'neutral') === sentimentFilter);
  });

  // IDs of articles that arrived via live SSE (for NEW badge)
  let liveIds = $derived(new Set(liveArticles.map(a => a.id)));

  // Whale alerts polling
  const whaleStore = createPoll<WhaleResponse>('/api/chain/whale-feed/json?limit=8&min_usd=500000', 15_000);
  let whaleData = $derived($whaleStore);
  let whaleAlerts = $derived(whaleData?.alerts ?? []);

  // ─── Computed: Sentiment Aggregates ─────────────────────────────────
  let sentimentCounts = $derived.by(() => {
    const counts = { positive: 0, negative: 0, neutral: 0 };
    let total = 0;
    for (const a of allArticles) {
      const s = (a.sentiment ?? 'neutral') as keyof typeof counts;
      if (s in counts) {
        counts[s]++;
        total++;
      }
    }
    return { ...counts, total };
  });

  let sentimentBars = $derived.by(() => {
    const { positive, negative, neutral, total } = sentimentCounts;
    if (total === 0) return [];
    return [
      { label: 'Positive', count: positive, pct: Math.round((positive / total) * 100), color: 'green' as const },
      { label: 'Negative', count: negative, pct: Math.round((negative / total) * 100), color: 'red' as const },
      { label: 'Neutral', count: neutral, pct: Math.round((neutral / total) * 100), color: 'amber' as const },
    ];
  });

  // ─── Computed: Per-Symbol Breakdown ─────────────────────────────────
  let symbolBreakdown = $derived.by(() => {
    const map: Record<string, SymbolSentiment> = {};
    for (const a of allArticles) {
      const s = (a.sentiment ?? 'neutral') as 'positive' | 'negative' | 'neutral';
      for (const link of a.assets) {
        const sym = link.symbol.toUpperCase();
        if (!map[sym]) {
          map[sym] = { symbol: sym, positive: 0, negative: 0, neutral: 0, total: 0 };
        }
        if (s === 'positive' || s === 'negative' || s === 'neutral') {
          map[sym][s]++;
        }
        map[sym].total++;
      }
    }
    return Object.values(map)
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  });

  // ─── Helpers ────────────────────────────────────────────────────────
  function timeAgo(iso: string): string {
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

  function sentimentColor(s: string | null): 'green' | 'red' | 'amber' | 'default' {
    if (s === 'positive') return 'green';
    if (s === 'negative') return 'red';
    if (s === 'neutral') return 'amber';
    return 'default';
  }

  function sentimentLabel(s: string | null): string {
    if (s === 'positive') return '▲ POS';
    if (s === 'negative') return '▼ NEG';
    if (s === 'neutral') return '— NEU';
    return '—';
  }

  function formatUSD(val: number | undefined | null): string {
    if (val == null) return '—';
    if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
    return `$${val.toFixed(0)}`;
  }

  function formatAmount(val: number | undefined | null): string {
    if (val == null) return '';
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
    return val.toFixed(2);
  }

  function compoundBar(compound: number | null): number {
    if (compound == null) return 50;
    // compound ranges from -1 to 1, map to 0–100
    return Math.round(((compound + 1) / 2) * 100);
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    newsStore.start();
    whaleStore.start();
  });

  onDestroy(() => {
    newsStore.stop();
    whaleStore.stop();
    _disconnectSSE();
  });
</script>

<svelte:head>
  <title>News — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ════════════════════════════════════════════════════════════════════
       LEFT PANE — News Feed (65%)
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

    <Panel title="News Feed" badge="60s" noPad fill>
      {#snippet header()}
        <span class="article-count">{filteredArticles.length} articles</span>
        <FilterChips
          options={filterOptions}
          active={sentimentFilter}
          onchange={(v) => sentimentFilter = v}
        />

        <!-- Live SSE controls -->
        <div class="live-controls">
          <input
            class="live-sym-input mono"
            type="text"
            maxlength="10"
            placeholder="MGC"
            bind:value={liveSymbol}
            onkeydown={handleSymbolKey}
            disabled={liveEnabled}
            aria-label="Symbol for live news feed"
          />
          <button
            class="live-btn"
            class:live-active={liveEnabled}
            onclick={toggleLive}
            title={liveEnabled ? 'Stop live feed' : 'Start live feed'}
            aria-pressed={liveEnabled}
          >
            <span class="live-dot" class:live-dot-on={liveEnabled && liveConnected} class:live-dot-err={liveEnabled && !liveConnected}></span>
            {liveEnabled ? 'LIVE' : 'LIVE'}
          </button>
          {#if liveEnabled && liveError}
            <span class="live-err" title={liveError}>!</span>
          {/if}
        </div>
      {/snippet}
        {#if !newsData}
          <Skeleton lines={8} height="20px" />
        {:else if filteredArticles.length === 0}
          <div class="empty-state">
            {#if sentimentFilter !== 'all'}
              No {sentimentFilter} articles found
            {:else}
              No news articles available
            {/if}
          </div>
        {:else}
          {#each filteredArticles as article (article.id)}
            <div class="news-row" class:news-row-live={liveIds.has(article.id)}>
              <div class="news-header">
                {#if liveIds.has(article.id)}
                  <Badge variant="green">🔴 NEW</Badge>
                {:else}
                  <Badge variant={sentimentColor(article.sentiment)}>
                    {sentimentLabel(article.sentiment)}
                  </Badge>
                {/if}
                <span class="news-source">{article.source}</span>
                <span class="news-time">{timeAgo(article.published_at)}</span>
                {#if article.compound != null}
                  <span class="compound-val" class:pos={article.compound > 0.05} class:neg={article.compound < -0.05}>
                    {article.compound > 0 ? '+' : ''}{article.compound.toFixed(3)}
                  </span>
                {/if}
              </div>

              <div class="news-headline">{article.headline}</div>

              {#if article.body_preview}
                <div class="news-preview">{article.body_preview}</div>
              {/if}

              {#if article.assets.length > 0}
                <div class="news-assets">
                  {#each article.assets as link}
                    <span class="asset-chip">{link.symbol}</span>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        {/if}
    </Panel>

  </div>

  <!-- ════════════════════════════════════════════════════════════════════
       RIGHT PANE — Sentiment + Whales (35%)
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <!-- ── Sentiment Overview ──────────────────────────────────────────── -->
    <div style="flex:5; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Sentiment Overview" badge="live" noPad fill>
        {#if !newsData}
          <Skeleton lines={4} />
        {:else if sentimentCounts.total === 0}
          <div class="empty-state">No articles loaded yet</div>
        {:else}
          <!-- Aggregate bars -->
          <div class="sentiment-bars">
            {#each sentimentBars as bar}
              <div class="sentiment-row">
                <div class="sentiment-row-head">
                  <span class="sentiment-label">{bar.label}</span>
                  <div class="sentiment-meta">
                    <Badge variant={bar.color}>{bar.count}</Badge>
                    <span class="sentiment-pct">{bar.pct}%</span>
                  </div>
                </div>
                <ProgressBar value={bar.pct} color={bar.color} height="6px" />
              </div>
            {/each}
          </div>

          <!-- Overall sentiment indicator -->
          <div class="overall-sentiment">
            {#if sentimentCounts.positive > sentimentCounts.negative}
              <span class="overall-label bullish">▲ Overall Bullish</span>
            {:else if sentimentCounts.negative > sentimentCounts.positive}
              <span class="overall-label bearish">▼ Overall Bearish</span>
            {:else}
              <span class="overall-label neutral">— Neutral</span>
            {/if}
            <span class="overall-total">{sentimentCounts.total} articles</span>
          </div>

          <!-- Divider -->
          <div class="divider"></div>

          <!-- Per-symbol breakdown -->
          <div class="section-label">By Asset</div>
          {#if symbolBreakdown.length === 0}
            <div class="empty-state" style="font-size:11px;">No symbol data yet</div>
          {:else}
            <div class="symbol-grid">
              {#each symbolBreakdown as sym}
                <div class="symbol-row">
                  <span class="sym-name">{sym.symbol}</span>
                  <span class="sym-pos">{sym.positive > 0 ? `+${sym.positive}` : ''}</span>
                  <span class="sym-neg">{sym.negative > 0 ? `-${sym.negative}` : ''}</span>
                  <div class="sym-bar-wrap">
                    <div class="sym-bar-fill"
                         style:width="{sym.total > 0 ? Math.round((sym.positive / sym.total) * 100) : 0}%">
                    </div>
                  </div>
                  <span class="sym-total">{sym.total}</span>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
    </Panel>
    </div>

    <!-- ── Whale Alerts ───────────────────────────────────────────────── -->
    <div style="flex:5; min-height:0; display:flex; flex-direction:column;">
    <Panel title="🐋 Whale Alerts" badge="15s" noPad fill>
        {#if !whaleData}
          <Skeleton lines={5} height="18px" />
        {:else if whaleAlerts.length === 0}
          <div class="empty-state">No whale alerts</div>
        {:else}
          {#each whaleAlerts as tx, i}
            <div class="whale-row">
              <div class="whale-header">
                <span class="whale-symbol">{tx.symbol ?? tx.chain ?? '—'}</span>
                <span class="whale-amount">{formatUSD(tx.usd_value)}</span>
              </div>
              <div class="whale-detail">
                {#if tx.amount}
                  <span class="whale-qty">{formatAmount(tx.amount)} {tx.symbol ?? ''}</span>
                {/if}
                {#if tx.transaction_type}
                  <Badge variant={tx.transaction_type === 'transfer' ? 'amber' : tx.transaction_type === 'mint' ? 'green' : 'red'}>
                    {tx.transaction_type}
                  </Badge>
                {/if}
                {#if tx.chain}
                  <span class="whale-chain">{tx.chain}</span>
                {/if}
              </div>
              <div class="whale-addresses">
                {#if tx.from_owner || tx.from_address}
                  <span class="whale-addr">
                    <span class="addr-label">From:</span>
                    {tx.from_owner || (tx.from_address ? tx.from_address.slice(0, 10) + '…' : '—')}
                  </span>
                {/if}
                {#if tx.to_owner || tx.to_address}
                  <span class="whale-addr">
                    <span class="addr-label">To:</span>
                    {tx.to_owner || (tx.to_address ? tx.to_address.slice(0, 10) + '…' : '—')}
                  </span>
                {/if}
              </div>
              {#if tx.timestamp}
                <span class="whale-time">{timeAgo(tx.timestamp)}</span>
              {/if}
            </div>
          {/each}
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
    flex: 65;
    border-right: 1px solid var(--b1);
    min-width: 0;
  }

  .pane-right {
    flex: 35;
    min-width: 280px;
    max-width: 460px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .article-count {
    font-size: 9px;
    color: var(--t3);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Live SSE controls
     ═══════════════════════════════════════════════════════════════════ */
  .live-controls {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 4px;
  }

  .live-sym-input {
    width: 52px;
    padding: 2px 5px;
    font-size: 10px;
    background: var(--bg3);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t1);
    outline: none;
    text-transform: uppercase;
    transition: border-color 0.15s;
  }

  .live-sym-input:focus {
    border-color: var(--accent);
  }

  .live-sym-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .live-btn {
    all: unset;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 2px 7px;
    border-radius: var(--r);
    border: 1px solid var(--b2);
    background: var(--bg3);
    color: var(--t3);
    transition: color 0.12s, background 0.12s, border-color 0.12s;
  }

  .live-btn:hover {
    color: var(--t1);
    border-color: var(--b1);
  }

  .live-btn.live-active {
    background: rgba(255, 59, 48, 0.08);
    border-color: rgba(255, 59, 48, 0.3);
    color: var(--red);
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--t3);
    flex-shrink: 0;
  }

  .live-dot.live-dot-on {
    background: var(--green);
    box-shadow: 0 0 4px var(--green);
    animation: livePulse 2s ease-in-out infinite;
  }

  .live-dot.live-dot-err {
    background: var(--red);
  }

  @keyframes livePulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }

  .live-err {
    font-size: 10px;
    font-weight: 700;
    color: var(--red);
    cursor: default;
    line-height: 1;
  }

  /* Live articles flash border */
  .news-row-live {
    border-left: 2px solid var(--green);
    background: rgba(52, 199, 89, 0.04);
    animation: liveFlash 0.6s ease-out;
  }

  @keyframes liveFlash {
    from { background: rgba(52, 199, 89, 0.18); }
    to   { background: rgba(52, 199, 89, 0.04); }
  }

  .empty-state {
    padding: 24px 16px;
    text-align: center;
    color: var(--t3);
    font-size: 12px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     News feed rows
     ═══════════════════════════════════════════════════════════════════ */
  .news-row {
    padding: 8px 12px;
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s;
  }

  .news-row:hover {
    background: var(--bg2);
  }

  .news-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }

  .news-source {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .news-time {
    font-size: 9px;
    color: var(--t3);
    margin-left: auto;
  }

  .compound-val {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
  }

  .compound-val.pos { color: var(--green); }
  .compound-val.neg { color: var(--red); }

  .news-headline {
    font-size: 12px;
    font-weight: 600;
    color: var(--t1);
    line-height: 1.35;
    margin-bottom: 3px;
  }

  .news-preview {
    font-size: 10px;
    color: var(--t3);
    line-height: 1.4;
    margin-bottom: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .news-assets {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin-top: 4px;
  }

  .asset-chip {
    display: inline-flex;
    align-items: center;
    padding: 1px 5px;
    border-radius: var(--r);
    font-size: 9px;
    font-weight: 600;
    font-family: var(--font-mono, monospace);
    background: var(--accent-dim, rgba(0, 229, 255, 0.08));
    color: var(--accent, var(--cyan));
    border: 1px solid var(--accent-brd, rgba(0, 229, 255, 0.15));
    letter-spacing: 0.03em;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Sentiment overview
     ═══════════════════════════════════════════════════════════════════ */
  .sentiment-bars {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px 12px;
  }

  .sentiment-row {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .sentiment-row-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .sentiment-label {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    color: var(--t2);
  }

  .sentiment-meta {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .sentiment-pct {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--t2);
  }

  .overall-sentiment {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background: var(--bg2);
    border-radius: var(--r);
    margin: 4px 12px;
  }

  .overall-label {
    font-size: 11px;
    font-weight: 700;
    font-family: var(--font-mono, monospace);
  }

  .overall-label.bullish { color: var(--green); }
  .overall-label.bearish { color: var(--red); }
  .overall-label.neutral { color: var(--amber); }

  .overall-total {
    font-size: 9px;
    color: var(--t3);
  }

  .divider {
    border-top: 1px solid var(--b1);
    margin: 8px 12px;
  }

  .section-label {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0 12px 6px;
  }

  /* ── Symbol breakdown ────────────────────────────────────────────── */
  .symbol-grid {
    padding: 0 12px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .symbol-row {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 0;
  }

  .sym-name {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    font-weight: 600;
    color: var(--t1);
    width: 52px;
    text-transform: uppercase;
    flex-shrink: 0;
  }

  .sym-pos {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--green);
    width: 30px;
    text-align: right;
    flex-shrink: 0;
  }

  .sym-neg {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--red);
    width: 30px;
    text-align: right;
    flex-shrink: 0;
  }

  .sym-bar-wrap {
    flex: 1;
    height: 5px;
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    overflow: hidden;
    margin: 0 4px;
  }

  .sym-bar-fill {
    height: 100%;
    background: var(--green);
    border-radius: var(--r);
    transition: width 0.3s ease;
  }

  .sym-total {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
    width: 20px;
    text-align: right;
    flex-shrink: 0;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Whale alerts
     ═══════════════════════════════════════════════════════════════════ */
  .whale-row {
    padding: 8px 12px;
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s;
  }

  .whale-row:hover {
    background: var(--bg2);
  }

  .whale-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 3px;
  }

  .whale-symbol {
    font-size: 12px;
    font-family: var(--font-mono, monospace);
    font-weight: 700;
    color: var(--t1);
    text-transform: uppercase;
  }

  .whale-amount {
    font-size: 13px;
    font-family: var(--font-mono, monospace);
    font-weight: 700;
    color: var(--amber);
  }

  .whale-detail {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 3px;
  }

  .whale-qty {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--t2);
  }

  .whale-chain {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .whale-addresses {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 2px;
  }

  .whale-addr {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
  }

  .addr-label {
    color: var(--t3);
    font-weight: 600;
    margin-right: 2px;
  }

  .whale-time {
    font-size: 8px;
    color: var(--t3);
    margin-top: 2px;
    display: block;
  }
</style>
