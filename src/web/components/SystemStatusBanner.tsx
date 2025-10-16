// components/SystemStatusBanner.tsx
import { Monitor, CheckCircle, AlertCircle } from 'lucide-react';
import React from 'react';

interface SystemStatus {
  buildApi: boolean;
  dockerServices: boolean;
}

interface SystemStatusBannerProps {
  systemStatus: SystemStatus;
}

export const SystemStatusBanner: React.FC<SystemStatusBannerProps> = ({ systemStatus }) => (
  <div className="mb-4 p-4 rounded-lg border bg-white">
    <h3 className="font-semibold mb-3 flex items-center">
      <Monitor className="w-5 h-5 mr-2 text-blue-500" />
      System Status
    </h3>
    <div className="grid md:grid-cols-3 gap-4">
      <StatusItem 
        label="Build API" 
        status={systemStatus.buildApi}
        errorColor="red"
      />
      <StatusItem 
        label="Docker Services" 
        status={systemStatus.dockerServices}
        errorColor="red"
      />
    </div>
    {!systemStatus.buildApi && (
      <div className="mt-2 p-2 bg-yellow-50 rounded text-yellow-800 text-sm">
        Build API not responding. Make sure Docker services are running.
      </div>
    )}
  </div>
);

// components/StatusItem.tsx
interface StatusItemProps {
  label: string;
  status: boolean;
  errorColor?: 'red' | 'yellow';
}

const StatusItem: React.FC<StatusItemProps> = ({ label, status, errorColor = 'red' }) => (
  <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
    <span className="text-sm">{label}</span>
    {status ? (
      <CheckCircle className="w-4 h-4 text-green-500" />
    ) : (
      <AlertCircle className={`w-4 h-4 text-${errorColor}-500`} />
    )}
  </div>
);