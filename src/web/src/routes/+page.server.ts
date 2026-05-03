/**
 * Overview page — SSR data loader.
 *
 * Pre-fetches the three heaviest data sets in parallel so the page renders
 * with real data on first paint instead of skeleton placeholders.
 *
 * Rules:
 *  - Every fetch is wrapped in .catch(() => null) — a broken backend must
 *    never crash SSR.
 *  - Promise.allSettled ensures one slow/failing endpoint never blocks the
 *    others.
 *  - The transforms here mirror the ones inside createPoll() in +page.svelte
 *    so the client receives data in the exact same shape the poll produces,
 *    and the $derived fallback chain works transparently.
 */
import type { PageServerLoad } from './$types';

// ─── Shape mirrors ────────────────────────────────────────────────────────────
// These mirror the inline interfaces in +page.svelte so the server can apply
// the same normalisations without importing from the component.

interface MarketAsset {
  symbol: string;
  name: string;
  price: number;
  score: number;
  cnn_signal?: string;
  ruby_signal?: string;
  asset_class?: string;
  age?: number;
  change_pct?: number;
}

interface OpenTrade {
  id: number;
  asset: string;
  direction: string;
  entry: number;
  pnl: number;
  contracts?: number;
  strategy?: string;
}

interface FactoryStatus {
  status?: string;
  healthy?: boolean;
  workers?: Record<string, string>;
  providers?: Record<string, { state?: string; failures?: number }>;
  gap_count?: number;
  last_gap_scan?: string;
  uptime_seconds?: number;
}

// ─── Transforms (mirrors of the createPoll transform options in +page.svelte) ─

/** /api/pipeline/scores/json may return { assets: [...] } or a bare array. */
function transformScores(raw: unknown): MarketAsset[] {
  if (raw && typeof raw === 'object' && 'assets' in raw) {
    return (raw as { assets?: MarketAsset[] }).assets ?? [];
  }
  if (Array.isArray(raw)) return raw as MarketAsset[];
  return [];
}

/** /api/trades/open may return a bare array or { trades: [...] }. */
function transformTrades(raw: unknown): OpenTrade[] {
  if (Array.isArray(raw)) return raw as OpenTrade[];
  if (raw && typeof raw === 'object' && 'trades' in raw) {
    return (raw as { trades?: OpenTrade[] }).trades ?? [];
  }
  return [];
}

/** /factory/status returns a plain object — just validate the shape. */
function transformFactory(raw: unknown): FactoryStatus | null {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as FactoryStatus;
  }
  return null;
}

// ─── Loader ───────────────────────────────────────────────────────────────────

export const load: PageServerLoad = async ({ fetch }) => {
  // Fire all three requests simultaneously.  A failure in any one of them is
  // silenced — the client-side polling stores will recover on their first tick.
  const [scoresResult, tradesResult, factoryResult] = await Promise.allSettled([
    fetch('/api/pipeline/scores/json')
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),

    fetch('/api/trades/open')
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),

    fetch('/factory/status')
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null),
  ]);

  const rawScores  = scoresResult.status  === 'fulfilled' ? scoresResult.value  : null;
  const rawTrades  = tradesResult.status  === 'fulfilled' ? tradesResult.value  : null;
  const rawFactory = factoryResult.status === 'fulfilled' ? factoryResult.value : null;

  return {
    /** Pre-transformed MarketAsset[] — null when the backend was unreachable. */
    initialScores: rawScores  != null ? transformScores(rawScores)   : null,
    /** Pre-transformed OpenTrade[] — null when the backend was unreachable. */
    initialTrades: rawTrades  != null ? transformTrades(rawTrades)   : null,
    /** FactoryStatus object — null when the backend was unreachable. */
    initialFactory: rawFactory != null ? transformFactory(rawFactory) : null,
  };
};
