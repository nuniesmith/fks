const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = 8081;

// Enable CORS for all origins
app.use(cors({
  origin: ['http://localhost:3000', 'http://localhost:8002', '*'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'Access-Control-Allow-Origin']
}));

// Health check endpoint
app.get('/healthz', (req, res) => {
  res.json({ 
    status: 'ok', 
    service: 'vscode-server',
    timestamp: new Date().toISOString(),
    version: '1.0.0'
  });
});

// Basic status endpoint
app.get('/api/status', (req, res) => {
  res.json({ 
    message: 'VS Code Server is running',
    version: '1.0.0',
    timestamp: new Date().toISOString()
  });
});

// Proxy all other requests to VS Code server if it's running
// This will be updated when the actual VS Code server is available
app.use('/', (req, res) => {
  res.json({
    message: 'VS Code Server Proxy',
    note: 'Start the full VS Code server using Docker Compose for full functionality',
    available_endpoints: ['/healthz', '/api/status']
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`VS Code Server Proxy running on port ${PORT}`);
  console.log(`Health check available at: http://localhost:${PORT}/healthz`);
});

module.exports = app;
