<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { createSSE } from '$stores/sse';
  import { api } from '$api/client';
  import { focusSymbol } from '$stores/focusSymbol';
  import Panel from '$components/ui/Panel.svelte';
  import DrawingTools from '$components/ui/DrawingTools.svelte';
  import type { IChartApi, ISeriesApi } from 'lightweight-charts';

  // ─── Types ─────────────────────────────────────────────────────────────────
  interface CandleBar {
    timestamp: number; // ms
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }

  interface CandleData {
    time: any;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }

  interface BarUpdate {
    time: number | string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
  }

  interface AssetSearchResult {
    symbol: string;
    name?: string;
    type?: string;
    exchange?: string;
  }

  interface AssetInfo {
    type?: string;
    source?: string;
    source_chain?: string[];
    ws_url?: string;
    provider_symbols?: Record<string, string>;
  }

  interface IndicatorPoint {
    time: number;
    value: number;
  }

  // ─── Kraken WS interval mapping ────────────────────────────────────────────
  const TF_TO_KRAKEN: Record<string, number> = {
    '1m': 1, '5m': 5, '15m': 15, '30m': 30,
    '1h': 60, '4h': 240, '1D': 1440, '1W': 10080,
  };

  // ─── Binance WS interval mapping ───────────────────────────────────────────
  const TF_TO_BINANCE: Record<string, string> = {
    '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
    '1h': '1h', '4h': '4h', '1D': '1d', '1W': '1w',
  };

  // ─── State ─────────────────────────────────────────────────────────────────
  let symbol = $state('MGC');
  let interval = $state('5m');

  // API symbol: strips slash — BTC/USD → BTC, MGC → MGC
  let apiSymbol = $derived(symbol.includes('/') ? symbol.split('/')[0] : symbol);
  // Kraken ticker format: BTC/USD or BTC → BTC/USD
  let krakenTicker = $derived(
    symbol.includes('/') ? symbol : `${symbol}/USD`
  );

  // Asset routing (REG-C)
  let assetInfo = $state<AssetInfo>({});
  let isCrypto = $derived(
    symbol.includes('/') ||
    assetInfo.source === 'kraken' ||
    assetInfo.source === 'binance' ||
    (assetInfo.source_chain ?? [])[0] === 'kraken' ||
    (assetInfo.source_chain ?? [])[0] === 'binance'
  );
  // Active data source ('kraken' | 'binance' | 'sse' | 'none')
  let activeSource = $state<'kraken' | 'binance' | 'sse' | 'none'>('none');
  let dataSource = $derived(
    activeSource === 'binance' ? 'Binance WS'
    : activeSource === 'kraken' ? 'Kraken WS'
    : isCrypto ? 'Kraken WS'
    : 'SSE bars'
  );

  // Kraken WS connection state
  let krakenWS = $state<WebSocket | null>(null);
  let krakenConnected = $state(false);
  let krakenReconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let krakenFailTimer: ReturnType<typeof setTimeout> | null = null;

  // Binance WS connection state (fallback)
  let binanceWS = $state<WebSocket | null>(null);
  let binanceConnected = $state(false);
  let binanceReconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let binanceReconnectDelay = 1000; // ms, doubles on each failure (cap 30 s)

  // Chart instances
  let chartContainer: HTMLDivElement = $state(null!);
  let rsiChartEl: HTMLDivElement | null = $state(null);
  let chart: IChartApi | null = $state(null);
  let rsiChart: IChartApi | null = null;
  let macdChartEl: HTMLDivElement | null = $state(null);
  let macdChart: IChartApi | null = null;

  // Primary series
  let candleSeries: ISeriesApi<'Candlestick'> | null = $state(null);

  // Overlay series
  let ema9Series: any = null;
  let ema21Series: any = null;
  let volumeSeries: any = null;
  let bbUpperSeries: any = null;
  let bbMidSeries: any = null;
  let bbLowSeries: any = null;
  let rsiSeries: any = null;

  // MACD sub-pane series
  let macdHistSeries: any = null;
  let macdLineSeries: any = null;
  let macdSignalSeries: any = null;

  // ATR price overlay
  let atrSeries: any = null;

  // Candle cache for client-side indicators
  let candles = $state<CandleData[]>([]);

  // SSE bars (futures)
  let barSSE: ReturnType<typeof createSSE<BarUpdate>> | null = null;

  // Indicator toggle state
  let showEma9 = $state(false);
  let showEma21 = $state(false);
  let showVolume = $state(false);
  let showBB = $state(false);
  let showRSI = $state(false);
  let showMACD = $state(false);
  let showATR  = $state(false);
  let drawingActive = $state(false);

  // Loading state
  let loading = $state(true);
  let indicatorLoading = $state(false);

  // Auto-focus symbol from strip SSE
  let ignoreNextFocusChange = false;
  $effect(() => {
    const unsub = focusSymbol.subscribe((sym) => {
      if (sym && sym !== symbol && !ignoreNextFocusChange) {
        symbol = sym;
        if (chart) loadChart();
      }
      ignoreNextFocusChange = false;
    });
    return unsub;
  });

  // RSI pane init when it mounts
  $effect(() => {
    if (showRSI && rsiChartEl && !rsiChart) {
      initRSIChart();
    }
    if (!showRSI && rsiChart) {
      rsiChart.remove();
      rsiChart = null;
      rsiSeries = null;
    }
  });

  // MACD pane init when it mounts
  $effect(() => {
    if (showMACD && macdChartEl && !macdChart) {
      initMACDChart();
    }
    if (!showMACD && macdChart) {
      macdChart.remove();
      macdChart = null;
      macdHistSeries = null;
      macdLineSeries = null;
      macdSignalSeries = null;
    }
  });

  // ─── Timeframes ────────────────────────────────────────────────────────────
  const timeframes = [
    { id: '1m', label: '1m' }, { id: '5m', label: '5m' },
    { id: '15m', label: '15m' }, { id: '30m', label: '30m' },
    { id: '1h', label: '1H' }, { id: '4h', label: '4H' },
    { id: '1D', label: '1D' }, { id: '1W', label: '1W' },
  ];

  // ─── Quick picks ───────────────────────────────────────────────────────────
  const quickPicks = ['MGC', 'MES', 'MNQ', 'MCL', 'BTC/USD', 'ETH/USD', 'SOL/USD'];

  // ─── Symbol search ─────────────────────────────────────────────────────────
  let searchQuery = $state('');
  let searchResults = $state<AssetSearchResult[]>([]);
  let showDropdown = $state(false);
  let searchTimeout: ReturnType<typeof setTimeout> | null = null;

  // ─── EMA (client-side) ─────────────────────────────────────────────────────
  function calcEMA(data: CandleData[], period: number): { time: any; value: number }[] {
    if (data.length < period) return [];
    const k = 2 / (period + 1);
    const result: { time: any; value: number }[] = [];
    let sum = 0;
    for (let i = 0; i < period; i++) sum += data[i].close;
    let ema = sum / period;
    result.push({ time: data[period - 1].time, value: ema });
    for (let i = period; i < data.length; i++) {
      ema = data[i].close * k + ema * (1 - k);
      result.push({ time: data[i].time, value: ema });
    }
    return result;
  }

  // ─── Overlay management ───────────────────────────────────────────────────
  function addEma9() {
    if (!chart || ema9Series) return;
    ema9Series = chart.addLineSeries({
      color: '#00e5ff', lineWidth: 1,
      priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false, title: 'EMA 9',
    });
    ema9Series.setData(calcEMA(candles, 9));
  }
  function removeEma9() {
    if (!chart || !ema9Series) return;
    chart.removeSeries(ema9Series);
    ema9Series = null;
  }

  function addEma21() {
    if (!chart || ema21Series) return;
    ema21Series = chart.addLineSeries({
      color: '#b388ff', lineWidth: 1,
      priceLineVisible: false, lastValueVisible: false,
      crosshairMarkerVisible: false, title: 'EMA 21',
    });
    ema21Series.setData(calcEMA(candles, 21));
  }
  function removeEma21() {
    if (!chart || !ema21Series) return;
    chart.removeSeries(ema21Series);
    ema21Series = null;
  }

  function addVolume() {
    if (!chart || volumeSeries) return;
    volumeSeries = chart.addHistogramSeries({
      color: '#26a69a80', priceFormat: { type: 'volume' },
      priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false,
    });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, borderVisible: false });
    volumeSeries.setData(candles.map((c) => ({
      time: c.time, value: c.volume,
      color: c.close >= c.open ? '#16c78440' : '#ea394340',
    })));
  }
  function removeVolume() {
    if (!chart || !volumeSeries) return;
    chart.removeSeries(volumeSeries);
    volumeSeries = null;
  }

  function refreshOverlays() {
    if (showEma9 && ema9Series) ema9Series.setData(calcEMA(candles, 9));
    if (showEma21 && ema21Series) ema21Series.setData(calcEMA(candles, 21));
    if (showVolume && volumeSeries) {
      volumeSeries.setData(candles.map((c) => ({
        time: c.time, value: c.volume,
        color: c.close >= c.open ? '#16c78440' : '#ea394340',
      })));
    }
  }

  function updateCandleCache(candle: CandleData) {
    const last = candles.length - 1;
    if (last >= 0 && candles[last].time === candle.time) {
      candles[last] = candle;
      candles = candles; // trigger reactivity
    } else {
      candles = [...candles, candle];
    }
    refreshOverlays();
    // Live-update RSI series if open
    if (showRSI && rsiSeries && candles.length >= 14) {
      // We don't recalc server-side RSI on every tick — that would be too many API calls.
      // The RSI pane shows the last server fetch; a refresh button can be used.
    }
  }

  // ─── Server-side indicators ────────────────────────────────────────────────
  async function loadBBands() {
    if (!chart) return;
    // Remove stale series
    if (bbUpperSeries) { chart.removeSeries(bbUpperSeries); bbUpperSeries = null; }
    if (bbMidSeries)   { chart.removeSeries(bbMidSeries);   bbMidSeries = null; }
    if (bbLowSeries)   { chart.removeSeries(bbLowSeries);   bbLowSeries = null; }
    if (!showBB) return;

    try {
      const res = await api.get<{ indicators?: Record<string, IndicatorPoint[]> }>(
        `/api/chart/${encodeURIComponent(apiSymbol)}/indicators?interval=${interval}&days_back=5&indicators=bbands`
      );
      const ind = res.indicators ?? {};
      if (ind.bb_upper?.length && chart) {
        const lineOpts = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
        bbUpperSeries = chart.addLineSeries({ ...lineOpts, color: '#ffa72680', lineWidth: 1, title: 'BB+' });
        bbUpperSeries.setData(ind.bb_upper);
        bbMidSeries = chart.addLineSeries({ ...lineOpts, color: '#ffa72640', lineWidth: 1, lineStyle: 2 });
        bbMidSeries.setData(ind.bb_middle ?? []);
        bbLowSeries = chart.addLineSeries({ ...lineOpts, color: '#ffa72680', lineWidth: 1, title: 'BB-' });
        bbLowSeries.setData(ind.bb_lower ?? []);
      }
    } catch (e) {
      console.warn('[charts] BBands load failed:', e);
    }
  }

  async function initRSIChart() {
    if (!rsiChartEl) return;
    const { createChart } = await import('lightweight-charts');
    if (rsiChart) rsiChart.remove();

    rsiChart = createChart(rsiChartEl, {
      layout: {
        background: { type: 'solid' as any, color: '#07070d' },
        textColor: '#8890b8',
        fontFamily: "'SF Mono', 'Fira Code', monospace",
        fontSize: 9,
      },
      grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#0d0d1a' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1a1a2e', minimumWidth: 40 },
      timeScale: { borderColor: '#1a1a2e', timeVisible: true, secondsVisible: false },
      handleScale: false,
      handleScroll: false,
    });

    rsiSeries = rsiChart.addLineSeries({
      color: '#6366f1', lineWidth: 1,
      priceLineVisible: false, lastValueVisible: true,
    });

    // Overbought / oversold reference lines
    const rsiRef = rsiChart.addLineSeries({
      color: '#ea394330', lineWidth: 1, lineStyle: 1,
      priceLineVisible: false, lastValueVisible: false,
    });

    await loadRSIData(rsiRef);

    // Sync time scale with main chart
    if (chart) {
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range && rsiChart) rsiChart.timeScale().setVisibleLogicalRange(range);
      });
      rsiChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range && chart) chart.timeScale().setVisibleLogicalRange(range);
      });
    }
  }

  async function loadRSIData(refSeries?: any) {
    if (!rsiSeries) return;
    indicatorLoading = true;
    try {
      const res = await api.get<{ indicators?: Record<string, IndicatorPoint[]> }>(
        `/api/chart/${encodeURIComponent(apiSymbol)}/indicators?interval=${interval}&days_back=5&indicators=rsi`
      );
      const rsiData = res.indicators?.rsi ?? [];
      rsiSeries.setData(rsiData);
      rsiChart?.timeScale().fitContent();

      // Overbought/oversold dashed reference lines
      if (refSeries && rsiData.length > 1) {
        const times = [rsiData[0].time, rsiData[rsiData.length - 1].time];
        refSeries.setData(
          [...times.map((t) => ({ time: t, value: 70 })),
           ...times.map((t) => ({ time: t, value: 30 }))]
            .sort((a, b) => a.time - b.time)
        );
      }
    } catch (e) {
      console.warn('[charts] RSI load failed:', e);
    } finally {
      indicatorLoading = false;
    }
  }

  // ─── ATR overlay (server-side, price axis) ─────────────────────────────────
  async function loadATR() {
    if (!chart) return;
    if (atrSeries) { chart.removeSeries(atrSeries); atrSeries = null; }
    if (!showATR) return;
    indicatorLoading = true;
    try {
      const res = await api.get<{ indicators?: Record<string, IndicatorPoint[]> }>(
        `/api/chart/${encodeURIComponent(apiSymbol)}/indicators?interval=${interval}&days_back=5&indicators=atr`
      );
      const atrData = res.indicators?.atr ?? [];
      if (atrData.length && chart) {
        atrSeries = chart.addLineSeries({
          color: '#f59e0b',
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: false,
          title: 'ATR 14',
          priceScaleId: 'atr',
        });
        chart.priceScale('atr').applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
          borderVisible: false,
        });
        atrSeries.setData(atrData);
      }
    } catch (e) {
      console.warn('[charts] ATR load failed:', e);
    } finally {
      indicatorLoading = false;
    }
  }

  // ─── MACD sub-pane ─────────────────────────────────────────────────────────
  async function initMACDChart() {
    if (!macdChartEl) return;
    const { createChart } = await import('lightweight-charts');
    if (macdChart) macdChart.remove();

    macdChart = createChart(macdChartEl, {
      layout: {
        background: { type: 'solid' as any, color: '#07070d' },
        textColor: '#8890b8',
        fontFamily: "'SF Mono', 'Fira Code', monospace",
        fontSize: 9,
      },
      grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#0d0d1a' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1a1a2e', minimumWidth: 40 },
      timeScale: { borderColor: '#1a1a2e', timeVisible: true, secondsVisible: false },
      handleScale: false,
      handleScroll: false,
    });

    // Histogram bars (green above zero, red below)
    macdHistSeries = macdChart.addHistogramSeries({
      priceLineVisible: false,
      lastValueVisible: false,
    });
    // Zero reference line on the histogram
    macdHistSeries.createPriceLine({
      price: 0,
      color: '#444466',
      lineWidth: 1,
      lineStyle: 0,
      axisLabelVisible: false,
    });

    // MACD line (blue)
    macdLineSeries = macdChart.addLineSeries({
      color: '#2196f3',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
      title: 'MACD',
    });

    // Signal line (orange)
    macdSignalSeries = macdChart.addLineSeries({
      color: '#ff9800',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
      title: 'Signal',
    });

    await loadMACDData();

    // Sync time scale with main chart (bi-directional)
    if (chart) {
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range && macdChart) macdChart.timeScale().setVisibleLogicalRange(range);
      });
      macdChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (range && chart) chart.timeScale().setVisibleLogicalRange(range);
      });
    }
  }

  async function loadMACDData() {
    if (!macdHistSeries || !macdLineSeries || !macdSignalSeries) return;
    indicatorLoading = true;
    try {
      const res = await api.get<{ indicators?: Record<string, IndicatorPoint[]> }>(
        `/api/chart/${encodeURIComponent(apiSymbol)}/indicators?interval=${interval}&days_back=5&indicators=macd`
      );
      const ind = res.indicators ?? {};
      // Histogram bars: green above zero, red below
      const histData = (ind.macd_hist ?? []).map((p: IndicatorPoint) => ({
        time: p.time,
        value: p.value,
        color: p.value >= 0 ? '#26a69a80' : '#ef535080',
      }));
      macdHistSeries.setData(histData);
      macdLineSeries.setData(ind.macd_line ?? []);
      macdSignalSeries.setData(ind.macd_signal ?? []);
      macdChart?.timeScale().fitContent();
    } catch (e) {
      console.warn('[charts] MACD load failed:', e);
    } finally {
      indicatorLoading = false;
    }
  }

  // ─── Asset registry lookup (REG-C) ────────────────────────────────────────
  async function lookupAsset(sym: string) {
    const short = sym.split('/')[0];
    try {
      const data = await api.get<AssetInfo>(`/api/assets/${encodeURIComponent(short)}`);
      assetInfo = data;
    } catch {
      // Fallback heuristic: slash means crypto
      assetInfo = sym.includes('/')
        ? { type: 'crypto', source: 'kraken', source_chain: ['kraken'] }
        : { type: 'futures', source: 'rithmic', source_chain: ['rithmic'] };
    }
  }

  // ─── Kraken WebSocket (CHART-B) ────────────────────────────────────────────
  function disconnectKrakenWS() {
    if (krakenReconnectTimer) { clearTimeout(krakenReconnectTimer); krakenReconnectTimer = null; }
    if (krakenFailTimer)      { clearTimeout(krakenFailTimer);      krakenFailTimer = null; }
    if (krakenWS) {
      krakenWS.onclose = null; // prevent auto-reconnect
      krakenWS.close();
      krakenWS = null;
    }
    krakenConnected = false;
  }

  function connectKrakenWS(ticker: string) {
    disconnectKrakenWS();
    const minutes = TF_TO_KRAKEN[interval] ?? 1;

    const ws = new WebSocket('wss://ws.kraken.com/v2');
    krakenWS = ws;

    // 5-second guard: if no OHLC data arrives, fall back to Binance
    krakenFailTimer = setTimeout(() => {
      krakenFailTimer = null;
      if (activeSource !== 'kraken' && isCrypto) {
        console.warn('[KrakenWS] 5 s timeout — falling back to Binance');
        disconnectKrakenWS();
        connectBinanceWS(symbol, interval);
      }
    }, 5000);

    ws.onopen = () => {
      krakenConnected = true;
      ws.send(JSON.stringify({
        method: 'subscribe',
        params: { channel: 'ohlc', symbol: [ticker], interval: minutes },
      }));
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as any;
        if (msg.channel === 'ohlc' && Array.isArray(msg.data)) {
          // First OHLC frame confirms Kraken is delivering data — cancel fallback timer
          if (krakenFailTimer) { clearTimeout(krakenFailTimer); krakenFailTimer = null; }
          activeSource = 'kraken';
          for (const bar of msg.data) {
            // interval_begin is the candle open time
            const time = Math.floor(new Date(bar.interval_begin as string).getTime() / 1000);
            const candle: CandleData = {
              time: time as any,
              open: parseFloat(bar.open),
              high: parseFloat(bar.high),
              low: parseFloat(bar.low),
              close: parseFloat(bar.close),
              volume: parseFloat(bar.volume ?? bar.volume_buy ?? '0'),
            };
            if (candleSeries) candleSeries.update(candle);
            updateCandleCache(candle);
          }
        }
      } catch { /* ignore malformed */ }
    };

    ws.onerror = () => {
      console.warn('[KrakenWS] connection error for', ticker);
      // Cancel fail timer and immediately switch to Binance
      if (krakenFailTimer) { clearTimeout(krakenFailTimer); krakenFailTimer = null; }
      if (activeSource !== 'binance' && isCrypto) {
        disconnectKrakenWS();
        connectBinanceWS(symbol, interval);
      }
    };

    ws.onclose = () => {
      krakenConnected = false;
      if (activeSource === 'kraken') {
        // Was actively delivering — attempt a Kraken reconnect cycle
        activeSource = 'none';
        if (krakenWS === ws && isCrypto) {
          krakenReconnectTimer = setTimeout(() => {
            if (isCrypto) connectKrakenWS(ticker);
          }, 5000);
        }
      }
      // activeSource === 'binance' → Binance already running, leave it alone
      // activeSource === 'none'    → fail timer already scheduled the fallback
    };
  }

  // ─── Binance WebSocket (fallback) ──────────────────────────────────────────
  /**
   * Map an FKS symbol to a Binance lowercase USDT pair.
   * Uses `provider_symbols.binance` from the registry when available;
   * otherwise derives it from the base symbol (e.g. BTC/USD → btcusdt).
   */
  function toBinanceSymbol(sym: string): string {
    const regSym = assetInfo.provider_symbols?.binance;
    if (regSym) return regSym.toLowerCase();
    const base = sym.includes('/') ? sym.split('/')[0] : sym;
    const norm = base.toUpperCase() === 'XBT' ? 'BTC' : base.toUpperCase();
    return `${norm.toLowerCase()}usdt`;
  }

  function disconnectBinanceWS() {
    if (binanceReconnectTimer) { clearTimeout(binanceReconnectTimer); binanceReconnectTimer = null; }
    if (binanceWS) {
      binanceWS.onclose = null; // prevent auto-reconnect
      binanceWS.close();
      binanceWS = null;
    }
    binanceConnected = false;
  }

  function connectBinanceWS(sym: string, tf: string) {
    disconnectBinanceWS();
    binanceReconnectDelay = 1000; // reset back-off for new connection session

    const binanceSymbol = toBinanceSymbol(sym);
    const binanceInterval = TF_TO_BINANCE[tf] ?? '1m';
    const url = `wss://stream.binance.com:9443/ws/${binanceSymbol}@kline_${binanceInterval}`;
    console.info('[BinanceWS] connecting:', url);

    const ws = new WebSocket(url);
    binanceWS = ws;

    ws.onopen = () => {
      binanceConnected = true;
      activeSource = 'binance';
      binanceReconnectDelay = 1000; // reset on successful open
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as any;
        if (msg.e === 'kline' && msg.k) {
          const k = msg.k;
          const candle: CandleData = {
            time: Math.floor(k.t / 1000) as any,
            open:   parseFloat(k.o),
            high:   parseFloat(k.h),
            low:    parseFloat(k.l),
            close:  parseFloat(k.c),
            volume: parseFloat(k.v),
          };
          if (candleSeries) candleSeries.update(candle);
          updateCandleCache(candle);
        }
      } catch { /* ignore malformed */ }
    };

    ws.onerror = () => console.warn('[BinanceWS] connection error for', binanceSymbol);

    ws.onclose = () => {
      binanceConnected = false;
      if (binanceWS === ws && isCrypto) {
        // Exponential back-off, capped at 30 s
        const delay = binanceReconnectDelay;
        binanceReconnectDelay = Math.min(binanceReconnectDelay * 2, 30_000);
        binanceReconnectTimer = setTimeout(() => {
          if (isCrypto) connectBinanceWS(sym, tf);
        }, delay);
      }
    };
  }

  // ─── SSE bars (futures) ────────────────────────────────────────────────────
  function connectBarSSE() {
    if (barSSE) barSSE.disconnect();
    barSSE = createSSE<BarUpdate>(`/sse/bars/${symbol}`, { eventName: 'bar' });
    barSSE.subscribe((bar: BarUpdate | null) => {
      if (!bar || !candleSeries) return;
      try {
        const time = typeof bar.time === 'number'
          ? bar.time
          : Math.floor(new Date(bar.time).getTime() / 1000);
        const candle: CandleData = {
          time: time as any,
          open: bar.open, high: bar.high, low: bar.low, close: bar.close,
          volume: bar.volume ?? 0,
        };
        candleSeries.update(candle);
        updateCandleCache(candle);
      } catch { /* ignore */ }
    });
    barSSE.connect();
  }

  function disconnectLiveData() {
    disconnectKrakenWS();   // also cancels krakenFailTimer
    disconnectBinanceWS();
    if (barSSE) { barSSE.disconnect(); barSSE = null; }
    activeSource = 'none';
  }

  // ─── Main chart load ───────────────────────────────────────────────────────
  async function loadChart() {
    if (!chartContainer) return;
    loading = true;

    const { createChart } = await import('lightweight-charts');

    // Tear down
    disconnectLiveData();
    ema9Series = null; ema21Series = null; volumeSeries = null;
    bbUpperSeries = null; bbMidSeries = null; bbLowSeries = null;
    atrSeries = null;
    if (chart) chart.remove();

    chart = createChart(chartContainer, {
      layout: {
        background: { type: 'solid' as any, color: '#07070d' },
        textColor: '#8890b8',
        fontFamily: "'SF Mono', 'Fira Code', monospace",
        fontSize: 11,
      },
      grid: { vertLines: { color: '#1a1a2e' }, horzLines: { color: '#1a1a2e' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1a1a2e' },
      timeScale: { borderColor: '#1a1a2e', timeVisible: true, secondsVisible: false },
    });

    candleSeries = chart.addCandlestickSeries({
      upColor: '#16c784', downColor: '#ea3943',
      borderUpColor: '#16c784', borderDownColor: '#ea3943',
      wickUpColor: '#16c784', wickDownColor: '#ea3943',
    });

    // Resolve asset data source
    await lookupAsset(symbol);

    // Fetch historical bars
    try {
      const res = await fetch(
        `/bars/${encodeURIComponent(apiSymbol)}/candles?interval=${interval}&days_back=5&limit=1000`,
        { headers: { Accept: 'application/json' } }
      );
      const data = await res.json();

      if (Array.isArray(data.candles) && data.candles.length > 0) {
        candles = (data.candles as CandleBar[]).map((c) => ({
          time: Math.floor(c.timestamp / 1000) as any,
          open: c.open, high: c.high, low: c.low, close: c.close,
          volume: c.volume ?? 0,
        }));
        candleSeries?.setData(candles);
        chart?.timeScale().fitContent();
      } else {
        candles = [];
      }
    } catch (e) {
      console.warn('[charts] Failed to load bars:', e);
      candles = [];
    } finally {
      loading = false;
    }

    // Re-add active overlays
    if (showEma9) addEma9();
    if (showEma21) addEma21();
    if (showVolume) addVolume();
    if (showBB) await loadBBands();
    if (showATR) await loadATR();

    // Reconnect RSI if open
    if (showRSI) {
      if (rsiChart) {
        // Just reload data for existing RSI chart
        await loadRSIData();
        // Re-wire time scale sync
        chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
          if (range && rsiChart) rsiChart.timeScale().setVisibleLogicalRange(range);
        });
      }
    }

    // Reconnect MACD if open
    if (showMACD) {
      if (macdChart) {
        await loadMACDData();
        chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
          if (range && macdChart) macdChart.timeScale().setVisibleLogicalRange(range);
        });
      }
    }

    // Connect live data feed — honour the registry source_chain order
    if (isCrypto) {
      const chain = assetInfo.source_chain ?? ['kraken'];
      if (chain[0] === 'binance') {
        // Asset explicitly lists Binance as primary source
        connectBinanceWS(symbol, interval);
      } else {
        // Kraken is primary; connectKrakenWS will auto-fall-back to Binance
        // after 5 s if no data arrives (or immediately on error)
        connectKrakenWS(krakenTicker);
      }
    } else {
      connectBarSSE();
    }
  }

  // ─── Indicator toggles ─────────────────────────────────────────────────────
  function toggleEma9() {
    showEma9 = !showEma9;
    if (showEma9) addEma9(); else removeEma9();
  }
  function toggleEma21() {
    showEma21 = !showEma21;
    if (showEma21) addEma21(); else removeEma21();
  }
  function toggleVolume() {
    showVolume = !showVolume;
    if (showVolume) addVolume(); else removeVolume();
  }
  async function toggleBB() {
    showBB = !showBB;
    await loadBBands();
  }
  async function toggleRSI() {
    showRSI = !showRSI;
    if (showRSI) {
      await tick(); // let DOM mount rsiChartEl
      // $effect handles initRSIChart when rsiChartEl becomes available
    }
  }
  async function toggleMACD() {
    showMACD = !showMACD;
    if (showMACD) {
      await tick(); // let DOM mount macdChartEl
      // $effect handles initMACDChart when macdChartEl becomes available
    }
  }
  async function toggleATR() {
    showATR = !showATR;
    await loadATR();
  }

  // ─── Chart export / screenshot ─────────────────────────────────────────────
  function exportChart() {
    const canvas = chartContainer.querySelector('canvas');
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `fks-chart-${symbol}-${new Date().toISOString().slice(0, 10)}.png`;
    link.href = (canvas as HTMLCanvasElement).toDataURL('image/png');
    link.click();
  }

  // ─── Symbol search ─────────────────────────────────────────────────────────
  async function handleSearch(query: string) {
    searchQuery = query;
    if (searchTimeout) clearTimeout(searchTimeout);
    if (query.length < 1) { searchResults = []; showDropdown = false; return; }
    searchTimeout = setTimeout(async () => {
      try {
        const data = await api.get<{ results?: AssetSearchResult[]; assets?: AssetSearchResult[] }>(
          `/api/assets/search?q=${encodeURIComponent(query)}`
        );
        searchResults = data.results ?? data.assets ?? [];
        showDropdown = searchResults.length > 0;
      } catch { searchResults = []; showDropdown = false; }
    }, 250);
  }

  function selectResult(result: AssetSearchResult) {
    setSymbol(result.symbol);
    searchQuery = ''; showDropdown = false;
  }

  function handleSearchKey(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      const q = searchQuery.trim().toUpperCase();
      if (q) { setSymbol(q); searchQuery = ''; showDropdown = false; }
    }
    if (e.key === 'Escape') showDropdown = false;
  }

  function setSymbol(s: string) {
    ignoreNextFocusChange = true;
    symbol = s;
    focusSymbol.set(s);
    loadChart();
  }

  function switchTimeframe(tf: string) {
    interval = tf;
    loadChart();
  }

  // ─── Lifecycle ─────────────────────────────────────────────────────────────
  onMount(() => {
    loadChart();

    const ro = new ResizeObserver(() => {
      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: chartContainer.clientHeight,
        });
      }
      if (rsiChart && rsiChartEl) {
        rsiChart.applyOptions({
          width: rsiChartEl.clientWidth,
          height: rsiChartEl.clientHeight,
        });
      }
      if (macdChart && macdChartEl) {
        macdChart.applyOptions({
          width: macdChartEl.clientWidth,
          height: macdChartEl.clientHeight,
        });
      }
    });
    ro.observe(chartContainer);

    const handleOutsideClick = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.symbol-search-wrap')) showDropdown = false;
    };
    document.addEventListener('click', handleOutsideClick);

    return () => {
      ro.disconnect();
      document.removeEventListener('click', handleOutsideClick);
    };
  });

  onDestroy(() => {
    disconnectLiveData();
    if (searchTimeout) clearTimeout(searchTimeout);
    chart?.remove(); chart = null;
    rsiChart?.remove(); rsiChart = null;
    macdChart?.remove(); macdChart = null;
  });
</script>

<svelte:head>
  <title>Charts — FKS Terminal</title>
</svelte:head>

<!-- ═══════════════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="chart-workspace">

    <!-- ── Toolbar ─────────────────────────────────────────────────────── -->
    <div class="toolbar" role="toolbar" aria-label="Chart controls">

      <!-- Symbol search -->
      <label class="lbl" for="chart-sym-search">SYMBOL</label>
      <div class="symbol-search-wrap" role="combobox" aria-expanded={showDropdown} aria-haspopup="listbox" aria-owns="chart-sym-dropdown" aria-controls="chart-sym-dropdown">
        <input
          id="chart-sym-search"
          type="text"
          class="input search-input"
          value={searchQuery || symbol}
          oninput={(e) => {
            const v = (e.target as HTMLInputElement).value;
            searchQuery = v;
            handleSearch(v);
          }}
          onfocus={() => { searchQuery = ''; if (searchResults.length) showDropdown = true; }}
          onblur={() => setTimeout(() => { searchQuery = ''; }, 200)}
          onkeydown={handleSearchKey}
          placeholder="Search assets…"
          autocomplete="off"
          spellcheck="false"
          aria-autocomplete="list"
        />
        {#if showDropdown && searchResults.length > 0}
          <div class="search-dropdown" id="chart-sym-dropdown" role="listbox" aria-label="Asset search results">
            {#each searchResults as result}
              <button
                class="search-row"
                role="option"
                aria-selected={symbol === result.symbol}
                onclick={() => selectResult(result)}
              >
                <span class="sr-symbol">{result.symbol}</span>
                {#if result.name}<span class="sr-name">{result.name}</span>{/if}
                {#if result.type}<span class="sr-type">{result.type}</span>{/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- TF tabs -->
      <div class="tf-tabs" role="radiogroup" aria-label="Timeframe">
        {#each timeframes as tf}
          <button
            class="tf-tab"
            class:active={interval === tf.id}
            onclick={() => switchTimeframe(tf.id)}
            aria-pressed={interval === tf.id ? 'true' : 'false'}
          >{tf.label}</button>
        {/each}
      </div>

      <!-- Indicators: client-side -->
      <div class="ind-group" aria-label="Overlay indicators">
        <button class="ind-btn" class:active={showEma9}  onclick={toggleEma9}  aria-pressed={showEma9 ? 'true' : 'false'}>
          <span class="ind-dot" style="background:#00e5ff"></span>EMA 9
        </button>
        <button class="ind-btn" class:active={showEma21} onclick={toggleEma21} aria-pressed={showEma21 ? 'true' : 'false'}>
          <span class="ind-dot" style="background:#b388ff"></span>EMA 21
        </button>
        <button class="ind-btn" class:active={showVolume} onclick={toggleVolume} aria-pressed={showVolume ? 'true' : 'false'}>
          <span class="ind-dot" style="background:#26a69a"></span>VOL
        </button>
        <button class="ind-btn" class:active={showBB} onclick={toggleBB} aria-pressed={showBB ? 'true' : 'false'}
          title="Bollinger Bands 20/2 (server-computed)">
          <span class="ind-dot" style="background:#ffa726"></span>BB
          {#if indicatorLoading && showBB}<span class="ind-spin"></span>{/if}
        </button>
        <button class="ind-btn" class:active={showATR} onclick={toggleATR} aria-pressed={showATR ? 'true' : 'false'}
          title="Average True Range 14 — price overlay (server-computed)">
          <span class="ind-dot" style="background:#f59e0b"></span>ATR
          {#if indicatorLoading && showATR}<span class="ind-spin"></span>{/if}
        </button>
      </div>

      <!-- Indicators: sub-pane -->
      <div class="ind-group" aria-label="Sub-pane indicators">
        <button class="ind-btn" class:active={showRSI} onclick={toggleRSI} aria-pressed={showRSI ? 'true' : 'false'}
          title="RSI 14 (server-computed)">
          <span class="ind-dot" style="background:#6366f1"></span>RSI
        </button>
        <button class="ind-btn" class:active={showMACD} onclick={toggleMACD} aria-pressed={showMACD ? 'true' : 'false'}
          title="MACD 12/26/9 — histogram + signal (server-computed)">
          <span class="ind-dot" style="background:#2196f3"></span>MACD
          {#if indicatorLoading && showMACD}<span class="ind-spin"></span>{/if}
        </button>
      </div>

      <!-- Quick picks -->
      <div class="quick-picks">
        {#each quickPicks as s}
          <button
            class="btn-ghost"
            class:active={symbol === s}
            onclick={() => setSymbol(s)}
            aria-pressed={symbol === s ? 'true' : 'false'}
          >{s.replace('/USD', '')}</button>
        {/each}
      </div>

      <!-- Drawing tools toggle -->
      <button
        class="ind-btn ml-auto"
        class:active={drawingActive}
        onclick={() => { drawingActive = !drawingActive; }}
        title="Drawing tools"
        aria-label="Toggle drawing tools"
        aria-pressed={drawingActive ? 'true' : 'false'}
      >✏️ Draw</button>

      <!-- Screenshot / export -->
      <button
        class="ind-btn"
        onclick={exportChart}
        title="Export chart as PNG"
        aria-label="Download chart screenshot"
      >📷</button>

      <!-- Multi-chart -->
      <a href="/charts/grid" class="btn-ghost" title="Multi-chart grid">▦ Grid</a>

      <!-- Status badges -->
      <div class="status-badges">
        <span class="sym-badge">{symbol}</span>
        <span class="tf-badge">{interval}</span>
        {#if isCrypto}
          {#if activeSource === 'binance'}
            <span class="src-badge binance" class:connected={binanceConnected} title="Binance WS (fallback)">
              {binanceConnected ? '⬤ BNB' : '○ BNB'}
            </span>
          {:else}
            <span class="src-badge" class:connected={krakenConnected} title="Kraken WS">
              {krakenConnected ? '⬤ KRK' : '○ KRK'}
            </span>
          {/if}
        {:else}
          <span class="src-badge sse" title="SSE bars">SSE</span>
        {/if}
      </div>
    </div>

    <!-- ── Drawing toolbar ──────────────────────────────────────────────── -->
    <DrawingTools {chartContainer} {chart} bind:active={drawingActive} />

    <!-- ── Chart body ───────────────────────────────────────────────────── -->
    <div class="chart-body">
      <!-- Main candlestick chart -->
      <div class="chart-area" bind:this={chartContainer}>
        {#if loading}
          <div class="chart-overlay">
            <div class="spinner" role="status" aria-label="Loading chart"></div>
            <span>Loading {symbol} · {interval}…</span>
          </div>
        {/if}
      </div>

      <!-- RSI sub-pane -->
      {#if showRSI}
        <div class="ind-pane" role="region" aria-label="RSI 14 indicator">
          <div class="pane-label">RSI 14</div>
          <div class="pane-chart" bind:this={rsiChartEl}></div>
          <!-- Overbought/oversold markers -->
          <div class="rsi-levels" aria-hidden="true">
            <span class="rsi-level ob">70</span>
            <span class="rsi-level os">30</span>
          </div>
        </div>
      {/if}

      <!-- MACD sub-pane -->
      {#if showMACD}
        <div class="ind-pane macd-pane" role="region" aria-label="MACD 12/26/9 indicator">
          <div class="pane-label">MACD</div>
          <div class="pane-chart" bind:this={macdChartEl}></div>
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════════ -->
<style>
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
  }

  .chart-workspace {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }

  /* ── Toolbar ─────────────────────────────────────────────────────────── */
  .toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--bg1);
    border-bottom: 1px solid var(--b2);
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .lbl {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    flex-shrink: 0;
  }

  .input {
    background: var(--bg2);
    border: 1px solid var(--b2);
    color: var(--t1);
    padding: 3px 8px;
    border-radius: var(--r);
    font-family: inherit;
    font-size: 12px;
  }
  .input:focus { border-color: var(--accent); outline: none; }

  /* Symbol typeahead */
  .symbol-search-wrap { position: relative; }
  .search-input { width: 140px; }
  .search-dropdown {
    position: absolute;
    top: 100%; left: 0;
    z-index: 200;
    min-width: 240px;
    max-height: 220px;
    overflow-y: auto;
    background: var(--bg1);
    border: 1px solid var(--b2);
    border-top: none;
    border-radius: 0 0 var(--r-md, 6px) var(--r-md, 6px);
    box-shadow: 0 8px 24px rgba(0,0,0,.6);
  }
  .search-row {
    all: unset;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    width: 100%;
    box-sizing: border-box;
    cursor: pointer;
    transition: background .1s;
  }
  .search-row:hover { background: var(--bg3); }
  .sr-symbol { font-size: 11px; font-weight: 600; color: var(--accent); min-width: 52px; }
  .sr-name { font-size: 10px; color: var(--t2); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sr-type { font-size: 8px; color: var(--t3); background: var(--bg3); padding: 1px 4px; border-radius: var(--r); text-transform: uppercase; }

  /* TF tabs */
  .tf-tabs { display: flex; gap: 2px; }
  .tf-tab {
    all: unset;
    padding: 2px 7px;
    font-size: 10px;
    color: var(--t3);
    border-radius: var(--r);
    cursor: pointer;
    font-family: inherit;
    transition: color .15s, background .15s;
  }
  .tf-tab:hover { color: var(--t2); background: var(--bg3); }
  .tf-tab.active { color: var(--t1); background: var(--accent-dim, rgba(99,102,241,.15)); }

  /* Indicator groups */
  .ind-group {
    display: flex;
    gap: 3px;
    padding-left: 8px;
    border-left: 1px solid var(--b1);
  }
  .ind-btn {
    all: unset;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 7px;
    font-size: 10px;
    color: var(--t3);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    cursor: pointer;
    font-family: inherit;
    transition: all .15s;
    white-space: nowrap;
  }
  .ind-btn:hover { color: var(--t2); background: var(--bg3); border-color: var(--b2); }
  .ind-btn.active { color: var(--t1); background: var(--bg3); border-color: var(--b2); }
  .ind-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; opacity: .45; transition: opacity .15s; }
  .ind-btn.active .ind-dot { opacity: 1; }
  .ind-spin {
    display: inline-block; width: 8px; height: 8px;
    border: 1px solid var(--b2); border-top-color: var(--accent);
    border-radius: 50%; animation: spin .7s linear infinite;
  }

  .ml-auto { margin-left: auto; }

  /* Quick picks */
  .quick-picks { display: flex; gap: 3px; }
  .btn-ghost {
    background: transparent;
    border: 1px solid var(--b1);
    color: var(--t3);
    padding: 2px 7px;
    border-radius: var(--r);
    cursor: pointer;
    font-family: inherit;
    font-size: 10px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    transition: all .15s;
  }
  .btn-ghost:hover { background: var(--bg3); color: var(--t1); }
  .btn-ghost.active { background: var(--bg3); color: var(--accent); border-color: var(--b2); }

  /* Status badges */
  .status-badges {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: 4px;
    padding-left: 8px;
    border-left: 1px solid var(--b1);
  }
  .sym-badge {
    font-size: 13px;
    font-weight: 700;
    color: var(--accent);
  }
  .tf-badge { font-size: 10px; color: var(--t3); }
  .src-badge {
    font-size: 9px;
    color: var(--t3);
    font-family: 'SF Mono', 'Fira Code', monospace;
  }
  .src-badge.connected { color: var(--green, #16c784); }
  .src-badge.sse { color: var(--cyan, #00e5ff); opacity: .6; }
  .src-badge.binance.connected { color: var(--yellow, #f0b90b); }

  /* ── Chart body ──────────────────────────────────────────────────────── */
  .chart-body {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .chart-area {
    flex: 1;
    min-height: 0;
    position: relative;
    background: var(--bg0);
  }
  .chart-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--t3);
    font-size: 12px;
    z-index: 10;
    pointer-events: none;
  }
  .spinner {
    width: 16px; height: 16px;
    border: 2px solid var(--b2);
    border-top-color: var(--cyan, #00e5ff);
    border-radius: 50%;
    animation: spin .8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── RSI sub-pane ────────────────────────────────────────────────────── */
  .ind-pane {
    height: 88px;
    flex-shrink: 0;
    border-top: 1px solid var(--b2);
    background: var(--bg0);
    display: flex;
    position: relative;
    overflow: hidden;
  }
  .pane-label {
    writing-mode: vertical-lr;
    transform: rotate(180deg);
    font-size: 8px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: .08em;
    padding: 4px 3px;
    background: var(--bg1);
    border-right: 1px solid var(--b1);
    flex-shrink: 0;
    opacity: .7;
  }
  .pane-chart {
    flex: 1;
    min-width: 0;
  }
  .rsi-levels {
    position: absolute;
    right: 44px; /* align roughly with price scale */
    top: 0; bottom: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    pointer-events: none;
  }
  .rsi-level {
    font-size: 8px;
    color: var(--t3);
    opacity: .5;
    font-family: 'SF Mono', 'Fira Code', monospace;
  }
  .rsi-level.ob { margin-top: 2px; }
  .rsi-level.os { margin-bottom: 2px; }

  /* ── MACD sub-pane ───────────────────────────────────────────────────────────────────────────── */
  .macd-pane {
    height: 100px; /* slightly taller than RSI for histogram readability */
  }
</style>
