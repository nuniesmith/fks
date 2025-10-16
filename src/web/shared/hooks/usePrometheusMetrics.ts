import React, { createContext, useCallback, useContext, useEffect, useRef } from 'react';

// Simplified Prometheus-like metrics provider (moved to shared)
type LabelValues = Record<string, string | number | boolean | undefined>;

interface CounterMetric { type: 'counter'; help?: string; values: Map<string, number>; }
interface GaugeMetric { type: 'gauge'; help?: string; values: Map<string, number>; }
interface HistogramBucket { le: number; count: number; }
interface HistogramMetric { type: 'histogram'; help?: string; buckets: number[]; values: Map<string, { buckets: HistogramBucket[]; sum: number; count: number; }>; }

interface Registry {
	counters: Record<string, CounterMetric>;
	gauges: Record<string, GaugeMetric>;
	histograms: Record<string, HistogramMetric>;
}

interface PrometheusAPI {
	inc: (name: string, labels?: LabelValues, value?: number, help?: string) => void;
	set: (name: string, value: number, labels?: LabelValues, help?: string) => void;
	observe: (name: string, value: number, labels?: LabelValues, buckets?: number[], help?: string) => void;
	exportText: () => string;
	reset: () => void;
	registryRef: React.MutableRefObject<Registry>;
}

const Ctx = createContext<PrometheusAPI | null>(null);

const serializeLabels = (labels?: LabelValues) => {
	if (!labels) return '';
	const entries = Object.entries(labels)
		.filter(([, v]) => v !== undefined)
		.map(([k, v]) => `${k}="${String(v).replace(/"/g, '\\"')}"`);
	return entries.length ? `{${entries.join(',')}}` : '';
};

export const PrometheusMetricsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
	const registryRef = useRef<Registry>({ counters: {}, gauges: {}, histograms: {} });

	const inc = useCallback((name: string, labels?: LabelValues, value = 1, help?: string) => {
		let metric = registryRef.current.counters[name];
		if (!metric) {
			metric = { type: 'counter', help, values: new Map() };
			registryRef.current.counters[name] = metric;
		}
		const key = serializeLabels(labels);
		metric.values.set(key, (metric.values.get(key) || 0) + value);
	}, []);

	const set = useCallback((name: string, value: number, labels?: LabelValues, help?: string) => {
		let metric = registryRef.current.gauges[name];
		if (!metric) {
			metric = { type: 'gauge', help, values: new Map() };
			registryRef.current.gauges[name] = metric;
		}
		const key = serializeLabels(labels);
		metric.values.set(key, value);
	}, []);

	const observe = useCallback((name: string, value: number, labels?: LabelValues, buckets: number[] = [50, 100, 200, 300, 500, 750, 1000, 2000, 5000], help?: string) => {
		let metric = registryRef.current.histograms[name];
		if (!metric) {
			metric = { type: 'histogram', help, buckets: [...buckets].sort((a, b) => a - b), values: new Map() };
			registryRef.current.histograms[name] = metric;
		}
		const key = serializeLabels(labels);
		let rec = metric.values.get(key);
		if (!rec) {
			rec = { buckets: metric.buckets.map(le => ({ le, count: 0 })), sum: 0, count: 0 };
			metric.values.set(key, rec);
		}
		rec.count += 1;
		rec.sum += value;
		for (const b of rec.buckets) {
			if (value <= b.le) b.count += 1;
		}
	}, []);

	const reset = useCallback(() => {
		registryRef.current = { counters: {}, gauges: {}, histograms: {} };
	}, []);

	const exportText = useCallback(() => {
		const lines: string[] = [];
		Object.entries(registryRef.current.counters).forEach(([name, m]) => {
			if (m.help) lines.push(`# HELP ${name} ${m.help}`);
			lines.push(`# TYPE ${name} counter`);
			m.values.forEach((v, k) => {
				lines.push(`${name}${k}${k ? ' ' : ''}${v}`.trim());
			});
		});
		Object.entries(registryRef.current.gauges).forEach(([name, m]) => {
			if (m.help) lines.push(`# HELP ${name} ${m.help}`);
			lines.push(`# TYPE ${name} gauge`);
			m.values.forEach((v, k) => {
				lines.push(`${name}${k}${k ? ' ' : ''}${v}`.trim());
			});
		});
		Object.entries(registryRef.current.histograms).forEach(([name, m]) => {
			if (m.help) lines.push(`# HELP ${name} ${m.help}`);
			lines.push(`# TYPE ${name} histogram`);
			m.values.forEach((rec, k) => {
				let cumulative = 0;
				rec.buckets.forEach(b => {
					cumulative = b.count;
					lines.push(
						`${name}_bucket${k.replace(/}$/,'')}${k ? (k.slice(-1) === '}' ? ',' : '{') : '{'}le="${b.le}"}${k ? '}' : '}'} ${cumulative}`
							.replace('{}', '{')
							.replace(',}', '}')
					);
				});
				lines.push(
					`${name}_bucket${k.replace(/}$/,'')}${k ? (k.slice(-1) === '}' ? ',' : '{') : '{'}le="+Inf"}${k ? '}' : '}'} ${rec.count}`
						.replace('{}', '{')
						.replace(',}', '}')
				);
				lines.push(`${name}_sum${k} ${rec.sum}`);
				lines.push(`${name}_count${k} ${rec.count}`);
			});
		});
		return lines.join('\n');
	}, []);

		const api: PrometheusAPI = { inc, set, observe, exportText, reset, registryRef };
		return React.createElement(Ctx.Provider, { value: api }, children);
};

export const usePrometheus = () => {
	const ctx = useContext(Ctx);
	if (!ctx) throw new Error('usePrometheus must be used within PrometheusMetricsProvider');
	return ctx;
};

export const usePrometheusPushGateway = (opts: { url: string; job: string; instance?: string; intervalMs?: number; enabled?: boolean }) => {
	const { exportText } = usePrometheus();
	const { url, job, instance, intervalMs = 15000, enabled = true } = opts;
	useEffect(() => {
		if (!enabled) return;
		let active = true;
		let timer: any;
		const push = async () => {
			try {
				const body = exportText();
				await fetch(`${url.replace(/\/$/, '')}/metrics/job/${encodeURIComponent(job)}${instance ? `/instance/${encodeURIComponent(instance)}` : ''}`, {
					method: 'POST',
					body,
					headers: { 'Content-Type': 'text/plain' }
				});
			} catch {}
			if (active) timer = setTimeout(push, intervalMs);
		};
		push();
		return () => { active = false; clearTimeout(timer); };
	}, [url, job, instance, intervalMs, enabled, exportText]);
};

export const getOptionalPrometheus = () => null;
