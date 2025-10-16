// Minimal mock for lightweight-charts v5 used in unit tests.
// Provides deterministic no-op implementations so rendering code can run in jsdom.

export type UTCTimestamp = number;

interface Series {
  setData: (data: any[]) => void;
  update: (d: any) => void;
}

interface Chart {
  addSeries: (kind: string, options?: any) => Series;
  applyOptions: (_: any) => void;
  timeScale: () => ({ fitContent: () => void });
  remove: () => void;
}

export function createChart(_el: HTMLElement, _opts: any): Chart {
  const chart: Chart = {
    addSeries: () => ({
      setData: () => {},
      update: () => {}
    }),
    applyOptions: () => {},
    timeScale: () => ({ fitContent: () => {} }),
    remove: () => {}
  };
  return chart;
}

export type IChartApi = ReturnType<typeof createChart>;
export type ISeriesApi<T extends string> = Series;
export type LineData<T> = { time: T; value: number };
export type Time = UTCTimestamp;
