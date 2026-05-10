# fks-web — Claude Code Project Instructions

> **Repo (future):** `github.com/nuniesmith/fks-web`
> **Today's path:** `fks-full/src/web/`
> Will become its own repo; deployed as `nuniesmith/fks:webui` via the
> Node Dockerfile pattern.

## What this is

SvelteKit 5 frontend for the FKS platform. Single-page terminal UI with:
top status strip, multi-group tab bar, route-per-feature workspace pane,
bottom status bar. Talks to Ruby (`/api/*`, `/sse/*`), Janus (`/api/*`),
and the spawner (`/api/spawner/*`, `/api/bots/*`).

## Stack

| | |
|--|--|
| Framework | SvelteKit 5 (runes syntax: `$state`, `$derived`, `$effect`, `$props`, `$snippet`) |
| Build | Vite 6 + `@sveltejs/adapter-node` |
| Language | TypeScript (strict) |
| Charts | `lightweight-charts` |
| Tests | Playwright (E2E) |
| Lint | `svelte-check` |

## Build & test

```bash
cd src/web

# Dev server (hot reload)
npm run dev                # http://localhost:5173

# Type-check
npm run check
npm run check:watch

# E2E tests (Playwright)
npm run test:e2e
npm run test:e2e:ui

# Production build
npm run build              # → build/ via adapter-node
npm run preview            # serve the production bundle locally
```

## Repository layout

```
src/web/
├── package.json
├── svelte.config.js
├── vite.config.ts            # dev proxies → fks_ruby, fks_bot_spawner, …
├── playwright.config.ts
├── src/
│   ├── app.html
│   ├── app.css
│   ├── app.d.ts
│   ├── hooks.server.ts
│   ├── lib/
│   │   ├── api/              # typed fetch wrappers (client.ts, spawner.ts, …)
│   │   ├── types/            # shared TS types per domain (spawner.ts, charts, …)
│   │   ├── stores/           # createPoll, createSSE, focusSymbol, strip
│   │   ├── components/
│   │   │   ├── shell/        # Strip, TabBar, StatusBar (the terminal chrome)
│   │   │   └── ui/           # Panel, Badge, Skeleton, ProgressBar, FilterChips, …
│   │   ├── utils/format.ts   # fmtPrice, fmtPct, fmtDollar, fmtTime, scoreColor, …
│   │   ├── config.ts         # PUBLIC_* env-var-driven runtime config
│   │   └── workspaces.ts     # registered workspace nav groups
│   ├── styles/
│   └── routes/               # one folder per feature (charts, bots, signals, …)
└── tests/                    # Playwright E2E
```

## Code conventions

- **Svelte 5 runes only.** No `let count = 0` reactive statements. Always:
  ```svelte
  let count = $state(0);
  let doubled = $derived(count * 2);
  $effect(() => { console.log(count); });
  let { foo, bar } = $props();
  ```
- **Snippets, not slots.** Components that need a header pass-through use `{#snippet header()}` (Svelte 5), not `<div slot="header">` (Svelte 4 — fails silently here).
- **Types live in `$lib/types/`.** Never redeclare a shared type inline in a component.
- **API calls go through `$lib/api/*`.** The `api` export from `$lib/api/client.ts` is an *object* with `.get / .post / .put / .delete` methods — **not a callable function**. Calling `api(url, opts)` is a common mistake.
- **Polls live in `$stores/poll.ts`.** Don't reinvent `setInterval` in components.
- **SSE lives in `$stores/sse.ts`** (or open `EventSource` directly when you need per-row control like the `/bots` log viewer does).
- **Styling:** dark theme via CSS variables (`var(--bg1)`, `var(--t1)`, `var(--cyan)`, `var(--accent)`, `var(--green-dim)`, …) defined in `app.css`. Use the existing palette before introducing new colours.

## Common workflows

### Add a new route
1. Create `src/routes/<feature>/+page.svelte`.
2. Reach for `Panel`, `Badge`, `Skeleton`, `StatCard` from `$components/ui/`.
3. If it needs an API client, add `src/lib/api/<feature>.ts` (typed wrapper) + `src/lib/types/<feature>.ts` (mirror of backend types).
4. Add the tab to `src/lib/components/shell/TabBar.svelte` in the right group (Markets / Trading / Analysis / System / per-workspace).
5. If it talks to a new backend, add the proxy to `vite.config.ts` (dev) and the equivalent location block to `infrastructure/config/nginx/conf.d/dev.conf` (prod).

### Add a new SSE-driven feature
Pattern: `routes/bots/+page.svelte` log viewer. `EventSource` opened lazily, `bind:this` on the container, `$effect` triggers scroll-to-tail when followed, `onscroll` handler flips follow state, optional "Jump to latest" button when paused.

### Add a chart
Use `lightweight-charts`. Pattern: `routes/charts/+page.svelte`. Bars come from Ruby via `/bars/{symbol}` (REST), updates via WebSocket on `/sse/data/{symbol}`.

## Pre-split gotchas

- **`vite.config.ts` proxies** point at internal hostnames (`fks_ruby`, `fks_bot_spawner`, `fks_janus`) that only resolve inside the Docker network. After the split, the new repo's `vite.config.ts` will need a localhost-friendly default for dev outside Docker.
- **`PUBLIC_API_URL`** is currently used as the dev proxy target. Production talks to nginx via relative URLs.
- **Auth.** Today the WebUI sits behind nginx + Tailscale; nginx injects `X-Internal-Token` on every proxied request. The Svelte side carries no auth. Don't add browser-side credential handling — Tailscale + a single shared token is the policy.
- **29 pre-existing type errors** in `npm run check` (`analysis/`, `chains/`, `news/`, `cnn/`, `pnl/`, +layout.ts) — small `any`/`unknown` gaps unrelated to the dual-script bug we already fixed in PR #14. Cleanup is in `TODO.md`.

## Status

After PRs #13, #14, #19 in `fks-full`:
- `/bots` route fully functional (spawn form + container list + SSE log viewer with follow-tail + run history).
- Build is green (`npm run build` succeeds after the dual-script repair).
- 29 of the original 59 `npm run check` errors fixed; the rest are
  tracked in `TODO.md`.
