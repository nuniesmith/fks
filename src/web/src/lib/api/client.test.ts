import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// A minimal Response stand-in (the client only touches ok/status/statusText/text).
function res(
  body: unknown,
  init: { ok?: boolean; status?: number; statusText?: string } = {},
) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    statusText: init.statusText ?? "OK",
    text: () => Promise.resolve(text),
  };
}

describe("api client", () => {
  it("GET parses a JSON response", async () => {
    mockFetch.mockResolvedValue(res({ value: 1 }));
    const out = await api.get<{ value: number }>("/api/x");
    expect(out).toEqual({ value: 1 });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/x");
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
    expect(init.headers.Accept).toBe("application/json");
  });

  it("POST serialises the body and sets content-type", async () => {
    mockFetch.mockResolvedValue(res({ ok: true }));
    await api.post("/api/y", { a: 1 });
    const [, init] = mockFetch.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("throws ApiError carrying status / statusText / body on a non-2xx", async () => {
    mockFetch.mockResolvedValue(
      res("nope", { ok: false, status: 503, statusText: "Service Unavailable" }),
    );
    await expect(api.get("/api/z")).rejects.toBeInstanceOf(ApiError);

    mockFetch.mockResolvedValue(
      res("boom", { ok: false, status: 500, statusText: "Server Error" }),
    );
    try {
      await api.get("/api/z");
      throw new Error("expected a throw");
    } catch (e) {
      const err = e as ApiError;
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(500);
      expect(err.statusText).toBe("Server Error");
      expect(err.body).toBe("boom");
    }
  });

  it("returns {} for an empty response body", async () => {
    mockFetch.mockResolvedValue(res("", {}));
    expect(await api.get("/api/empty")).toEqual({});
  });

  it("DELETE issues a DELETE with no body", async () => {
    mockFetch.mockResolvedValue(res({}));
    await api.delete("/api/d");
    const [, init] = mockFetch.mock.calls[0];
    expect(init.method).toBe("DELETE");
    expect(init.body).toBeUndefined();
  });

  it("passes an AbortSignal so the request can time out", async () => {
    mockFetch.mockResolvedValue(res({}));
    await api.get("/api/x");
    const [, init] = mockFetch.mock.calls[0];
    expect(init.signal).toBeDefined();
  });
});
