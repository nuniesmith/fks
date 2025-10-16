import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { PrometheusMetricsProvider, usePrometheus } from '../../shared/hooks/usePrometheusMetrics';

describe('usePrometheusMetrics', () => {
  it('records and exports counter and histogram', () => {
    const wrapper: React.FC<{children: React.ReactNode}> = ({ children }) => <PrometheusMetricsProvider>{children}</PrometheusMetricsProvider>;
    const { result } = renderHook(() => usePrometheus(), { wrapper });
    act(() => {
      result.current.inc('test_counter_total', { route: '/x' });
      result.current.observe('test_latency_ms', 120, { route: '/x' }, [100,200]);
      result.current.observe('test_latency_ms', 80, { route: '/x' }, [100,200]);
    });
    const text = result.current.exportText();
    expect(text).toContain('test_counter_total');
    expect(text).toContain('test_latency_ms_bucket');
    expect(text).toContain('test_latency_ms_sum');
  });
});
