import { Play, RefreshCw, StopCircle, Settings, Activity } from 'lucide-react';
import React from 'react';

// Updated to import from feature slice (legacy path still works but we prefer canonical path)
import TradingChart from '@/features/lazy/TradingChartLazy';

const ForwardTesting: React.FC = () => {
  const [name, setName] = React.useState('Forward Test Session');
  const [symbols, setSymbols] = React.useState('AAPL');
  const [paper, setPaper] = React.useState(true);
  const [interval, setInterval] = React.useState('1m');
  const [running, setRunning] = React.useState(false);
  const [status, setStatus] = React.useState<string>('idle');
  const [message, setMessage] = React.useState<string>('Ready');
  const [timeframe, setTimeframe] = React.useState('1m');
  const [useBinanceCrypto, setUseBinanceCrypto] = React.useState(false);
  const [cryptoPair, setCryptoPair] = React.useState<'BTCUSDT' | 'ETHUSDT' | 'SOLUSDT'>('BTCUSDT');
  const [useBinanceBTC, setUseBinanceBTC] = React.useState(false);

  const start = async () => {
    setRunning(true);
    setStatus('starting');
    setMessage('Spinning up staging simulator...');
    setTimeout(() => {
      setStatus('running');
      setMessage('Streaming market data and executing paper orders');
    }, 1200);
  };

  const stop = async () => {
    setRunning(false);
    setStatus('stopped');
    setMessage('Session stopped');
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Forward Testing</h1>
            <p className="text-white/70">Test strategies in a staging environment with live-like data.</p>
          </div>
        </div>

        <div className="glass-card p-5 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="text-sm text-white/80">
              <div className="mb-1">Session Name</div>
              <input value={name} onChange={e=>setName(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
            </label>
            <label className="text-sm text-white/80">
              <div className="mb-1">Symbols</div>
              <input value={symbols} onChange={e=>setSymbols(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white" />
            </label>
            <label className="text-sm text-white/80">
              <div className="mb-1 flex items-center gap-2"><Settings className="w-4 h-4"/> Interval</div>
        <select value={interval} onChange={e=>setInterval(e.target.value)} className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded text-white">
                {['1m','5m','15m','1h'].map(iv => (<option key={iv} value={iv}>{iv}</option>))}
              </select>
            </label>
          </div>

          <label className="flex items-center gap-2 text-white/80">
            <input type="checkbox" checked={paper} onChange={e=>setPaper(e.target.checked)} />
            Paper trading (no real orders)
          </label>
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
            <label className="flex items-center gap-2 text-white/80 select-none">
              <input type="checkbox" checked={useBinanceCrypto} onChange={e=>setUseBinanceCrypto(e.target.checked)} />
              Live Binance Crypto
            </label>
            {useBinanceCrypto && (
              <select
                className="px-3 py-2 bg-white/10 border border-white/20 rounded text-white"
                value={cryptoPair}
                onChange={e=>setCryptoPair(e.target.value as any)}
              >
                <option value="BTCUSDT">BTCUSDT</option>
                <option value="ETHUSDT">ETHUSDT</option>
                <option value="SOLUSDT">SOLUSDT</option>
              </select>
            )}
          </div>
          <label className="flex items-center gap-2 text-white/80">
            <input type="checkbox" checked={useBinanceBTC} onChange={e=>setUseBinanceBTC(e.target.checked)} />
            Live Binance BTCUSDT
          </label>

          <div className="flex items-center gap-3">
            <button disabled={running} onClick={start} className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-60 flex items-center gap-2">
              {running ? <RefreshCw className="w-4 h-4 animate-spin"/> : <Play className="w-4 h-4"/>}
              <span>{running ? 'Starting…' : 'Start Session'}</span>
            </button>
            <button disabled={!running} onClick={stop} className="px-4 py-2 rounded bg-red-600 hover:bg-red-700 text-white flex items-center gap-2">
              <StopCircle className="w-4 h-4"/>
              <span>Stop</span>
            </button>
          </div>
        </div>

        <div className="glass-card p-5">
          <div className="flex items-center justify-between">
            <div className="text-white font-semibold">Status: <span className="text-white/80 font-mono">{status}</span></div>
            <Activity className={`w-4 h-4 ${running ? 'text-green-400' : 'text-white/40'}`}/>
          </div>
          <div className="mt-2 text-white/70 text-sm">{message}</div>
        </div>

        {running && (
          <div className="glass-card p-4">
            {useBinanceCrypto ? (
              <TradingChart
                symbol={cryptoPair}
                timeframe={interval}
                height={360}
                realTimeEnabled
                dataSource="binance"
              />
            ) : (
              <TradingChart
                symbol={(symbols.split(',')[0] || 'AAPL').trim()}
                timeframe={interval}
                height={360}
                realTimeEnabled
                dataSource="internal"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ForwardTesting;
