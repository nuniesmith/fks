/**
 * +page.server.ts — Trading page SSR data loader
 *
 * Pre-fetches the two heaviest data sources on the server during SSR so the
 * page renders with real data on first paint instead of showing skeleton
 * loaders while client-side polls/timers fire for the first time.
 *
 * Rules:
 *  - Every fetch is wrapped in .catch(() => null) so a broken backend never
 *    crashes SSR — the client-side polling logic handles recovery.
 *  - Promise.allSettled ensures one slow/failing endpoint never blocks others.
 *  - Data is pre-shaped to match what the client-side stores produce, so the
 *    component can drop it in without extra parsing.
 */

import type { PageServerLoad } from './$types';

// ─── Shared transform helpers ─────────────────────────────────────────────────

/**
 * Normalise the /api/trades/open response into a flat Trade array.
 * The endpoint returns either a bare array or `{ trades: [...] }`.
 */
function normaliseTrades(raw: unknown): unknown[] {
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === 'object' && 'trades' in raw) {
    const wrapped = (raw as Record<string, unknown>).trades;
    return Array.isArray(wrapped) ? wrapped : [];
  }
  return [];
}

/**
 * Parse the Redis signal payload from /api/db/redis/get/fks:memories:new.
 *
 * The endpoint can return:
 *   - An array of signal objects / JSON strings
 *   - An object with a `value` field (single or serialised array)
 *   - null / undefined on a cache miss
 *
 * Returns at most 10 parsed Signal objects that have at least a `symbol`
 * or `direction` field, mirroring the fetchSignals() logic in +page.svelte.
 */
function parseSignals(raw: unknown): unknown[] {
  if (!raw) return [];

  // Determine the iterable source
  let items: unknown[];
  if (Array.isArray(raw)) {
    items = raw;
  } else if (raw && typeof raw === 'object' && 'value' in raw) {
    items = [(raw as Record<string, unknown>).value];
  } else {
    items = [raw];
  }

  const parsed: unknown[] = [];

  for (const item of items) {
    try {
      const sig = typeof item === 'string' ? JSON.parse(item) : item;
      if (sig && typeof sig === 'object') {
        const s = sig as Record<string, unknown>;
        if (s.symbol || s.direction) {
          parsed.push(sig);
        }
      }
    } catch {
      // Skip items that can't be parsed — same as client-side behaviour
    }
  }

  return parsed.slice(0, 10);
}

// ─── Loader ───────────────────────────────────────────────────────────────────

export const load: PageServerLoad = async ({ fetch }) => {
  const [tradesResult, signalsResult] = await Promise.allSettled([
    // Open positions — polled every 5 s on the client
    fetch('/api/trades/open')
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),

    // Recent signals from Redis — polled every 4 s on the client
    fetch('/api/db/redis/get/fks:memories:new')
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
  ]);

  // Extract settled values (rejected promises fall back to null)
  const rawTrades = tradesResult.status === 'fulfilled' ? tradesResult.value : null;
  const rawSignals = signalsResult.status === 'fulfilled' ? signalsResult.value : null;

  return {
    /** Pre-shaped Trade[] ready for `let trades = $derived($tradesStore ?? data.initialTrades ?? [])` */
    initialTrades: rawTrades != null ? normaliseTrades(rawTrades) : null,

    /** Pre-parsed Signal[] ready for seeding the $state variable in +page.svelte */
    initialSignals: rawSignals != null ? parseSignals(rawSignals) : null,
  };
};
