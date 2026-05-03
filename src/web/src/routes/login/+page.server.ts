import { redirect, fail } from "@sveltejs/kit";
import { env } from "$env/dynamic/private";
import type { Actions, PageServerLoad } from "./$types";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** SHA-256 hash via Web Crypto API (globally available in Node 18+ and browsers). */
async function hashPassword(password: string): Promise<string> {
  const data = new TextEncoder().encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Constant-time string comparison via XOR over every character code.
 * Avoids early-exit leaks without needing Node's timingSafeEqual.
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

async function verifyPassword(
  password: string,
  storedHash: string,
): Promise<boolean> {
  const inputHash = await hashPassword(password);
  return timingSafeEqual(inputHash, storedHash.toLowerCase());
}

function safeNext(raw: string | null): string {
  if (!raw) return "/";
  try {
    const decoded = decodeURIComponent(raw);
    // Only allow relative paths — prevent open-redirect attacks.
    if (decoded.startsWith("/") && !decoded.startsWith("//")) return decoded;
  } catch {
    // ignore malformed URIs
  }
  return "/";
}

// ── Load ─────────────────────────────────────────────────────────────────────

export const load: PageServerLoad = async ({ cookies, url }) => {
  const secret = env.WEBUI_SESSION_SECRET ?? "";

  // No secret configured → dev mode, skip auth entirely.
  if (!secret) return {};

  const session = cookies.get("fks_session");
  if (session && session === secret) {
    // Already authenticated — bounce to the intended destination.
    const next = safeNext(url.searchParams.get("next"));
    redirect(302, next);
  }

  return {};
};

// ── Actions ──────────────────────────────────────────────────────────────────

export const actions: Actions = {
  login: async ({ request, cookies, url }) => {
    const passwordHash = env.WEBUI_PASSWORD_HASH ?? "";
    const secret = env.WEBUI_SESSION_SECRET ?? "";

    const data = await request.formData();
    const password = (data.get("password") as string | null) ?? "";
    const next = safeNext(url.searchParams.get("next"));

    if (!password) {
      return fail(400, { error: "Password is required" });
    }

    // ── Dev mode: no password hash configured ────────────────────────────────
    if (!passwordHash) {
      console.warn(
        "[FKS Auth] WEBUI_PASSWORD_HASH is not set — allowing any password (dev mode).",
      );
      if (secret) {
        cookies.set("fks_session", secret, {
          path: "/",
          httpOnly: true,
          sameSite: "lax",
          maxAge: 60 * 60 * 24 * 7, // 7 days
        });
      }
      redirect(302, next);
    }

    // ── Verify password ──────────────────────────────────────────────────────
    const ok = await verifyPassword(password, passwordHash);

    if (!ok) {
      // Small delay to blunt brute-force timing attacks.
      await new Promise((r) => setTimeout(r, 300));
      return fail(401, { error: "Access denied" });
    }

    // ── Set session cookie ───────────────────────────────────────────────────
    if (secret) {
      cookies.set("fks_session", secret, {
        path: "/",
        httpOnly: true,
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 7, // 7 days
      });
    }

    redirect(302, next);
  },
};
