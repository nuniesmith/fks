import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { usePrometheus } from './usePrometheusMetrics';

export interface FrontendMetricsOptions {
	enableNavigationTimings?: boolean;
	histogramBucketsMs?: number[];
}

export const useFrontendMetrics = (opts: FrontendMetricsOptions = {}) => {
	const { enableNavigationTimings = true, histogramBucketsMs = [25,50,75,100,150,200,300,500,750,1000,2000] } = opts;
	const prom = usePrometheus();
	const location = useLocation();
	const prevPathRef = useRef<string | null>(null);
	const navStartRef = useRef<number | null>(null);

	useEffect(() => {
		if (!enableNavigationTimings) return;
		try {
			const navEntries = performance.getEntriesByType('navigation');
			if (navEntries && navEntries.length > 0) {
				const nav = navEntries[0] as PerformanceNavigationTiming;
				const dcl = nav.domContentLoadedEventEnd - nav.startTime;
				const load = nav.loadEventEnd - nav.startTime;
				if (dcl >= 0) prom.set('frontend_nav_timing_dom_content_loaded_ms', dcl);
				if (load >= 0) prom.set('frontend_nav_timing_page_load_ms', load);
				prom.observe('frontend_ttfb_ms', nav.responseStart - nav.startTime, undefined, [50,100,200,300,500]);
			} else if ((performance as any).timing) {
				const t = (performance as any).timing;
				const dcl = t.domContentLoadedEventEnd - t.navigationStart;
				const load = t.loadEventEnd - t.navigationStart;
				if (dcl > 0) prom.set('frontend_nav_timing_dom_content_loaded_ms', dcl);
				if (load > 0) prom.set('frontend_nav_timing_page_load_ms', load);
				const ttfb = t.responseStart - t.navigationStart;
				if (ttfb > 0) prom.observe('frontend_ttfb_ms', ttfb, undefined, [50,100,200,300,500]);
			}
		} catch {}
	}, []); // eslint-disable-line react-hooks/exhaustive-deps

	const sanitize = (path: string) => {
		path = path.replace(/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/g, ':uuid');
		path = path.replace(/\b[0-9a-fA-F]{20,}\b/g, ':hex');
		path = path.replace(/\b\d+\b/g, ':id');
		return path;
	};

	useEffect(() => {
		const path = location.pathname + location.search;
		const sanitized = sanitize(path);
		if (prevPathRef.current !== null) {
			if (navStartRef.current != null) {
				const dur = performance.now() - navStartRef.current;
				prom.observe('frontend_route_change_duration_ms', dur, { to: sanitized }, histogramBucketsMs);
			}
			prom.inc('frontend_route_changes_total', { to: sanitized });
		}
		prevPathRef.current = path;
		navStartRef.current = performance.now();
	}, [location, prom, histogramBucketsMs]);

	useEffect(() => {
		const hash = (s: string) => { let h = 0, i = 0, len = s.length; while (i < len) { h = (h * 31 + s.charCodeAt(i++)) | 0; } return (h >>> 0).toString(36); };
		const FP_KEY = 'fks_error-fingerprints';
		const TTL_MS = 24 * 60 * 60 * 1000;
		interface StoredFp { fp: string; first: number; last: number; count: number; }
		let stored: StoredFp[] = [];
		try { const raw = localStorage.getItem(FP_KEY); if (raw) { const parsed = JSON.parse(raw); if (Array.isArray(parsed)) stored = parsed.filter(r => Date.now() - r.first < TTL_MS); } } catch {}
		const fingerprintSet = new Set<string>(stored.map(r => r.fp));
		const persist = () => { try { localStorage.setItem(FP_KEY, JSON.stringify(stored)); } catch {} };
		const recordFingerprint = (err: any, type: string) => {
			try {
				const stack = (err && err.error && err.error.stack) || err?.stack || err?.message || String(err) || 'unknown';
				const fp = hash(stack.slice(0, 2000));
				prom.inc('frontend_error_events_total');
				prom.inc('frontend_error_fingerprint_events_total', { fingerprint: fp, type });
				let rec = stored.find(r => r.fp === fp);
				if (!rec) { rec = { fp, first: Date.now(), last: Date.now(), count: 1 }; stored.push(rec); fingerprintSet.add(fp); }
				else { rec.last = Date.now(); rec.count += 1; }
				const before = stored.length;
				stored = stored.filter(r => Date.now() - r.first < TTL_MS);
				if (stored.length !== before) { const fresh = new Set(stored.map(r => r.fp)); fingerprintSet.clear(); fresh.forEach(v => fingerprintSet.add(v)); }
				prom.set('frontend_error_unique_fingerprints', fingerprintSet.size);
				prom.set('frontend_error_fingerprints_total_active_window', stored.reduce((a,b)=>a+b.count,0));
				persist();
			} catch { prom.inc('frontend_error_events_total'); }
		};
		const onError = (e: ErrorEvent) => { prom.inc('frontend_errors_total'); recordFingerprint(e, 'error'); };
		const onRejection = (e: PromiseRejectionEvent) => { prom.inc('frontend_errors_total', { type: 'promise' }); recordFingerprint(e.reason, 'promise'); };
		window.addEventListener('error', onError);
		window.addEventListener('unhandledrejection', onRejection);
		return () => { window.removeEventListener('error', onError); window.removeEventListener('unhandledrejection', onRejection); };
	}, []); // eslint-disable-line react-hooks/exhaustive-deps

	const recordRouteChange = (durationMs: number, to: string) => {
		const sanitized = sanitize(to);
		prom.observe('frontend_route_change_duration_ms', durationMs, { to: sanitized }, histogramBucketsMs);
		prom.inc('frontend_route_changes_total', { to: sanitized });
	};
	const recordError = (type?: string, error?: any) => {
		prom.inc('frontend_errors_total', type ? { type } : undefined);
		if (error) { try { (window as any).dispatchEvent(new ErrorEvent('error', { error })); } catch {} }
	};

	return { recordRouteChange, recordError };
};

export default useFrontendMetrics;
