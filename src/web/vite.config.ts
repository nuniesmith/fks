import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  // No dev proxies: the SvelteKit server hook (src/hooks.server.ts) is the single
  // backend seam in both dev and prod — it proxies /api, /sse, /bars, /factory,
  // /kraken, /fapi to janus / spawner / Prometheus / QuestDB (or stubs them).
  // A Vite server.proxy here would shadow the hook and break that path. Override
  // upstream hosts for non-Docker dev via *_INTERNAL_URL env vars (see the hook).
});
