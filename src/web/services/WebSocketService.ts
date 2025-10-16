// WebSocket service for real-time data connections
export interface WebSocketMessage {
  type: string;
  timestamp: string;
  data: any;
}

export interface WebSocketConfig {
  url: string;
  protocols?: string[];
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

export type WebSocketEventHandler = (message: WebSocketMessage) => void;
export type WebSocketStatusHandler = (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private eventHandlers: Map<string, WebSocketEventHandler[]> = new Map();
  private statusHandlers: WebSocketStatusHandler[] = [];
  private reconnectAttempts = 0;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isConnecting = false;
  private shouldReconnect = true;

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectInterval: 5000,
      maxReconnectAttempts: 5,
      heartbeatInterval: 30000,
      ...config
    };
  }

  public connect(): void {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    this.notifyStatusHandlers('connecting');

    try {
      this.ws = new WebSocket(this.config.url, this.config.protocols);
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      this.isConnecting = false;
      this.notifyStatusHandlers('error');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.shouldReconnect = false;
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  public send(message: any): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket is not connected');
      return false;
    }

    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  public on(eventType: string, handler: WebSocketEventHandler): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, []);
    }
    this.eventHandlers.get(eventType)!.push(handler);
  }

  public off(eventType: string, handler: WebSocketEventHandler): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index >= 0) {
        handlers.splice(index, 1);
      }
    }
  }

  public onStatusChange(handler: WebSocketStatusHandler): void {
    this.statusHandlers.push(handler);
  }

  public offStatusChange(handler: WebSocketStatusHandler): void {
    const index = this.statusHandlers.indexOf(handler);
    if (index >= 0) {
      this.statusHandlers.splice(index, 1);
    }
  }

  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private handleOpen(): void {
    console.log('WebSocket connected');
    this.isConnecting = false;
    this.reconnectAttempts = 0;
    this.notifyStatusHandlers('connected');
    this.startHeartbeat();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.notifyEventHandlers(message.type, message);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private handleError(error: Event): void {
    console.error('WebSocket error:', error);
    this.notifyStatusHandlers('error');
  }

  private handleClose(event: CloseEvent): void {
    console.log('WebSocket disconnected:', event.code, event.reason);
    this.isConnecting = false;
    this.ws = null;
    this.notifyStatusHandlers('disconnected');
    
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    
    if (this.shouldReconnect) {
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts!) {
      console.log('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.config.reconnectInterval! * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
    
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    if (this.config.heartbeatInterval && this.config.heartbeatInterval > 0) {
      this.heartbeatTimer = setInterval(() => {
        this.send({ type: 'ping', timestamp: new Date().toISOString() });
      }, this.config.heartbeatInterval);
    }
  }

  private notifyEventHandlers(eventType: string, message: WebSocketMessage): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in WebSocket event handler:', error);
        }
      });
    }
  }

  private notifyStatusHandlers(status: 'connecting' | 'connected' | 'disconnected' | 'error'): void {
    this.statusHandlers.forEach(handler => {
      try {
        handler(status);
      } catch (error) {
        console.error('Error in WebSocket status handler:', error);
      }
    });
  }
}

// WebSocket service factory
export class WebSocketServiceFactory {
  private static instances: Map<string, WebSocketService> = new Map();

  public static createMarketDataService(baseUrl: string): WebSocketService {
    const key = `market-data-${baseUrl}`;
    
    if (!this.instances.has(key)) {
      const wsUrl = baseUrl.replace(/^http/, 'ws') + '/ws/market-data';
      const service = new WebSocketService({
        url: wsUrl,
        reconnectInterval: 3000,
        maxReconnectAttempts: 10,
        heartbeatInterval: 30000
      });
      
      this.instances.set(key, service);
    }
    
    return this.instances.get(key)!;
  }

  public static createAccountUpdatesService(baseUrl: string): WebSocketService {
    const key = `account-updates-${baseUrl}`;
    
    if (!this.instances.has(key)) {
      const wsUrl = baseUrl.replace(/^http/, 'ws') + '/ws/account-updates';
      const service = new WebSocketService({
        url: wsUrl,
        reconnectInterval: 5000,
        maxReconnectAttempts: 5,
        heartbeatInterval: 60000
      });
      
      this.instances.set(key, service);
    }
    
    return this.instances.get(key)!;
  }

  public static cleanup(): void {
    this.instances.forEach(service => {
      service.disconnect();
    });
    this.instances.clear();
  }
}
