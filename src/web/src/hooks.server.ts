import type { Handle, RequestEvent } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";

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
  const wantsArray = /(list|recent|open|trades|signals|alerts|sessions|containers|runs|notes|providers|gaps|news|quotes|feed|history|scores)/.test(
    pathname,
  );
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
async function janusHealth(event: RequestEvent): Promise<Response> {
  const j = await janusJson(event, JANUS_URL, "/health");
  const comp: Record<string, { status?: string }> = (j?.components ?? {}) as Record<
    string,
    { status?: string }
  >;
  const body = {
    janus: String(j?.status ?? "down"),
    redis: String(comp.redis?.status ?? "—"),
    feed: String(j?.forward_service ?? comp.data?.status ?? comp.questdb?.status ?? "—"),
  };
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
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

// ── /monitoring: Prometheus proxy ───────────────────────────────────────────
// The /monitoring page calls /api/metrics/* (these used to be served by Ruby's
// data service, which queried Prometheus and reshaped). We reprise that role:
// query/query_range/targets are a straight pass-through (identical shapes), and
// alerts/layout get a light reshape.

// "2026-06-08T12:00:00Z" → "5m" / "2h" / "3d" (compact age, for the alert feed).
function humanizeSince(iso?: string): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

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
