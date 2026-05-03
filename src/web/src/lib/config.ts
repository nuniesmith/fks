/**
 * Centralised runtime configuration.
 *
 * All values are read from SvelteKit's `$env/dynamic/public` so they are
 * available on the client side **and** can be changed per-deployment
 * without rebuilding the application.
 *
 * Each variable falls back to a sensible default that preserves the
 * behaviour the app had before this module existed.
 *
 * To override any value, set the corresponding `PUBLIC_*` variable in
 * your `.env` (or real environment) and restart the dev server / app.
 */
import { env } from "$env/dynamic/public";

/** SSE reconnect interval in milliseconds */
export const SSE_RECONNECT_MS: number = parseInt(
  env.PUBLIC_SSE_RECONNECT_MS || "5000",
  10,
);

/** Default polling interval for non-SSE endpoints in milliseconds */
export const POLL_INTERVAL_MS: number = parseInt(
  env.PUBLIC_POLL_INTERVAL_MS || "30000",
  10,
);

/** API base URL — leave empty to use relative URLs (same origin) */
export const API_BASE_URL: string = env.PUBLIC_API_BASE_URL || "";
