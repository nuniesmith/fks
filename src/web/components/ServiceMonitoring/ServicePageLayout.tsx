import React from 'react';

import ServiceDiagnosticsPanel from './ServiceDiagnosticsPanel';
import { useSingleService } from './ServiceHealthProvider';

interface Props { serviceId: string; title: string; children?: React.ReactNode; description?: string; }

const ServicePageLayout: React.FC<Props> = ({ serviceId, title, children, description }) => {
  const svc = useSingleService(serviceId);
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold gradient-text flex items-center gap-3">{title}<span className="text-sm font-normal text-white/50">({serviceId})</span></h1>
        {description && <p className="text-white/60 max-w-2xl text-sm">{description}</p>}
        {!svc && <p className="text-amber-300 text-xs">Service not currently in registry; add to serviceEndpoints to enable live status.</p>}
      </header>
      <ServiceDiagnosticsPanel serviceId={serviceId} />
      {children && <div className="space-y-6">{children}</div>}
    </div>
  );
};

export default ServicePageLayout;
