import React from 'react';

const TradingChartLazy = React.lazy(() => import('../trading/components/charts/TradingChart'));

export default function TradingChartLazyWrapper(props: any) {
  return (
    <React.Suspense fallback={<div className="p-4 text-xs text-gray-400">Loading trading chart…</div>}>
      <TradingChartLazy {...props} />
    </React.Suspense>
  );
}
