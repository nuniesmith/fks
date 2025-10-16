import React from 'react';
import PageContainer from '@layout/PageContainer';

import { serviceEndpoints } from '../../hooks/useServiceMonitoring';

import ServiceHealthTable from './ServiceHealthTable';

const ServiceHealthPage: React.FC = () => {
  return (
    <PageContainer className="space-y-6">
        <header>
          <h1 className="text-3xl font-bold text-white mb-2">Service & Dependency Health</h1>
          <p className="text-white/70 text-sm max-w-2xl">Live snapshot of internal services and key external dependencies. Refresh to re-run simulated health checks.</p>
        </header>
        <ServiceHealthTable />
        <div className="glass-card p-4">
          <h3 className="font-semibold mb-2">Registered Endpoints</h3>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
            {serviceEndpoints.map(ep => (
              <div key={ep.id} className="p-2 bg-white/5 rounded border border-white/10">
                <div className="font-mono text-white/80">{ep.id}</div>
                <div className="text-white/60 truncate">{ep.url}</div>
              </div>
            ))}
          </div>
        </div>
    </PageContainer>
  );
};

export default ServiceHealthPage;
