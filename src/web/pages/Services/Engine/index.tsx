import React from 'react';

import FKSEngine from '../../../components/FKSServices/FKSEngine';
import ServiceContractTestPanel from '../../../components/ServiceMonitoring/ServiceContractTestPanel';
import ServicePageLayout from '../../../components/ServiceMonitoring/ServicePageLayout';

const engineBase = 'http://localhost:9010';
const engineSpecs = [
  { id: 'health', label: 'Health', endpoint: '/health', expectedStatus: 200, maxLatencyMs: 900, hardLatencyBudgetMs: 2500, jsonSchema: { status: 'string' } as const },
  { id: 'jobs', label: 'Jobs', endpoint: '/jobs', expectedStatus: [200, 404], maxLatencyMs: 1500 },
  { id: 'backtest', label: 'Backtest (unauth)', endpoint: '/backtest', expectedStatus: [401, 403, 405], maxLatencyMs: 1200 },
  { id: 'version', label: 'Version Header', endpoint: '/health', expectedStatus: 200, headers: { Accept: 'application/json' }, requiredKeys: ['status'], maxLatencyMs: 900 }
];

const EngineServicePage: React.FC = () => (
  <ServicePageLayout serviceId="engine" title="Engine Orchestrator" description="Forecasting, backtesting and orchestration layer for strategy workflows.">
    <div className="space-y-6">
      <FKSEngine />
      <div className="grid md:grid-cols-2 gap-4">
        <div className="glass-card p-6 text-sm text-white/70 space-y-2">
          <p className="font-semibold text-white/90">Planned metrics:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Forecast latency (p95)</li>
            <li>Active job count</li>
            <li>Backtest throughput</li>
          </ul>
        </div>
        <ServiceContractTestPanel serviceId="engine" baseUrl={engineBase} specs={engineSpecs} />
      </div>
    </div>
  </ServicePageLayout>
);

export default EngineServicePage;
