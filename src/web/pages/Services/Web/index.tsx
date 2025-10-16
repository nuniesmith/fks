import React from 'react';

import ServicePageLayout from '../../../components/ServiceMonitoring/ServicePageLayout';

const WebServicePage: React.FC = () => (
  <ServicePageLayout serviceId="web" title="Web UI" description="Frontend delivery service: static asset optimization, edge caching, and client performance.">
    <div className="glass-card p-6 text-sm text-white/70 space-y-2">
      <p>Planned metrics:</p>
      <ul className="list-disc list-inside">
        <li>Build artifact sizes (from CI manifest)</li>
        <li>LCP / FID synthetic measurements (Web Vitals)</li>
        <li>Client error rate & retry counts</li>
      </ul>
    </div>
  </ServicePageLayout>
);

export default WebServicePage;
