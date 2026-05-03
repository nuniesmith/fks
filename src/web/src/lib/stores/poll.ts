/**
 * Polling Store — reactive Svelte store backed by periodic fetch.
 *
 * Usage:
 *   const data = createPoll<MyType>('/api/positions', 5000);
 *   $effect(() => { data.start(); return () => data.stop(); });
 *   // Use $data in templates
 */
import { writable, type Readable } from 'svelte/store';
import { api } from '$api/client';

export interface PollStore<T> extends Readable<T | null> {
  start: () => void;
  stop: () => void;
  refresh: () => Promise<void>;
  readonly loading: Readable<boolean>;
  readonly error: Readable<string | null>;
}

export interface PollOpts<T> {
  /** Fetch immediately on start (default: true) */
  immediate?: boolean;
  /** Transform raw API response before storing */
  transform?: (raw: unknown) => T;
}

export function createPoll<T>(
  url: string,
  intervalMs: number,
  opts?: PollOpts<T>,
): PollStore<T> {
  const { immediate = true, transform } = opts ?? {};

  const data = writable<T | null>(null);
  const loading = writable<boolean>(false);
  const error = writable<string | null>(null);

  let timer: ReturnType<typeof setInterval> | null = null;
  let active = false;

  async function fetchOnce(): Promise<void> {
    loading.set(true);
    try {
      const raw = await api.get<T>(url);
      const value = transform ? transform(raw) : raw;
      data.set(value);
      error.set(null);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : String(err);
      error.set(msg);
      console.warn('[poll]', url, msg);
      // Don't crash — keep polling on next interval
    } finally {
      loading.set(false);
    }
  }

  function start(): void {
    if (active) return;
    active = true;

    if (immediate) {
      fetchOnce();
    }

    timer = setInterval(fetchOnce, intervalMs);
  }

  function stop(): void {
    active = false;
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }

  /** Manual one-shot fetch, independent of the interval timer. */
  async function refresh(): Promise<void> {
    await fetchOnce();
  }

  return {
    subscribe: data.subscribe,
    start,
    stop,
    refresh,
    loading: { subscribe: loading.subscribe },
    error: { subscribe: error.subscribe },
  };
}
