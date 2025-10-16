import React from 'react';

import FKSData from '../../../components/FKSServices/FKSData';
import ServiceContractTestPanel from '../../../components/ServiceMonitoring/ServiceContractTestPanel';
import ServicePageLayout from '../../../components/ServiceMonitoring/ServicePageLayout';

const dataBase = 'http://localhost:9001';
const dataSpecs = [
  { id: 'health', label: 'Health', endpoint: '/health', expectedStatus: 200, maxLatencyMs: 900, hardLatencyBudgetMs: 2500, jsonSchema: { status: 'string' } as const },
  { id: 'symbols', label: 'Symbols', endpoint: '/symbols', expectedStatus: 200, maxLatencyMs: 1200, hardLatencyBudgetMs: 4000, jsonSchema: { symbols: 'array' } as const },
  { id: 'latest', label: 'Latest Tick', endpoint: '/ticks/latest?symbol=ES', expectedStatus: [200, 404], maxLatencyMs: 800 },
  { id: 'latency-budget', label: 'Latency Budget Probe', endpoint: '/health', expectedStatus: 200, hardLatencyBudgetMs: 1800 }
];

const DataServicePage: React.FC = () => (
  <ServicePageLayout serviceId="data" title="Data Service" description="Ingestion, validation, enrichment, and realtime distribution of market & auxiliary data.">
    <div className="space-y-6">
      <FKSData />
      <div className="grid md:grid-cols-2 gap-4">
        <div className="glass-card p-6 text-sm text-white/70 space-y-2">
          <p className="font-semibold text-white/90">Planned metrics:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Ingestion throughput</li>
            <li>Tick processing latency</li>
            <li>Cache hit rate</li>
          </ul>
        </div>
        <ServiceContractTestPanel serviceId="data" baseUrl={dataBase} specs={dataSpecs} />
      </div>
    </div>
  </ServicePageLayout>
);

export default DataServicePage;
