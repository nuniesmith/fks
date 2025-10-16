import React from 'react';

const RealtimeTickerChartLazy = React.lazy(() => import('../../components/Realtime/RealtimeTickerChart'));

export default function RealtimeTickerChartLazyWrapper(props: any) {
  return (
    <React.Suspense fallback={<div className="p-2 text-xs text-gray-400">Loading live ticker…</div>}>
      <RealtimeTickerChartLazy {...props} />
    </React.Suspense>
  );
}
