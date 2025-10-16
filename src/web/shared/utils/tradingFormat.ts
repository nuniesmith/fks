import { Order, OrderStatus, OrderType, Signal } from '../types/trading';

export function formatOrder(o: Order): string {
  const type = o.type === OrderType.MARKET ? 'MKT' : o.type;
  const filledPct = o.qty ? Math.round((o.filledQty / o.qty) * 100) : 0;
  return `${o.symbol} ${o.side[0]} ${o.qty}@${type}${o.limitPrice ? ':'+o.limitPrice : ''} [${filledPct}%] ${o.status}`;
}

export function conciseStatus(status: OrderStatus): string {
  switch (status) {
    case OrderStatus.NEW: return 'New';
    case OrderStatus.WORKING: return 'Wrk';
    case OrderStatus.PARTIAL: return 'Part';
    case OrderStatus.FILLED: return 'Fill';
    case OrderStatus.CANCELLED: return 'Canc';
    case OrderStatus.REJECTED: return 'Rej';
    default: return status;
  }
}

export function formatSignal(sig: Signal): string {
  return `${sig.symbol} ${sig.kind}${sig.strategy ? ' '+sig.strategy : ''}${sig.strength!=null ? ' s='+sig.strength : ''}`;
}
