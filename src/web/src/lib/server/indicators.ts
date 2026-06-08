// ════════════════════════════════════════════════════════════════════════════
// Server-side technical indicators (computed from QuestDB candles)
// ════════════════════════════════════════════════════════════════════════════
// Powers GET /api/chart/:sym/indicators (see hooks.server.ts). Pure functions
// over a candle series — no I/O. Mirrors the math of `indicators-ta` (the Rust
// crate janus/bots use) so the UI can show the same indicators without a Rust
// round-trip. All outputs are { time, value } points aligned to candle time
// (epoch SECONDS, matching lightweight-charts), with the warm-up region omitted.
//
// Default params match the chart's series titles: RSI 14, ATR 14, BB(20, 2),
// MACD(12, 26, 9), EMA 9/21.

export interface Candle {
  time: number; // epoch seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Point {
  time: number;
  value: number;
}

const round = (v: number): number => Math.round(v * 1e6) / 1e6;

// Emit { time, value } for each finite entry, aligned to `times` by index.
function toPoints(times: number[], arr: (number | null)[]): Point[] {
  const out: Point[] = [];
  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    if (v != null && Number.isFinite(v)) out.push({ time: times[i], value: round(v) });
  }
  return out;
}

// ── Index-aligned series (null during warm-up) ──────────────────────────────

function smaArr(vals: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(vals.length).fill(null);
  if (period <= 0) return out;
  let sum = 0;
  for (let i = 0; i < vals.length; i++) {
    sum += vals[i];
    if (i >= period) sum -= vals[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

// EMA seeded with the SMA of the first `period` values (matches the chart's
// client-side calcEMA so server/client overlays agree).
function emaArr(vals: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(vals.length).fill(null);
  if (period <= 0 || vals.length < period) return out;
  const k = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i++) sum += vals[i];
  let ema = sum / period;
  out[period - 1] = ema;
  for (let i = period; i < vals.length; i++) {
    ema = vals[i] * k + ema * (1 - k);
    out[i] = ema;
  }
  return out;
}

// Wilder's RSI.
function rsiArr(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null);
  if (closes.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const ch = closes[i] - closes[i - 1];
    if (ch >= 0) gain += ch;
    else loss -= ch;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < closes.length; i++) {
    const ch = closes[i] - closes[i - 1];
    avgGain = (avgGain * (period - 1) + (ch > 0 ? ch : 0)) / period;
    avgLoss = (avgLoss * (period - 1) + (ch < 0 ? -ch : 0)) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

// Wilder's ATR (true range, then smoothed).
function atrArr(c: Candle[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(c.length).fill(null);
  if (c.length <= period) return out;
  const tr: number[] = new Array(c.length).fill(0);
  for (let i = 1; i < c.length; i++) {
    tr[i] = Math.max(
      c[i].high - c[i].low,
      Math.abs(c[i].high - c[i - 1].close),
      Math.abs(c[i].low - c[i - 1].close),
    );
  }
  let sum = 0;
  for (let i = 1; i <= period; i++) sum += tr[i];
  let atr = sum / period;
  out[period] = atr;
  for (let i = period + 1; i < c.length; i++) {
    atr = (atr * (period - 1) + tr[i]) / period;
    out[i] = atr;
  }
  return out;
}

function bbandsArr(closes: number[], period: number, mult: number) {
  const mid = smaArr(closes, period);
  const upper: (number | null)[] = new Array(closes.length).fill(null);
  const lower: (number | null)[] = new Array(closes.length).fill(null);
  for (let i = period - 1; i < closes.length; i++) {
    const m = mid[i];
    if (m == null) continue;
    let sq = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const d = closes[j] - m;
      sq += d * d;
    }
    const sd = Math.sqrt(sq / period);
    upper[i] = m + mult * sd;
    lower[i] = m - mult * sd;
  }
  return { mid, upper, lower };
}

function macdArr(closes: number[], fast: number, slow: number, signal: number) {
  const ef = emaArr(closes, fast);
  const es = emaArr(closes, slow);
  const line: (number | null)[] = closes.map((_, i) =>
    ef[i] != null && es[i] != null ? (ef[i] as number) - (es[i] as number) : null,
  );
  const sig: (number | null)[] = new Array(closes.length).fill(null);
  const hist: (number | null)[] = new Array(closes.length).fill(null);
  const first = line.findIndex((v) => v != null);
  if (first >= 0) {
    const sigVals = emaArr(line.slice(first) as number[], signal);
    for (let k = 0; k < sigVals.length; k++) {
      const s = sigVals[k];
      if (s == null) continue;
      const i = first + k;
      sig[i] = s;
      hist[i] = (line[i] as number) - s;
    }
  }
  return { line, signal: sig, hist };
}

// Cumulative session VWAP (whole window — no intraday reset).
function vwapArr(c: Candle[]): (number | null)[] {
  const out: (number | null)[] = new Array(c.length).fill(null);
  let pv = 0;
  let vol = 0;
  for (let i = 0; i < c.length; i++) {
    const typical = (c[i].high + c[i].low + c[i].close) / 3;
    pv += typical * c[i].volume;
    vol += c[i].volume;
    out[i] = vol > 0 ? pv / vol : null;
  }
  return out;
}

// ── Catalog (metadata for the UI picker) ────────────────────────────────────

export interface IndicatorMeta {
  id: string;
  label: string;
  pane: "overlay" | "separate";
  keys: string[]; // response keys this indicator emits
}

export const INDICATOR_CATALOG: IndicatorMeta[] = [
  { id: "ema9", label: "EMA 9", pane: "overlay", keys: ["ema9"] },
  { id: "ema21", label: "EMA 21", pane: "overlay", keys: ["ema21"] },
  { id: "sma20", label: "SMA 20", pane: "overlay", keys: ["sma20"] },
  { id: "bbands", label: "Bollinger Bands (20, 2)", pane: "overlay", keys: ["bb_upper", "bb_middle", "bb_lower"] },
  { id: "vwap", label: "VWAP", pane: "overlay", keys: ["vwap"] },
  { id: "rsi", label: "RSI 14", pane: "separate", keys: ["rsi"] },
  { id: "macd", label: "MACD (12, 26, 9)", pane: "separate", keys: ["macd_line", "macd_signal", "macd_hist"] },
  { id: "atr", label: "ATR 14", pane: "separate", keys: ["atr"] },
];

// ── Dispatcher ──────────────────────────────────────────────────────────────

// Compute the requested indicators and return them keyed exactly as the chart
// expects. Unknown names are ignored. `ema<N>` / `sma<N>` accept any period.
export function computeIndicators(
  candles: Candle[],
  names: string[],
): Record<string, Point[]> {
  const times = candles.map((c) => c.time);
  const closes = candles.map((c) => c.close);
  const out: Record<string, Point[]> = {};

  for (const raw of names) {
    const name = raw.toLowerCase().trim();
    if (!name) continue;
    if (name === "rsi") {
      out.rsi = toPoints(times, rsiArr(closes, 14));
    } else if (name === "atr") {
      out.atr = toPoints(times, atrArr(candles, 14));
    } else if (name === "bbands" || name === "bb") {
      const b = bbandsArr(closes, 20, 2);
      out.bb_upper = toPoints(times, b.upper);
      out.bb_middle = toPoints(times, b.mid);
      out.bb_lower = toPoints(times, b.lower);
    } else if (name === "macd") {
      const m = macdArr(closes, 12, 26, 9);
      out.macd_line = toPoints(times, m.line);
      out.macd_signal = toPoints(times, m.signal);
      out.macd_hist = toPoints(times, m.hist);
    } else if (name === "vwap") {
      out.vwap = toPoints(times, vwapArr(candles));
    } else if (/^ema\d+$/.test(name)) {
      out[name] = toPoints(times, emaArr(closes, parseInt(name.slice(3), 10)));
    } else if (/^sma\d+$/.test(name)) {
      out[name] = toPoints(times, smaArr(closes, parseInt(name.slice(3), 10)));
    }
  }
  return out;
}
