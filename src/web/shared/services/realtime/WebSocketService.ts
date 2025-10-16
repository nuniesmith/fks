/* Shared realtime WebSocket client (migrated from services/realtime/WebSocketService.ts)
 * Responsibility: single lightweight pub/sub + channel subscription abstraction.
 * NOTE: Original location now re-exports from here for backward compatibility.
 */
import { config } from '../../../services/config';
import { getCurrentAccessToken, refreshAccessToken } from '../../../services/authToken';

type Listener = (msg: any) => void;
type StatusListener = (status: WSStatus) => void;

export type WSStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

class RealtimeClient {
  private ws: WebSocket | null = null;
  private url: string;
  private listeners = new Set<Listener>();
  private statusListeners = new Set<StatusListener>();
  private status: WSStatus = 'idle';
  private backoff = 1000;
  private maxBackoff = 15000;
  private jitter = 0.2; // 20% reconnect jitter
  private shouldReconnect = true;
  private heartbeatTimer: number | null = null;
  private channels = new Map<string, Set<Listener>>();
  private wantedChannels = new Set<string>();

  constructor() {
    const envUrl = (import.meta as any).env?.VITE_WS_URL as string | undefined;
    this.url = (config.wsBaseUrl || envUrl || this.inferDefaultUrl()).replace(/\/$/, '');
  }

  private inferDefaultUrl(): string {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${loc.host}/ws`;
  }

  getStatus(): WSStatus { return this.status; }
  getUrl(): string { return this.url; }

  onMessage(fn: Listener) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  onStatusChange(fn: StatusListener) { this.statusListeners.add(fn); return () => this.statusListeners.delete(fn); }

  subscribe(channel: string, fn: Listener) {
    if (!this.channels.has(channel)) this.channels.set(channel, new Set());
    this.channels.get(channel)!.add(fn);
    this.wantedChannels.add(channel);
    if (this.status === 'open') this.safeSend({ type: 'subscribe', channel });
    return () => this.unsubscribe(channel, fn);
  }

  unsubscribe(channel: string, fn?: Listener) {
    const set = this.channels.get(channel);
    if (set && fn) set.delete(fn);
    if (set && (!fn || set.size === 0)) {
      this.channels.delete(channel);
      this.wantedChannels.delete(channel);
      if (this.status === 'open') this.safeSend({ type: 'unsubscribe', channel });
    }
  }

  private emit(msg: any) { this.listeners.forEach((fn) => { try { fn(msg); } catch {} }); }
  private emitStatus(st: WSStatus) { this.statusListeners.forEach((fn) => { try { fn(st); } catch {} }); }

  private token(): string | undefined { return getCurrentAccessToken(); }

  /** Periodically ensure the socket uses a fresh token (if backend checks on upgrade only, reconnection suffices) */
  private scheduleTokenRotation() {
    // Every 4 minutes attempt refresh if we have a refresh token; reconnect if token changed
    const intervalMs = 240000; // 4 min
    const loop = async () => {
      if (this.status === 'closed' || this.status === 'idle') return; // stop when fully closed
      const before = this.token();
      // Attempt refresh silently (will no-op if missing refresh token)
      await refreshAccessToken().catch(()=>undefined);
      const after = this.token();
      if (after && before && after !== before) {
        // Token rotated; reconnect to propagate query token
        try { this.ws?.close(); } catch {}
      }
      setTimeout(loop, intervalMs);
    };
    setTimeout(loop, intervalMs);
  }

  connect() {
    if (this.ws && (this.status === 'connecting' || this.status === 'open')) return;
    this.shouldReconnect = true;
    const t = this.token();
    const sep = this.url.includes('?') ? '&' : '?';
    const url = t ? `${this.url}${sep}token=${encodeURIComponent(t)}` : this.url;
    this.setStatus('connecting');
    try {
      this.ws = new WebSocket(url);
    } catch (e) {
      this.setStatus('error');
      setTimeout(() => this.connect(), this.backoff);
      return;
    }

    this.ws.onopen = () => {
      this.setStatus('open');
      this.backoff = 1000;
      this.wantedChannels.forEach((ch) => this.safeSend({ type: 'subscribe', channel: ch }));
      this.startHeartbeat();
      this.scheduleTokenRotation();
    };
    this.ws.onclose = () => {
      this.setStatus('closed');
      this.stopHeartbeat();
      if (this.shouldReconnect) {
        const rand = 1 + (Math.random() * 2 - 1) * this.jitter; // 1±jitter
        const wait = Math.max(500, Math.floor(this.backoff * rand));
        this.backoff = Math.min(this.backoff * 2, this.maxBackoff);
        setTimeout(() => this.connect(), wait);
      }
    };
    this.ws.onerror = () => {
      this.setStatus('error');
    };
    this.ws.onmessage = (ev) => {
      let data: any = ev.data;
      try { data = JSON.parse(ev.data); } catch {}
      if (data && (data.type === 'pong' || data === 'pong')) return;
      // Detect auth errors from server push and trigger reconnection with refreshed token
      if (data && (data.type === 'auth_error' || data.code === 401)) {
        refreshAccessToken().then(newTok => {
          if (newTok) { try { this.ws?.close(); } catch {} }
        }).catch(()=>undefined);
        return;
      }
      const channel = data?.channel || data?.topic;
      if (channel && this.channels.has(channel)) {
        this.channels.get(channel)!.forEach((fn) => { try { fn(data); } catch {} });
      } else {
        this.emit(data);
      }
    };
  }

  disconnect() {
    this.shouldReconnect = false;
    try { this.ws?.close(); } catch {}
    this.ws = null;
    this.setStatus('closed');
    this.stopHeartbeat();
  }

  send(obj: any) {
    if (this.ws && this.status === 'open') {
      const payload = typeof obj === 'string' ? obj : JSON.stringify(obj);
      this.ws.send(payload);
    }
  }

  private safeSend(obj: any) { try { this.send(obj); } catch {} }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.status === 'open') this.safeSend({ type: 'ping', ts: Date.now() });
    }, 25000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null; }
  }

  private setStatus(s: WSStatus) {
    if (this.status !== s) { this.status = s; this.emitStatus(s); }
  }
}

export const realtimeClient = new RealtimeClient();
