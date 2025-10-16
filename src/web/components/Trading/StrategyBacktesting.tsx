import React from 'react';

import BacktestRunner from './BacktestRunner';
import BacktestsHistory from './BacktestsHistory';

const StrategyBacktesting: React.FC = () => {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Backtesting</h1>
            <p className="text-white/70">Create, run, and review backtests in one place.</p>
          </div>
          <div className="flex items-center gap-2">
            <a href="/strategy/backtesting" className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm">Backtesting</a>
            <a href="/strategy/forward-test" className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm">Forward Testing</a>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <BacktestRunner embedded />
          </div>
          <div className="lg:col-span-1">
            <BacktestsHistory embedded />
          </div>
        </div>
      </div>
    </div>
  );
};

export default StrategyBacktesting;
