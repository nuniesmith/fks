import React from 'react';

import { usePrometheus } from '../../shared/hooks/usePrometheusMetrics';

const MetricsPage: React.FC = () => {
  let exportText: string | null = null;
  try {
    const api = usePrometheus();
    exportText = api.exportText();
  } catch {
    exportText = '# Prometheus provider not mounted';
  }
  return (
    <div className="p-6 min-h-screen">
      <h1 className="text-2xl font-bold text-white mb-4">Metrics Export</h1>
      <div className="glass-card p-4">
        <pre className="text-xs whitespace-pre-wrap text-green-300 overflow-auto max-h-[70vh]" data-testid="metrics-export">{exportText || '# no metrics yet'}</pre>
      </div>
      <p className="text-white/60 mt-4 text-sm">Scrape this endpoint via a headless request to <code>/metrics</code> (client-rendered). For production, expose a server endpoint or use the Pushgateway hook.</p>
    </div>
  );
};

export default MetricsPage;
