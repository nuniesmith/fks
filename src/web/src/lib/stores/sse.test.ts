import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { get as readStore } from "svelte/store";

// sse.ts pulls SSE_RECONNECT_MS from $lib/config, which imports `$env` (not
// resolvable in a plain node test). Mock it — the reconnect interval is passed
// explicitly in the tests that exercise reconnection.
vi.mock("$lib/config", () => ({ SSE_RECONNECT_MS: 5000 }));

import { createSSE } from "./sse";

// Minimal, controllable EventSource stand-in.
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, ((e: { data: string }) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (e: { data: string }) => void) {
    (this.listeners[name] ??= []).push(fn);
  }
  close() {
    this.closed = true;
  }

  // ── test drivers ──
  emitOpen() {
    this.onopen?.();
  }
  emitMessage(data: string) {
    this.onmessage?.({ data });
  }
  emitNamed(name: string, data: string) {
    (this.listeners[name] ?? []).forEach((fn) => fn({ data }));
  }
  emitError() {
    this.onerror?.();
  }
}

const last = () => MockEventSource.instances[MockEventSource.instances.length - 1];

beforeEach(() => {
  vi.useFakeTimers();
  MockEventSource.instances = [];
  (globalThis as unknown as { EventSource: unknown }).EventSource = MockEventSource;
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  delete (globalThis as unknown as { EventSource?: unknown }).EventSource;
});

describe("createSSE", () => {
  it("connects, flips `connected` on open, and parses JSON messages by default", () => {
    const sse = createSSE<{ v: number }>("/sse/x");
    sse.connect();
    expect(last().url).toBe("/sse/x");
    expect(readStore(sse.connected)).toBe(false);

    last().emitOpen();
    expect(readStore(sse.connected)).toBe(true);

    last().emitMessage(JSON.stringify({ v: 42 }));
    expect(readStore(sse)).toEqual({ v: 42 });
  });

  it("routes named events through addEventListener", () => {
    const sse = createSSE<{ v: number }>("/sse/x", { eventName: "bar" });
    sse.connect();
    last().emitNamed("bar", JSON.stringify({ v: 7 }));
    expect(readStore(sse)).toEqual({ v: 7 });
  });

  it("uses a custom parser and swallows parse errors", () => {
    const sse = createSSE<number>("/sse/x", { parse: (d) => Number(d) });
    sse.connect();
    last().emitMessage("123");
    expect(readStore(sse)).toBe(123);

    const j = createSSE("/sse/y"); // default JSON.parse
    j.connect();
    last().emitMessage("not json{");
    expect(readStore(j)).toBeNull(); // parse threw → value unchanged
  });

  it("auto-reconnects after an error, then disconnect tears it down", () => {
    const sse = createSSE("/sse/x", { reconnectMs: 5000 });
    sse.connect();
    last().emitOpen();
    expect(readStore(sse.connected)).toBe(true);

    const first = last();
    first.emitError();
    expect(readStore(sse.connected)).toBe(false);
    expect(first.closed).toBe(true);
    expect(MockEventSource.instances).toHaveLength(1); // not reconnected yet

    vi.advanceTimersByTime(5000);
    expect(MockEventSource.instances).toHaveLength(2); // reconnected

    sse.disconnect();
    expect(last().closed).toBe(true);
    expect(readStore(sse.connected)).toBe(false);
  });

  it("disconnect cancels a scheduled reconnect", () => {
    const sse = createSSE("/sse/x", { reconnectMs: 5000 });
    sse.connect();
    last().emitError();
    expect(MockEventSource.instances).toHaveLength(1);

    sse.disconnect();
    vi.advanceTimersByTime(10_000);
    expect(MockEventSource.instances).toHaveLength(1); // no reconnect after disconnect
  });
});
