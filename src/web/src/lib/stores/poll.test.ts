import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { get as readStore } from "svelte/store";
import { api } from "$api/client";
import { createPoll } from "./poll";

// The poll store's only I/O is `api.get`; mock it and drive the timers.
vi.mock("$api/client", () => ({ api: { get: vi.fn() } }));
const apiGet = vi.mocked(api.get);

beforeEach(() => {
  vi.useFakeTimers();
  apiGet.mockReset();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("createPoll", () => {
  it("fetches immediately on start and stores the result", async () => {
    apiGet.mockResolvedValue({ value: 1 });
    const poll = createPoll<{ value: number }>("/api/x", 1000);
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(apiGet).toHaveBeenCalledWith("/api/x");
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(readStore(poll)).toEqual({ value: 1 });
    poll.stop();
  });

  it("re-fetches on each interval tick", async () => {
    apiGet.mockResolvedValue({ value: 1 });
    const poll = createPoll("/api/x", 1000);
    poll.start();
    await vi.advanceTimersByTimeAsync(0); // immediate
    expect(apiGet).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(apiGet).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1000);
    expect(apiGet).toHaveBeenCalledTimes(3);
    poll.stop();
  });

  it("stops fetching after stop()", async () => {
    apiGet.mockResolvedValue({ value: 1 });
    const poll = createPoll("/api/x", 1000);
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    poll.stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(apiGet).toHaveBeenCalledTimes(1); // only the immediate fetch
  });

  it("skips the immediate fetch when immediate:false", async () => {
    apiGet.mockResolvedValue({ value: 1 });
    const poll = createPoll("/api/x", 1000, { immediate: false });
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(apiGet).toHaveBeenCalledTimes(0);
    await vi.advanceTimersByTimeAsync(1000);
    expect(apiGet).toHaveBeenCalledTimes(1);
    poll.stop();
  });

  it("ignores a second start() (no duplicate intervals)", async () => {
    apiGet.mockResolvedValue({ value: 1 });
    const poll = createPoll("/api/x", 1000);
    poll.start();
    poll.start(); // guarded by the `active` flag
    await vi.advanceTimersByTimeAsync(0);
    expect(apiGet).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(apiGet).toHaveBeenCalledTimes(2); // not 4
    poll.stop();
  });

  it("captures errors without crashing and leaves data null", async () => {
    apiGet.mockRejectedValue(new Error("boom"));
    const poll = createPoll("/api/x", 1000);
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(readStore(poll)).toBeNull();
    expect(readStore(poll.error)).toBe("boom");
    expect(readStore(poll.loading)).toBe(false);
    poll.stop();
  });

  it("applies the transform before storing", async () => {
    apiGet.mockResolvedValue({ n: 21 });
    const poll = createPoll<number>("/api/x", 1000, {
      transform: (raw: any) => raw.n * 2,
    });
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(readStore(poll)).toBe(42);
    poll.stop();
  });

  it("refresh() fetches once, independent of the interval", async () => {
    apiGet.mockResolvedValue({ value: 1 });
    const poll = createPoll("/api/x", 1000, { immediate: false });
    await poll.refresh();
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(readStore(poll)).toEqual({ value: 1 });
  });
});
