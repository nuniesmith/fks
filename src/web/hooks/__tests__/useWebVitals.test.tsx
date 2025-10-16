import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { PrometheusMetricsProvider, usePrometheus } from '../../shared/hooks/usePrometheusMetrics';
import { useWebVitals } from '@shared';

describe('useWebVitals', () => {
  it('captures basic vitals via mocked PerformanceObserver', () => {
    const listeners: Record<string, any> = {};
    class MockObserver {
      private cb: any;
      constructor(cb: any) { this.cb = cb; }
      observe(opts: any) { listeners[opts.type] = this.cb; }
      disconnect(){}
    }
    (global as any).PerformanceObserver = MockObserver as any;
    const wrapper: React.FC<{children: React.ReactNode}> = ({ children }) => <PrometheusMetricsProvider>{children}</PrometheusMetricsProvider>;
    const { result } = renderHook(() => { const api = usePrometheus(); useWebVitals(); return { api }; }, { wrapper });
    act(() => {
      listeners['largest-contentful-paint']?.({ getEntries: () => [{ startTime: 2500 }] });
      listeners['layout-shift']?.({ getEntries: () => [{ value: 0.12, hadRecentInput: false }] });
      listeners['event']?.({ getEntries: () => [{ duration: 160 }] });
    });
    const text = result.current.api.exportText();
    expect(text).toContain('frontend_web_vital_lcp_ms');
    expect(text).toContain('frontend_web_vital_cls');
    expect(text).toContain('frontend_web_vital_inp_ms');
  });
});
