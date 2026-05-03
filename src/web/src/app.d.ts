// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
  namespace App {
    // interface Error {}
    // interface Locals {}
    // interface PageData {}
    // interface PageState {}
    // interface Platform {}
  }
}

declare module "$env/dynamic/public" {
  /**
   * Dynamic public environment variables, accessible on the client.
   *
   * These are read at runtime (not inlined at build time) so they can
   * be changed per-deployment without rebuilding.
   */
  export const env: {
    /**
     * SSE reconnect interval in milliseconds.
     *
     * How long to wait before reconnecting a dropped SSE connection.
     * @default '5000'
     */
    PUBLIC_SSE_RECONNECT_MS: string;

    /**
     * Default polling interval in milliseconds.
     *
     * Suggested interval for non-SSE periodic data fetching.
     * @default '30000'
     */
    PUBLIC_POLL_INTERVAL_MS: string;

    /**
     * API base URL.
     *
     * Leave empty to use relative URLs (same origin).
     * Set when the data service lives on a different host/port.
     * @default ''
     */
    PUBLIC_API_BASE_URL: string;

    /**
     * Backend API URL used by the Vite dev proxy and SSR fetch calls.
     * @default 'http://localhost:8000'
     */
    PUBLIC_API_URL: string;

    /**
     * Janus service URL.
     * @default 'http://localhost:7000'
     */
    PUBLIC_JANUS_URL: string;

    /** Allow additional PUBLIC_ variables without explicit declarations. */
    [key: `PUBLIC_${string}`]: string | undefined;
  };
}

export {};
