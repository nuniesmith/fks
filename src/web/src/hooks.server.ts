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
// const JANUS_URL = env.JANUS_INTERNAL_URL ?? "http://fks_janus:8080";       // Phase 2
// const JANUS_FORWARD_URL = env.JANUS_FORWARD_INTERNAL_URL ?? "http://fks_janus:8180"; // Phase 2

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
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(": fks — backend not wired yet (janus repoint pending)\n\n"),
        );
        // Intentionally left open + idle. Closed when the client disconnects.
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

async function proxyBackend(event: RequestEvent): Promise<Response> {
  const { pathname, search } = event.url;

  // ── Spawner — a real, working backend (the /bots page) ──────────────────────
  // /api/spawner/<rest> → spawner /<rest>  (mirrors the old vite/nginx rewrite)
  if (pathname === "/api/spawner" || pathname.startsWith("/api/spawner/")) {
    const rest = pathname.replace(/^\/api\/spawner/, "") || "/";
    return forward(event, SPAWNER_URL, rest + search);
  }

  // ── Phase 2: janus mappings go here ─────────────────────────────────────────
  // e.g. /api/health → JANUS_URL/health ; /api/signals → JANUS_URL/api/signals/latest
  //      /api/services/* → JANUS_URL/api/services/* ; /api/v1/risk/* → JANUS_FORWARD_URL
  // (each with a reshape to the panel's expected shape — see WEBUI_JANUS_REPOINT.md)

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
