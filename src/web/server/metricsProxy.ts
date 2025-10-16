// Simple metrics proxy endpoint for production scraping.
// This is a placeholder Node/Express-like handler example; integrate with your backend server.
// If deploying a static SPA only, host a small server that imports Prometheus registry state.

import fs from 'fs';

import type { IncomingMessage, ServerResponse } from 'http';

// Since frontend metrics live in-browser, a true /metrics endpoint needs a backend aggregator.
// Placeholder returns static guidance text.
export const handleMetrics = (_req: IncomingMessage, res: ServerResponse) => {
  res.setHeader('Content-Type', 'text/plain');
  res.write('# FKS Frontend Metrics Proxy\n');
  res.write('# Implement server-side aggregation or pushgateway scraping.\n');
  try {
    const guidance = fs.readFileSync('docs/FRONTEND_METRICS.md','utf-8');
    res.write(`# See docs/FRONTEND_METRICS.md for integration steps (length ${guidance.length})\n`);
  } catch {}
  res.end();
};
