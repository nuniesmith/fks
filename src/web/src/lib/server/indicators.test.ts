import { describe, it, expect } from "vitest";
import { computeIndicators, INDICATOR_CATALOG, type Candle, type Point } from "./indicators";

// Build a candle series from a close array. High/low default to the close
// (flat candles) unless overridden; volume defaults to 0. Times are evenly
// spaced epoch seconds so we can assert alignment.
function candles(
  closes: number[],
  opts: { volume?: number[]; high?: number[]; low?: number[] } = {},
): Candle[] {
  return closes.map((c, i) => ({
    time: 1000 + i * 60,
    open: c,
    high: opts.high?.[i] ?? c,
    low: opts.low?.[i] ?? c,
    close: c,
    volume: opts.volume?.[i] ?? 0,
  }));
}

const vals = (pts: Point[]): number[] => pts.map((p) => p.value);

describe("computeIndicators", () => {
  it("returns {} for no names and ignores empty / unknown names", () => {
    expect(computeIndicators(candles([1, 2, 3]), [])).toEqual({});
    expect(computeIndicators(candles([1, 2, 3]), ["", "  ", "nonsense"])).toEqual({});
  });

  it("SMA(3) omits the warm-up and averages a trailing window, aligned to candle time", () => {
    const out = computeIndicators(candles([1, 2, 3, 4, 5]), ["sma3"]);
    expect(vals(out.sma3)).toEqual([2, 3, 4]);
    // first point is the 3rd candle (index 2) — warm-up omitted
    expect(out.sma3[0].time).toBe(1000 + 2 * 60);
  });

  it("RSI is 100 on a strictly rising series (no losses)", () => {
    const closes = Array.from({ length: 20 }, (_, i) => 100 + i);
    const out = computeIndicators(candles(closes), ["rsi"]);
    expect(out.rsi.length).toBeGreaterThan(0);
    for (const p of out.rsi) expect(p.value).toBe(100);
  });

  it("OBV adds volume on up-closes and subtracts on down-closes", () => {
    const out = computeIndicators(
      candles([10, 11, 10, 12], { volume: [5, 3, 2, 4] }),
      ["obv"],
    );
    expect(vals(out.obv)).toEqual([0, 3, 1, 5]);
  });

  it("Bollinger Bands collapse to the mean on a constant series (zero stdev)", () => {
    const out = computeIndicators(candles(new Array(25).fill(100)), ["bbands"]);
    expect(out.bb_upper.length).toBeGreaterThan(0);
    expect(out.bb_upper.length).toBe(out.bb_middle.length);
    for (let i = 0; i < out.bb_upper.length; i++) {
      expect(out.bb_middle[i].value).toBe(100);
      expect(out.bb_upper[i].value).toBe(100);
      expect(out.bb_lower[i].value).toBe(100);
    }
  });

  it("VWAP equals the price when H=L=C is constant", () => {
    const out = computeIndicators(
      candles(new Array(5).fill(50), { volume: [1, 1, 1, 1, 1] }),
      ["vwap"],
    );
    expect(out.vwap.length).toBe(5);
    for (const p of out.vwap) expect(p.value).toBe(50);
  });

  it("MACD emits line / signal / hist once there is enough data", () => {
    const closes = Array.from({ length: 60 }, (_, i) => 100 + Math.sin(i / 3) * 5);
    const out = computeIndicators(candles(closes), ["macd"]);
    expect(out.macd_line.length).toBeGreaterThan(0);
    expect(out.macd_signal.length).toBeGreaterThan(0);
    expect(out.macd_hist.length).toBeGreaterThan(0);
  });

  it("supports dynamic ema<N> / sma<N> / wma<N> names", () => {
    const out = computeIndicators(candles([1, 2, 3, 4, 5]), ["ema2", "wma2"]);
    expect(out.ema2).toBeDefined();
    expect(out.wma2).toBeDefined();
    // WMA(2) of the first window [1,2] with weights (1,2)/3 = (1·1 + 2·2)/3
    expect(out.wma2[0].value).toBeCloseTo((1 * 1 + 2 * 2) / 3, 4);
  });

  it("tolerates a series too short for the requested indicator", () => {
    // 3 candles < RSI(14) warm-up → no points, not a throw.
    expect(computeIndicators(candles([1, 2, 3]), ["rsi", "atr"])).toEqual({
      rsi: [],
      atr: [],
    });
  });
});

describe("INDICATOR_CATALOG", () => {
  it("exposes the expected indicator set", () => {
    const ids = INDICATOR_CATALOG.map((m) => m.id);
    expect(INDICATOR_CATALOG.length).toBe(16);
    for (const id of ["ema9", "sma20", "bbands", "rsi", "macd", "atr", "adx"]) {
      expect(ids).toContain(id);
    }
  });

  it("tags panes and lists the emit keys each indicator produces", () => {
    const rsi = INDICATOR_CATALOG.find((m) => m.id === "rsi");
    expect(rsi?.pane).toBe("separate");
    expect(rsi?.keys).toEqual(["rsi"]);

    const bb = INDICATOR_CATALOG.find((m) => m.id === "bbands");
    expect(bb?.pane).toBe("overlay");
    expect(bb?.keys).toEqual(["bb_upper", "bb_middle", "bb_lower"]);
  });
});
