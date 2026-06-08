import { defineConfig } from "vitest/config";

// Unit tests for pure-TS modules (the indicator engine, etc.). Component and
// end-to-end flows are covered by Playwright (`npm run test:e2e`) instead.
// Kept separate from vite.config.ts so vitest doesn't load the SvelteKit plugin
// — these tests have no Svelte/`$app` dependencies.
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
