import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Resolve the SvelteKit `$`-aliases (mirrors svelte.config.js `kit.alias`) so
// unit tests can import lib modules that use them, e.g. `$api/client`.
const r = (p: string) => fileURLToPath(new URL(p, import.meta.url));

// Unit tests for pure-TS modules (the indicator engine, adapter helpers,
// formatters, stores, …). Component/E2E flows are covered by Playwright
// (`npm run test:e2e`); kept separate from vite.config.ts so vitest doesn't load
// the SvelteKit plugin.
export default defineConfig({
  resolve: {
    alias: {
      $lib: r("./src/lib"),
      $api: r("./src/lib/api"),
      $stores: r("./src/lib/stores"),
      $components: r("./src/lib/components"),
    },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
