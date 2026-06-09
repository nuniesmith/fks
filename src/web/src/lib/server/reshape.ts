// ════════════════════════════════════════════════════════════════════════════
// Pure adapter helpers for hooks.server.ts (shape mapping + input sanitizing)
// ════════════════════════════════════════════════════════════════════════════
// Extracted from the SvelteKit hook so the logic is unit-testable without fetch /
// `$env`. The reshapers take already-fetched upstream JSON and return the body the
// WebUI expects; the sanitizers guard the QuestDB query interpolation. The hook
// keeps the I/O (fetch, headers, Response) and delegates the pure work here.

/** Pass through only genuine numbers (janus already sends typed JSON). */
const num = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);

/** Coerce form values (which may be strings) to a finite number, else undefined. */
const coerceNum = (v: unknown): number | undefined => {
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
};

// janus `/health` → a superset consumed by both the bottom StatusBar (flat
// `{janus,redis,feed}`) and the /settings System Info panel
// (`{status,components,version,uptime}`).
export function reshapeHealth(j: any): Record<string, unknown> {
  const comp: Record<string, { status?: string; latency?: string }> = (j?.components ??
    {}) as Record<string, { status?: string; latency?: string }>;
  const overall = String(j?.status ?? "down");
  return {
    status: overall,
    version: j?.version,
    uptime: j?.uptime,
    components: comp,
    janus: overall,
    redis: String(comp.redis?.status ?? "—"),
    feed: String(j?.forward_service ?? comp.data?.status ?? comp.questdb?.status ?? "—"),
  };
}

// forward `risk/performance` merged over `dashboard/performance` → the
// /performance metrics grid, mapping each field defensively (risk wins on overlap).
export function reshapePerformance(risk: any, dash: any): Record<string, number | undefined> {
  const s: any = { ...(dash ?? {}), ...(risk ?? {}) };
  return {
    total_trades: num(s.total_trades ?? s.trades ?? s.num_trades),
    win_rate: num(s.win_rate),
    total_pnl: num(s.total_pnl ?? s.net_pnl ?? s.pnl),
    profit_factor: num(s.profit_factor),
    sharpe_ratio: num(s.sharpe_ratio ?? s.sharpe),
    sortino_ratio: num(s.sortino_ratio ?? s.sortino),
    max_drawdown: num(s.max_drawdown ?? s.max_dd),
    recovery_factor: num(s.recovery_factor),
    avg_win: num(s.avg_win),
    avg_loss: num(s.avg_loss),
    largest_win: num(s.largest_win),
    largest_loss: num(s.largest_loss),
  };
}

// janus risk config → the /settings risk panel. The UI works in positive USD;
// janus stores the daily-loss halt threshold as ≤ 0, so surface its magnitude.
export function reshapeRiskConfig(c: any): {
  max_daily_loss_usd: number | undefined;
  max_positions: number | undefined;
  max_gross_exposure_usd: number | undefined;
} {
  const dl = num(c?.max_daily_loss ?? c?.daily_loss ?? c?.max_daily_loss_usd);
  return {
    max_daily_loss_usd: dl != null ? Math.abs(dl) : undefined,
    max_positions: num(c?.max_concurrent_positions ?? c?.max_positions),
    max_gross_exposure_usd: num(c?.max_gross_exposure ?? c?.max_gross_exposure_usd),
  };
}

// /settings risk panel body → the rustrade `PortfolioRiskConfig` PUT payload.
// The UI works in positive USD; rustrade's halt threshold must be ≤ 0, so the
// daily-loss sign is flipped on the way out.
export function toRiskConfigPayload(body: any): {
  max_daily_loss: number | undefined;
  max_concurrent_positions: number | undefined;
  max_gross_exposure: number | undefined;
} {
  const dl = coerceNum(body?.max_daily_loss_usd);
  return {
    max_daily_loss: dl != null ? -Math.abs(dl) : undefined,
    max_concurrent_positions: coerceNum(body?.max_positions),
    max_gross_exposure: coerceNum(body?.max_gross_exposure_usd),
  };
}

// "2026-06-08T12:00:00Z" → a compact age ("5m" / "2h" / "3d") for the alert feed.
export function humanizeSince(iso?: string): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

// ── Input sanitizers ─────────────────────────────────────────────────────────
// QuestDB's HTTP /exec endpoint has no parameterized-query API, so symbol /
// interval tokens are interpolated into the SQL string. These strip everything
// that isn't a valid token character and cap the length — the injection guard
// for those queries. Keep them strict.

/** Strip non-symbol chars and cap length; the result is safe in a SQL literal. */
export function sanitizeSymbol(raw: string | null | undefined, maxLen = 32): string {
  return (raw ?? "").replace(/[^A-Za-z0-9._/-]/g, "").slice(0, maxLen);
}

/** Strip non-alphanumerics from an interval token; empty/all-stripped → "5m". */
export function sanitizeInterval(raw: string | null | undefined): string {
  return (raw ?? "5m").replace(/[^A-Za-z0-9]/g, "").slice(0, 8) || "5m";
}

// ── QuestDB candle mapping ───────────────────────────────────────────────────

export interface CandleRow {
  tsMs: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// QuestDB `candles_crypto` dataset rows are [t_µs, open, high, low, close,
// volume], newest-first. Map → ascending OHLCV with the timestamp in ms (what
// lightweight-charts' setData expects). Non-arrays → []; missing volume → 0.
export function mapCandleRows(dataset: unknown): CandleRow[] {
  const rows: unknown[] = Array.isArray(dataset) ? dataset : [];
  return rows
    .map((r) => {
      const row = r as unknown[];
      return {
        tsMs: Math.round(Number(row[0]) / 1000),
        open: Number(row[1]),
        high: Number(row[2]),
        low: Number(row[3]),
        close: Number(row[4]),
        volume: Number(row[5] ?? 0),
      };
    })
    .reverse();
}

// gracefulEmpty's REST heuristic: list-ish paths degrade to `[]` (so array
// consumers don't throw), singular/status paths to `{}`. Cheap but good enough
// while a panel is unmapped.
const ARRAY_PATH_RE =
  /(list|recent|open|trades|signals|alerts|sessions|containers|runs|notes|providers|gaps|news|quotes|feed|history|scores)/;

export function wantsArrayResponse(pathname: string): boolean {
  return ARRAY_PATH_RE.test(pathname);
}

// ── Timeframe resampling (B3) ────────────────────────────────────────────────

// "5m" → 300, "1h" → 3600, "1D" → 86400, "1W" → 604800 (seconds). null for
// tokens we don't recognise. Case-insensitive on the unit (the app uses 1D/1W).
export function intervalToSeconds(iv: string): number | null {
  const m = /^(\d+)\s*([mhdw])$/i.exec((iv ?? "").trim());
  if (!m) return null;
  const n = parseInt(m[1], 10);
  if (!Number.isFinite(n) || n <= 0) return null;
  const unit = m[2].toLowerCase();
  const per = unit === "m" ? 60 : unit === "h" ? 3600 : unit === "d" ? 86400 : 604800;
  return n * per;
}

// Aggregate ascending fine-grained candles into `bucketSec`-second OHLCV buckets:
// open = first, high = max, low = min, close = last, volume = sum; bucket time =
// floor(t / bucket) (bucket-start, ms). Used to synthesize a coarser interval from
// 1m bars when the exact interval isn't stored natively.
export function resampleCandles(rows: CandleRow[], bucketSec: number): CandleRow[] {
  if (bucketSec <= 0 || rows.length === 0) return [];
  const bucketMs = bucketSec * 1000;
  const out: CandleRow[] = [];
  let cur: CandleRow | null = null;
  let curBucket = Number.NaN;
  for (const r of rows) {
    const bucket = Math.floor(r.tsMs / bucketMs) * bucketMs;
    if (cur === null || bucket !== curBucket) {
      if (cur) out.push(cur);
      cur = { tsMs: bucket, open: r.open, high: r.high, low: r.low, close: r.close, volume: r.volume };
      curBucket = bucket;
    } else {
      cur.high = Math.max(cur.high, r.high);
      cur.low = Math.min(cur.low, r.low);
      cur.close = r.close;
      cur.volume += r.volume;
    }
  }
  if (cur) out.push(cur);
  return out;
}
