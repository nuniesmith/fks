import React from 'react';

import ServicePageLayout from '../../../components/ServiceMonitoring/ServicePageLayout';

const TrainingServicePage: React.FC = () => (
  <ServicePageLayout serviceId="training" title="Model Training" description="Offline / asynchronous model training and evaluation jobs.">
    <div className="glass-card p-6 text-sm text-white/70 space-y-2">
      <p>Planned metrics:</p>
      <ul className="list-disc list-inside">
        <li>Active training jobs & queue depth</li>
        <li>GPU utilization & memory (if available)</li>
        <li>Checkpoint artifact sizes & last updated</li>
      </ul>
    </div>
  </ServicePageLayout>
);

export default TrainingServicePage;
