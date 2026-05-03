<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import FilterChips from '$components/ui/FilterChips.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import Panel from '$components/ui/Panel.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface FearGreed {
    value?: number;
    value_classification?: string;
  }

  interface GlobalMetrics {
    total_market_cap?: number;
    total_volume_24h?: number;
    btc_dominance?: number;
    eth_dominance?: number;
    active_cryptocurrencies?: number;
    total_market_cap_change_24h?: number;
  }

  interface QuoteCoin {
    symbol: string;
    name?: string;
    price?: number;
    percent_change_24h?: number;
    market_cap?: number;
  }

  interface WhaleAlert {
    hash?: string;
    chain?: string;
    from_owner?: string;
    to_owner?: string;
    from_address?: string;
    to_address?: string;
    symbol?: string;
    amount?: number;
    usd_value?: number;
    timestamp?: string;
    transaction_type?: string;
  }

  interface WhaleResponse {
    alerts: WhaleAlert[];
    total: number;
  }

  interface CorrelationEvent {
    timestamp?: string;
    whale_signal?: string;
    janus_signal?: string;
    strength?: number;
    symbol?: string;
    description?: string;
  }

  interface CorrelationResponse {
    events: CorrelationEvent[];
    count: number;
  }

  interface MempoolSnapshot {
    pending_txns?: number;
    congestion_level?: string;
    fee_tiers?: FeeTier[];
    total_fees?: number;
    fastest_fee?: number;
    half_hour_fee?: number;
    hour_fee?: number;
    economy_fee?: number;
    minimum_fee?: number;
  }

  interface FeeTier {
    label?: string;
    min_sat_vb?: number;
    max_sat_vb?: number;
    count?: number;
    percentage?: number;
  }

  interface WatchlistEntry {
    address: string;
    label: string;
    chain: string;
    added_at?: string;
  }

  // ─── State ──────────────────────────────────────────────────────────

  // CMC Macro
  let fearGreed = $state<FearGreed | null>(null);
  let globalMetrics = $state<GlobalMetrics | null>(null);
  let quotes = $state<QuoteCoin[] | null>(null);
  let macroLoading = $state(true);
  let macroTimer: ReturnType<typeof setInterval> | null = null;

  // Whale Feed
  let whaleFilter = $state('all');
  let whaleMinUsd = $state(500000);
  const whaleFilterOptions = [
    { value: 'all', label: 'All' },
    { value: 'BTC', label: 'BTC' },
    { value: 'ETH', label: 'ETH' },
    { value: 'SOL', label: 'SOL' },
  ];
  const usdThresholds = [
    { value: 500000, label: '$500K' },
    { value: 1000000, label: '$1M' },
    { value: 5000000, label: '$5M' },
    { value: 10000000, label: '$10M' },
  ];

  // Watchlist
  let watchlist = $state<WatchlistEntry[]>([]);
  let watchlistLoading = $state(true);
  let newAddr = $state('');
  let newLabel = $state('');
  let newChain = $state('ethereum');
  let addingWatchlist = $state(false);
  let removingAddr = $state<string | null>(null);
  const chainOptions = ['ethereum', 'bitcoin', 'solana', 'polygon', 'arbitrum', 'avalanche', 'bsc'];

  // ─── Whale Poll (dynamic URL based on threshold) ────────────────────
  let whaleUrl = $derived(`/api/chain/whale-feed/json?limit=12&min_usd=${whaleMinUsd}`);
  let whaleStore = $state<ReturnType<typeof createPoll<WhaleResponse>> | null>(null);
  let whaleData = $state<WhaleResponse | null>(null);

  function restartWhalePoll() {
    if (whaleStore) whaleStore.stop();
    const store = createPoll<WhaleResponse>(whaleUrl, 15_000);
    store.subscribe((val) => { whaleData = val; });
    store.start();
    whaleStore = store;
  }

  let allAlerts = $derived(whaleData?.alerts ?? []);
  let filteredAlerts = $derived.by(() => {
    if (whaleFilter === 'all') return allAlerts;
    return allAlerts.filter(a => (a.symbol ?? '').toUpperCase() === whaleFilter.toUpperCase());
  });

  // ─── Correlation Poll ───────────────────────────────────────────────
  const correlationStore = createPoll<CorrelationResponse>('/api/chain/correlation', 60_000);
  let correlationData = $derived($correlationStore);
  let correlationEvents = $derived(correlationData?.events ?? []);

  // ─── Mempool Poll ───────────────────────────────────────────────────
  const mempoolStore = createPoll<MempoolSnapshot>('/api/chain/mempool', 60_000);
  let mempoolData = $derived($mempoolStore);

  // ─── CMC Macro Fetch ────────────────────────────────────────────────
  async function fetchMacro() {
    macroLoading = fearGreed === null;
    try {
      const [fg, gm, qt] = await Promise.all([
        api.get<FearGreed>('/api/chain/cmc/fear-greed').catch(() => null),
        api.get<GlobalMetrics>('/api/chain/cmc/global').catch(() => null),
        api.get<QuoteCoin[]>('/api/chain/cmc/quotes').catch(() => null),
      ]);
      if (fg) fearGreed = fg;
      if (gm) globalMetrics = gm;
      if (qt) quotes = qt;
    } catch (e) {
      console.warn('[chains/macro] fetch error:', e);
    } finally {
      macroLoading = false;
    }
  }

  // ─── Watchlist CRUD ─────────────────────────────────────────────────
  async function loadWatchlist() {
    watchlistLoading = true;
    try {
      const res = await api.get<WatchlistEntry[]>('/api/chain/watchlist');
      watchlist = res ?? [];
    } catch (e) {
      console.warn('[chains/watchlist] load error:', e);
      watchlist = [];
    } finally {
      watchlistLoading = false;
    }
  }

  async function addToWatchlist() {
    if (!newAddr.trim() || !newLabel.trim()) return;
    addingWatchlist = true;
    try {
      await api.post('/api/chain/watchlist', {
        address: newAddr.trim(),
        label: newLabel.trim(),
        chain: newChain,
      });
      newAddr = '';
      newLabel = '';
      newChain = 'ethereum';
      await loadWatchlist();
    } catch (e) {
      console.warn('[chains/watchlist] add error:', e);
    } finally {
      addingWatchlist = false;
    }
  }

  async function removeFromWatchlist(address: string) {
    removingAddr = address;
    try {
      await api.delete(`/api/chain/watchlist/${encodeURIComponent(address)}`);
      await loadWatchlist();
    } catch (e) {
      console.warn('[chains/watchlist] remove error:', e);
    } finally {
      removingAddr = null;
    }
  }

  // ─── Helpers ────────────────────────────────────────────────────────
  function formatUSD(val: number | undefined | null): string {
    if (val == null) return '—';
    if (val >= 1_000_000_000_000) return `$${(val / 1_000_000_000_000).toFixed(2)}T`;
    if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`;
    return `$${val.toFixed(0)}`;
  }

  function formatPrice(val: number | undefined | null): string {
    if (val == null) return '—';
    if (val >= 1000) return `$${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (val >= 1) return `$${val.toFixed(2)}`;
    return `$${val.toFixed(4)}`;
  }

  function formatAmount(val: number | undefined | null): string {
    if (val == null) return '';
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
    return val.toFixed(2);
  }

  function formatPct(val: number | undefined | null): string {
    if (val == null) return '—';
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toFixed(2)}%`;
  }

  function timeAgo(iso: string | undefined): string {
    if (!iso) return '';
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

  function truncAddr(addr: string | undefined | null, len: number = 10): string {
    if (!addr) return '—';
    if (addr.length <= len + 4) return addr;
    return addr.slice(0, len) + '…' + addr.slice(-4);
  }

  function fearColor(val: number | undefined): 'green' | 'red' | 'amber' | 'cyan' {
    if (val == null) return 'cyan';
    if (val >= 70) return 'green';
    if (val >= 45) return 'amber';
    return 'red';
  }

  function strengthVariant(s: number | undefined): 'green' | 'red' | 'amber' | 'cyan' | 'default' {
    if (s == null) return 'default';
    if (s >= 0.75) return 'green';
    if (s >= 0.5) return 'amber';
    if (s >= 0.25) return 'cyan';
    return 'default';
  }

  function strengthLabel(s: number | undefined): string {
    if (s == null) return '—';
    if (s >= 0.75) return 'STRONG';
    if (s >= 0.5) return 'MOD';
    if (s >= 0.25) return 'WEAK';
    return 'LOW';
  }

  function congestionVariant(level: string | undefined): 'green' | 'red' | 'amber' | 'cyan' {
    if (!level) return 'cyan';
    const l = level.toLowerCase();
    if (l === 'low' || l === 'normal') return 'green';
    if (l === 'medium' || l === 'moderate') return 'amber';
    if (l === 'high' || l === 'critical') return 'red';
    return 'cyan';
  }

  function txTypeBadge(t: string | undefined): 'amber' | 'green' | 'red' | 'cyan' | 'default' {
    if (!t) return 'default';
    const lt = t.toLowerCase();
    if (lt === 'transfer') return 'amber';
    if (lt === 'mint') return 'green';
    if (lt === 'burn') return 'red';
    if (lt === 'exchange') return 'cyan';
    return 'default';
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    // CMC Macro strip — fetch immediately, then every 300s
    fetchMacro();
    macroTimer = setInterval(fetchMacro, 300_000);

    // Whale feed poll
    restartWhalePoll();

    // Correlation + Mempool polls
    correlationStore.start();
    mempoolStore.start();

    // Watchlist — one-time load
    loadWatchlist();
  });

  onDestroy(() => {
    if (macroTimer) clearInterval(macroTimer);
    if (whaleStore) whaleStore.stop();
    correlationStore.stop();
    mempoolStore.stop();
  });

  // Restart whale poll when threshold changes
  $effect(() => {
    // Track only whaleUrl (derived from whaleMinUsd)
    const _url = whaleUrl;
    // Read whaleStore without tracking to avoid infinite loop
    const store = untrack(() => whaleStore);
    if (store) {
      restartWhalePoll();
    }
  });
</script>

<svelte:head>
  <title>Chains — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ════════════════════════════════════════════════════════════════════
       LEFT PANE — CMC Macro + Whale Feed (60%)
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

    <!-- ── CMC Macro Strip ─────────────────────────────────────────────── -->
    <Panel title="Market Overview" badge="300s" noPad>
      <div class="macro-body">
        {#if macroLoading && !fearGreed && !globalMetrics && !quotes}
          <Skeleton lines={1} height="24px" />
        {:else}
          <div class="macro-strip">
            <!-- Fear & Greed -->
            {#if fearGreed}
              <div class="macro-pill">
                <span class="macro-key">Fear &amp; Greed</span>
                <span class="macro-val" class:fg-green={fearGreed.value != null && fearGreed.value >= 70}
                      class:fg-amber={fearGreed.value != null && fearGreed.value >= 45 && fearGreed.value < 70}
                      class:fg-red={fearGreed.value != null && fearGreed.value < 45}>
                  {fearGreed.value ?? '—'}
                </span>
                {#if fearGreed.value_classification}
                  <Badge variant={fearColor(fearGreed.value)}>
                    {fearGreed.value_classification}
                  </Badge>
                {/if}
              </div>
            {/if}

            <!-- Global Metrics -->
            {#if globalMetrics}
              <div class="macro-pill">
                <span class="macro-key">Mkt Cap</span>
                <span class="macro-val">{formatUSD(globalMetrics.total_market_cap)}</span>
                {#if globalMetrics.total_market_cap_change_24h != null}
                  <span class="macro-chg" class:positive={globalMetrics.total_market_cap_change_24h >= 0}
                        class:negative={globalMetrics.total_market_cap_change_24h < 0}>
                    {formatPct(globalMetrics.total_market_cap_change_24h)}
                  </span>
                {/if}
              </div>
              <div class="macro-pill">
                <span class="macro-key">24h Vol</span>
                <span class="macro-val">{formatUSD(globalMetrics.total_volume_24h)}</span>
              </div>
              <div class="macro-pill">
                <span class="macro-key">BTC.D</span>
                <span class="macro-val btc-dom">{globalMetrics.btc_dominance != null ? globalMetrics.btc_dominance.toFixed(1) + '%' : '—'}</span>
              </div>
              {#if globalMetrics.eth_dominance != null}
                <div class="macro-pill">
                  <span class="macro-key">ETH.D</span>
                  <span class="macro-val">{globalMetrics.eth_dominance.toFixed(1)}%</span>
                </div>
              {/if}
            {/if}

            <!-- Top Coin Quotes -->
            {#if quotes && quotes.length > 0}
              {#each quotes as coin (coin.symbol)}
                <div class="macro-pill">
                  <span class="macro-key coin-symbol">{coin.symbol}</span>
                  <span class="macro-val">{formatPrice(coin.price)}</span>
                  {#if coin.percent_change_24h != null}
                    <span class="macro-chg" class:positive={coin.percent_change_24h >= 0}
                          class:negative={coin.percent_change_24h < 0}>
                      {formatPct(coin.percent_change_24h)}
                    </span>
                  {/if}
                </div>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    </Panel>

    <!-- ── Whale Activity Feed ─────────────────────────────────────────── -->
    <Panel title="🐋 Whale Activity" badge="15s" fill noPad>
      {#snippet header()}
        <span class="alert-count">{filteredAlerts.length} txns</span>
        <div class="whale-controls">
          <select class="threshold-select" bind:value={whaleMinUsd}>
            {#each usdThresholds as t (t.value)}
              <option value={t.value}>{t.label}</option>
            {/each}
          </select>
          <FilterChips
            options={whaleFilterOptions}
            active={whaleFilter}
            onchange={(v) => whaleFilter = v}
          />
        </div>
      {/snippet}
        {#if !whaleData}
          <Skeleton lines={8} height="20px" />
        {:else if filteredAlerts.length === 0}
          <div class="empty-state">
            {#if whaleFilter !== 'all'}
              No {whaleFilter} whale transactions above {usdThresholds.find(t => t.value === whaleMinUsd)?.label ?? '$500K'}
            {:else}
              No whale transactions detected
            {/if}
          </div>
        {:else}
          {#each filteredAlerts as tx, i (tx.hash ?? i)}
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
                  <Badge variant={txTypeBadge(tx.transaction_type)}>
                    {tx.transaction_type}
                  </Badge>
                {/if}
                {#if tx.chain}
                  <span class="whale-chain">{tx.chain}</span>
                {/if}
              </div>
              <div class="whale-addresses">
                <span class="whale-addr">
                  <span class="addr-label">From:</span>
                  {tx.from_owner || truncAddr(tx.from_address)}
                </span>
                <span class="whale-addr-arrow">→</span>
                <span class="whale-addr">
                  <span class="addr-label">To:</span>
                  {tx.to_owner || truncAddr(tx.to_address)}
                </span>
              </div>
              {#if tx.timestamp}
                <span class="whale-time">{timeAgo(tx.timestamp)}</span>
              {/if}
            </div>
          {/each}
        {/if}
    </Panel>

  </div>

  <!-- ════════════════════════════════════════════════════════════════════
       RIGHT PANE — Correlation + Mempool + Watchlist (40%)
       ════════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <!-- ── Signal Correlation ──────────────────────────────────────────── -->
    <div style="flex:3; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Signal Correlation" badge="60s" fill noPad>
      {#snippet header()}
        {#if correlationData}
          <span class="alert-count">{correlationData.count} events</span>
        {/if}
      {/snippet}
        {#if !correlationData}
          <Skeleton lines={4} height="16px" />
        {:else if correlationEvents.length === 0}
          <div class="empty-state">No correlation events</div>
        {:else}
          {#each correlationEvents as ev, i (i)}
            <div class="corr-row">
              <div class="corr-header">
                {#if ev.symbol}
                  <span class="corr-symbol">{ev.symbol}</span>
                {/if}
                {#if ev.timestamp}
                  <span class="corr-time">{timeAgo(ev.timestamp)}</span>
                {/if}
                {#if ev.strength != null}
                  <Badge variant={strengthVariant(ev.strength)}>
                    {strengthLabel(ev.strength)} {(ev.strength * 100).toFixed(0)}%
                  </Badge>
                {/if}
              </div>
              <div class="corr-signals">
                {#if ev.whale_signal}
                  <div class="corr-signal">
                    <span class="signal-label">Whale:</span>
                    <span class="signal-val">{ev.whale_signal}</span>
                  </div>
                {/if}
                {#if ev.janus_signal}
                  <div class="corr-signal">
                    <span class="signal-label">Janus:</span>
                    <span class="signal-val janus">{ev.janus_signal}</span>
                  </div>
                {/if}
              </div>
              {#if ev.description}
                <div class="corr-desc">{ev.description}</div>
              {/if}
              {#if ev.strength != null}
                <ProgressBar
                  value={ev.strength * 100}
                  color={ev.strength >= 0.75 ? 'green' : ev.strength >= 0.5 ? 'amber' : 'cyan'}
                  height="4px"
                />
              {/if}
            </div>
          {/each}
        {/if}
    </Panel>
    </div>

    <!-- ── BTC Mempool ─────────────────────────────────────────────────── -->
    <div style="flex:3; min-height:0; display:flex; flex-direction:column;">
    <Panel title="BTC Mempool" badge="60s" fill noPad>
        {#if !mempoolData}
          <Skeleton lines={5} height="14px" />
        {:else}
          <div class="mempool-stats">
            <!-- Congestion level -->
            <div class="mempool-stat-row">
              <span class="mempool-key">Congestion</span>
              <Badge variant={congestionVariant(mempoolData.congestion_level)}>
                {mempoolData.congestion_level ?? 'Unknown'}
              </Badge>
            </div>

            <!-- Pending txns -->
            {#if mempoolData.pending_txns != null}
              <div class="mempool-stat-row">
                <span class="mempool-key">Pending Txns</span>
                <span class="mempool-val">{mempoolData.pending_txns.toLocaleString()}</span>
              </div>
            {/if}

            <!-- Fee tiers from explicit fields -->
            {#if mempoolData.fastest_fee != null}
              <div class="mempool-divider"></div>
              <div class="mempool-section-label">Fee Estimates (sat/vB)</div>
              <div class="mempool-fee-grid">
                <div class="fee-row">
                  <span class="fee-label">Fastest</span>
                  <span class="fee-val high">{mempoolData.fastest_fee}</span>
                </div>
                {#if mempoolData.half_hour_fee != null}
                  <div class="fee-row">
                    <span class="fee-label">30 min</span>
                    <span class="fee-val mid">{mempoolData.half_hour_fee}</span>
                  </div>
                {/if}
                {#if mempoolData.hour_fee != null}
                  <div class="fee-row">
                    <span class="fee-label">1 hour</span>
                    <span class="fee-val">{mempoolData.hour_fee}</span>
                  </div>
                {/if}
                {#if mempoolData.economy_fee != null}
                  <div class="fee-row">
                    <span class="fee-label">Economy</span>
                    <span class="fee-val low">{mempoolData.economy_fee}</span>
                  </div>
                {/if}
                {#if mempoolData.minimum_fee != null}
                  <div class="fee-row">
                    <span class="fee-label">Minimum</span>
                    <span class="fee-val low">{mempoolData.minimum_fee}</span>
                  </div>
                {/if}
              </div>
            {/if}

            <!-- Fee tier distribution bars (if fee_tiers array present) -->
            {#if mempoolData.fee_tiers && mempoolData.fee_tiers.length > 0}
              <div class="mempool-divider"></div>
              <div class="mempool-section-label">Fee Distribution</div>
              <div class="fee-tier-bars">
                {#each mempoolData.fee_tiers as tier, i (i)}
                  <div class="fee-tier-row">
                    <span class="fee-tier-label">
                      {tier.label ?? `${tier.min_sat_vb ?? '?'}–${tier.max_sat_vb ?? '?'}`}
                    </span>
                    <div class="fee-tier-bar-wrap">
                      <ProgressBar
                        value={tier.percentage ?? 0}
                        color={i === 0 ? 'red' : i === 1 ? 'amber' : i === 2 ? 'cyan' : 'green'}
                        height="5px"
                        label={tier.percentage != null ? `${tier.percentage.toFixed(0)}%` : tier.count != null ? `${tier.count}` : ''}
                      />
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
    </Panel>
    </div>

    <!-- ── Wallet Watchlist ────────────────────────────────────────────── -->
    <div style="flex:4; min-height:0; display:flex; flex-direction:column;">
    <Panel title="Wallet Watchlist" fill noPad>
      {#snippet header()}
        {#if watchlist.length > 0}
          <span class="alert-count">{watchlist.length} addresses</span>
        {/if}
      {/snippet}
        <!-- Add form -->
        <div class="watchlist-form">
          <input
            class="wl-input"
            type="text"
            placeholder="Address"
            bind:value={newAddr}
          />
          <input
            class="wl-input wl-label-input"
            type="text"
            placeholder="Label"
            bind:value={newLabel}
          />
          <select class="wl-select" bind:value={newChain}>
            {#each chainOptions as c (c)}
              <option value={c}>{c}</option>
            {/each}
          </select>
          <button
            class="wl-add-btn"
            onclick={addToWatchlist}
            disabled={addingWatchlist || !newAddr.trim() || !newLabel.trim()}
          >
            {addingWatchlist ? '…' : '+ Add'}
          </button>
        </div>

        <div class="wl-divider"></div>

        <!-- Watchlist entries -->
        {#if watchlistLoading}
          <Skeleton lines={3} height="16px" />
        {:else if watchlist.length === 0}
          <div class="empty-state">No watched wallets</div>
        {:else}
          {#each watchlist as entry (entry.address)}
            <div class="wl-row">
              <div class="wl-row-main">
                <span class="wl-addr" title={entry.address}>{truncAddr(entry.address, 14)}</span>
                <span class="wl-entry-label">{entry.label}</span>
                <Badge variant={entry.chain === 'bitcoin' ? 'amber' : entry.chain === 'ethereum' ? 'purple' : entry.chain === 'solana' ? 'cyan' : 'default'}>
                  {entry.chain}
                </Badge>
              </div>
              <div class="wl-row-actions">
                {#if entry.added_at}
                  <span class="wl-added">{timeAgo(entry.added_at)}</span>
                {/if}
                <button
                  class="wl-remove-btn"
                  onclick={() => removeFromWatchlist(entry.address)}
                  disabled={removingAddr === entry.address}
                  title="Remove from watchlist"
                >
                  {removingAddr === entry.address ? '…' : '✕'}
                </button>
              </div>
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
    flex: 6;
    border-right: 1px solid var(--b1);
    min-width: 0;
  }

  .pane-right {
    flex: 4;
    min-width: 280px;
    max-width: 520px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 0;
  }



  .alert-count {
    font-size: 9px;
    color: var(--t3);
  }

  .empty-state {
    padding: 24px 16px;
    text-align: center;
    color: var(--t3);
    font-size: 12px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     CMC Macro Strip
     ═══════════════════════════════════════════════════════════════════ */
  .macro-body {
    padding: 6px 10px;
  }

  .macro-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .macro-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: 9999px;
    white-space: nowrap;
  }

  .macro-key {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .macro-val {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    font-weight: 700;
    color: var(--t1);
  }

  .macro-val.fg-green { color: var(--green); }
  .macro-val.fg-amber { color: var(--amber); }
  .macro-val.fg-red   { color: var(--red); }
  .macro-val.btc-dom  { color: var(--amber); }

  .macro-chg {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    font-weight: 600;
  }

  .macro-chg.positive { color: var(--green); }
  .macro-chg.negative { color: var(--red); }

  .coin-symbol {
    color: var(--accent, var(--cyan));
  }

  /* ═══════════════════════════════════════════════════════════════════
     Whale Feed
     ═══════════════════════════════════════════════════════════════════ */
  .whale-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }

  .threshold-select {
    font-size: 9px;
    font-family: inherit;
    font-weight: 600;
    color: var(--t2);
    background: var(--bg1);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 2px 6px;
    cursor: pointer;
    outline: none;
  }

  .threshold-select:focus {
    border-color: var(--accent, var(--cyan));
  }

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
    gap: 4px;
    align-items: center;
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

  .whale-addr-arrow {
    font-size: 10px;
    color: var(--t3);
  }

  .whale-time {
    font-size: 8px;
    color: var(--t3);
    margin-top: 2px;
    display: block;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Signal Correlation
     ═══════════════════════════════════════════════════════════════════ */
  .corr-row {
    padding: 8px 12px;
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s;
  }

  .corr-row:hover {
    background: var(--bg2);
  }

  .corr-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }

  .corr-symbol {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    font-weight: 700;
    color: var(--t1);
    text-transform: uppercase;
  }

  .corr-time {
    font-size: 9px;
    color: var(--t3);
    margin-left: auto;
  }

  .corr-signals {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 4px;
  }

  .corr-signal {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .signal-label {
    font-size: 9px;
    font-weight: 600;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    width: 42px;
    flex-shrink: 0;
  }

  .signal-val {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--t2);
  }

  .signal-val.janus {
    color: var(--purple, var(--t2));
  }

  .corr-desc {
    font-size: 10px;
    color: var(--t3);
    line-height: 1.4;
    margin-bottom: 4px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     BTC Mempool
     ═══════════════════════════════════════════════════════════════════ */
  .mempool-stats {
    padding: 8px 12px;
  }

  .mempool-stat-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
  }

  .mempool-key {
    font-size: 10px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }

  .mempool-val {
    font-size: 12px;
    font-family: var(--font-mono, monospace);
    font-weight: 600;
    color: var(--t1);
  }

  .mempool-divider {
    border-top: 1px solid var(--b1);
    margin: 6px 0;
  }

  .mempool-section-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 6px;
  }

  .mempool-fee-grid {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .fee-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 0;
  }

  .fee-label {
    font-size: 10px;
    color: var(--t2);
    font-family: var(--font-mono, monospace);
  }

  .fee-val {
    font-size: 11px;
    font-family: var(--font-mono, monospace);
    font-weight: 700;
    color: var(--t1);
  }

  .fee-val.high { color: var(--red); }
  .fee-val.mid  { color: var(--amber); }
  .fee-val.low  { color: var(--green); }

  .fee-tier-bars {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .fee-tier-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .fee-tier-label {
    font-size: 9px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
    width: 70px;
    flex-shrink: 0;
    text-align: right;
  }

  .fee-tier-bar-wrap {
    flex: 1;
    min-width: 0;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Wallet Watchlist
     ═══════════════════════════════════════════════════════════════════ */
  .watchlist-form {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 8px 10px;
    align-items: center;
  }

  .wl-input {
    flex: 1;
    min-width: 80px;
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--t1);
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 4px 6px;
    outline: none;
    transition: border-color 0.15s;
  }

  .wl-input:focus {
    border-color: var(--accent, var(--cyan));
  }

  .wl-input::placeholder {
    color: var(--t3);
  }

  .wl-label-input {
    max-width: 90px;
  }

  .wl-select {
    font-size: 9px;
    font-family: inherit;
    font-weight: 600;
    color: var(--t2);
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 4px 6px;
    cursor: pointer;
    outline: none;
  }

  .wl-select:focus {
    border-color: var(--accent, var(--cyan));
  }

  .wl-add-btn {
    font-size: 9px;
    font-family: inherit;
    font-weight: 700;
    color: var(--bg1);
    background: var(--accent, var(--cyan));
    border: none;
    border-radius: var(--r);
    padding: 4px 10px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    transition: opacity 0.15s;
  }

  .wl-add-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .wl-add-btn:hover:not(:disabled) {
    opacity: 0.85;
  }

  .wl-divider {
    border-top: 1px solid var(--b1);
    margin: 0 10px;
  }

  .wl-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s;
    gap: 8px;
  }

  .wl-row:hover {
    background: var(--bg2);
  }

  .wl-row-main {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    flex: 1;
  }

  .wl-addr {
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    color: var(--t3);
    flex-shrink: 0;
  }

  .wl-entry-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--t1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }

  .wl-row-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .wl-added {
    font-size: 8px;
    color: var(--t3);
  }

  .wl-remove-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    font-size: 10px;
    color: var(--t3);
    background: transparent;
    border: 1px solid var(--b1);
    border-radius: var(--r);
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
    font-family: inherit;
    padding: 0;
  }

  .wl-remove-btn:hover:not(:disabled) {
    color: var(--red);
    border-color: var(--red);
    background: var(--red-dim, rgba(234, 57, 67, 0.08));
  }

  .wl-remove-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>
