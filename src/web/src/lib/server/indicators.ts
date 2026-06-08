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

// Weighted moving average (linear weights 1..period).
function wmaArr(vals: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(vals.length).fill(null);
  if (period <= 0 || vals.length < period) return out;
  const denom = (period * (period + 1)) / 2;
  for (let i = period - 1; i < vals.length; i++) {
    let s = 0;
    for (let j = 0; j < period; j++) s += vals[i - period + 1 + j] * (j + 1);
    out[i] = s / denom;
  }
  return out;
}

// Stochastic oscillator: %K (period) + %D (SMA of %K over dPeriod).
function stochArr(c: Candle[], kPeriod: number, dPeriod: number) {
  const k: (number | null)[] = new Array(c.length).fill(null);
  for (let i = kPeriod - 1; i < c.length; i++) {
    let hh = -Infinity;
    let ll = Infinity;
    for (let j = i - kPeriod + 1; j <= i; j++) {
      if (c[j].high > hh) hh = c[j].high;
      if (c[j].low < ll) ll = c[j].low;
    }
    const range = hh - ll;
    k[i] = range === 0 ? 100 : (100 * (c[i].close - ll)) / range;
  }
  // %D = trailing SMA of the (contiguous) %K values.
  const d: (number | null)[] = new Array(c.length).fill(null);
  const win: number[] = [];
  let sum = 0;
  for (let i = 0; i < c.length; i++) {
    if (k[i] == null) continue;
    win.push(k[i] as number);
    sum += k[i] as number;
    if (win.length > dPeriod) sum -= win.shift() as number;
    if (win.length === dPeriod) d[i] = sum / dPeriod;
  }
  return { k, d };
}

// Williams %R (−100..0).
function williamsRArr(c: Candle[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(c.length).fill(null);
  for (let i = period - 1; i < c.length; i++) {
    let hh = -Infinity;
    let ll = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (c[j].high > hh) hh = c[j].high;
      if (c[j].low < ll) ll = c[j].low;
    }
    const range = hh - ll;
    out[i] = range === 0 ? -50 : (-100 * (hh - c[i].close)) / range;
  }
  return out;
}

// Commodity Channel Index (typical price vs its SMA, scaled by mean deviation).
function cciArr(c: Candle[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(c.length).fill(null);
  const tp = c.map((x) => (x.high + x.low + x.close) / 3);
  for (let i = period - 1; i < c.length; i++) {
    let mean = 0;
    for (let j = i - period + 1; j <= i; j++) mean += tp[j];
    mean /= period;
    let md = 0;
    for (let j = i - period + 1; j <= i; j++) md += Math.abs(tp[j] - mean);
    md /= period;
    out[i] = md === 0 ? 0 : (tp[i] - mean) / (0.015 * md);
  }
  return out;
}

// On-Balance Volume (cumulative).
function obvArr(c: Candle[]): (number | null)[] {
  const out: (number | null)[] = new Array(c.length).fill(null);
  if (c.length === 0) return out;
  let obv = 0;
  out[0] = 0;
  for (let i = 1; i < c.length; i++) {
    if (c[i].close > c[i - 1].close) obv += c[i].volume;
    else if (c[i].close < c[i - 1].close) obv -= c[i].volume;
    out[i] = obv;
  }
  return out;
}

// Donchian channel: highest-high / lowest-low / midline over `period`.
function donchianArr(c: Candle[], period: number) {
  const upper: (number | null)[] = new Array(c.length).fill(null);
  const lower: (number | null)[] = new Array(c.length).fill(null);
  const mid: (number | null)[] = new Array(c.length).fill(null);
  for (let i = period - 1; i < c.length; i++) {
    let hh = -Infinity;
    let ll = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      if (c[j].high > hh) hh = c[j].high;
      if (c[j].low < ll) ll = c[j].low;
    }
    upper[i] = hh;
    lower[i] = ll;
    mid[i] = (hh + ll) / 2;
  }
  return { upper, mid, lower };
}

// Keltner channel: EMA midline ± mult·ATR.
function keltnerArr(c: Candle[], period: number, mult: number) {
  const mid = emaArr(c.map((x) => x.close), period);
  const atr = atrArr(c, period);
  const upper: (number | null)[] = new Array(c.length).fill(null);
  const lower: (number | null)[] = new Array(c.length).fill(null);
  for (let i = 0; i < c.length; i++) {
    if (mid[i] != null && atr[i] != null) {
      upper[i] = (mid[i] as number) + mult * (atr[i] as number);
      lower[i] = (mid[i] as number) - mult * (atr[i] as number);
    }
  }
  return { upper, mid, lower };
}

// Wilder's ADX with +DI / −DI (directional movement). Needs > 2·period bars.
function adxArr(c: Candle[], period: number) {
  const n = c.length;
  const plusDI: (number | null)[] = new Array(n).fill(null);
  const minusDI: (number | null)[] = new Array(n).fill(null);
  const adx: (number | null)[] = new Array(n).fill(null);
  if (n <= 2 * period) return { plusDI, minusDI, adx };

  const tr = new Array(n).fill(0);
  const pDM = new Array(n).fill(0);
  const mDM = new Array(n).fill(0);
  for (let i = 1; i < n; i++) {
    const up = c[i].high - c[i - 1].high;
    const down = c[i - 1].low - c[i].low;
    pDM[i] = up > down && up > 0 ? up : 0;
    mDM[i] = down > up && down > 0 ? down : 0;
    tr[i] = Math.max(
      c[i].high - c[i].low,
      Math.abs(c[i].high - c[i - 1].close),
      Math.abs(c[i].low - c[i - 1].close),
    );
  }
  // Wilder "sum" smoothing of TR/+DM/−DM, seeded over the first `period` bars.
  let sTR = 0;
  let sP = 0;
  let sM = 0;
  for (let i = 1; i <= period; i++) {
    sTR += tr[i];
    sP += pDM[i];
    sM += mDM[i];
  }
  const dx: (number | null)[] = new Array(n).fill(null);
  for (let i = period; i < n; i++) {
    if (i > period) {
      sTR = sTR - sTR / period + tr[i];
      sP = sP - sP / period + pDM[i];
      sM = sM - sM / period + mDM[i];
    }
    const pdi = sTR === 0 ? 0 : (100 * sP) / sTR;
    const mdi = sTR === 0 ? 0 : (100 * sM) / sTR;
    plusDI[i] = pdi;
    minusDI[i] = mdi;
    const sum = pdi + mdi;
    dx[i] = sum === 0 ? 0 : (100 * Math.abs(pdi - mdi)) / sum;
  }
  // ADX = Wilder smoothing of DX (seed = mean of the first `period` DX values).
  let adxVal = 0;
  let cnt = 0;
  let seeded = false;
  for (let i = period; i < n; i++) {
    const d = dx[i];
    if (d == null) continue;
    if (!seeded) {
      adxVal += d;
      if (++cnt === period) {
        adxVal /= period;
        adx[i] = adxVal;
        seeded = true;
      }
    } else {
      adxVal = (adxVal * (period - 1) + d) / period;
      adx[i] = adxVal;
    }
  }
  return { plusDI, minusDI, adx };
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
  { id: "wma20", label: "WMA 20", pane: "overlay", keys: ["wma20"] },
  { id: "donchian", label: "Donchian (20)", pane: "overlay", keys: ["dc_upper", "dc_middle", "dc_lower"] },
  { id: "keltner", label: "Keltner (20, 2)", pane: "overlay", keys: ["kc_upper", "kc_middle", "kc_lower"] },
  { id: "rsi", label: "RSI 14", pane: "separate", keys: ["rsi"] },
  { id: "macd", label: "MACD (12, 26, 9)", pane: "separate", keys: ["macd_line", "macd_signal", "macd_hist"] },
  { id: "atr", label: "ATR 14", pane: "separate", keys: ["atr"] },
  { id: "stoch", label: "Stochastic (14, 3)", pane: "separate", keys: ["stoch_k", "stoch_d"] },
  { id: "willr", label: "Williams %R 14", pane: "separate", keys: ["willr"] },
  { id: "cci", label: "CCI 20", pane: "separate", keys: ["cci"] },
  { id: "obv", label: "OBV", pane: "separate", keys: ["obv"] },
  { id: "adx", label: "ADX 14 (+DI/−DI)", pane: "separate", keys: ["adx", "plus_di", "minus_di"] },
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
    } else if (name === "stoch") {
      const s = stochArr(candles, 14, 3);
      out.stoch_k = toPoints(times, s.k);
      out.stoch_d = toPoints(times, s.d);
    } else if (name === "willr" || name === "williamsr") {
      out.willr = toPoints(times, williamsRArr(candles, 14));
    } else if (name === "cci") {
      out.cci = toPoints(times, cciArr(candles, 20));
    } else if (name === "obv") {
      out.obv = toPoints(times, obvArr(candles));
    } else if (name === "adx") {
      const a = adxArr(candles, 14);
      out.adx = toPoints(times, a.adx);
      out.plus_di = toPoints(times, a.plusDI);
      out.minus_di = toPoints(times, a.minusDI);
    } else if (name === "donchian" || name === "dc") {
      const d = donchianArr(candles, 20);
      out.dc_upper = toPoints(times, d.upper);
      out.dc_middle = toPoints(times, d.mid);
      out.dc_lower = toPoints(times, d.lower);
    } else if (name === "keltner" || name === "kc") {
      const k = keltnerArr(candles, 20, 2);
      out.kc_upper = toPoints(times, k.upper);
      out.kc_middle = toPoints(times, k.mid);
      out.kc_lower = toPoints(times, k.lower);
    } else if (/^wma\d+$/.test(name)) {
      out[name] = toPoints(times, wmaArr(closes, parseInt(name.slice(3), 10)));
    } else if (/^ema\d+$/.test(name)) {
      out[name] = toPoints(times, emaArr(closes, parseInt(name.slice(3), 10)));
    } else if (/^sma\d+$/.test(name)) {
      out[name] = toPoints(times, smaArr(closes, parseInt(name.slice(3), 10)));
    }
  }
  return out;
}
