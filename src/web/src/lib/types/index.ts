/**
 * FKS WebUI — Shared Types
 *
 * Central type definitions shared across multiple routes and components.
 * Import from '$lib/types' (resolves to this file via the $lib alias).
 */

// ─── Strip / Status Bar ───────────────────────────────────────────────────────

/** Live data streamed from /sse/strip */
export interface StripData {
  focus?: { symbol: string; price: number; change_pct: number };
  pnl?: { daily: number; weekly: number };
  risk?: { dd_pct: number; max_dd: number };
  equity?: number;
  session?: { status: string; duration: string };
  regime?: { label: string; confidence: number };
}

// ─── Chart / OHLCV ───────────────────────────────────────────────────────────

/** A single OHLCV candle from the Ruby data service (timestamps in ms). */
export interface CandleBar {
  timestamp: number; // epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/**
 * Incremental bar update from a live WebSocket feed.
 * `time` may be an epoch-second integer (lightweight-charts convention) or
 * an ISO-8601 string depending on the source.
 */
export interface BarUpdate {
  time: number | string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// ─── Asset Registry ───────────────────────────────────────────────────────────

/** A search result entry from /api/assets/search */
export interface AssetSearchResult {
  symbol: string;
  name?: string;
  type?: string;
  exchange?: string;
}

/**
 * Asset routing metadata returned by /api/assets/{symbol}/info.
 * Tells the chart which data source and WebSocket URL to use.
 */
export interface AssetInfo {
  type?: string;
  source?: string;
  /** Ordered list of data sources to try (e.g. ["kraken", "ruby"]). */
  source_chain?: string[];
  ws_url?: string;
}

// ─── Indicators ───────────────────────────────────────────────────────────────

/** A single point on an indicator overlay series. */
export interface IndicatorPoint {
  /** Epoch-second timestamp (lightweight-charts convention). */
  time: number;
  value: number;
}
