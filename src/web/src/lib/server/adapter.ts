// Pure routing + auth-decision helpers for the SvelteKit server adapter
// (`hooks.server.ts`). Deliberately free of `$env` / `fetch` / SvelteKit
// runtime imports so the access-control core is unit-testable in isolation —
// the hook reads the env + cookies and performs the side effects, this module
// just decides.

/** Same-origin prefixes the dashboard proxies to internal backends. */
export const BACKEND_PREFIXES = [
  "/api/",
  "/sse/",
  "/bars/",
  "/factory/",
  "/kraken/",
  "/fapi/",
];

/** Whether a path is a backend call (proxied) rather than a page. */
export function isBackend(pathname: string): boolean {
  return BACKEND_PREFIXES.some((x) => pathname.startsWith(x));
}

/** Page prefixes that never require an authenticated session. */
export const PUBLIC_PREFIXES = ["/login", "/logout"];
/** Exact paths that never require auth (health probes). */
export const PUBLIC_EXACT = ["/api/health", "/healthz"];

/** Whether a (non-backend) path bypasses the session-auth gate. */
export function isPublic(pathname: string): boolean {
  if (PUBLIC_EXACT.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

// Hop-by-hop / connection-specific headers that must not be forwarded to (or
// streamed back from) an upstream — forwarding them can corrupt message framing
// or smuggle requests.
const HOP = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "keep-alive",
]);

/**
 * Copy `src` minus hop-by-hop headers — used for both the upstream request and
 * the response streamed back. Everything else (the `X-Internal-Token`, cookies,
 * `content-type`, …) is preserved.
 */
export function upstreamHeaders(src: Headers): Headers {
  const h = new Headers();
  for (const [k, v] of src) if (!HOP.has(k.toLowerCase())) h.set(k, v);
  return h;
}

/** Outcome of routing a request through the adapter's auth/proxy gate. */
export type AdapterRoute =
  | { kind: "backend" }
  | { kind: "pass" }
  | { kind: "redirect"; location: string };

/**
 * Decide how the server hook should handle a request — the access-control core,
 * extracted pure so it's testable without a SvelteKit runtime:
 *
 *   - backend prefixes are proxied (never auth-redirected — a 302 → /login
 *     would corrupt a JSON/SSE consumer);
 *   - login/logout pages + health probes are public;
 *   - an empty `secret` is the dev bypass (no auth configured);
 *   - a session cookie matching the secret passes;
 *   - otherwise redirect to `/login?next=<encoded original URL>`.
 */
export function routeRequest(
  pathname: string,
  search: string,
  secret: string,
  session: string,
): AdapterRoute {
  if (isBackend(pathname)) return { kind: "backend" };
  if (isPublic(pathname)) return { kind: "pass" };
  if (!secret) return { kind: "pass" };
  if (session === secret) return { kind: "pass" };
  const next = encodeURIComponent(pathname + search);
  return { kind: "redirect", location: `/login?next=${next}` };
}
