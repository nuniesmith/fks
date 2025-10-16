import React, { useEffect, useRef } from 'react';

import type { LogEntry } from '../../types/projectManager';

interface Props { logs: LogEntry[]; onClear: () => void; }

const LogViewer: React.FC<Props> = ({ logs, onClear }) => {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);
  // Trend deltas: last 20 vs previous 20
  const recent = logs.slice(-20);
  const prev = logs.slice(-40, -20);
  const count = (arr: LogEntry[], type: LogEntry['type']) => arr.filter(l => l.type === type).length;
  const errDelta = count(recent, 'error') - count(prev, 'error');
  const warnDelta = count(recent, 'warning') - count(prev, 'warning');
  const successDelta = count(recent, 'success') - count(prev, 'success');
  const badge = (label: string, delta: number, color: string) => (
    <span className={`text-[10px] px-1.5 py-0.5 rounded bg-white/5 ${color}`}>{label}{delta>0?` +${delta}`: delta<0?` ${delta}`:' 0'}</span>
  );
  return (
    <div className="glass-card p-6 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Activity Log</h3>
        <div className="flex items-center gap-2">
          {logs.length >= 20 && (
            <div className="flex items-center gap-1">
              {badge('Err', errDelta, 'text-red-300')}
              {badge('Warn', warnDelta, 'text-amber-200')}
              {badge('Ok', successDelta, 'text-green-300')}
            </div>
          )}
          <button onClick={onClear} className="text-xs text-white/60 hover:text-white/90">Clear</button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-sm custom-scrollbar">
        {logs.length === 0 && <div className="text-white/40">No activity yet</div>}
        {logs.map((l, i) => (
          <div key={i} className={`log-entry ${l.type}`}>
            <span className="font-mono text-white/60 mr-2">{l.timestamp}</span>{l.message}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
};

export default LogViewer;
