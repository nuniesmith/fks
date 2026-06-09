import { describe, it, expect } from "vitest";
import {
  type CandleRow,
  humanizeSince,
  intervalToSeconds,
  mapCandleRows,
  reshapeHealth,
  reshapePerformance,
  reshapeRiskConfig,
  resampleCandles,
  sanitizeInterval,
  sanitizeSymbol,
  toRiskConfigPayload,
  wantsArrayResponse,
} from "./reshape";

describe("reshapeHealth", () => {
  it("builds the StatusBar + System Info superset", () => {
    const out = reshapeHealth({
      status: "ok",
      version: "1.2.3",
      uptime: "3h",
      forward_service: "running",
      components: { redis: { status: "up" }, data: { status: "live" } },
    });
    expect(out.status).toBe("ok");
    expect(out.janus).toBe("ok");
    expect(out.version).toBe("1.2.3");
    expect(out.uptime).toBe("3h");
    expect(out.redis).toBe("up");
    expect(out.feed).toBe("running"); // forward_service wins
  });

  it("defaults to down / — on an empty payload", () => {
    const out = reshapeHealth({});
    expect(out.status).toBe("down");
    expect(out.janus).toBe("down");
    expect(out.redis).toBe("—");
    expect(out.feed).toBe("—");
    expect(out.components).toEqual({});
  });

  it("falls back to component statuses for the feed", () => {
    expect(reshapeHealth({ components: { data: { status: "live" } } }).feed).toBe("live");
    expect(reshapeHealth({ components: { questdb: { status: "ok" } } }).feed).toBe("ok");
  });
});

describe("reshapePerformance", () => {
  it("prefers risk over dashboard on overlap and maps field aliases", () => {
    const out = reshapePerformance(
      { win_rate: 0.7, net_pnl: 100 },
      { win_rate: 0.5, trades: 10 },
    );
    expect(out.win_rate).toBe(0.7); // risk wins over dashboard
    expect(out.total_pnl).toBe(100); // net_pnl alias
    expect(out.total_trades).toBe(10); // dashboard `trades` alias
  });

  it("drops non-numeric values and tolerates null inputs", () => {
    expect(reshapePerformance({ total_trades: "5" }, {}).total_trades).toBeUndefined();
    const empty = reshapePerformance(null, null);
    expect(empty.win_rate).toBeUndefined();
    expect(empty.total_pnl).toBeUndefined();
  });
});

describe("reshapeRiskConfig", () => {
  it("surfaces the daily-loss halt threshold as positive USD", () => {
    expect(reshapeRiskConfig({ max_daily_loss: -5000 }).max_daily_loss_usd).toBe(5000);
    expect(reshapeRiskConfig({ daily_loss: -3000 }).max_daily_loss_usd).toBe(3000);
  });

  it("maps positions + gross exposure and tolerates empty", () => {
    const out = reshapeRiskConfig({
      max_concurrent_positions: 10,
      max_gross_exposure: 2_000_000,
    });
    expect(out.max_positions).toBe(10);
    expect(out.max_gross_exposure_usd).toBe(2_000_000);
    const empty = reshapeRiskConfig({});
    expect(empty.max_daily_loss_usd).toBeUndefined();
    expect(empty.max_positions).toBeUndefined();
  });
});

describe("toRiskConfigPayload", () => {
  it("flips the daily-loss sign to rustrade's ≤ 0 halt threshold", () => {
    expect(toRiskConfigPayload({ max_daily_loss_usd: 5000 }).max_daily_loss).toBe(-5000);
    // already negative → normalized to a negative magnitude, never positive
    expect(toRiskConfigPayload({ max_daily_loss_usd: -5000 }).max_daily_loss).toBe(-5000);
  });

  it("coerces string form values (number inputs arrive as strings)", () => {
    const out = toRiskConfigPayload({
      max_daily_loss_usd: "5000",
      max_positions: "10",
      max_gross_exposure_usd: "2000000",
    });
    expect(out.max_daily_loss).toBe(-5000);
    expect(out.max_concurrent_positions).toBe(10);
    expect(out.max_gross_exposure).toBe(2_000_000);
  });

  it("leaves missing / non-numeric fields undefined", () => {
    const out = toRiskConfigPayload({});
    expect(out.max_daily_loss).toBeUndefined();
    expect(out.max_concurrent_positions).toBeUndefined();
    expect(out.max_gross_exposure).toBeUndefined();
    expect(toRiskConfigPayload({ max_positions: "abc" }).max_concurrent_positions).toBeUndefined();
  });
});

describe("humanizeSince", () => {
  it("returns — for missing / invalid input", () => {
    expect(humanizeSince(undefined)).toBe("—");
    expect(humanizeSince("not-a-date")).toBe("—");
  });

  it("formats compact ages", () => {
    const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
    expect(humanizeSince(ago(30_000))).toBe("30s");
    expect(humanizeSince(ago(90_000))).toBe("1m");
    expect(humanizeSince(ago(2 * 3_600_000))).toBe("2h");
    expect(humanizeSince(ago(3 * 86_400_000))).toBe("3d");
  });
});

describe("sanitizeSymbol", () => {
  it("keeps valid symbol characters", () => {
    expect(sanitizeSymbol("BTC/USD")).toBe("BTC/USD");
    expect(sanitizeSymbol("XBTUSDTM")).toBe("XBTUSDTM");
    expect(sanitizeSymbol("ETH-USD.PERP")).toBe("ETH-USD.PERP");
  });

  it("strips SQL-injection metacharacters (the QuestDB query guard)", () => {
    // quotes, spaces, semicolons, parens, equals are all removed
    expect(sanitizeSymbol("a b;c(d)='e'")).toBe("abcde");
    expect(sanitizeSymbol("BTC'); DROP TABLE candles_crypto; --")).toBe(
      "BTCDROPTABLEcandles_crypto--",
    );
  });

  it("caps length and tolerates null / undefined", () => {
    expect(sanitizeSymbol("A".repeat(50))).toHaveLength(32);
    expect(sanitizeSymbol("A".repeat(50), 24)).toHaveLength(24);
    expect(sanitizeSymbol(null)).toBe("");
    expect(sanitizeSymbol(undefined)).toBe("");
  });
});

describe("sanitizeInterval", () => {
  it("keeps valid interval tokens", () => {
    expect(sanitizeInterval("5m")).toBe("5m");
    expect(sanitizeInterval("1h")).toBe("1h");
    expect(sanitizeInterval("1D")).toBe("1D");
  });

  it("defaults to 5m for empty / fully-stripped input", () => {
    expect(sanitizeInterval(null)).toBe("5m");
    expect(sanitizeInterval("")).toBe("5m");
    expect(sanitizeInterval("'; --")).toBe("5m"); // all chars stripped → fallback
    expect(sanitizeInterval("5m'")).toBe("5m"); // trailing quote dropped
  });
});

describe("mapCandleRows", () => {
  it("maps newest-first QuestDB rows to ascending ms OHLCV", () => {
    const dataset = [
      [2_000_000, 11, 12, 10, 11.5, 100], // newer (µs)
      [1_000_000, 10, 11, 9, 10.5, 50], // older
    ];
    expect(mapCandleRows(dataset)).toEqual([
      { tsMs: 1000, open: 10, high: 11, low: 9, close: 10.5, volume: 50 },
      { tsMs: 2000, open: 11, high: 12, low: 10, close: 11.5, volume: 100 },
    ]);
  });

  it("defaults missing volume to 0 and tolerates non-arrays", () => {
    expect(mapCandleRows([[1_000_000, 1, 2, 0.5, 1.5]])).toEqual([
      { tsMs: 1000, open: 1, high: 2, low: 0.5, close: 1.5, volume: 0 },
    ]);
    expect(mapCandleRows(null)).toEqual([]);
    expect(mapCandleRows(undefined)).toEqual([]);
  });
});

describe("wantsArrayResponse", () => {
  it("returns true for list-ish endpoints", () => {
    for (const p of ["/api/signals", "/api/trades", "/api/x/runs", "/api/alerts", "/api/containers"]) {
      expect(wantsArrayResponse(p)).toBe(true);
    }
  });

  it("returns false for singular / status endpoints", () => {
    for (const p of ["/api/health", "/api/janus/state", "/api/settings/risk"]) {
      expect(wantsArrayResponse(p)).toBe(false);
    }
  });
});

describe("intervalToSeconds", () => {
  it("parses the chart's interval tokens", () => {
    expect(intervalToSeconds("1m")).toBe(60);
    expect(intervalToSeconds("5m")).toBe(300);
    expect(intervalToSeconds("15m")).toBe(900);
    expect(intervalToSeconds("1h")).toBe(3600);
    expect(intervalToSeconds("4h")).toBe(14400);
    expect(intervalToSeconds("1D")).toBe(86400);
    expect(intervalToSeconds("1W")).toBe(604800);
  });

  it("returns null for unknown / invalid tokens", () => {
    expect(intervalToSeconds("")).toBeNull();
    expect(intervalToSeconds("0m")).toBeNull();
    expect(intervalToSeconds("abc")).toBeNull();
    expect(intervalToSeconds("5x")).toBeNull();
  });
});

describe("resampleCandles", () => {
  // Five ascending 1m bars in one 5m bucket, then one bar in the next bucket.
  const m = (i: number, o: number, h: number, l: number, c: number, v: number): CandleRow => ({
    tsMs: i * 60_000,
    open: o,
    high: h,
    low: l,
    close: c,
    volume: v,
  });

  it("aggregates 1m bars into a 5m OHLCV bucket", () => {
    const bars = [
      m(0, 10, 12, 9, 11, 5),
      m(1, 11, 13, 10, 12, 6),
      m(2, 12, 12.5, 11, 11.5, 7),
      m(3, 11.5, 14, 11, 13, 8),
      m(4, 13, 13.5, 12, 12.5, 9),
    ];
    expect(resampleCandles(bars, 300)).toEqual([
      { tsMs: 0, open: 10, high: 14, low: 9, close: 12.5, volume: 35 },
    ]);
  });

  it("splits across bucket boundaries", () => {
    const bars = [m(0, 1, 2, 1, 2, 1), m(4, 2, 3, 2, 3, 1), m(5, 3, 4, 3, 4, 1)];
    const out = resampleCandles(bars, 300); // 5-minute buckets
    expect(out).toHaveLength(2);
    expect(out[0]).toEqual({ tsMs: 0, open: 1, high: 3, low: 1, close: 3, volume: 2 });
    expect(out[1]).toEqual({ tsMs: 300_000, open: 3, high: 4, low: 3, close: 4, volume: 1 });
  });

  it("returns [] for empty input or a non-positive bucket", () => {
    expect(resampleCandles([], 300)).toEqual([]);
    expect(resampleCandles([m(0, 1, 1, 1, 1, 1)], 0)).toEqual([]);
  });
});
