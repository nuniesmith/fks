import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createDemoOrder, Order, OrderSide, OrderStatus } from '@shared/types/trading';
import { formatOrder } from '@shared/utils/tradingFormat';
import { useRealtime } from '@shared/hooks/useRealtime';

interface Column { key: keyof Order | 'actions'; label: string; }
const columns: Column[] = [
	{ key: 'symbol', label: 'Symbol' },
	{ key: 'side', label: 'Side' },
	{ key: 'type', label: 'Type' },
	{ key: 'qty', label: 'Qty' },
	{ key: 'filledQty', label: 'Filled' },
	{ key: 'status', label: 'Status' },
	{ key: 'actions', label: 'Actions' }
];

const OrderManagement: React.FC = () => {
	const [orders, setOrders] = useState<Order[]>(() => Array.from({ length: 4 }, () => createDemoOrder()));
	const { subscribe } = useRealtime();

	useEffect(() => {
		const off = subscribe('orders', msg => {
			if (msg?.type === 'order_update' && msg.order?.id) {
				setOrders(cur => cur.map(o => o.id === msg.order.id ? { ...o, ...msg.order, updatedAt: Date.now() } : o));
			}
		});
		return () => { off(); };
	}, [subscribe]);

	const addOrder = useCallback(() => setOrders(cur => [createDemoOrder(), ...cur]), []);
	const cancelOrder = useCallback((id: string) => setOrders(cur => cur.map(o => o.id === id ? { ...o, status: OrderStatus.CANCELLED, updatedAt: Date.now() } : o)), []);
	const fillOrder = useCallback((id: string) => setOrders(cur => cur.map(o => o.id === id ? { ...o, filledQty: o.qty, status: OrderStatus.FILLED, updatedAt: Date.now() } : o)), []);
	const working = useMemo(() => orders.filter(o => [OrderStatus.WORKING, OrderStatus.NEW].includes(o.status)), [orders]);

	return (
		<div className="p-4 space-y-4" data-testid="orders-root">
			<header className="flex items-center gap-2">
				<h2 className="text-sm font-semibold tracking-wide">Orders</h2>
				<button data-testid="add-order" onClick={addOrder} className="px-2 py-1 text-xs rounded bg-emerald-600 hover:bg-emerald-500 text-white">Add Demo</button>
				<span className="ml-auto text-[10px] uppercase opacity-60" data-testid="order-count">{working.length} open / {orders.length} total</span>
			</header>
			<div className="overflow-auto border border-neutral-700 rounded">
				<table className="min-w-full text-xs" data-testid="orders-table">
					<thead className="bg-neutral-900/60">
						<tr>{columns.map(c => <th key={c.key as string} className="px-2 py-1 text-left font-medium whitespace-nowrap">{c.label}</th>)}</tr>
					</thead>
					<tbody>
						{orders.map(o => (
							<tr key={o.id} data-order-id={o.id} className="border-t border-neutral-800 hover:bg-neutral-800/40 transition-colors">
								<td className="px-2 py-1 font-mono">{o.symbol}</td>
								<td className={"px-2 py-1 font-semibold " + (o.side === OrderSide.BUY ? 'text-emerald-400' : 'text-rose-400')}>{o.side[0]}</td>
								<td className="px-2 py-1">{o.type}</td>
								<td className="px-2 py-1 tabular-nums">{o.qty}</td>
								<td className="px-2 py-1 tabular-nums">{o.filledQty}</td>
								<td className="px-2 py-1" data-status={o.status}>{o.status}</td>
								<td className="px-2 py-1 flex gap-1">
									{o.status === OrderStatus.NEW && <button data-testid={`work-${o.id}`} onClick={() => setOrders(cur => cur.map(x => x.id === o.id ? { ...x, status: OrderStatus.WORKING } : x))} className="px-1 py-0.5 rounded bg-blue-600 hover:bg-blue-500">Work</button>}
									{[OrderStatus.NEW, OrderStatus.WORKING].includes(o.status) && <button data-testid={`cancel-${o.id}`} onClick={() => cancelOrder(o.id)} className="px-1 py-0.5 rounded bg-neutral-600 hover:bg-neutral-500">Cancel</button>}
									{o.status === OrderStatus.WORKING && <button data-testid={`fill-${o.id}`} onClick={() => fillOrder(o.id)} className="px-1 py-0.5 rounded bg-emerald-600 hover:bg-emerald-500">Fill</button>}
								</td>
							</tr>
						))}
						{orders.length === 0 && <tr><td colSpan={columns.length} className="px-2 py-4 text-center text-neutral-500">No orders</td></tr>}
					</tbody>
				</table>
			</div>
			<details className="text-[10px] opacity-60">
				<summary>Debug snapshot</summary>
				<pre className="whitespace-pre-wrap leading-snug mt-2" data-testid="orders-debug">{orders.map(formatOrder).join('\n')}</pre>
			</details>
		</div>
	);
};

export default OrderManagement;
