/**
 * SSE Store — reactive Svelte store backed by an EventSource.
 *
 * Usage:
 *   const bars = createSSE<BarEvent>('/sse/bars/MGC');
 *   $effect(() => { console.log($bars); });
 */
import { writable, type Readable } from "svelte/store";
import { SSE_RECONNECT_MS } from "$lib/config";

export interface SSEStore<T> extends Readable<T | null> {
  connect: () => void;
  disconnect: () => void;
  readonly connected: Readable<boolean>;
}

export function createSSE<T>(
  url: string,
  opts?: {
    eventName?: string;
    parse?: (data: string) => T;
    reconnectMs?: number;
  },
): SSEStore<T> {
  const {
    eventName,
    parse = JSON.parse,
    reconnectMs = SSE_RECONNECT_MS,
  } = opts ?? {};

  const data = writable<T | null>(null);
  const connected = writable(false);
  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    disconnect();

    source = new EventSource(url);

    source.onopen = () => {
      connected.set(true);
    };

    const handler = (evt: MessageEvent) => {
      try {
        data.set(parse(evt.data));
      } catch {
        console.warn("[SSE] Parse error:", url, evt.data);
      }
    };

    if (eventName) {
      source.addEventListener(eventName, handler);
    } else {
      source.onmessage = handler;
    }

    source.onerror = () => {
      connected.set(false);
      source?.close();
      source = null;

      // Auto-reconnect
      reconnectTimer = setTimeout(connect, reconnectMs);
    };
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (source) {
      source.close();
      source = null;
    }
    connected.set(false);
  }

  return {
    subscribe: data.subscribe,
    connect,
    disconnect,
    connected: { subscribe: connected.subscribe },
  };
}
