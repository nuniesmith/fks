// hooks/useLogger.ts
import { useEffect, useState } from 'react';

import { Logger } from '../utils/Logger';

import type { LogEntry } from '../types';

export const useLogger = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logger = Logger.getInstance();

  useEffect(() => {
    setLogs(logger.getLogs());
    
    const unsubscribe = logger.subscribe(setLogs);
    return unsubscribe;
  }, [logger]);

  const addLog = (message: string, type: LogEntry['type'] = 'info') => {
    logger.addLog(message, type);
  };

  const clearLogs = () => {
    logger.clearLogs();
  };

  return { logs, addLog, clearLogs };
};