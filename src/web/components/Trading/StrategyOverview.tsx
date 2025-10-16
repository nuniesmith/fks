import React from 'react';

const StrategyOverview: React.FC = () => {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white">Strategy Overview</h1>
          <p className="text-white/70">Build, backtest, forward test, and validate strategies.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/strategy/backtesting" className="glass-card p-5 hover:bg-white/10 transition">
            <div className="text-white text-lg font-semibold">Backtesting</div>
            <div className="text-white/70 text-sm">Run and review historical tests.</div>
          </a>
          <a href="/strategy/forward-test" className="glass-card p-5 hover:bg-white/10 transition">
            <div className="text-white text-lg font-semibold">Forward Testing</div>
            <div className="text-white/70 text-sm">Stage strategies with live-like data.</div>
          </a>
          <a href="/strategy/builder" className="glass-card p-5 hover:bg-white/10 transition">
            <div className="text-white text-lg font-semibold">Strategy Builder</div>
            <div className="text-white/70 text-sm">Create and configure strategy logic.</div>
          </a>
        </div>
      </div>
    </div>
  );
};

export default StrategyOverview;
