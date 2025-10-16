import React from 'react';

import ServicePageLayout from '../../../components/ServiceMonitoring/ServicePageLayout';

const WorkerServicePage: React.FC = () => (
  <ServicePageLayout serviceId="worker" title="Worker" description="Background task execution & job orchestration service.">
    <div className="glass-card p-6 text-sm text-white/70 space-y-2">
      <p>Planned metrics:</p>
      <ul className="list-disc list-inside">
        <li>Queue depths (immediate / delayed)</li>
        <li>Task success vs failure rate</li>
        <li>Average execution duration & p95</li>
      </ul>
    </div>
  </ServicePageLayout>
);

export default WorkerServicePage;
