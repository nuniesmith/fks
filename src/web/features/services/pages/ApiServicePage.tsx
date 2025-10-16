import React from 'react';
const ApiServicePage: React.FC = () => (
  <div className="glass-card p-6">
    <h1 className="text-2xl font-bold text-white mb-2">API Service</h1>
    <p className="text-white/70 text-sm mb-4">Stub page describing the Core API gateway. Replace with real implementation.</p>
    <ul className="list-disc list-inside text-white/70 text-sm space-y-1">
      <li>Health checks</li>
      <li>Authentication / JWT</li>
      <li>Routing to data, engine, transformer services</li>
    </ul>
  </div>
);
export default ApiServicePage;
