import { useEffect, useMemo, useState } from 'react';
import { realtimeClient, type WSStatus } from '@shared/services/realtime/WebSocketService';

export function useRealtime() {
  const [status, setStatus] = useState<WSStatus>(realtimeClient.getStatus());
  const [lastMessage, setLastMessage] = useState<any>(null);

  useEffect(() => {
    realtimeClient.connect();
    const unsub = realtimeClient.onMessage((m) => setLastMessage(m));
    const off = realtimeClient.onStatusChange((s) => setStatus(s));
    return () => { unsub(); off(); };
  }, []);

  return useMemo(() => ({
    status,
    lastMessage,
    send: (m: any) => realtimeClient.send(m),
    disconnect: () => realtimeClient.disconnect(),
    subscribe: (channel: string, fn: (msg: any) => void) => realtimeClient.subscribe(channel, fn),
    unsubscribe: (channel: string, fn?: (msg: any) => void) => realtimeClient.unsubscribe(channel, fn),
  }), [status, lastMessage]);
}
