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
