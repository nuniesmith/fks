import React, { useState } from 'react';
import AsyncMermaid from './AsyncMermaid';

interface DiagramDef { key: string; title: string; description: string; code: string; }

const diagrams: DiagramDef[] = [
  {
    key: 'sequence-request',
    title: 'Request Sequence (Trade Forecast)',
    description: 'End-to-end flow of a forecast request through the stack',
    code: `sequenceDiagram
      autonumber
      participant U as User
      participant W as Web UI
      participant N as Nginx
      participant A as API Gateway
      participant E as Engine
      participant T as Transformer
      participant D as Data Service
      U->>W: Click "Generate Forecast"
      W->>N: HTTPS /api/forecast
      N->>A: Forward request (JWT)
      A->>E: /forecast
      E->>D: Fetch latest market features
      D-->>E: Feature batch
      E->>T: Inference(batch)
      T-->>E: Predictions
      E-->>A: Forecast result + metadata
      A-->>W: JSON response
      W-->>U: Render chart + metrics`
  },
  {
    key: 'data-flow',
    title: 'Market Data Flow',
    description: 'Acquisition, enrichment, storage and cache path',
    code: `flowchart LR
      subgraph Sources
        EX[Exchanges]
        TP[Data Vendors]
      end
      EX --> ING[Ingestion Pipelines]
      TP --> ING
      ING --> Q[Quality Filters]
      Q --> ENR[Enrichment]
      ENR -->|Write| TS[(TimescaleDB)]
      ENR -->|Cache hot| REDIS[(Redis Cluster)]
      TS --> API[API Gateway]
      REDIS --> API
      API --> UI[Web UI]
      API --> Engine[Engine Orchestrator]
      Engine --> Transformer[Transformer Inference]
      Transformer --> Engine
      Engine --> API
      style ING fill:#1e3a8a,stroke:#3b82f6
      style ENR fill:#0369a1,stroke:#38bdf8
      style TS fill:#334155,stroke:#64748b
      style REDIS fill:#7f1d1d,stroke:#f87171
      style Transformer fill:#065f46,stroke:#34d399`
  },
  {
    key: 'deployment',
    title: 'Deployment / Runtime Topology',
    description: 'Container + network level deployment overview',
    code: `graph TD
      subgraph Edge
        CDN[CDN/Browser Cache]
        DNS[DNS]
      end
      subgraph DMZ[Nginx Layer]
        Nginx[Nginx Reverse Proxy]
      end
      subgraph App[Application Tier]
        API[API Gateway]
        Engine[Engine Orchestrator]
        Transform[Transformer Service]
        DataSvc[Market Data Service]
      end
      subgraph Infra[Infrastructure]
        Redis[(Redis Cluster)]
        TS[(TimescaleDB)]
        Graf[Grafana]
        Prom[Prometheus]
      end
      Browser-->DNS-->CDN-->Nginx-->API
      Nginx-->DataSvc
      Nginx-->Engine
      Nginx-->Transform
      API-->Redis
      API-->TS
      Engine-->DataSvc
      Engine-->Transform
      DataSvc-->TS
      Transform-->TS
      Prom-->API
      Prom-->Engine
      Prom-->DataSvc
      Prom-->Transform
      Graf-->Prom`
  }
];

const SystemDiagrams: React.FC = () => {
  const [active, setActive] = useState(diagrams[0].key);
  const current = diagrams.find(d => d.key === active)!;
  return (
    <div className="glass-card p-4 space-y-4">
      <div className="flex flex-wrap gap-2">
        {diagrams.map(d => (
          <button
            key={d.key}
            onClick={() => setActive(d.key)}
            className={`px-3 py-1 rounded text-sm transition-colors ${active === d.key ? 'bg-blue-600 text-white' : 'bg-white/10 text-white/70 hover:bg-white/20'}`}
          >{d.title}</button>
        ))}
      </div>
      <div className="text-white/70 text-sm">{current.description}</div>
      <div className="bg-slate-900/60 rounded-lg p-3 border border-white/10 overflow-x-auto">
  <AsyncMermaid chart={current.code} config={{ theme: 'dark' }} />
      </div>
    </div>
  );
};

export default SystemDiagrams;
