import React from 'react';

const Performance: React.FC = () => {
  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white">Performance</h1>
          <p className="text-white/70">Detailed performance metrics and time-series charts.</p>
        </div>
        <div className="glass-card p-6 text-white/70">Charts coming soon.</div>
      </div>
    </div>
  );
};

export default Performance;
