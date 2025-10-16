// Moved from components/TradingChart.tsx to features/trading/components/charts
// NOTE: Legacy path re-export remains at original location during migration.
import { createChart } from 'lightweight-charts';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import useSecurity from '@/hooks/useSecurity';
import { buildAuthHeaders } from '@/services/authToken';

import { config } from '@/services/config';
import { useNotifications } from '@/components/Notifications';

import type { IChartApi, UTCTimestamp } from 'lightweight-charts';

interface TradingChartProps {
  symbol: string;
  timeframe?: string; // e.g., '1m', '5m', '15m', '1h'
  height?: number;
  className?: string;
  realTimeEnabled?: boolean;
  indicators?: string[];
  // Data source: 'internal' uses our /api and ws, 'binance' uses Binance public REST/WS
  dataSource?: 'internal' | 'binance';
}

interface ChartDataPoint {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

const TradingChart: React.FC<TradingChartProps> = ({
  symbol,
  timeframe = '1h',
  height = 400,
  className = '',
  realTimeEnabled = false,
  indicators = [],
  dataSource = 'internal'
}) => {
  const { addNotification } = useNotifications?.() || { addNotification: () => {} } as any;
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ReturnType<any> | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ReturnType<any>>>(new Map());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastPrice, setLastPrice] = useState<number | null>(null);

  // Initialize chart
  const initChart = useCallback(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#1a1a1a' },
        textColor: '#ffffff',
      },
      grid: {
        vertLines: { color: '#333333' },
        horzLines: { color: '#333333' },
      },
      crosshair: {
        mode: 1, // Normal crosshair mode
      },
      rightPriceScale: {
        borderColor: '#485c7b',
      },
      timeScale: {
        borderColor: '#485c7b',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Create candlestick series using the correct v5 API
  const candlestickSeries = (chart as any).addSeries('Candlestick', {
      upColor: '#4ade80',
      downColor: '#f87171',
      borderDownColor: '#f87171',
      borderUpColor: '#4ade80',
      wickDownColor: '#f87171',
      wickUpColor: '#4ade80',
    } as any);

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [height]);

  const [security] = useSecurity();
  // Helper to build auth headers (only when we have tokens and security is ready)
  const localAuthHeaders = () => security?.ready ? (buildAuthHeaders() as Record<string,string>) : undefined;

  // Fetch chart data
  const fetchChartData = useCallback(async () => {
    if (dataSource === 'internal' && !security.ready) return; // wait for auth posture
    try {
      setLoading(true);
      setError(null);

      let chartData: ChartDataPoint[] = [];

      if (dataSource === 'binance') {
        // Fetch initial klines from Binance Futures REST
        const restBase = 'https://fapi.binance.com';
        const sym = symbol.toUpperCase();
        const tfMap: Record<string, string> = {
          '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m',
          '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
          '1d': '1d', '3d': '3d', '1w': '1w', '1M': '1M'
        };
        const tf = tfMap[timeframe] || timeframe;
        const url = `${restBase}/fapi/v1/klines?symbol=${encodeURIComponent(sym)}&interval=${encodeURIComponent(tf)}&limit=500`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Binance REST error: ${response.statusText}`);
        const klines = await response.json();
        // Each kline: [ openTime, open, high, low, close, volume, closeTime, ... ]
        chartData = (klines || []).map((k: any[]) => ({
          time: Math.floor((k[0] as number) / 1000) as UTCTimestamp,
          open: Number(k[1]),
          high: Number(k[2]),
          low: Number(k[3]),
          close: Number(k[4]),
          volume: Number(k[5]),
        }));
      } else {
        // Internal API
        const API_BASE = (config.apiBaseUrl || '/api').replace(/\/$/, '');
  const headers = localAuthHeaders();
        const response = await fetch(
          `${API_BASE}/chart-data/${symbol}?timeframe=${timeframe}&limit=500`, { headers }
        );
        if (!response.ok) throw new Error(`Failed to fetch data: ${response.statusText}`);
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        chartData = result.data.map((point: any) => ({
          time: point.time as UTCTimestamp,
          open: point.open,
          high: point.high,
          low: point.low,
          close: point.close,
          volume: point.volume,
        }));
      }

      if (candlestickSeriesRef.current && chartData.length > 0) {
        candlestickSeriesRef.current.setData(chartData);
        setLastPrice(chartData[chartData.length - 1].close);
        if (chartRef.current) chartRef.current.timeScale().fitContent();
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch chart data');
      setLoading(false);
    }
  }, [symbol, timeframe, dataSource, security.ready]);

  // Fetch indicators
  const fetchIndicators = useCallback(async () => {
    if (indicators.length === 0) return;
    if (dataSource === 'internal' && !security.ready) return;

    try {
      const API_BASE = (config.apiBaseUrl || '/api').replace(/\/$/, '');
      const indicatorsParam = indicators.join(',');
  const headers = localAuthHeaders();
      const response = await fetch(
        `${API_BASE}/chart-indicators/${symbol}?indicators=${indicatorsParam}&timeframe=${timeframe}&limit=500`, { headers }
      );

      if (!response.ok) return;

      const result = await response.json();
      
      if (result.series && chartRef.current) {
        // Clear existing indicator series
        indicatorSeriesRef.current.forEach((series) => {
          chartRef.current?.removeSeries(series);
        });
        indicatorSeriesRef.current.clear();

        // Add new indicator series using v5 API
    result.series.forEach((indicator: any) => {
          if (indicator.data.length > 0) {
      const lineSeries = (chartRef.current! as any).addSeries('Line', {
              color: indicator.options?.color || '#2196F3',
              lineWidth: indicator.options?.lineWidth || 2,
              title: indicator.name,
            } as any);

            lineSeries.setData(indicator.data);
            indicatorSeriesRef.current.set(indicator.name, lineSeries);
          }
        });
      }
    } catch (err) {
      console.warn('Failed to fetch indicators:', err);
    }
  }, [symbol, timeframe, indicators, dataSource, security.ready]);

  // Update real-time data
  const updateRealTimeData = useCallback((newData: ChartDataPoint) => {
    if (candlestickSeriesRef.current) {
      candlestickSeriesRef.current.update(newData);
      setLastPrice(newData.close);
    }
  }, []);

  // Setup WebSocket for real-time updates
  useEffect(() => {
    if (!realTimeEnabled) return;
    if (dataSource === 'internal' && !security.ready) return; // delay connecting until auth ready

    // Choose WebSocket based on data source
    let wsUrl: string;
    if (dataSource === 'binance') {
      // Map our timeframe to Binance interval tokens (mostly identical for supported values)
      const tfMap: Record<string, string> = {
        '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m',
        '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
        '1d': '1d', '3d': '3d', '1w': '1w', '1M': '1M'
      };
      const binanceTf = tfMap[timeframe] || timeframe;
      const stream = `${symbol.toLowerCase()}@kline_${binanceTf}`; // e.g., btcusdt@kline_1m
      // Market streams base for USDⓈ-M Futures
      wsUrl = `wss://fstream.binance.com/ws/${stream}`;
    } else {
      const wsBase = (config.wsBaseUrl as string | undefined)
        || (typeof window !== 'undefined' ? window.location.origin.replace(/^http/, 'ws') : 'ws://localhost');
      const baseNoSlash = wsBase.replace(/\/$/, '');
      wsUrl = /\/ws\/?$/.test(baseNoSlash) ? baseNoSlash : `${baseNoSlash}/ws`;
    }

    const cleanupPrev = () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        try { wsRef.current.close(); } catch {}
        wsRef.current = null;
      }
    };

    const connect = () => {
      cleanupPrev();
      try {
        let authQuery = '';
        try {
          if (security.ready) {
            const hdrs = buildAuthHeaders();
            const token = (hdrs as any)?.Authorization?.toString().replace(/^Bearer\s+/,'');
            if (token) authQuery = wsUrl.includes('?') ? `&token=${encodeURIComponent(token)}` : `?token=${encodeURIComponent(token)}`;
          }
        } catch {}
        const ws = new WebSocket(wsUrl + authQuery);
        wsRef.current = ws;

        ws.onopen = () => {
          reconnectAttemptsRef.current = 0;
          if (realTimeEnabled) {
            addNotification({ type: 'xp', title: 'Live feed connected', message: `${dataSource} ${symbol} ${timeframe}`, duration: 2000 } as any);
          }
        };

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);

            if (dataSource === 'binance') {
              // Binance kline payload shape: { e: 'kline', k: { t,o,h,l,c,v,..., x } }
              const k = payload?.k;
              if (k && k.t != null) {
                updateRealTimeData({
                  time: Math.floor(Number(k.t) / 1000) as UTCTimestamp,
                  open: Number(k.o),
                  high: Number(k.h),
                  low: Number(k.l),
                  close: Number(k.c),
                  volume: Number(k.v),
                });
              }
            } else {
              // Internal stream format
              if (payload.type === 'chart_update' && payload.symbol === symbol) {
                updateRealTimeData({
                  time: payload.data.time as UTCTimestamp,
                  open: payload.data.open,
                  high: payload.data.high,
                  low: payload.data.low,
                  close: payload.data.close,
                  volume: payload.data.volume,
                });
              }
            }
          } catch (err) {
            console.warn('Failed to parse WebSocket message:', err);
          }
        };

        ws.onerror = (error) => {
          console.warn('WebSocket error:', error);
          addNotification({ type: 'warning', title: 'Live feed error', message: `${symbol} ${timeframe}`, duration: 2500 } as any);
        };

        ws.onclose = () => {
          // Reconnect with exponential backoff (cap 30s)
          if (!realTimeEnabled) return;
          const attempt = (reconnectAttemptsRef.current = reconnectAttemptsRef.current + 1);
          const delay = Math.min(30000, Math.pow(2, attempt) * 250);
          if (attempt === 1) {
            addNotification({ type: 'milestone', title: 'Live feed disconnected', message: `Reconnecting…`, duration: 2000 } as any);
          }
          reconnectTimerRef.current = window.setTimeout(connect, delay);
        };
      } catch (err) {
        console.warn('Failed to setup WebSocket:', err);
      }
    };

    connect();

    return () => {
      cleanupPrev();
      reconnectAttemptsRef.current = 0;
    };
  }, [realTimeEnabled, symbol, timeframe, dataSource, updateRealTimeData, security.ready]);

  // Initialize chart on mount
  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart]);

  // Fetch data when symbol or timeframe changes
  useEffect(() => {
    if (chartRef.current) {
      fetchChartData();
    }
  }, [fetchChartData]);

  // Fetch indicators when they change
  useEffect(() => {
    if (chartRef.current) {
      fetchIndicators();
    }
  }, [fetchIndicators]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, []);

  return (
    <div className={`relative ${className}`}>
      {/* Chart Header */}
      <div className="flex items-center justify-between p-4 bg-gray-800 rounded-t-lg">
        <div className="flex items-center space-x-4">
          <h3 className="text-lg font-semibold text-white">{symbol}</h3>
          <span className="text-sm text-gray-400">{timeframe}</span>
          {lastPrice && (
            <span className="text-lg font-mono text-green-400">
              ${lastPrice.toFixed(2)}
            </span>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          {realTimeEnabled && (
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-xs text-green-400">Live</span>
            </div>
          )}
          
          {loading && (
            <div className="text-xs text-blue-400">Loading...</div>
          )}
          
          {error && (
            <div className="text-xs text-red-400" title={error}>
              Error
            </div>
          )}
        </div>
      </div>
      
      {/* Chart Container */}
      <div 
        ref={chartContainerRef}
        className="w-full bg-gray-900 rounded-b-lg"
        style={{ height: `${height}px` }}
      />
      
      {/* Error Display */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900 bg-opacity-90 rounded-lg">
          <div className="text-center">
            <div className="text-red-400 mb-2">Failed to load chart</div>
            <div className="text-sm text-gray-400">{error}</div>
            <button
              onClick={fetchChartData}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingChart;
