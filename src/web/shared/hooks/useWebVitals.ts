import { useEffect } from 'react';
import { usePrometheus } from './usePrometheusMetrics';

interface PerfEntryLike { name: string; startTime: number; value?: number; duration?: number; entryType?: string; }

export const useWebVitals = () => {
	const prom = usePrometheus();
	useEffect(() => {
		if (typeof PerformanceObserver === 'undefined') return;
		try {
			const lcpObserver = new PerformanceObserver(list => {
				const entries = list.getEntries();
				const last = entries[entries.length - 1] as PerfEntryLike | undefined;
				if (last) prom.set('frontend_web_vital_lcp_ms', last.startTime);
			});
			lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true } as any);
		} catch {}
		try {
			let clsValue = 0;
			const clsObserver = new PerformanceObserver(list => {
				for (const entry of list.getEntries() as any as PerfEntryLike[]) {
					const anyEntry: any = entry;
					if (anyEntry && anyEntry.value && !anyEntry.hadRecentInput) {
						clsValue += anyEntry.value;
						prom.set('frontend_web_vital_cls', +clsValue.toFixed(4));
					}
				}
			});
			clsObserver.observe({ type: 'layout-shift', buffered: true } as any);
		} catch {}
		try {
			const inpObserver = new PerformanceObserver(list => {
				for (const entry of list.getEntries() as any as PerfEntryLike[]) {
					const anyEntry: any = entry;
					const dur = (anyEntry.processingEnd || anyEntry.duration || 0);
					if (dur > 0) prom.set('frontend_web_vital_inp_ms', dur);
				}
			});
			inpObserver.observe({ type: 'event', buffered: true } as any);
		} catch {}
	}, [prom]);
};

export default useWebVitals;
