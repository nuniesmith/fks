import { describe, expect, it } from "vitest";
import { isBackend, isPublic, routeRequest, upstreamHeaders } from "./adapter";

describe("isBackend", () => {
  it("matches the proxied backend prefixes", () => {
    for (const p of [
      "/api/health",
      "/sse/bars/BTC",
      "/bars/BTC/candles",
      "/factory/news",
      "/kraken/status",
      "/fapi/dashboard",
    ]) {
      expect(isBackend(p)).toBe(true);
    }
  });

  it("does not match pages or a bare prefix without the trailing slash", () => {
    for (const p of ["/", "/charts", "/login", "/api", "/bars"]) {
      expect(isBackend(p)).toBe(false);
    }
  });
});

describe("isPublic", () => {
  it("treats login/logout pages and health probes as public", () => {
    for (const p of [
      "/login",
      "/login/oauth",
      "/logout",
      "/api/health",
      "/healthz",
    ]) {
      expect(isPublic(p)).toBe(true);
    }
  });

  it("treats every other page as non-public", () => {
    for (const p of ["/", "/charts", "/settings", "/api/health/extra", "/healthzz"]) {
      expect(isPublic(p)).toBe(false);
    }
  });
});

describe("upstreamHeaders", () => {
  it("strips hop-by-hop headers and preserves the rest (case-insensitive)", () => {
    const src = new Headers();
    src.set("Host", "evil.example");
    src.set("Connection", "keep-alive");
    src.set("Content-Length", "10");
    src.set("Transfer-Encoding", "chunked");
    src.set("Keep-Alive", "timeout=5");
    src.set("X-Internal-Token", "secret-token");
    src.set("Cookie", "fks_session=abc");
    src.set("Content-Type", "application/json");

    const out = upstreamHeaders(src);

    for (const stripped of [
      "host",
      "connection",
      "content-length",
      "transfer-encoding",
      "keep-alive",
    ]) {
      expect(out.has(stripped)).toBe(false);
    }
    // The internal-auth token, cookies and content type must survive.
    expect(out.get("x-internal-token")).toBe("secret-token");
    expect(out.get("cookie")).toBe("fks_session=abc");
    expect(out.get("content-type")).toBe("application/json");
  });
});

describe("routeRequest", () => {
  const SECRET = "s3cret";

  it("proxies backend paths regardless of auth — never redirects an API/SSE call", () => {
    expect(routeRequest("/api/signals", "", SECRET, "")).toEqual({ kind: "backend" });
    // even with a wrong session, a backend call is proxied (a 302 would corrupt it)
    expect(routeRequest("/sse/bars/BTC", "", SECRET, "wrong")).toEqual({ kind: "backend" });
  });

  it("passes public pages without a session", () => {
    expect(routeRequest("/login", "", SECRET, "")).toEqual({ kind: "pass" });
    expect(routeRequest("/healthz", "", SECRET, "")).toEqual({ kind: "pass" });
  });

  it("dev-bypasses every page when no secret is configured", () => {
    expect(routeRequest("/settings", "", "", "")).toEqual({ kind: "pass" });
  });

  it("passes a protected page with the matching session cookie", () => {
    expect(routeRequest("/settings", "", SECRET, SECRET)).toEqual({ kind: "pass" });
  });

  it("redirects a protected page with a missing/wrong session, preserving the URL", () => {
    expect(routeRequest("/settings", "?tab=keys", SECRET, "")).toEqual({
      kind: "redirect",
      location: "/login?next=%2Fsettings%3Ftab%3Dkeys",
    });
    expect(routeRequest("/charts", "", SECRET, "nope")).toEqual({
      kind: "redirect",
      location: "/login?next=%2Fcharts",
    });
  });
});
