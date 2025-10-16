import React from 'react';

// Lazy-load the heavy mermaid renderer only when needed
const LazyMermaid = React.lazy(() => import('./MermaidDiagram'));

interface Props { chart: string; className?: string; config?: Record<string, any>; }

const AsyncMermaid: React.FC<Props> = (props) => (
  <React.Suspense fallback={<div className="text-xs text-white/50">Loading diagram...</div>}>
    <LazyMermaid {...props} />
  </React.Suspense>
);

export default AsyncMermaid;
