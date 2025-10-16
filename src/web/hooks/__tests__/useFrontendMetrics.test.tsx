import { renderHook, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import { useFrontendMetrics } from '@shared';
import { PrometheusMetricsProvider, usePrometheus } from '../../shared/hooks/usePrometheusMetrics';

describe('useFrontendMetrics', () => {
  it('records route change and error counters', () => {
    const wrapper: React.FC<{children: React.ReactNode}> = ({ children }) => (
      <PrometheusMetricsProvider>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </PrometheusMetricsProvider>
    );
    const { result } = renderHook(() => {
      const api = usePrometheus();
      const { recordRouteChange, recordError } = useFrontendMetrics({ enableNavigationTimings: false });
      return { api, recordRouteChange, recordError };
    }, { wrapper });
    act(() => {
      result.current.recordRouteChange(42, '/test');
      result.current.recordError('manual');
    });
    const text = result.current.api.exportText();
    expect(text).toContain('frontend_route_changes_total');
    expect(text).toContain('frontend_errors_total');
    expect(text).toContain('frontend_route_change_duration_ms_bucket');
  });
});
