<script lang="ts">
  import { onMount, onDestroy, untrack } from 'svelte';
  import { createSSE } from '$stores/sse';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import { focusSymbol } from '$stores/focusSymbol';
  import type { BarUpdate, AssetSearchResult } from '$lib/types';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import InnerTabs from '$components/ui/InnerTabs.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import type { PageData } from './$types';

  // ─── Server data (SSR prefetch) ────────────────────────────────────
  // Populated by +page.server.ts before first paint; client-side polls/timers
  // take over on their first tick and these values become unreferenced.
  let { data }: { data: PageData } = $props();

  // ─── Types ──────────────────────────────────────────────────────────

  interface Trade {
    id: number;
    created_at: string;
    asset: string;
    direction: string;
    entry: number;
    sl: number | null;
    tp: number | null;
    contracts: number;
    status: string;
    close_price: number | null;
    pnl: number | null;
    rr: number | null;
    strategy: string;
    notes: string;
  }

  interface Signal {
    id?: string;
    symbol?: string;
    direction?: string;
    strategy?: string;
    confidence?: number;
    timestamp?: string;
    price?: number;
  }

  interface BarData {
    columns: string[];
    data: any[][];
  }

  // ─── Risk Calculator Presets ─────────────────────────────────────────
  const CONTRACT_PRESETS: Record<string, { label: string; pointValue: number }> = {
    MES:    { label: 'MES — Micro S&P ($5/pt)',       pointValue: 5 },
    MNQ:    { label: 'MNQ — Micro Nasdaq ($2/pt)',    pointValue: 2 },
    MGC:    { label: 'MGC — Micro Gold ($10/oz)',      pointValue: 10 },
    MYM:    { label: 'MYM — Micro Dow ($0.50/pt)',    pointValue: 0.5 },
    M2K:    { label: 'M2K — Micro Russell ($5/pt)',   pointValue: 5 },
    SIL:    { label: 'SIL — Micro Silver ($10/oz)',   pointValue: 10 },
    custom: { label: 'Custom…',                        pointValue: 1 },
  };

  // ─── State ──────────────────────────────────────────────────────────
  let symbol = $state('MGC');
  let activeTimeframe = $state('5m');
  const timeframes = [
    { id: '1m', label: '1m' },
    { id: '5m', label: '5m' },
    { id: '15m', label: '15m' },
    { id: '1h', label: '1H' },
    { id: '4h', label: '4H' },
    { id: '1D', label: '1D' },
  ];

  // Chart state
  let chartContainer: HTMLDivElement;
  let chart: any = null;
  let candleSeries: any = null;
  let chartLoading = $state(true);

  // Order form state
  let orderSymbol = $state('MGC');
  let orderType = $state<'market' | 'limit' | 'stop'>('market');
  let orderPrice = $state<number | undefined>(undefined);
  let orderQty = $state(1);
  let orderSL = $state<number | undefined>(undefined);
  let orderTP = $state<number | undefined>(undefined);
  let orderSubmitting = $state(false);
  let orderFeedback = $state<{ message: string; type: 'success' | 'error' } | null>(null);

  // Symbol search state
  let searchQuery = $state('');
  let searchResults = $state<AssetSearchResult[]>([]);
  let showDropdown = $state(false);
  let searchTimeout: ReturnType<typeof setTimeout> | null = null;

  // Risk calculator state
  let riskCalcOpen = $state(true);
  let rcPreset = $state('MES');
  let rcAccount = $state(25000);
  let rcRiskPct = $state(1);
  let rcEntry = $state<number | undefined>(undefined);
  let rcStop = $state<number | undefined>(undefined);
  let rcTarget = $state<number | undefined>(undefined);
  let rcPointValue = $state(5);

  // ─── Polling stores ─────────────────────────────────────────────────
  const tradesStore = createPoll<Trade[]>('/api/trades/open', 5000);
  // Fall back to SSR-prefetched trades until the poll fires for the first time.
  let trades = $derived($tradesStore ?? (data.initialTrades as Trade[] | null) ?? []);

  // Signals: poll from Redis via the DB tools endpoint (returns JSON)
  // Snapshot SSR values into plain consts before $state to silence the
  // `state_referenced_locally` Svelte lint warning — the one-time capture is
  // intentional; server data is immutable after SSR and the 4-second timer
  // will refresh regardless, clearing `signalsLoading` via fetchSignals() → finally.
  // untrack() tells Svelte 5 "this is an intentional one-shot read of reactive
  // props — do not warn about state_referenced_locally".  Server data from
  // +page.server.ts is immutable after SSR; the 4-second timer refreshes anyway.
  const _initSignals: Signal[] = untrack(() => (data.initialSignals as Signal[] | null) ?? []);
  const _initSignalsLoading: boolean = untrack(() => data.initialSignals === null);
  let signals = $state<Signal[]>(_initSignals);
  let signalsLoading = $state(_initSignalsLoading);
  let signalsTimer: ReturnType<typeof setInterval> | null = null;

  // SSE for live bar updates
  let barSSE: ReturnType<typeof createSSE<BarUpdate>> | null = null;

  // ─── Risk Calculator (derived) ──────────────────────────────────────
  let riskCalcResult = $derived.by(() => {
    const account = rcAccount || 0;
    const riskPct = rcRiskPct || 1;
    const entry = rcEntry ?? 0;
    const stop = rcStop ?? 0;
    const target = rcTarget ?? 0;
    const pointVal = rcPointValue || 5;

    if (!account || !entry || !stop || entry === stop || !pointVal) {
      return { contracts: '—', dollarRisk: '—', riskPer: '—', rr: '—', rrColor: 'var(--purple)' };
    }

    const maxRisk = account * (riskPct / 100);
    const stopDist = Math.abs(entry - stop);
    const riskPerCont = stopDist * pointVal;
    const contracts = riskPerCont > 0 ? Math.floor(maxRisk / riskPerCont) : 0;
    const actualRisk = contracts * riskPerCont;

    let rr = '—';
    let rrColor = 'var(--purple)';
    if (target && target !== entry) {
      const targetDist = Math.abs(target - entry);
      const rrVal = riskPerCont > 0 ? (targetDist * pointVal) / riskPerCont : 0;
      rr = rrVal.toFixed(2) + ':1';
      rrColor = rrVal >= 2 ? 'var(--green)' : rrVal >= 1 ? 'var(--amber)' : 'var(--red)';
    }

    return {
      contracts: contracts > 0 ? contracts.toString() : '0',
      dollarRisk: '$' + actualRisk.toFixed(2),
      riskPer: '$' + riskPerCont.toFixed(2),
      rr,
      rrColor,
    };
  });

  // ─── Chart ──────────────────────────────────────────────────────────
  async function loadChart() {
    if (!chartContainer) return;
    chartLoading = true;

    const { createChart } = await import('lightweight-charts');

    if (chart) chart.remove();

    chart = createChart(chartContainer, {
      layout: {
        background: { type: 'solid' as any, color: '#07070d' },
        textColor: '#8890b8',
        fontFamily: "'SF Mono', 'Fira Code', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1a1a2e' },
        horzLines: { color: '#1a1a2e' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1a1a2e' },
      timeScale: {
        borderColor: '#1a1a2e',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    candleSeries = chart.addCandlestickSeries({
      upColor: '#16c784',
      downColor: '#ea3943',
      borderUpColor: '#16c784',
      borderDownColor: '#ea3943',
      wickUpColor: '#16c784',
      wickDownColor: '#ea3943',
    });

    try {
      const res = await fetch(`/bars/${symbol}?interval=${activeTimeframe}&days_back=5`, {
        headers: { Accept: 'application/json' },
      });
      const data: BarData = await res.json();

      if (data.columns && data.data) {
        const cols = data.columns;
        const iO = cols.indexOf('open');
        const iH = cols.indexOf('high');
        const iL = cols.indexOf('low');
        const iC = cols.indexOf('close');

        const candles = data.data.map((row: any[]) => ({
          time: Math.floor(new Date(row[0]).getTime() / 1000) as any,
          open: row[iO],
          high: row[iH],
          low: row[iL],
          close: row[iC],
        }));

        candleSeries.setData(candles);
        chart.timeScale().fitContent();
      }
    } catch (e) {
      console.warn('[trading/chart] Failed to load bars:', e);
    } finally {
      chartLoading = false;
    }

    // Subscribe to live bar updates via SSE
    connectBarSSE();
  }

  function connectBarSSE() {
    if (barSSE) {
      barSSE.disconnect();
    }
    barSSE = createSSE<BarUpdate>(`/sse/bars/${symbol}`, { eventName: 'bar' });
    barSSE.subscribe((bar: BarUpdate | null) => {
      if (bar && candleSeries) {
        try {
          const time = typeof bar.time === 'number' ? bar.time : Math.floor(new Date(bar.time).getTime() / 1000);
          candleSeries.update({
            time: time as any,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          });
        } catch {
          // Ignore update errors
        }
      }
    });
    barSSE.connect();
  }

  // ─── Auto-switch to strip focus symbol ──────────────────────────────
  $effect(() => {
    const unsub = focusSymbol.subscribe((sym) => {
      if (sym && sym !== symbol) {
        switchSymbol(sym);
      }
    });
    return unsub;
  });

  function switchTimeframe(tf: string) {
    activeTimeframe = tf;
    loadChart();
  }

  function switchSymbol(newSymbol: string) {
    symbol = newSymbol;
    orderSymbol = newSymbol;
    focusSymbol.set(newSymbol);
    searchQuery = '';
    showDropdown = false;
    loadChart();
  }

  // ─── Symbol Search ──────────────────────────────────────────────────
  async function handleSearch(query: string) {
    searchQuery = query;
    if (searchTimeout) clearTimeout(searchTimeout);

    if (query.length < 1) {
      searchResults = [];
      showDropdown = false;
      return;
    }

    searchTimeout = setTimeout(async () => {
      try {
        const data = await api.get<{ results?: AssetSearchResult[]; assets?: AssetSearchResult[] }>(
          `/api/assets/search?q=${encodeURIComponent(query)}`
        );
        searchResults = data.results ?? data.assets ?? [];
        showDropdown = searchResults.length > 0;
      } catch {
        searchResults = [];
        showDropdown = false;
      }
    }, 200);
  }

  function selectSearchResult(result: AssetSearchResult) {
    orderSymbol = result.symbol;
    switchSymbol(result.symbol);
    showDropdown = false;
  }

  function handleSearchKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      switchSymbol(orderSymbol.toUpperCase());
      showDropdown = false;
    }
    if (e.key === 'Escape') {
      showDropdown = false;
    }
  }

  // ─── Signals ────────────────────────────────────────────────────────
  async function fetchSignals() {
    try {
      // Try the DB tools endpoint which returns JSON from Redis
      const data = await api.get<any>('/api/db/redis/get/fks:memories:new');
      if (data && typeof data === 'object') {
        // May be a single signal or a list
        const raw = Array.isArray(data) ? data : (data.value ? [data.value] : [data]);
        const parsed: Signal[] = [];
        for (const item of raw) {
          try {
            const sig = typeof item === 'string' ? JSON.parse(item) : item;
            if (sig && (sig.symbol || sig.direction)) {
              parsed.push(sig);
            }
          } catch {
            // skip unparseable
          }
        }
        if (parsed.length > 0) {
          signals = parsed.slice(0, 10);
        }
      }
    } catch {
      // Fallback: try janus signals recent from the sorted set
      try {
        const data = await api.get<any>('/api/janus/signals/recent');
        if (Array.isArray(data)) {
          signals = data.slice(0, 10);
        }
      } catch {
        // silently continue
      }
    } finally {
      signalsLoading = false;
    }
  }

  function prefillFromSignal(sig: Signal) {
    if (sig.symbol) orderSymbol = sig.symbol;
    if (sig.price) {
      orderPrice = sig.price;
      orderType = 'limit';
    }
    switchSymbol(sig.symbol ?? orderSymbol);
  }

  // ─── Order Submission ───────────────────────────────────────────────
  async function submitOrder(side: 'buy' | 'sell') {
    orderSubmitting = true;
    orderFeedback = null;

    const body: Record<string, any> = {
      asset: orderSymbol.toUpperCase(),
      direction: side,
      entry: orderType === 'market' ? 0 : (orderPrice ?? 0),
      contracts: orderQty,
      account_size: rcAccount,
    };
    if (orderSL != null) body.sl = orderSL;
    if (orderTP != null) body.tp = orderTP;
    if (orderType !== 'market' && orderPrice != null) body.entry = orderPrice;

    try {
      await api.post('/api/trades', body);
      orderFeedback = { message: `${side.toUpperCase()} order submitted`, type: 'success' };
      // Refresh positions
      tradesStore.refresh();
      // Clear feedback after 3s
      setTimeout(() => { orderFeedback = null; }, 3000);
    } catch (e: any) {
      orderFeedback = { message: e?.message ?? 'Order failed', type: 'error' };
      setTimeout(() => { orderFeedback = null; }, 5000);
    } finally {
      orderSubmitting = false;
    }
  }

  // ─── Trade Actions ──────────────────────────────────────────────────
  async function closeTrade(tradeId: number) {
    try {
      await api.post(`/api/trades/${tradeId}/close`, {});
      tradesStore.refresh();
    } catch (e) {
      console.warn('[trading] Failed to close trade:', e);
    }
  }

  // ─── Preset Change ─────────────────────────────────────────────────
  function applyPreset(preset: string) {
    rcPreset = preset;
    const p = CONTRACT_PRESETS[preset];
    if (p) rcPointValue = p.pointValue;
  }

  // ─── Formatting ─────────────────────────────────────────────────────
  function fmtPrice(n: number | null | undefined): string {
    if (n == null) return '—';
    const abs = Math.abs(n);
    const digits = abs < 1 ? 6 : abs < 100 ? 4 : 2;
    return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function fmtPnl(n: number | null | undefined): string {
    if (n == null) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}$${n.toFixed(2)}`;
  }

  function fmtTime(ts: string | undefined): string {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return ts;
    }
  }

  function fmtConfidence(n: number | undefined): string {
    if (n == null) return '—';
    return (n * 100).toFixed(0) + '%';
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    loadChart();
    tradesStore.start();

    // Poll signals every 4s
    fetchSignals();
    signalsTimer = setInterval(fetchSignals, 4000);

    // Resize observer for chart
    const ro = new ResizeObserver(() => {
      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: chartContainer.clientHeight,
        });
      }
    });
    if (chartContainer) ro.observe(chartContainer);

    // Close dropdown on outside click
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.symbol-search-wrap')) {
        showDropdown = false;
      }
    };
    document.addEventListener('click', handleOutsideClick);

    return () => {
      ro.disconnect();
      document.removeEventListener('click', handleOutsideClick);
    };
  });

  onDestroy(() => {
    if (chart) { chart.remove(); chart = null; }
    if (barSSE) { barSSE.disconnect(); barSSE = null; }
    tradesStore.stop();
    if (signalsTimer) { clearInterval(signalsTimer); signalsTimer = null; }
    if (searchTimeout) clearTimeout(searchTimeout);
  });
</script>

<svelte:head>
  <title>Trading — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ═══════════════════════════════════════════════════════════════════
       LEFT PANE (70%) — Chart + Active Trades
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

    <!-- ── Chart Panel ──────────────────────────────────────────────── -->
    <div class="chart-panel">
      <Panel title="Chart" noPad fill>
        {#snippet header()}
          <span class="symbol-badge">{symbol}</span>
          <span class="tf-current muted">{activeTimeframe}</span>
          <div class="tf-tabs">
            {#each timeframes as tf}
              <button
                class="tf-tab"
                class:active={activeTimeframe === tf.id}
                onclick={() => switchTimeframe(tf.id)}
              >
                {tf.label}
              </button>
            {/each}
          </div>
        {/snippet}
        <div class="chart-area" bind:this={chartContainer}>
          {#if chartLoading}
            <div class="chart-loading">
              <div class="spinner"></div>
              Loading {symbol} · {activeTimeframe}
            </div>
          {/if}
        </div>
      </Panel>
    </div>

    <!-- ── Active Trades Panel ──────────────────────────────────────── -->
    <div class="trades-panel">
      <Panel title="Open Positions" badge="5s" noPad fill>
        {#snippet header()}
          <Badge variant="default">{trades.length}</Badge>
        {/snippet}
        <div class="trades-body">
        {#if trades.length === 0}
          <div class="empty-state">No open positions</div>
        {:else}
          <table class="tbl">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Qty</th>
                <th>SL</th>
                <th>TP</th>
                <th>P&L</th>
                <th>Strategy</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each trades as trade}
                <tr>
                  <td class="accent">{trade.asset}</td>
                  <td>
                    <span class:buy-side={trade.direction === 'buy' || trade.direction === 'long'}
                          class:sell-side={trade.direction === 'sell' || trade.direction === 'short'}>
                      {trade.direction?.toUpperCase()}
                    </span>
                  </td>
                  <td>{fmtPrice(trade.entry)}</td>
                  <td>{trade.contracts}</td>
                  <td class="muted">{fmtPrice(trade.sl)}</td>
                  <td class="muted">{fmtPrice(trade.tp)}</td>
                  <td class:green={(trade.pnl ?? 0) >= 0}
                      class:red={(trade.pnl ?? 0) < 0}>
                    {fmtPnl(trade.pnl)}
                  </td>
                  <td class="muted">{trade.strategy || '—'}</td>
                  <td>
                    <button class="btn-close-trade" onclick={() => closeTrade(trade.id)}
                            title="Close position">✕</button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
        </div>
      </Panel>
    </div>

  </div>

  <!-- ═══════════════════════════════════════════════════════════════════
       RIGHT PANE (30%) — Order Entry + Risk Calculator + Signals
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <!-- ── Order Entry ──────────────────────────────────────────────── -->
    <div class="order-panel">
      <Panel title="Order Entry" noPad>
        <div class="order-body">

        <!-- Symbol -->
        <div class="form-row">
          <label class="form-label" for="order-symbol">Symbol</label>
          <div class="symbol-search-wrap">
            <input
              id="order-symbol"
              class="form-input"
              type="text"
              bind:value={orderSymbol}
              oninput={(e: Event) => handleSearch((e.target as HTMLInputElement).value)}
              onfocus={() => { if (searchResults.length > 0) showDropdown = true; }}
              onkeydown={handleSearchKeydown}
              placeholder="Search assets…"
              autocomplete="off"
              spellcheck="false"
            />
            {#if showDropdown && searchResults.length > 0}
              <div class="search-dropdown">
                {#each searchResults as result}
                  <button class="search-row" onclick={() => selectSearchResult(result)}>
                    <span class="search-symbol">{result.symbol}</span>
                    {#if result.name}
                      <span class="search-name">{result.name}</span>
                    {/if}
                    {#if result.type}
                      <span class="search-type">{result.type}</span>
                    {/if}
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        </div>

        <!-- Order type -->
        <div class="form-row">
          <span class="form-label">Type</span>
          <div class="radio-group">
            <label class="radio-option">
              <input type="radio" name="order-type" value="market"
                     checked={orderType === 'market'}
                     onchange={() => { orderType = 'market'; }} />
              Market
            </label>
            <label class="radio-option">
              <input type="radio" name="order-type" value="limit"
                     checked={orderType === 'limit'}
                     onchange={() => { orderType = 'limit'; }} />
              Limit
            </label>
            <label class="radio-option">
              <input type="radio" name="order-type" value="stop"
                     checked={orderType === 'stop'}
                     onchange={() => { orderType = 'stop'; }} />
              Stop
            </label>
          </div>
        </div>

        <!-- Price (hidden for market) -->
        {#if orderType !== 'market'}
          <div class="form-row">
            <label class="form-label" for="order-price">Price</label>
            <input id="order-price" class="form-input" type="number" step="0.01" placeholder="0.00"
                   bind:value={orderPrice} />
          </div>
        {/if}

        <!-- Quantity -->
        <div class="form-row">
          <label class="form-label" for="order-qty">Qty</label>
          <input id="order-qty" class="form-input" type="number" step="1" min="1" placeholder="1"
                 bind:value={orderQty} />
        </div>

        <!-- Stop Loss -->
        <div class="form-row">
          <label class="form-label" for="order-sl">SL</label>
          <input id="order-sl" class="form-input" type="number" step="0.01" placeholder="Stop loss"
                 bind:value={orderSL} />
        </div>

        <!-- Take Profit -->
        <div class="form-row">
          <label class="form-label" for="order-tp">TP</label>
          <input id="order-tp" class="form-input" type="number" step="0.01" placeholder="Take profit"
                 bind:value={orderTP} />
        </div>

        <!-- Buy / Sell buttons -->
        <div class="order-buttons">
          <button class="btn-buy" onclick={() => submitOrder('buy')} disabled={orderSubmitting}>
            {orderSubmitting ? '…' : 'BUY'}
          </button>
          <button class="btn-sell" onclick={() => submitOrder('sell')} disabled={orderSubmitting}>
            {orderSubmitting ? '…' : 'SELL'}
          </button>
        </div>

        <!-- Order feedback -->
        {#if orderFeedback}
          <div class="order-feedback" class:feedback-success={orderFeedback.type === 'success'}
                                       class:feedback-error={orderFeedback.type === 'error'}>
            {orderFeedback.message}
          </div>
        {/if}

        </div>
      </Panel>
    </div>

    <!-- ── Risk Calculator ──────────────────────────────────────────── -->
    <div class="risk-panel">
      <button class="risk-head" onclick={() => riskCalcOpen = !riskCalcOpen}>
        <span class="risk-title">Risk Calculator</span>
        <span class="toggle-arrow" class:collapsed={!riskCalcOpen}>▼</span>
      </button>

      {#if riskCalcOpen}
        <div class="risk-body">

          <!-- Contract preset -->
          <div class="form-row">
            <label class="form-label" for="rc-contract">Contract</label>
            <select id="rc-contract" class="form-input" bind:value={rcPreset}
                    onchange={(e: Event) => applyPreset((e.target as HTMLSelectElement).value)}>
              {#each Object.entries(CONTRACT_PRESETS) as [key, preset]}
                <option value={key}>{preset.label}</option>
              {/each}
            </select>
          </div>

          <!-- Account + Risk % -->
          <div class="form-row form-row-split">
            <div class="form-col">
              <label class="form-label" for="rc-account">Acct $</label>
              <input id="rc-account" class="form-input" type="number" step="1000" bind:value={rcAccount} />
            </div>
            <div class="form-col">
              <label class="form-label" for="rc-risk-pct">Risk%</label>
              <input id="rc-risk-pct" class="form-input" type="number" step="0.25" min="0.1" max="5" bind:value={rcRiskPct} />
            </div>
          </div>

          <!-- Entry + Stop -->
          <div class="form-row form-row-split">
            <div class="form-col">
              <label class="form-label" for="rc-entry">Entry</label>
              <input id="rc-entry" class="form-input" type="number" step="0.01" placeholder="0.00" bind:value={rcEntry} />
            </div>
            <div class="form-col">
              <label class="form-label" for="rc-stop">Stop</label>
              <input id="rc-stop" class="form-input" type="number" step="0.01" placeholder="0.00" bind:value={rcStop} />
            </div>
          </div>

          <!-- Target + Point value -->
          <div class="form-row form-row-split">
            <div class="form-col">
              <label class="form-label" for="rc-target">Target</label>
              <input id="rc-target" class="form-input" type="number" step="0.01" placeholder="optional" bind:value={rcTarget} />
            </div>
            <div class="form-col">
              <label class="form-label" for="rc-pt-value">Pt$</label>
              <input id="rc-pt-value" class="form-input" type="number" step="0.01" bind:value={rcPointValue}
                     title="Dollar value per 1 point move" />
            </div>
          </div>

          <!-- Results grid -->
          <div class="risk-output">
            <span class="risk-label">Contracts</span>
            <span class="risk-value" style="color: var(--green)">{riskCalcResult.contracts}</span>
            <span class="risk-label">$ Risk</span>
            <span class="risk-value" style="color: var(--amber)">{riskCalcResult.dollarRisk}</span>
            <span class="risk-label">Risk/Contract</span>
            <span class="risk-value">{riskCalcResult.riskPer}</span>
            <span class="risk-label">R:R</span>
            <span class="risk-value" style="color: {riskCalcResult.rrColor}">{riskCalcResult.rr}</span>
          </div>

        </div>
      {/if}
    </div>

    <!-- ── Live Signals ────────────────────────────────────────────── -->
    <div class="signals-panel">
      <Panel title="Live Signals" badge="4s" fill>
        <div class="signals-body">
        {#if signalsLoading && signals.length === 0}
          <Skeleton lines={4} />
        {:else if signals.length === 0}
          <div class="empty-state">No recent signals</div>
        {:else}
          {#each signals as sig}
            <button class="signal-card" onclick={() => prefillFromSignal(sig)}>
              <div class="signal-top">
                <span class="signal-symbol">{sig.symbol ?? '—'}</span>
                <span class="signal-dir"
                      class:buy-side={sig.direction === 'buy' || sig.direction === 'long' || sig.direction === 'LONG'}
                      class:sell-side={sig.direction === 'sell' || sig.direction === 'short' || sig.direction === 'SHORT'}>
                  {sig.direction?.toUpperCase() ?? '—'}
                </span>
                {#if sig.confidence != null}
                  <span class="signal-conf">{fmtConfidence(sig.confidence)}</span>
                {/if}
              </div>
              <div class="signal-bottom">
                <span class="signal-strategy">{sig.strategy ?? ''}</span>
                <span class="signal-time">{fmtTime(sig.timestamp)}</span>
              </div>
            </button>
          {/each}
        {/if}
        </div>
      </Panel>
    </div>

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
    flex: 7;
    border-right: 1px solid var(--b1);
    min-width: 0;
  }

  .pane-right {
    flex: 3;
    min-width: 260px;
    max-width: 380px;
    overflow-y: auto;
  }

  .symbol-badge {
    font-size: 12px;
    font-weight: 700;
    color: var(--accent);
  }

  .tf-current {
    font-size: 10px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Chart
     ═══════════════════════════════════════════════════════════════════ */
  .chart-panel {
    flex: 7;
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-bottom: 1px solid var(--b1);
  }

  .chart-area {
    height: 100%;
    min-height: 0;
    position: relative;
    background: var(--bg0);
  }

  .chart-loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--t3);
    font-size: 12px;
    z-index: 5;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--b2);
    border-top-color: var(--cyan);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin { to { transform: rotate(360deg); } }

  /* TF tabs */
  .tf-tabs {
    display: flex;
    gap: 2px;
    margin-left: auto;
  }

  .tf-tab {
    all: unset;
    padding: 2px 7px;
    font-size: 10px;
    color: var(--t3);
    cursor: pointer;
    border-radius: var(--r);
    transition: color 0.12s, background 0.12s;
  }

  .tf-tab:hover { color: var(--t2); background: var(--bg3); }
  .tf-tab.active { color: var(--t1); background: var(--accent-dim); }

  /* ═══════════════════════════════════════════════════════════════════
     Trades table
     ═══════════════════════════════════════════════════════════════════ */
  .trades-panel {
    flex: 3;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .trades-body {
    overflow: auto;
  }

  .tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  .tbl th {
    text-align: left;
    padding: 4px 8px;
    color: var(--t3);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--b2);
    white-space: nowrap;
  }

  .tbl td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
  }

  .tbl tr:hover { background: var(--bg3); }

  .btn-close-trade {
    all: unset;
    cursor: pointer;
    color: var(--t3);
    font-size: 10px;
    padding: 2px 6px;
    border-radius: var(--r);
    transition: color 0.12s, background 0.12s;
  }

  .btn-close-trade:hover { color: var(--red); background: var(--red-dim); }

  .buy-side { color: var(--green); font-weight: 600; }
  .sell-side { color: var(--red); font-weight: 600; }

  .empty-state {
    padding: 16px 0;
    text-align: center;
    font-size: 11px;
    color: var(--t3);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Order Entry
     ═══════════════════════════════════════════════════════════════════ */
  .order-panel {
    flex-shrink: 0;
    border-bottom: 1px solid var(--b1);
  }

  .order-body {
    display: flex;
    flex-direction: column;
    gap: 7px;
    padding: 10px !important;
  }

  .form-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .form-row-split {
    display: flex;
    gap: 6px;
  }

  .form-col {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .form-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    width: 48px;
    flex-shrink: 0;
    text-align: right;
  }

  .form-col .form-label {
    width: auto;
    min-width: 32px;
  }

  .form-input {
    flex: 1;
    background: var(--bg2);
    border: 1px solid var(--b2);
    color: var(--t1);
    padding: 4px 8px;
    border-radius: var(--r);
    font-family: inherit;
    font-size: 12px;
    min-width: 0;
  }

  .form-input:focus { border-color: var(--accent); outline: none; }

  select.form-input { cursor: pointer; }

  .radio-group {
    display: flex;
    gap: 8px;
    flex: 1;
  }

  .radio-option {
    font-size: 11px;
    color: var(--t2);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 3px;
  }

  .radio-option input[type="radio"] {
    accent-color: var(--accent);
  }

  .order-buttons {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }

  .btn-buy, .btn-sell {
    flex: 1;
    padding: 6px 0;
    border: none;
    border-radius: var(--r);
    font-family: inherit;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.06em;
    cursor: pointer;
    transition: opacity 0.12s, filter 0.12s;
  }

  .btn-buy {
    background: var(--green-dim);
    color: var(--green);
    border: 1px solid var(--green-brd);
  }

  .btn-buy:hover:not(:disabled) { filter: brightness(1.2); }

  .btn-sell {
    background: var(--red-dim);
    color: var(--red);
    border: 1px solid var(--red-brd);
  }

  .btn-sell:hover:not(:disabled) { filter: brightness(1.2); }

  .btn-buy:disabled, .btn-sell:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .order-feedback {
    font-size: 10px;
    padding: 4px 8px;
    border-radius: var(--r);
    text-align: center;
    animation: fade-in 0.2s ease;
  }

  .feedback-success { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-brd); }
  .feedback-error { background: var(--red-dim); color: var(--red); border: 1px solid var(--red-brd); }

  @keyframes fade-in {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Symbol search dropdown */
  .symbol-search-wrap {
    position: relative;
    flex: 1;
  }

  .search-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    max-height: 240px;
    overflow-y: auto;
    background: var(--bg1);
    border: 1px solid var(--b2);
    border-top: none;
    border-radius: 0 0 var(--r-md) var(--r-md);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  }

  .search-row {
    all: unset;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    cursor: pointer;
    width: 100%;
    box-sizing: border-box;
    transition: background 0.1s;
  }

  .search-row:hover { background: var(--bg3); }

  .search-symbol {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent);
    min-width: 56px;
  }

  .search-name {
    font-size: 10px;
    color: var(--t2);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .search-type {
    font-size: 8px;
    color: var(--t3);
    background: var(--bg3);
    padding: 1px 4px;
    border-radius: var(--r);
    text-transform: uppercase;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Risk Calculator
     ═══════════════════════════════════════════════════════════════════ */
  .risk-panel {
    flex-shrink: 0;
    border-bottom: 1px solid var(--b1);
  }

  .risk-head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    background: var(--bg2);
    border: none;
    border-bottom: 1px solid var(--b1);
    flex-shrink: 0;
    cursor: pointer;
    width: 100%;
    text-align: left;
    font-family: inherit;
  }

  .risk-title {
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }

  .risk-body {
    padding: 8px 10px;
    overflow: auto;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .toggle-arrow {
    margin-left: auto;
    font-size: 10px;
    color: var(--t3);
    transition: transform 0.2s ease;
  }

  .toggle-arrow.collapsed {
    transform: rotate(-90deg);
  }

  .risk-output {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 12px;
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    padding: 8px 10px;
    font-size: 10px;
    margin-top: 2px;
  }

  .risk-label {
    color: var(--t3);
  }

  .risk-value {
    text-align: right;
    font-weight: 600;
    color: var(--t1);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Signals
     ═══════════════════════════════════════════════════════════════════ */
  .signals-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .signals-body {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .signal-card {
    all: unset;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 8px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    transition: border-color 0.12s, background 0.12s;
  }

  .signal-card:hover {
    border-color: var(--accent-brd);
    background: var(--bg3);
  }

  .signal-top {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .signal-symbol {
    font-size: 11px;
    font-weight: 700;
    color: var(--accent);
  }

  .signal-dir {
    font-size: 10px;
    font-weight: 600;
  }

  .signal-conf {
    margin-left: auto;
    font-size: 9px;
    color: var(--t2);
    background: var(--bg3);
    padding: 0 5px;
    border-radius: var(--r);
  }

  .signal-bottom {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .signal-strategy {
    font-size: 9px;
    color: var(--t3);
  }

  .signal-time {
    font-size: 9px;
    color: var(--t3);
    margin-left: auto;
  }
</style>
