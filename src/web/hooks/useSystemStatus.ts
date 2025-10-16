// hooks/useSystemStatus.ts
import { useEffect, useState } from 'react';

interface SystemStatus {
  buildApi: boolean;
  dockerServices: boolean;
}

export const useSystemStatus = (apiBase: string) => {
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    buildApi: false,
    dockerServices: false
  });

  const checkSystemStatus = async () => {
    try {
      // Check Build API
      const buildApiResponse = await fetch(`${apiBase}/api/health`).catch(() => null);
      
      setSystemStatus({
        buildApi: buildApiResponse?.ok || false,
        dockerServices: true // Assume docker is running if we're here
      });
    } catch (error) {
      console.error('Status check failed:', error);
    }
  };

  useEffect(() => {
    checkSystemStatus();
    const interval = setInterval(checkSystemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  return { systemStatus, checkSystemStatus };
};