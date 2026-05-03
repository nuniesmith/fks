import type { Handle } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";

// ─── Paths that bypass auth ───────────────────────────────────────────────────

const PUBLIC_PREFIXES = ["/login", "/logout"];
const PUBLIC_EXACT = ["/api/health", "/healthz"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_EXACT.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export const handle: Handle = async ({ event, resolve }) => {
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
