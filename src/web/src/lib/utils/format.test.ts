import { describe, it, expect } from "vitest";
import {
  fmtPrice,
  fmtPct,
  fmtDollar,
  fmtConfidence,
  fmtFixed,
  fmtInt,
  scoreColor,
  signalVariant,
  riskVariant,
  regimeVariant,
  directionVariant,
  fmtTime,
  fmtDateTime,
} from "./format";

describe("fmtPrice", () => {
  it("adapts decimal precision to magnitude", () => {
    expect(fmtPrice(0.5)).toBe("0.500000"); // < 1 → 6 dp
    expect(fmtPrice(0.123456789)).toBe("0.123457"); // rounded to 6 dp
    expect(fmtPrice(1)).toBe("1.0000"); // < 100 → 4 dp
    expect(fmtPrice(99.99)).toBe("99.9900");
    expect(fmtPrice(100)).toBe("100.00"); // >= 100 → 2 dp
    expect(fmtPrice(1234.5)).toBe("1,234.50"); // thousands separator
    expect(fmtPrice(-0.5)).toBe("-0.500000"); // magnitude drives precision
  });
  it("returns — for null/undefined", () => {
    expect(fmtPrice(null)).toBe("—");
    expect(fmtPrice(undefined)).toBe("—");
  });
});

describe("fmtPct", () => {
  it("prefixes a sign and fixes 2 decimals", () => {
    expect(fmtPct(1.23)).toBe("+1.23%");
    expect(fmtPct(-0.45)).toBe("-0.45%");
    expect(fmtPct(0)).toBe("+0.00%");
    expect(fmtPct(null)).toBe("—");
  });
});

describe("fmtDollar", () => {
  it("formats signed P&L with a $ and 2 decimals", () => {
    expect(fmtDollar(12.34)).toBe("+$12.34");
    expect(fmtDollar(-5)).toBe("-$5.00");
    expect(fmtDollar(0)).toBe("+$0.00");
    expect(fmtDollar(null)).toBe("—");
  });
});

describe("fmtConfidence", () => {
  it("accepts a fraction (0–1) or a percentage (1–100)", () => {
    expect(fmtConfidence(0.73)).toBe("73%");
    expect(fmtConfidence(0.5)).toBe("50%");
    expect(fmtConfidence(1)).toBe("100%"); // boundary: treated as a fraction
    expect(fmtConfidence(73)).toBe("73%");
    expect(fmtConfidence(null)).toBe("—");
  });
});

describe("fmtFixed", () => {
  it("fixes the requested decimals (default 2)", () => {
    expect(fmtFixed(3.14159)).toBe("3.14");
    expect(fmtFixed(3.14159, 4)).toBe("3.1416");
    expect(fmtFixed(10, 0)).toBe("10");
    expect(fmtFixed(null)).toBe("—");
  });
});

describe("fmtInt", () => {
  it("rounds and groups thousands", () => {
    expect(fmtInt(1234567)).toBe("1,234,567");
    expect(fmtInt(1234.6)).toBe("1,235");
    expect(fmtInt(0)).toBe("0");
    expect(fmtInt(null)).toBe("—");
  });
});

describe("scoreColor", () => {
  it("buckets a 0–100 score into a colour", () => {
    expect(scoreColor(85)).toBe("green");
    expect(scoreColor(70)).toBe("green"); // boundary
    expect(scoreColor(50)).toBe("cyan");
    expect(scoreColor(40)).toBe("cyan"); // boundary
    expect(scoreColor(30)).toBe("amber");
    expect(scoreColor(20)).toBe("amber"); // boundary
    expect(scoreColor(10)).toBe("red");
  });
});

describe("signalVariant", () => {
  it("maps buy/sell/hold keywords to variants", () => {
    expect(signalVariant("buy")).toBe("green");
    expect(signalVariant("STRONG SELL")).toBe("red");
    expect(signalVariant("long")).toBe("green");
    expect(signalVariant("bear")).toBe("red");
    expect(signalVariant("hold")).toBe("amber");
    expect(signalVariant("whatever")).toBe("default");
    expect(signalVariant(null)).toBe("default");
  });
});

describe("riskVariant", () => {
  it("maps drawdown % to a risk colour", () => {
    expect(riskVariant(6)).toBe("red");
    expect(riskVariant(5)).toBe("amber"); // > 5 is strict
    expect(riskVariant(3)).toBe("amber");
    expect(riskVariant(2)).toBe("green"); // > 2 is strict
    expect(riskVariant(0)).toBe("green");
    expect(riskVariant(null)).toBe("default");
  });
});

describe("regimeVariant", () => {
  it("maps regime labels to variants (default cyan)", () => {
    expect(regimeVariant("Bull market")).toBe("green");
    expect(regimeVariant("risk off")).toBe("red");
    expect(regimeVariant("choppy range")).toBe("amber");
    expect(regimeVariant("high volatility")).toBe("purple");
    expect(regimeVariant("trending")).toBe("cyan");
    expect(regimeVariant(null)).toBe("default");
  });
});

describe("directionVariant", () => {
  it("maps exact long/short/buy/sell to a variant", () => {
    expect(directionVariant("long")).toBe("green");
    expect(directionVariant("BUY")).toBe("green");
    expect(directionVariant("short")).toBe("red");
    expect(directionVariant("sell")).toBe("red");
    expect(directionVariant("flat")).toBe("default");
    expect(directionVariant(null)).toBe("default");
  });
});

// The time formatters depend on the runner's timezone, so assert the guard
// cases exactly and only shape-check valid output (TZ-independent).
describe("fmtTime / fmtDateTime", () => {
  it("return — for null / invalid input", () => {
    expect(fmtTime(null)).toBe("—");
    expect(fmtTime("not-a-date")).toBe("—");
    expect(fmtDateTime(null)).toBe("—");
    expect(fmtDateTime("not-a-date")).toBe("—");
  });

  it("format valid timestamps in the expected shape", () => {
    expect(fmtTime(Date.UTC(2025, 6, 18, 14, 32, 7))).toMatch(/^\d{1,2}:\d{2}:\d{2}$/);
    expect(fmtDateTime(Date.UTC(2025, 6, 18, 14, 32))).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/,
    );
  });
});
