import type { Handle, RequestEvent } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";
import { computeIndicators, INDICATOR_CATALOG, type Candle } from "$lib/server/indicators";
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
} from "$lib/server/reshape";

// ════════════════════════════════════════════════════════════════════════════
// Backend proxy  (replaces the old vite/nginx → fks_ruby reverse proxy)
// ════════════════════════════════════════════════════════════════════════════
// The dashboard makes same-origin calls to /api, /sse, /bars, /factory, /kraken,
// /fapi. Those used to be proxied to the Python "Ruby" service, which is gone.
// Until the janus repoint lands (docs/architecture/WEBUI_JANUS_REPOINT.md), this
// hook proxies what we can and gracefully absorbs the rest, so panels degrade
// quietly (empty data) instead of flooding the console with 404s.
//
// PHASE 1 (this): /api/spawner/* → the spawner (real); everything else under a
//                 backend prefix → graceful empty (REST) or an idle SSE stream.
// PHASE 2 (next): map specific paths to janus (see JANUS_MAP below) + reshape.
//
// Upstreams use in-container Docker-network addresses (overridable via env).
// NB: from inside the webui container, janus is fks_janus:8080 (api) /
//     fks_janus:8180 (forward) — NOT the host-published :7000/:7001.
const SPAWNER_URL = env.SPAWNER_INTERNAL_URL ?? "http://fks_bot_spawner:8090";
const JANUS_URL = env.JANUS_INTERNAL_URL ?? "http://fks_janus:8080"; // janus-api
const JANUS_FORWARD_URL = env.JANUS_FORWARD_INTERNAL_URL ?? "http://fks_janus:8180"; // forward (brain/risk)
const PROMETHEUS_URL = env.PROMETHEUS_INTERNAL_URL ?? "http://fks_prometheus:9090"; // /monitoring
const QUESTDB_URL = env.QUESTDB_INTERNAL_URL ?? "http://fks_questdb:9000"; // /charts OHLC (HTTP query API)

const BACKEND_PREFIXES = ["/api/", "/sse/", "/bars/", "/factory/", "/kraken/", "/fapi/"];

const isBackend = (p: string): boolean => BACKEND_PREFIXES.some((x) => p.startsWith(x));

// Headers we must not forward upstream (hop-by-hop / connection-specific).
const HOP = new Set(["host", "connection", "content-length", "transfer-encoding", "keep-alive"]);

function upstreamHeaders(src: Headers): Headers {
  const h = new Headers();
  for (const [k, v] of src) if (!HOP.has(k.toLowerCase())) h.set(k, v);
  return h;
}

// Forward a request to `base + path`, streaming the response straight back.
async function forward(
  event: RequestEvent,
  base: string,
  path: string,
): Promise<Response> {
  const method = event.request.method;
  const init: RequestInit & { duplex?: "half" } = {
    method,
    headers: upstreamHeaders(event.request.headers),
  };
  if (method !== "GET" && method !== "HEAD") {
    init.body = await event.request.arrayBuffer();
    init.duplex = "half";
  }
  try {
    const res = await fetch(base + path, init);
    const headers = new Headers();
    for (const [k, v] of res.headers) if (!HOP.has(k.toLowerCase())) headers.set(k, v);
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
  } catch {
    return new Response(JSON.stringify({ error: "upstream_unreachable", upstream: base }), {
      status: 502,
      headers: { "content-type": "application/json" },
    });
  }
}

// Unmapped backend path → degrade quietly so the UI doesn't error.
function gracefulEmpty(pathname: string): Response {
  // SSE / streaming endpoints: hold an idle, well-formed event stream so the
  // browser's EventSource stays "connected" (no error + reconnect storm).
  const isSse =
    pathname.startsWith("/sse/") ||
    pathname.endsWith("/stream") ||
    /\/sse(\/|$)/.test(pathname);
  if (isSse) {
    let iv: ReturnType<typeof setInterval> | undefined;
    const stream = new ReadableStream({
      start(controller) {
        const enc = new TextEncoder();
        controller.enqueue(enc.encode(": fks — backend not wired yet (janus repoint pending)\n\n"));
        // Heartbeat keeps the connection genuinely alive so EventSource doesn't
        // treat an idle socket as dropped and reconnect-loop.
        iv = setInterval(() => {
          try {
            controller.enqueue(enc.encode(": keepalive\n\n"));
          } catch {
            if (iv) clearInterval(iv);
          }
        }, 25_000);
      },
      cancel() {
        if (iv) clearInterval(iv);
      },
    });
    return new Response(stream, {
      status: 200,
      headers: {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
        "x-fks-unmapped": "1",
      },
    });
  }
  // REST: return an empty list or object. Most polled endpoints want an array;
  // singular/status-ish ones want an object — cheap heuristic, good enough to
  // keep components from throwing while the panel is unmapped.
  const wantsArray = wantsArrayResponse(pathname);
  return new Response(wantsArray ? "[]" : "{}", {
    status: 200,
    headers: { "content-type": "application/json", "x-fks-unmapped": "1" },
  });
}

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

// Read a janus JSON endpoint, tolerating failure (returns {} on any error).
async function janusJson(event: RequestEvent, base: string, path: string): Promise<any> {
  try {
    const r = await fetch(base + path, { headers: upstreamHeaders(event.request.headers) });
    return await r.json();
  } catch {
    return {};
  }
}

// janus recent signals — { symbol, signal_type, confidence, timestamp }[].
// Sourced from /api/dashboard/signals/summary.recent_signals.
async function janusRecentSignals(
  event: RequestEvent,
): Promise<{ symbol?: string; signal_type?: string; confidence?: number; timestamp?: string }[]> {
  const j = await janusJson(event, JANUS_URL, "/api/dashboard/signals/summary");
  return Array.isArray(j?.recent_signals) ? j.recent_signals : [];
}

// /api/health → reshape janus /health into the StatusBar's flat {redis,janus,feed}.
// janus /health: { status, forward_service, components: Record<string,{status}> }.
// Two consumers share /api/health: the bottom StatusBar wants a flat
// {redis,janus,feed}; the /settings "System Info" panel wants {status,components,
// version,uptime}. We return a superset so both render (and the settings panel
// no longer hits `healthData.status` undefined).
async function janusHealth(event: RequestEvent): Promise<Response> {
  const j = await janusJson(event, JANUS_URL, "/health");
  return json(reshapeHealth(j));
}

// /api/janus/state → the /janus-ai "Janus State" panel's JanusStateResponse:
//   { janus: { status }, redis: { regime, affinity, signals_recent } }.
// `janus.status` is the trading brain's health (forward /api/v1/brain/health),
// falling back to the api service /health. `signals_recent` reuses the dashboard
// signals feed. regime/affinity have no janus feed wired here yet → empty (the
// panel renders a clean "no data" state rather than stale Ruby shapes).
async function janusState(event: RequestEvent): Promise<Response> {
  const [brain, health, sigs] = await Promise.all([
    janusJson(event, JANUS_FORWARD_URL, "/api/v1/brain/health"),
    janusJson(event, JANUS_URL, "/health"),
    janusRecentSignals(event),
  ]);
  const rawStatus =
    typeof brain?.healthy === "boolean"
      ? brain.healthy
        ? "ok"
        : "down"
      : String(brain?.state ?? brain?.status ?? health?.status ?? "down");
  // The panel greens on 'UP'/'ok'; normalise any healthy-ish word to 'ok'.
  const status = /^(ok|up|healthy|running|connected|active)$/i.test(rawStatus)
    ? "ok"
    : rawStatus.toUpperCase();
  return json({
    janus: { status },
    redis: {
      regime: {},
      affinity: {},
      signals_recent: sigs.map((s) => ({
        symbol: s.symbol,
        direction: s.signal_type,
        confidence: s.confidence,
        timestamp: s.timestamp,
      })),
    },
  });
}

// /api/janus/affinity → the /janus-ai "Strategy Affinity" matrix:
//   { status, weights: Record<strategy, Record<asset, number>> }.
// Sourced from forward /api/v1/brain/affinity; if janus returns a different
// shape we degrade to an empty matrix (panel shows "no affinity data").
async function janusAffinity(event: RequestEvent): Promise<Response> {
  const a = await janusJson(event, JANUS_FORWARD_URL, "/api/v1/brain/affinity");
  const weights = a && typeof a.weights === "object" && a.weights ? a.weights : {};
  return json({ status: String(a?.status ?? "ok"), weights });
}

// /api/performance → the /performance metrics grid (Performance shape).
// Merges forward /api/v1/risk/performance (preferred) with /api/dashboard/
// performance, mapping fields defensively. Empty in the paper demo (no closed
// trades through janus) → every card shows "—"; populates once trades flow.
async function janusPerformance(event: RequestEvent): Promise<Response> {
  const [risk, dash] = await Promise.all([
    janusJson(event, JANUS_FORWARD_URL, "/api/v1/risk/performance"),
    janusJson(event, JANUS_URL, "/api/dashboard/performance"),
  ]);
  return json(reshapePerformance(risk, dash));
}

// ── /monitoring: Prometheus proxy ───────────────────────────────────────────
// The /monitoring page calls /api/metrics/* (these used to be served by Ruby's
// data service, which queried Prometheus and reshaped). We reprise that role:
// query/query_range/targets are a straight pass-through (identical shapes), and
// alerts/layout get a light reshape.

// /api/metrics/alerts → reshape Prometheus /api/v1/alerts ({data:{alerts:[…]}})
// into the page's { data: Alert[] } with an age_str derived from activeAt.
async function promAlerts(event: RequestEvent): Promise<Response> {
  const j = await janusJson(event, PROMETHEUS_URL, "/api/v1/alerts");
  const list: any[] = Array.isArray(j?.data?.alerts) ? j.data.alerts : [];
  return json({
    data: list.map((a) => ({
      labels: a?.labels ?? {},
      age_str: humanizeSince(a?.activeAt),
      severity_color: "",
    })),
  });
}

// /api/metrics/layout — Ruby served a configurable dashboard layout; there's no
// janus/Prometheus equivalent, so we ship a small default built only from
// synthetic metrics Prometheus always generates (up, scrape_duration_seconds),
// plus the live alert-feed/targets panels. Node/redis KPIs depend on exporters.
const METRICS_LAYOUT = {
  panels: [
    { id: "targets_up", type: "stat", title: "Targets Up", query: "sum(up)" },
    { id: "targets_total", type: "stat", title: "Targets Total", query: "count(up)" },
    {
      id: "scrape_p95",
      type: "sparkline",
      title: "Scrape Duration (1h, max)",
      query: "max(scrape_duration_seconds)",
      color: "var(--cyan)",
    },
    { id: "alerts", type: "alert-feed", title: "Active Alerts" },
    { id: "targets", type: "targets", title: "Scrape Targets" },
  ],
};

// ── /charts: historical OHLC + indicators from QuestDB ──────────────────────
// Candles come from QuestDB's `candles_crypto` (ts µs, symbol, exchange,
// interval, o/h/l/c/v) via the HTTP /exec query API. The page strips the quote
// currency (BTC/USD → BTC), so we match the symbol loosely (exact, or
// `SYM/…`/`SYM-…`). Live updates are client-side (crypto: Kraken/Binance WS) or
// /sse/bars (futures, still stubbed); this is the history backbone.

// Query candles_crypto → ascending rows { tsMs, o,h,l,c,v }. Shared by the
// candles endpoint and the indicators endpoint.
// One QuestDB candles_crypto query. `sym`/`iv` are already sanitized (they go
// into the SQL string literal). Returns ascending OHLCV rows ([] on any failure).
async function queryCandles(
  sym: string,
  iv: string,
  days: number,
  lim: number,
): Promise<CandleRow[]> {
  const sql =
    `SELECT cast(ts as long) t, open, high, low, close, volume FROM candles_crypto ` +
    `WHERE (symbol = '${sym}' OR symbol LIKE '${sym}/%' OR symbol LIKE '${sym}-%') ` +
    `AND interval = '${iv}' AND ts >= dateadd('d', -${days}, now()) ` +
    `ORDER BY ts DESC LIMIT ${lim}`;
  try {
    const r = await fetch(`${QUESTDB_URL}/exec?query=${encodeURIComponent(sql)}`, {
      headers: { accept: "application/json" },
    });
    const j: any = await r.json();
    return mapCandleRows(j?.dataset);
  } catch {
    return [];
  }
}

async function fetchCandles(event: RequestEvent, symbolRaw: string): Promise<CandleRow[]> {
  // Strip anything that isn't a symbol char — these go straight into a SQL string
  // literal, so this is also the injection guard.
  const sym = sanitizeSymbol(symbolRaw, 32);
  if (!sym) return [];
  const p = event.url.searchParams;
  const iv = sanitizeInterval(p.get("interval"));
  const days = Math.min(365, Math.max(1, parseInt(p.get("days_back") ?? "5", 10) || 5));
  const lim = Math.min(5000, Math.max(1, parseInt(p.get("limit") ?? "1000", 10) || 1000));

  let rows = await queryCandles(sym, iv, days, lim);

  // B3: if nothing is stored natively at this interval, synthesize it by
  // resampling 1m bars. Only fires when the direct query came back empty, so it
  // can only improve on the "no data" case — it never changes a populated chart.
  const sec = intervalToSeconds(iv);
  if (rows.length === 0 && iv !== "1m" && sec !== null && sec % 60 === 0) {
    const oneMin = await queryCandles(sym, "1m", days, Math.min(5000, Math.ceil((sec / 60) * lim)));
    if (oneMin.length > 0) rows = resampleCandles(oneMin, sec);
  }
  return rows;
}

// GET /bars/:symbol/candles → { candles: [{ timestamp /*ms*/, o,h,l,c,v }] }.
async function questdbCandles(event: RequestEvent, symbolRaw: string): Promise<Response> {
  const rows = await fetchCandles(event, symbolRaw);
  return json({
    candles: rows.map((r) => ({
      timestamp: r.tsMs,
      open: r.open,
      high: r.high,
      low: r.low,
      close: r.close,
      volume: r.volume,
    })),
  });
}

// GET /api/chart/:symbol/indicators?interval=&indicators=rsi,macd,bbands,atr,… →
// { indicators: { <key>: [{ time /*sec*/, value }] } } computed from the candles.
// Keys match what the chart expects (bb_upper/bb_middle/bb_lower, rsi, atr,
// macd_line/macd_signal/macd_hist, ema9/sma20/vwap, …).
async function chartIndicators(event: RequestEvent, symbolRaw: string): Promise<Response> {
  const rows = await fetchCandles(event, symbolRaw);
  const candles: Candle[] = rows.map((r) => ({
    time: Math.floor(r.tsMs / 1000), // ms → s, matching the chart's candle time
    open: r.open,
    high: r.high,
    low: r.low,
    close: r.close,
    volume: r.volume,
  }));
  const names = (event.url.searchParams.get("indicators") ?? "").split(",");
  return json({ indicators: computeIndicators(candles, names) });
}

// Run a QuestDB /exec query and return its dataset rows ([] on any failure).
async function questdbRows(sql: string): Promise<any[]> {
  try {
    const r = await fetch(`${QUESTDB_URL}/exec?query=${encodeURIComponent(sql)}`, {
      headers: { accept: "application/json" },
    });
    const j: any = await r.json();
    return Array.isArray(j?.dataset) ? j.dataset : [];
  } catch {
    return [];
  }
}

// GET /api/assets/search?q= → the chart's symbol picker. Real symbols straight
// from QuestDB `candles_crypto` (so you can only pick symbols that have data).
async function symbolSearch(event: RequestEvent): Promise<Response> {
  // Sanitised + uppercased — goes into a SQL literal (injection guard).
  const q = sanitizeSymbol(event.url.searchParams.get("q"), 24).toUpperCase();
  if (!q) return json({ results: [] });
  const rows = await questdbRows(
    `SELECT DISTINCT symbol, exchange FROM candles_crypto ` +
      `WHERE upper(symbol) LIKE '%${q}%' ORDER BY symbol LIMIT 30`,
  );
  return json({
    results: rows.map((row) => ({
      symbol: String(row[0]),
      name: String(row[0]),
      type: "crypto",
      exchange: row[1] != null ? String(row[1]) : undefined,
    })),
  });
}

// GET /api/assets/:short → the chart's asset-routing lookup (AssetInfo). We map
// the stored exchange to `source`/`source_chain` so the page picks the right
// live-data path; unknown symbols → {} (page falls back to its slash heuristic).
async function assetInfo(event: RequestEvent, shortRaw: string): Promise<Response> {
  const sym = sanitizeSymbol(shortRaw, 24).toUpperCase();
  if (!sym) return json({});
  const rows = await questdbRows(
    `SELECT exchange FROM candles_crypto ` +
      `WHERE upper(symbol) = '${sym}' OR upper(symbol) LIKE '${sym}/%' ` +
      `OR upper(symbol) LIKE '${sym}-%' LIMIT 1`,
  );
  const ex = rows[0]?.[0] != null ? String(rows[0][0]) : "";
  if (!ex) return json({});
  return json({ type: "crypto", source: ex, source_chain: [ex] });
}

// /settings risk panel ↔ janus forward /api/v1/risk/config (rustrade
// PortfolioRiskConfig: max_daily_loss ≤ 0, max_concurrent_positions,
// max_gross_exposure). The UI works in positive USD for the daily-loss limit; we
// flip the sign on write. The save is honest now (a real PUT) — no fake "Saved".
async function riskConfigGet(event: RequestEvent): Promise<Response> {
  const c = await janusJson(event, JANUS_FORWARD_URL, "/api/v1/risk/config");
  return json(reshapeRiskConfig(c));
}

async function riskConfigPost(event: RequestEvent): Promise<Response> {
  let body: any = {};
  try {
    body = await event.request.json();
  } catch {
    /* empty / non-JSON body */
  }
  const payload = toRiskConfigPayload(body);
  try {
    const headers = upstreamHeaders(event.request.headers);
    headers.set("content-type", "application/json");
    const r = await fetch(`${JANUS_FORWARD_URL}/api/v1/risk/config`, {
      method: "PUT",
      headers,
      body: JSON.stringify(payload),
    });
    if (!r.ok) return json({ ok: false, message: `risk update rejected (${r.status})` }, 502);
    return json({ ok: true });
  } catch {
    return json({ ok: false, message: "risk service unreachable" }, 502);
  }
}

// ── /settings exchange API keys → the spawner's secret store (Postgres ruby_db).
// SECURITY: the browser only ever SUBMITS credentials here; they are never read
// back. The spawner persists them server-side behind X-Internal-Token; the
// status endpoint reports only WHICH exchanges are configured (never the keys).
// Default operation is keyless/public — keys only unlock the authenticated path.
async function exchangeKeysPost(event: RequestEvent, exchange: string): Promise<Response> {
  let body: any = {};
  try {
    body = await event.request.json();
  } catch {
    /* empty / non-JSON body */
  }
  const str = (v: unknown): string => (typeof v === "string" ? v.trim() : "");
  const api_key = str(body?.api_key);
  const api_secret = str(body?.api_secret);
  const passphrase = str(body?.api_passphrase);
  if (!api_key || !api_secret) {
    return json({ ok: false, message: "API key and secret are required" }, 400);
  }
  const payload: Record<string, string> = { exchange, api_key, api_secret };
  if (passphrase) payload.api_passphrase = passphrase;
  try {
    const headers = upstreamHeaders(event.request.headers);
    headers.set("content-type", "application/json");
    const r = await fetch(`${SPAWNER_URL}/secrets`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (r.status === 503) {
      return json({ ok: false, message: "Secret storage (spawner DB) is not configured" }, 503);
    }
    if (!r.ok) return json({ ok: false, message: `Save rejected by spawner (${r.status})` }, 502);
    return json({ ok: true, exchange });
  } catch {
    return json({ ok: false, message: "Secret storage service unreachable" }, 502);
  }
}

// GET → whether the given exchange has stored credentials (never the secrets).
async function exchangeKeysStatus(event: RequestEvent, exchange: string): Promise<Response> {
  try {
    const headers = upstreamHeaders(event.request.headers);
    const r = await fetch(`${SPAWNER_URL}/secrets/status`, { headers });
    if (!r.ok) return json({ configured: false, db_enabled: false });
    const j: any = await r.json();
    const list: any[] = Array.isArray(j?.exchanges) ? j.exchanges : [];
    const match = list.find((e) => String(e?.exchange ?? "").toLowerCase() === exchange);
    return json({
      configured: !!match,
      updated_at: match?.updated_at,
      db_enabled: j?.db_enabled !== false,
    });
  } catch {
    return json({ configured: false, db_enabled: false });
  }
}

async function proxyBackend(event: RequestEvent): Promise<Response> {
  const { pathname, search } = event.url;

  // ── Spawner — a real, working backend (the /bots page) ──────────────────────
  // /api/spawner/<rest> → spawner /<rest>  (mirrors the old vite/nginx rewrite)
  if (pathname === "/api/spawner" || pathname.startsWith("/api/spawner/")) {
    const rest = pathname.replace(/^\/api\/spawner/, "") || "/";
    return forward(event, SPAWNER_URL, rest + search);
  }

  // ── janus mappings (Phase 2) ────────────────────────────────────────────────
  // Status-bar health: reshape janus /health → {redis,janus,feed}.
  if (pathname === "/api/health") {
    return janusHealth(event);
  }

  // Overview "recent signals" panel → janus signals reshaped to RecentSignal[]
  // ({ symbol, direction, confidence, timestamp }).
  if (pathname === "/api/db/redis/get/fks:memories:new") {
    const sigs = await janusRecentSignals(event);
    return json(
      sigs.map((s) => ({
        symbol: s.symbol,
        direction: s.signal_type,
        confidence: s.confidence,
        timestamp: s.timestamp,
      })),
    );
  }

  // Signals page list → janus signals reshaped to { signals: Signal[] }.
  // (janus has no staging/approve workflow — surface them as read-only
  // "generated" signals; the approve/reject actions stay no-ops for now.)
  if (pathname === "/api/signals") {
    const sigs = await janusRecentSignals(event);
    return json({
      signals: sigs.map((s, i) => ({
        id: `${s.symbol ?? "sig"}-${s.timestamp ?? i}`,
        symbol: s.symbol ?? "—",
        type: "entry",
        side: s.signal_type,
        status: "generated",
        timestamp: s.timestamp,
        message: s.signal_type,
      })),
    });
  }

  // janus-ai "Janus State" panel → brain health + recent signals.
  if (pathname === "/api/janus/state") {
    return janusState(event);
  }

  // janus-ai "Strategy Affinity" matrix → forward brain affinity.
  if (pathname === "/api/janus/affinity") {
    return janusAffinity(event);
  }

  // /performance metrics grid → forward risk/performance (+ dashboard).
  if (pathname === "/api/performance") {
    return janusPerformance(event);
  }

  // /settings risk panel — load (GET) / save (POST→PUT) janus risk config.
  if (pathname === "/api/settings/risk") {
    return event.request.method === "POST" ? riskConfigPost(event) : riskConfigGet(event);
  }

  // /settings Kraken API keys → spawner secret store (browser submits only;
  // GET reports only whether keys are configured, never the secrets).
  if (pathname === "/api/settings/kraken-keys") {
    return exchangeKeysPost(event, "kraken");
  }
  if (pathname === "/api/settings/kraken-status") {
    return exchangeKeysStatus(event, "kraken");
  }
  // /performance trade history — janus has no closed-trade ledger here; the
  // demo bot keeps fills on its MockExchange. Honest empty until that's exposed.
  if (pathname === "/api/trades") {
    return json({ trades: [] });
  }

  // ── /monitoring → Prometheus (fks_prometheus:9090) ──────────────────────────
  // Instant/range queries + targets are identical in shape → straight proxy.
  if (pathname === "/api/metrics/query") {
    return forward(event, PROMETHEUS_URL, "/api/v1/query" + search);
  }
  if (pathname === "/api/metrics/query_range") {
    return forward(event, PROMETHEUS_URL, "/api/v1/query_range" + search);
  }
  if (pathname === "/api/metrics/targets") {
    return forward(event, PROMETHEUS_URL, "/api/v1/targets" + search);
  }
  if (pathname === "/api/metrics/alerts") {
    return promAlerts(event);
  }
  if (pathname === "/api/metrics/layout") {
    return json(METRICS_LAYOUT);
  }

  // ── /charts historical candles → QuestDB candles_crypto (OHLCV) ─────────────
  const barsMatch = /^\/bars\/([^/]+)\/candles$/.exec(pathname);
  if (barsMatch) {
    let sym = barsMatch[1];
    try {
      sym = decodeURIComponent(sym);
    } catch {
      /* malformed %-encoding — fall back to the raw segment */
    }
    return questdbCandles(event, sym);
  }

  // Indicator catalog (metadata for the chart's picker UI).
  if (pathname === "/api/indicators/catalog") {
    return json(INDICATOR_CATALOG);
  }

  // ── /charts indicators → computed in-adapter from QuestDB candles ───────────
  const indMatch = /^\/api\/chart\/([^/]+)\/indicators$/.exec(pathname);
  if (indMatch) {
    let sym = indMatch[1];
    try {
      sym = decodeURIComponent(sym);
    } catch {
      /* malformed %-encoding — fall back to the raw segment */
    }
    return chartIndicators(event, sym);
  }

  // ── /charts symbol catalog → QuestDB candles_crypto ─────────────────────────
  if (pathname === "/api/assets/search") {
    return symbolSearch(event);
  }
  const assetMatch = /^\/api\/assets\/([^/]+)$/.exec(pathname);
  if (assetMatch) {
    let sym = assetMatch[1];
    try {
      sym = decodeURIComponent(sym);
    } catch {
      /* malformed %-encoding — fall back to the raw segment */
    }
    return assetInfo(event, sym);
  }

  // More janus panels (overview aggregate / performance) land here next —
  // see docs/architecture/WEBUI_JANUS_REPOINT.md for the per-panel mapping.

  // ── Everything else under a backend prefix → degrade quietly ────────────────
  return gracefulEmpty(pathname);
}

// ════════════════════════════════════════════════════════════════════════════
// Auth  (unchanged) — pages only; API calls are handled by the proxy above
// ════════════════════════════════════════════════════════════════════════════

const PUBLIC_PREFIXES = ["/login", "/logout"];
const PUBLIC_EXACT = ["/api/health", "/healthz"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_EXACT.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export const handle: Handle = async ({ event, resolve }) => {
  // Backend API/SSE calls: proxy or stub them. Never run an API call through the
  // page-auth redirect (a 302→/login would corrupt JSON/SSE consumers).
  if (isBackend(event.url.pathname)) {
    return proxyBackend(event);
  }

  // Always pass through login/logout pages and health endpoints.
  if (isPublic(event.url.pathname)) {
    return resolve(event);
  }

  const secret = env.WEBUI_SESSION_SECRET ?? "";

  // Dev-mode bypass: if no secret is configured, let every request through.
  // This keeps local development friction-free.
  if (!secret) {
    return resolve(event);
  }

  // Validate the session cookie.
  const session = event.cookies.get("fks_session") ?? "";

  if (session === secret) {
    // Valid session — continue to the requested route.
    return resolve(event);
  }

  // Invalid or missing session — redirect to login, preserving the intended URL
  // as a `next` query param so the login page can bounce the user back.
  const next = encodeURIComponent(event.url.pathname + event.url.search);
  return new Response(null, {
    status: 302,
    headers: {
      Location: `/login?next=${next}`,
    },
  });
};
