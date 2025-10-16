export interface LogEntry { timestamp: string; message: string; type: 'info' | 'error' | 'success' | 'warning'; }
// Allow null while status checks are pending
export interface SystemStatus { buildApi: boolean | null; dockerServices: boolean | null; }
