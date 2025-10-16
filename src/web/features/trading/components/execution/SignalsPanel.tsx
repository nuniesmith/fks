import React, { useEffect, useMemo, useState } from 'react';
import { createDemoSignal, Signal, SignalKind } from '@shared/types/trading';
import { formatSignal } from '@shared/utils/tradingFormat';
import { useRealtime } from '@shared/hooks/useRealtime';

const kindColors: Record<SignalKind,string> = {
	[SignalKind.ENTRY]: 'text-emerald-400',
	[SignalKind.EXIT]: 'text-rose-400',
	[SignalKind.ALERT]: 'text-amber-400'
};

const SignalsPanel: React.FC = () => {
	const [signals, setSignals] = useState<Signal[]>(() => Array.from({ length: 6 }, () => createDemoSignal()));
	const [filter, setFilter] = useState<SignalKind | 'ALL'>('ALL');
	const { subscribe } = useRealtime();

	useEffect(() => {
		const off = subscribe('signals', msg => {
			if (msg?.type === 'signal') {
				setSignals(cur => [msg.signal as Signal, ...cur].slice(0, 100));
			}
		});
		return () => { off(); };
	}, [subscribe]);

	const filtered = useMemo(() => filter === 'ALL' ? signals : signals.filter(s => s.kind === filter), [signals, filter]);

	return (
		<div className="p-4 space-y-3" data-testid="signals-root">
			<header className="flex items-center gap-2">
				<h2 className="text-sm font-semibold tracking-wide">Signals</h2>
				<select data-testid="signals-filter" value={filter} onChange={e => setFilter(e.target.value as any)} className="bg-neutral-900 text-xs rounded px-2 py-1 border border-neutral-700">
					<option value="ALL">All</option>
					{Object.values(SignalKind).map(k => <option key={k} value={k}>{k}</option>)}
				</select>
				<button data-testid="add-signal" onClick={() => setSignals(cur => [createDemoSignal(), ...cur])} className="px-2 py-1 text-xs rounded bg-emerald-600 hover:bg-emerald-500 text-white">Add Demo</button>
				<span className="ml-auto text-[10px] uppercase opacity-60" data-testid="signals-count">{signals.length} total</span>
			</header>
			<div className="h-64 overflow-auto border border-neutral-700 rounded divide-y divide-neutral-800 text-xs font-mono leading-tight" data-testid="signals-list">
				{filtered.map(s => (
					<div key={s.id} data-signal-id={s.id} className="px-2 py-1 flex items-center gap-2 hover:bg-neutral-800/40">
						<span className={kindColors[s.kind] + ' w-10'}>{s.kind}</span>
						<span className="w-20">{s.symbol}</span>
						<span className="flex-1 truncate">{s.message || formatSignal(s)}</span>
						<span className="opacity-50 tabular-nums">{new Date(s.ts).toLocaleTimeString()}</span>
					</div>
				))}
				{filtered.length === 0 && <div className="px-2 py-4 text-center text-neutral-500" data-testid="signals-empty">No signals</div>}
			</div>
		</div>
	);
};

export default SignalsPanel;
