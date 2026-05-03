/**
 * Focus Symbol Store — global reactive store for the currently focused trading symbol.
 *
 * The Strip SSE pushes focus symbol updates here; chart pages subscribe
 * and auto-switch when the focus changes.
 */
import { writable, derived } from 'svelte/store';

/** The current focus symbol (e.g. "MGC", "MES", "BTC/USD"). */
export const focusSymbol = writable<string>('MGC');

/** Always-uppercase variant for display / API calls. */
export const focusSymbolUpper = derived(focusSymbol, ($s) => $s.toUpperCase());
