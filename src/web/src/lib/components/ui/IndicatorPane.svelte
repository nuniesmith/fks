<script lang="ts">
  // Generic oscillator sub-pane for /charts. One lightweight-charts instance per
  // indicator, time-scale-synced to the main chart, rendering each response key
  // as a line series. Self-contained lifecycle (create on mount, reload on
  // symbol/interval change, destroy on unmount) so the picker can add/remove any
  // separate-pane indicator from the catalog without bespoke per-indicator code.
  import { onMount, onDestroy } from 'svelte';
  import { api } from '$api/client';
  import type { IChartApi } from 'lightweight-charts';

  interface IndicatorPoint { time: number; value: number; }

  let {
    symbol,
    interval,
    id,
    label,
    keys,
    mainChart,
    onremove,
  }: {
    symbol: string;
    interval: string;
    id: string;
    label: string;
    keys: string[];
    mainChart: IChartApi | null;
    onremove: () => void;
  } = $props();

  let el: HTMLDivElement = $state(null!);
  let chart: IChartApi | null = null;
  let series: any[] = [];
  let loading = $state(true);
  let empty = $state(false);
  let chartReady = $state(false);
  let rangeHandler: ((r: any) => void) | null = null;
  let ro: ResizeObserver | null = null;

  const PALETTE = ['#6366f1', '#22d3ee', '#f472b6', '#a3e635', '#fbbf24', '#fb923c'];
  const apiSymbol = (s: string) => (s.includes('/') ? s.split('/')[0] : s);

  async function load() {
    if (!chart) return;
    loading = true;
    try {
      const res = await api.get<{ indicators?: Record<string, IndicatorPoint[]> }>(
        `/api/chart/${encodeURIComponent(apiSymbol(symbol))}/indicators?interval=${interval}&days_back=5&indicators=${encodeURIComponent(id)}`
      );
      const ind = res.indicators ?? {};
      for (const s of series) { try { chart.removeSeries(s); } catch { /* gone */ } }
      series = [];
      let any = false;
      keys.forEach((key, ci) => {
        const data = ind[key] ?? [];
        const s = chart!.addLineSeries({
          color: PALETTE[ci % PALETTE.length], lineWidth: 1,
          priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
          title: key,
        });
        s.setData(data as any);
        series.push(s);
        if (data.length) any = true;
      });
      empty = !any;
      chart.timeScale().fitContent();
    } catch (e) {
      console.warn('[IndicatorPane] load failed', id, e);
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    const { createChart } = await import('lightweight-charts');
    chart = createChart(el, {
      layout: {
        background: { type: 'solid' as any, color: '#07070d' },
        textColor: '#8890b8',
        fontFamily: "'SF Mono', 'Fira Code', monospace",
        fontSize: 9,
      },
      grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#0d0d1a' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1a1a2e', minimumWidth: 44 },
      timeScale: { borderColor: '#1a1a2e', timeVisible: true, secondsVisible: false },
      handleScale: false,
      handleScroll: false,
    });
    // Follow the main chart's visible range (one-directional → no feedback loops
    // between multiple panes).
    if (mainChart && chart) {
      rangeHandler = (range: any) => { if (range && chart) chart.timeScale().setVisibleLogicalRange(range); };
      mainChart.timeScale().subscribeVisibleLogicalRangeChange(rangeHandler);
      const r = mainChart.timeScale().getVisibleLogicalRange();
      if (r) chart.timeScale().setVisibleLogicalRange(r);
    }
    if (el && chart) {
      ro = new ResizeObserver(() => {
        if (chart && el) chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
      });
      ro.observe(el);
    }
    chartReady = true;
  });

  onDestroy(() => {
    if (ro) { ro.disconnect(); ro = null; }
    if (mainChart && rangeHandler) {
      try { mainChart.timeScale().unsubscribeVisibleLogicalRangeChange(rangeHandler); } catch { /* gone */ }
    }
    if (chart) { try { chart.remove(); } catch { /* gone */ } chart = null; }
  });

  // Load once the chart exists, then reload whenever symbol/interval change.
  $effect(() => {
    const _key = `${symbol}|${interval}`; // track symbol + interval
    if (chartReady) {
      void _key;
      load();
    }
  });
</script>

<div class="ind-pane" role="region" aria-label="{label} indicator">
  <div class="pane-head">
    <span class="pane-label">{label}</span>
    <button class="pane-x" onclick={onremove} title="Remove {label}" aria-label="Remove {label}">×</button>
  </div>
  <div class="pane-chart" bind:this={el}></div>
  {#if !loading && empty}
    <div class="pane-empty">no data</div>
  {/if}
</div>

<style>
  .ind-pane {
    position: relative;
    height: 110px;
    border-top: 1px solid var(--b1, #1a1a2e);
    flex-shrink: 0;
  }
  .pane-head {
    position: absolute;
    top: 2px;
    left: 6px;
    right: 6px;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    pointer-events: none;
  }
  .pane-label {
    font-size: 9px;
    color: var(--t3, #8890b8);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .pane-x {
    pointer-events: auto;
    background: none;
    border: none;
    color: var(--t3, #8890b8);
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    padding: 0 4px;
  }
  .pane-x:hover { color: var(--red, #ea3943); }
  .pane-chart { width: 100%; height: 100%; }
  .pane-empty {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--t3, #8890b8);
    pointer-events: none;
  }
</style>
