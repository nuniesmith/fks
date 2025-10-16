import React, { useCallback, useEffect, useState } from 'react';

import { useRealtime } from '../../hooks/useRealtime';

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
  size?: number;
  q?: number;
  volume?: number;
};

function toDate(v: number | string | undefined) {
  if (v == null) return '';
  if (typeof v === 'number') {
    const ms = v < 1e12 ? v * 1000 : v;
    return new Date(ms).toLocaleTimeString();
  }
  const parsed = Date.parse(v);
  return isNaN(parsed) ? '' : new Date(parsed).toLocaleTimeString();
}

function getPrice(m: TickMsg) {
  return m.price ?? m.p ?? m.last;
}

function getSize(m: TickMsg) {
  return m.size ?? m.q ?? m.volume;
}

interface Props {
  channel: string;
  limit?: number;
  title?: string;
}

const RecentTicksTable: React.FC<Props> = ({ channel, limit = 50, title }) => {
  const { subscribe, unsubscribe } = useRealtime();
  const [rows, setRows] = useState<TickMsg[]>([]);
  const onTick = useCallback((m: TickMsg) => {
    setRows((prev) => {
      const next = [m, ...prev];
      if (next.length > limit) next.pop();
      return next;
    });
  }, [limit]);

  useEffect(() => {
    const off = subscribe(channel, onTick);
    return () => { off(); unsubscribe(channel, onTick); };
  }, [channel, onTick, subscribe, unsubscribe]);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-700 text-sm text-gray-200 font-medium">
        {title || `Recent Ticks (${channel})`}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-700 text-gray-300">
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-right">Price</th>
              <th className="px-3 py-2 text-right">Size</th>
              <th className="px-3 py-2 text-left">Symbol</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {rows.length === 0 ? (
              <tr>
                <td className="px-3 py-3 text-gray-400" colSpan={4}>No ticks yet.</td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={i} className="hover:bg-gray-700/40">
                  <td className="px-3 py-2 text-gray-200">{toDate(r.ts ?? r.t ?? r.time)}</td>
                  <td className="px-3 py-2 text-right text-blue-300">{getPrice(r)}</td>
                  <td className="px-3 py-2 text-right text-gray-300">{getSize(r) ?? ''}</td>
                  <td className="px-3 py-2 text-gray-300">{r.symbol ?? ''}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RecentTicksTable;
