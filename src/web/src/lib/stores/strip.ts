/**
 * Strip SSE Store — singleton SSE connection to /sse/strip shared across components.
 *
 * Usage:
 *   import { focusSymbol } from '$lib/stores/strip';
 *   // In a component $effect or template: $focusSymbol
 */
import { createSSE } from '$stores/sse';
import { derived } from 'svelte/store';
import type { StripData } from '$lib/types';

/** Singleton SSE connection to /sse/strip shared across components */
export const stripSSE = createSSE<StripData>('/sse/strip');

/** Current focus symbol from the strip (e.g. "MES", "BTC"). Null until first SSE message. */
export const focusSymbol = derived(
  stripSSE,
  ($strip) => $strip?.focus?.symbol ?? null,
);
