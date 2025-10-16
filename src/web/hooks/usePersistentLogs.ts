import { useCallback, useEffect, useRef, useState } from 'react';

import type { LogEntry } from '../types/projectManager';

// Hook to persist logs in localStorage with a size cap and debounced writes.
export const usePersistentLogs = (key = 'fks_pm_logs', limit = 200) => {
  const loadedRef = useRef(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const writeRef = useRef<number | null>(null);

  // Hydrate once
  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setLogs(parsed.filter(e => e && e.timestamp && e.message).slice(-limit));
        }
      }
    } catch {/* ignore */}
  }, [key, limit]);

  // Persist (debounced) on change
  useEffect(() => {
    if (!loadedRef.current) return;
    if (writeRef.current) window.clearTimeout(writeRef.current);
    writeRef.current = window.setTimeout(() => {
      try { localStorage.setItem(key, JSON.stringify(logs.slice(-limit))); } catch {/* ignore */}
    }, 250);
    return () => { if (writeRef.current) window.clearTimeout(writeRef.current); };
  }, [logs, key, limit]);

  const add = useCallback((message: string, type: LogEntry['type'] = 'info') => {
    setLogs(prev => [...prev.slice(-limit + 1), { timestamp: new Date().toLocaleTimeString(), message, type }]);
  }, [limit]);

  const append = useCallback((entry: LogEntry) => {
    setLogs(prev => [...prev.slice(-limit + 1), entry]);
  }, [limit]);

  const clear = useCallback(() => {
    setLogs([]);
    try { localStorage.removeItem(key); } catch {/* ignore */}
  }, [key]);

  return { logs, add, append, clear };
};
