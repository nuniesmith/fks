// Trading domain shared types & enums
// Centralized primitives so features/components can converge on one model.

export enum OrderSide {
  BUY = 'BUY',
  SELL = 'SELL'
}

export enum OrderType {
  MARKET = 'MARKET',
  LIMIT = 'LIMIT',
  STOP = 'STOP'
}

export enum OrderStatus {
  NEW = 'NEW',
  WORKING = 'WORKING',
  PARTIAL = 'PARTIAL',
  FILLED = 'FILLED',
  CANCELLED = 'CANCELLED',
  REJECTED = 'REJECTED'
}

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  qty: number;
  filledQty: number;
  limitPrice?: number;
  stopPrice?: number;
  status: OrderStatus;
  createdAt: number; // epoch ms
  updatedAt: number; // epoch ms
  meta?: Record<string, any>;
}

export enum SignalKind {
  ENTRY = 'ENTRY',
  EXIT = 'EXIT',
  ALERT = 'ALERT'
}

export interface Signal {
  id: string;
  symbol: string;
  kind: SignalKind;
  strength?: number; // 0-1 normalized
  message?: string;
  ts: number; // epoch ms
  strategy?: string;
  meta?: Record<string, any>;
}

export interface RealtimeEvent<T = any> {
  channel: string;
  payload: T;
  ts?: number;
}

export type OrderUpdate = Partial<Pick<Order,'status'|'filledQty'|'updatedAt'|'limitPrice'|'stopPrice'>> & { id: string };

export const demoSymbols = ['AAPL','MSFT','NVDA','ETHUSD','BTCUSD'];

export function createDemoOrder(partial: Partial<Order> = {}): Order {
  const now = Date.now();
  return {
    id: partial.id || `demo_${Math.random().toString(36).slice(2,10)}`,
    symbol: partial.symbol || demoSymbols[Math.floor(Math.random()*demoSymbols.length)],
    side: partial.side || (Math.random() > 0.5 ? OrderSide.BUY : OrderSide.SELL),
    type: partial.type || OrderType.MARKET,
    qty: partial.qty ?? (Math.floor(Math.random()*9)+1)*10,
    filledQty: partial.filledQty ?? 0,
    status: partial.status || OrderStatus.NEW,
    createdAt: partial.createdAt || now,
    updatedAt: partial.updatedAt || now,
    ...partial
  };
}

export function createDemoSignal(partial: Partial<Signal> = {}): Signal {
  return {
    id: partial.id || `sig_${Math.random().toString(36).slice(2,10)}`,
    symbol: partial.symbol || demoSymbols[Math.floor(Math.random()*demoSymbols.length)],
    kind: partial.kind || SignalKind.ENTRY,
    strength: partial.strength ?? +(Math.random()).toFixed(2),
    ts: partial.ts || Date.now(),
    ...partial
  };
}
