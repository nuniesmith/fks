/**
 * FKS Terminal — Shared Formatter Utilities
 *
 * Centralises all common display-formatting functions so they can be
 * imported from `$lib/utils/format` instead of being copy-pasted into
 * every page/component.
 */

// ─── Price / Number ────────────────────────────────────────────────────────

/**
 * Format a price with adaptive decimal precision.
 *  < 1      → 6 decimals  (crypto sub-dollar)
 *  < 100    → 4 decimals  (mid-range futures)
 *  >= 100   → 2 decimals  (equities / large futures)
 */
export function fmtPrice(n: number | undefined | null): string {
  if (n == null) return '—';
  const abs = Math.abs(n);
  const digits = abs < 1 ? 6 : abs < 100 ? 4 : 2;
  return n.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/**
 * Format a percentage with sign prefix: "+1.23%" / "-0.45%"
 */
export function fmtPct(n: number | undefined | null): string {
  if (n == null) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

/**
 * Format a dollar P&L value with sign prefix: "+$12.34" / "-$5.00"
 */
export function fmtDollar(n: number | undefined | null): string {
  if (n == null) return '—';
  const sign = n >= 0 ? '+' : '';
  return `${sign}$${Math.abs(n).toFixed(2)}`;
}

/**
 * Format a confidence value.
 * Accepts either a fraction (0–1) or a percentage (1–100).
 * Returns "73%" style string.
 */
export function fmtConfidence(n: number | undefined | null): string {
  if (n == null) return '—';
  if (n <= 1) return (n * 100).toFixed(0) + '%';
  return n.toFixed(0) + '%';
}

/**
 * Format a number with a fixed number of decimal places.
 */
export function fmtFixed(n: number | undefined | null, decimals = 2): string {
  if (n == null) return '—';
  return n.toFixed(decimals);
}

/**
 * Format a large integer with locale thousands separators: "1,234,567"
 */
export function fmtInt(n: number | undefined | null): string {
  if (n == null) return '—';
  return Math.round(n).toLocaleString('en-US');
}

// ─── Colour Helpers ────────────────────────────────────────────────────────

export type ScoreColor = 'green' | 'amber' | 'cyan' | 'red';
export type SignalVariant = 'green' | 'red' | 'amber' | 'default';
export type RiskVariant = 'green' | 'amber' | 'red' | 'default';
export type RegimeVariant = 'green' | 'red' | 'amber' | 'cyan' | 'purple' | 'default';
export type DirectionVariant = 'green' | 'red' | 'default';

/**
 * Map a 0–100 score to a colour bucket for badges / progress bars.
 *  >= 70 → green
 *  >= 40 → cyan
 *  >= 20 → amber
 *  <  20 → red
 */
export function scoreColor(score: number): ScoreColor {
  if (score >= 70) return 'green';
  if (score >= 40) return 'cyan';
  if (score >= 20) return 'amber';
  return 'red';
}

/**
 * Map a signal string (buy/sell/hold/…) to a Badge variant.
 */
export function signalVariant(signal: string | undefined | null): SignalVariant {
  if (!signal) return 'default';
  const s = signal.toLowerCase();
  if (s.includes('buy') || s.includes('long') || s.includes('bull')) return 'green';
  if (s.includes('sell') || s.includes('short') || s.includes('bear')) return 'red';
  if (s.includes('hold') || s.includes('neutral')) return 'amber';
  return 'default';
}

/**
 * Map a drawdown percentage to a risk colour variant.
 *  > 5% → red
 *  > 2% → amber
 *  else → green
 */
export function riskVariant(dd: number | undefined | null): RiskVariant {
  if (dd == null) return 'default';
  if (dd > 5) return 'red';
  if (dd > 2) return 'amber';
  return 'green';
}

/**
 * Map a regime label string to a Badge variant.
 */
export function regimeVariant(
  label: string | undefined | null,
): RegimeVariant {
  if (!label) return 'default';
  const l = label.toLowerCase();
  if (l.includes('bull') || l.includes('trend up') || l.includes('risk on')) return 'green';
  if (l.includes('bear') || l.includes('trend down') || l.includes('risk off')) return 'red';
  if (l.includes('chop') || l.includes('range') || l.includes('neutral')) return 'amber';
  if (l.includes('volat')) return 'purple';
  return 'cyan';
}

/**
 * Map a trade direction string (long/short/buy/sell) to a Badge variant.
 */
export function directionVariant(dir: string | undefined | null): DirectionVariant {
  if (!dir) return 'default';
  const d = dir.toLowerCase();
  if (d === 'long' || d === 'buy') return 'green';
  if (d === 'short' || d === 'sell') return 'red';
  return 'default';
}

// ─── Time ──────────────────────────────────────────────────────────────────

/**
 * Format a UTC timestamp (ISO string or ms epoch) as a short local time.
 * e.g. "14:32:07"
 */
export function fmtTime(ts: string | number | undefined | null): string {
  if (ts == null) return '—';
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-US', { hour12: false });
}

/**
 * Format a UTC timestamp as a short local date+time.
 * e.g. "2025-07-18 14:32"
 */
export function fmtDateTime(ts: string | number | undefined | null): string {
  if (ts == null) return '—';
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts);
  if (isNaN(d.getTime())) return '—';
  const date = d.toLocaleDateString('en-CA'); // YYYY-MM-DD
  const time = d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

/**
 * Return the current wall-clock time as a "HH:MM:SS TZ" string,
 * suitable for the terminal strip clock.
 */
export function nowClock(): string {
  return new Date().toLocaleTimeString('en-US', {
    hour12: false,
    timeZoneName: 'short',
  });
}
