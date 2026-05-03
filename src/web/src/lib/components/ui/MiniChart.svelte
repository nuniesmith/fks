<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createSSE } from '$stores/sse';
  import type { IChartApi, ISeriesApi } from 'lightweight-charts';

  interface CandleBar {
    timestamp: number; // ms
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }

  interface BarUpdate {
    time: number | string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }

  let {
    symbol = 'MGC',
    interval = '5m',
    height = '100%',
    showToolbar = true,
  } = $props<{
    symbol?: string;
    interval?: string;
    height?: string;
    showToolbar?: boolean;
  }>();

  // API symbol strips slashes: BTC/USD → BTC
  const apiSymbol = $derived(symbol.includes('/') ? symbol.split('/')[0] : symbol);

  let container: HTMLDivElement;
  let chart: IChartApi | null = null;
  let series: ISeriesApi<'Candlestick'> | null = null;
  let loading = $state(true);
  let barSSE: ReturnType<typeof createSSE<BarUpdate>> | null = null;
  let sseUnsub: (() => void) | null = null;

  async function initChart() {
    if (!container) return;
    loading = true;

    const { createChart } = await import('lightweight-charts');

    if (chart) chart.remove();

    chart = createChart(container, {
      layout: {
        background: { type: 'solid' as any, color: '#07070d' },
        textColor: '#8890b8',
        fontFamily: "'SF Mono', 'Fira Code', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: '#1a1a2e' },
        horzLines: { color: '#1a1a2e' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1a1a2e', minimumWidth: 50 },
      timeScale: {
        borderColor: '#1a1a2e',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    series = chart.addCandlestickSeries({
      upColor: '#16c784',
      downColor: '#ea3943',
      borderUpColor: '#16c784',
      borderDownColor: '#ea3943',
      wickUpColor: '#16c784',
      wickDownColor: '#ea3943',
    });

    try {
      // Use /candles endpoint — returns flat array with ms timestamps
      const res = await fetch(
        `/bars/${encodeURIComponent(apiSymbol)}/candles?interval=${interval}&days_back=3&limit=500`,
        { headers: { Accept: 'application/json' } }
      );
      const data = await res.json();

      if (Array.isArray(data.candles) && data.candles.length > 0) {
        const candles = (data.candles as CandleBar[]).map((c) => ({
          time: Math.floor(c.timestamp / 1000) as any,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));
        series?.setData(candles);
        chart?.timeScale().fitContent();
      }
    } catch (e) {
      console.warn(`[MiniChart] Failed to load ${symbol}:`, e);
    } finally {
      loading = false;
    }

    // SSE live bars (works for futures; crypto gets bar events via engine too)
    cleanupSSE();
    barSSE = createSSE<BarUpdate>(`/sse/bars/${symbol}`, { eventName: 'bar' });
    sseUnsub = barSSE.subscribe((bar) => {
      if (bar && series) {
        try {
          const time = typeof bar.time === 'number'
            ? bar.time
            : Math.floor(new Date(bar.time).getTime() / 1000);
          series.update({
            time: time as any,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
          });
        } catch { /* ignore */ }
      }
    });
    barSSE.connect();
  }

  function cleanupSSE() {
    if (sseUnsub) { sseUnsub(); sseUnsub = null; }
    if (barSSE) { barSSE.disconnect(); barSSE = null; }
  }

  onMount(() => {
    initChart();

    const ro = new ResizeObserver(() => {
      if (chart && container) {
        chart.applyOptions({
          width: container.clientWidth,
          height: container.clientHeight,
        });
      }
    });
    ro.observe(container);

    return () => ro.disconnect();
  });

  onDestroy(() => {
    cleanupSSE();
    chart?.remove();
    chart = null;
  });

  // Re-initialize when symbol or interval changes
  $effect(() => {
    void symbol;
    void interval;
    if (container && chart) {
      initChart();
    }
  });
</script>

<div class="mini-chart" style:height>
  {#if showToolbar}
    <div class="mc-toolbar">
      <span class="mc-symbol">{symbol}</span>
      <span class="mc-interval">{interval}</span>
    </div>
  {/if}
  <div class="mc-body" bind:this={container}>
    {#if loading}
      <div class="mc-loading">
        <div class="mc-spinner"></div>
      </div>
    {/if}
  </div>
</div>

<style>
  .mini-chart {
    display: flex;
    flex-direction: column;
    background: var(--bg0, #07070d);
    border: 1px solid var(--b2, #2a2a3e);
    border-radius: var(--r-md, 6px);
    overflow: hidden;
    min-height: 120px;
  }
  .mc-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    background: var(--bg1, #0c0c18);
    border-bottom: 1px solid var(--b1, #1a1a2e);
    flex-shrink: 0;
  }
  .mc-symbol {
    font-size: 11px;
    font-weight: 700;
    color: var(--accent, #6366f1);
  }
  .mc-interval {
    font-size: 9px;
    color: var(--t3, #555);
    text-transform: uppercase;
  }
  .mc-body {
    flex: 1;
    min-height: 0;
    position: relative;
  }
  .mc-loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 5;
  }
  .mc-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--b2, #2a2a3e);
    border-top-color: var(--cyan, #00e5ff);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
