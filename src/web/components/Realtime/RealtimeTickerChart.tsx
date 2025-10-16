import { createChart } from 'lightweight-charts';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { ISeriesApi, LineData, Time, UTCTimestamp } from 'lightweight-charts';

import { useRealtime } from '@/hooks/useRealtime';

type TickMsg = {
  channel?: string;
  topic?: string;
  symbol?: string;
  ts?: number | string;
  t?: number | string;
  time?: number | string;
  price?: number;
  p?: number;
  last?: number;
};

interface Props {
  channel: string; // e.g., "ticks:AAPL"
  title?: string;
  maxPoints?: number;
  height?: number;
}

function toUtcTimestamp(v: number | string): UTCTimestamp | undefined {
  if (v == null) return undefined;
  let ms: number | undefined;
  if (typeof v === 'number') {
    // heuristics: if it's seconds, multiply
    ms = v < 1e12 ? v * 1000 : v;
  } else {
    const parsed = Date.parse(v);
    ms = isNaN(parsed) ? undefined : parsed;
  }
  return ms ? (Math.floor(ms / 1000) as UTCTimestamp) : undefined;
}

function parsePrice(m: TickMsg): number | undefined {
  return m.price ?? m.p ?? m.last;
}

const RealtimeTickerChart: React.FC<Props> = ({ channel, title, maxPoints = 500, height = 220 }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const { status, subscribe, unsubscribe } = useRealtime();
  const [lastPrice, setLastPrice] = useState<number | undefined>(undefined);

  const label = useMemo(() => title || channel.replace(/^.*?:/, ''), [title, channel]);

  const onTick = useCallback((raw: any) => {
    const m: TickMsg = raw || {};
    const price = parsePrice(m);
    const ts = toUtcTimestamp(m.ts ?? m.t ?? m.time ?? Date.now());
    if (price == null || ts == null) return;
    const point: LineData<Time> = { time: ts, value: price };
    seriesRef.current?.update(point);
    setLastPrice(price);
  }, []);

  // Subscribe to channel
  useEffect(() => {
    const off = subscribe(channel, onTick);
    return () => { off(); unsubscribe(channel, onTick); };
  }, [channel, onTick, subscribe, unsubscribe]);

  // Create chart
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      height,
      layout: { background: { color: '#111827' }, textColor: '#E5E7EB' },
      grid: { vertLines: { color: '#1F2937' }, horzLines: { color: '#1F2937' } },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151' },
      autoSize: true,
    });
  // Typed line series creation (v5 API shape: addSeries(kind, options))
  const series = (chart as any).addSeries('Line', { lineWidth: 2, color: '#60A5FA' });
    seriesRef.current = series;
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({});
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  // Trim data if needed (lightweight-charts keeps internal series; here we rely on series update streaming)
  // If needed, we could maintain a circular buffer and setData periodically.

  const statusColor = status === 'open' ? 'text-green-400' : status === 'connecting' ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className={`text-xs ${statusColor}`}>WS: {status}</span>
          <span className="text-sm text-gray-200 font-medium">{label}</span>
        </div>
        <div className="text-sm text-gray-300">
          {lastPrice != null ? <span>Last: <span className="text-blue-300">{lastPrice}</span></span> : <span className="text-gray-500">waiting…</span>}
        </div>
      </div>
      <div ref={containerRef} style={{ width: '100%', height }} />
    </div>
  );
};

export default RealtimeTickerChart;
