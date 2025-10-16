import { AlertTriangle, CheckCircle, Bell, BellOff, Link2 } from 'lucide-react';
import React from 'react';

import type { APIConnection, AlertConfig } from '../../types';

interface IntegrationAndAlertsProps {
  apiConnections: APIConnection[];
  alertConfigs: AlertConfig[];
  onUpdateApiConnections: (connections: APIConnection[]) => void;
  onUpdateAlertConfigs: (configs: AlertConfig[]) => void;
}

const IntegrationAndAlerts: React.FC<IntegrationAndAlertsProps> = ({ 
  apiConnections, 
  alertConfigs, 
  onUpdateApiConnections, 
  onUpdateAlertConfigs 
}) => {
  const toggleConnection = (connectionId: string) => {
    const updatedConnections = apiConnections.map(conn => 
      conn.id === connectionId 
        ? { ...conn, isConnected: !conn.isConnected }
        : conn
    );
    onUpdateApiConnections(updatedConnections);
  };

  const toggleAlert = (alertId: string) => {
    const updatedAlerts = alertConfigs.map(alert => 
      alert.id === alertId 
        ? { ...alert, enabled: !alert.enabled }
        : alert
    );
    onUpdateAlertConfigs(updatedAlerts);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Integration & Alerts</h2>
        
        {/* Alerts Section */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Alert Configuration</h3>
          <div className="space-y-3">
            {alertConfigs.map((alert) => (
              <div key={alert.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  {alert.enabled ? (
                    <Bell className="h-5 w-5 text-blue-600" />
                  ) : (
                    <BellOff className="h-5 w-5 text-gray-400" />
                  )}
                  <div>
                    <span className="font-medium text-gray-900 block">
                      {alert.type.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    <span className="text-sm text-gray-600">{alert.message}</span>
                  </div>
                </div>
                <button
                  onClick={() => toggleAlert(alert.id)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    alert.enabled ? 'bg-blue-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      alert.enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Integrations Section */}
        <div>
          <h3 className="text-lg font-semibold text-gray-800 mb-3">API Connections</h3>
          <div className="space-y-3">
            {apiConnections.map((connection) => (
              <div key={connection.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <Link2 className="h-5 w-5 text-gray-600" />
                  <div>
                    <span className="font-medium text-gray-900 block">{connection.name}</span>
                    <span className="text-sm text-gray-600">{connection.provider} • {connection.type}</span>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {connection.isConnected ? (
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-orange-500" />
                  )}
                  <span className={`text-sm font-medium ${
                    connection.isConnected ? 'text-green-600' : 'text-orange-500'
                  }`}>
                    {connection.isConnected ? 'Connected' : 'Not Connected'}
                  </span>
                  <button 
                    onClick={() => toggleConnection(connection.id)}
                    className="ml-2 px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    {connection.isConnected ? 'Disconnect' : 'Connect'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntegrationAndAlerts;