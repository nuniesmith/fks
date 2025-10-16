import React from 'react';

import FKSTransformer from '../../../components/FKSServices/FKSTransformer';
import ServiceContractTestPanel from '../../../components/ServiceMonitoring/ServiceContractTestPanel';
import ServicePageLayout from '../../../components/ServiceMonitoring/ServicePageLayout';

const transformerBase = 'http://localhost:8089';
const transformerSpecs = [
  { id: 'health', label: 'Health', endpoint: '/health', expectedStatus: 200, maxLatencyMs: 1000, hardLatencyBudgetMs: 3000, jsonSchema: { status: 'string' } as const },
  { id: 'embed', label: 'Embedding (unauth)', endpoint: '/embed', expectedStatus: [401, 403, 405], maxLatencyMs: 1200 },
  { id: 'inference', label: 'Inference (unauth)', endpoint: '/infer', expectedStatus: [401, 403, 405], maxLatencyMs: 1200 },
  { id: 'queue', label: 'Queue Stats', endpoint: '/queue', expectedStatus: [200,404], maxLatencyMs: 1500 }
];

const TransformerServicePage: React.FC = () => (
  <ServicePageLayout serviceId="transformer" title="Transformer Inference" description="Low-latency model inference & NLP analysis for market context.">
    <div className="space-y-6">
      <FKSTransformer />
      <div className="grid md:grid-cols-2 gap-4">
        <div className="glass-card p-6 text-sm text-white/70 space-y-2">
          <p className="font-semibold text-white/90">Planned metrics:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Queue depth</li>
            <li>GPU utilization</li>
            <li>Average inference latency</li>
          </ul>
        </div>
        <ServiceContractTestPanel serviceId="transformer" baseUrl={transformerBase} specs={transformerSpecs} />
      </div>
    </div>
  </ServicePageLayout>
);

export default TransformerServicePage;
