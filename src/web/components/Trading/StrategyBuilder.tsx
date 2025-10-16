import { PlusCircle } from 'lucide-react';
import React from 'react';

const StrategyBuilder: React.FC = () => {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Strategy Builder</h1>
            <p className="text-white/70">Create and configure strategies (HMM, Transformer, and more).</p>
          </div>
        </div>

        <div className="glass-card p-6 text-white/70">
          <div className="flex items-center gap-2">
            <PlusCircle className="w-4 h-4" />
            <span>Schema-driven builder coming soon.</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StrategyBuilder;
