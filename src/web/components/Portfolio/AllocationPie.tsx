import React from 'react';

// Lazy load minimal pie chart (micro-chunk) instead of full recharts bundle
const LazyPie = React.lazy(() => import('../../features/lazy/recharts-parts/Pie'));

interface Props { data: Record<string, number>; }
const palette = ['#60a5fa', '#a78bfa', '#34d399', '#f472b6', '#f59e0b', '#f87171'];

const AllocationPie: React.FC<Props> = ({ data }) => {
  const entries = Object.entries(data);
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
  const chartData = entries.map(([name, value]) => ({ name, value }));
  return (
    <div className="p-4 bg-white/5 rounded border border-white/10">
      <h3 className="text-white text-sm font-semibold mb-2">Allocation Breakdown</h3>
      <div className="h-48">
        <React.Suspense fallback={<div className="text-xs text-white/50">Loading chart...</div>}>
          <LazyPie data={chartData} palette={palette} />
        </React.Suspense>
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-1 text-[11px] text-white/70">
        {chartData.map((d, i) => (
          <li key={d.name} className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-sm" style={{ background: palette[i % palette.length] }} />
            <span className="truncate" title={d.name}>{d.name}</span>
            <span className="ml-auto text-white/50">{((d.value / total) * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AllocationPie;
