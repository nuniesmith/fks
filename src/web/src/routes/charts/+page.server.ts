/**
 * +page.server.ts — Charts SSR data loader
 *
 * Pre-fetches asset routing metadata for the initial symbol so that the
 * `isCrypto` flag and data-source label are known on first paint, removing
 * the skeleton flash and the extra round-trip to /api/assets/{symbol} that
 * `loadChart` would otherwise make inside onMount.
 *
 * The `symbol` is read from the URL search-param so that a shareable URL
 * like /charts?symbol=BTC/USD renders the right asset immediately on the
 * server.  Falls back to DEFAULT_SYMBOL when absent.
 *
 * Rules:
 *  - Every fetch is wrapped in .catch(() => null) — a broken backend must
 *    never crash SSR.
 *  - Promise.allSettled is used so one failure never blocks the others.
 *  - No data here is required for the page to function; the client's
 *    onMount loadChart() will refresh everything regardless.
 */

import type { PageServerLoad } from './$types';

const DEFAULT_SYMBOL = 'MGC';

export const load: PageServerLoad = async ({ fetch, url }) => {
  // Honour a ?symbol= query-param so /charts?symbol=MES etc. works server-side.
  const symbol = url.searchParams.get('symbol') ?? DEFAULT_SYMBOL;

  // Strip the slash for crypto pairs: BTC/USD → BTC (matches client-side apiSymbol logic)
  const short = symbol.includes('/') ? symbol.split('/')[0] : symbol;

  // Parallel SSR fetches — currently just asset info, but structured with
  // allSettled so more prefetches can be added without refactoring.
  const [assetInfoResult] = await Promise.allSettled([
    fetch(`/api/assets/${encodeURIComponent(short)}`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
  ]);

  return {
    /** The resolved symbol (either from URL param or the default). */
    symbol,

    /**
     * Asset routing metadata — tells the client whether the symbol is
     * crypto (Kraken WS) or futures (SSE bars) without a client-side
     * round-trip.  Null when the backend is unavailable; the client will
     * fall back to its own heuristic inside lookupAsset().
     */
    initialAssetInfo:
      assetInfoResult.status === 'fulfilled' ? assetInfoResult.value : null,
  };
};
