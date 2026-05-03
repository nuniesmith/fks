<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$api/client';

  // ─── State ────────────────────────────────────────────────────────────────

  type DotState = 'ok' | 'warn' | 'down' | 'unknown';

  interface HealthState {
    redis: string;
    janus: string;
    feed: string;
  }

  let health = $state<HealthState>({ redis: '—', janus: '—', feed: '—' });
  let lastFetch = $state<Date | null>(null);

  // ─── Helpers ─────────────────────────────────────────────────────────────

  /** Classify a raw health value string into a dot state. */
  function classify(val: string): DotState {
    if (!val || val === '—') return 'unknown';
    const v = val.toLowerCase();
    if (
      v === 'ok' ||
      v === 'connected' ||
      v === 'up' ||
      v === 'ready' ||
      v === 'healthy' ||
      v === 'running'
    ) {
      return 'ok';
    }
    if (
      v === 'degraded' ||
      v === 'slow' ||
      v === 'warn' ||
      v === 'warning' ||
      v === 'partial'
    ) {
      return 'warn';
    }
    return 'down';
  }

  /** Map a dot state to its CSS colour variable. */
  function dotColor(state: DotState): string {
    switch (state) {
      case 'ok':      return 'var(--green)';
      case 'warn':    return 'var(--amber)';
      case 'down':    return 'var(--red)';
      case 'unknown': return 'var(--t3)';
    }
  }

  /** Map a dot state to an accessible label. */
  function dotLabel(service: string, state: DotState): string {
    const stateStr = state === 'ok' ? 'healthy' : state === 'warn' ? 'degraded' : state === 'down' ? 'down' : 'unknown';
    return `${service}: ${stateStr}`;
  }

  // ─── Derived ─────────────────────────────────────────────────────────────

  let redisState  = $derived(classify(health.redis));
  let janusState  = $derived(classify(health.janus));
  let feedState   = $derived(classify(health.feed));

  // ─── Data Fetching ────────────────────────────────────────────────────────

  async function fetchHealth(): Promise<void> {
    try {
      const data = await api.get<Record<string, unknown>>('/api/health');
      health = {
        redis: String((data as any).redis ?? '—'),
        janus: String((data as any).janus ?? '—'),
        feed:  String((data as any).feed  ?? '—'),
      };
      lastFetch = new Date();
    } catch {
      // Network or parse error — leave current values; dots will amber/grey out
      // on the next successful fetch cycle or after restart.
    }
  }

  onMount(() => {
    // Fetch immediately so dots are not stuck on grey at boot.
    fetchHealth();

    const interval = setInterval(fetchHealth, 15_000);
    return () => clearInterval(interval);
  });
</script>

<footer class="statusbar" role="status" aria-live="polite" aria-label="System health status">
  <span class="status-item" aria-label={dotLabel('Redis', redisState)}>
    <span
      class="dot"
      class:dot-pulse={redisState === 'ok'}
      style="background: {dotColor(redisState)}"
    ></span>
    Redis
    {#if health.redis !== '—'}
      <span class="health-val">{health.redis}</span>
    {/if}
  </span>

  <span class="status-item" aria-label={dotLabel('Janus', janusState)}>
    <span
      class="dot"
      class:dot-pulse={janusState === 'ok'}
      style="background: {dotColor(janusState)}"
    ></span>
    Janus
    {#if health.janus !== '—'}
      <span class="health-val">{health.janus}</span>
    {/if}
  </span>

  <span class="status-item" aria-label={dotLabel('Feed', feedState)}>
    <span
      class="dot"
      class:dot-pulse={feedState === 'ok'}
      style="background: {dotColor(feedState)}"
    ></span>
    Feed
    {#if health.feed !== '—'}
      <span class="health-val">{health.feed}</span>
    {/if}
  </span>

  <span class="status-right">
    FKS Terminal · SvelteKit
    {#if lastFetch}
      <span class="last-fetch" title="Last health check: {lastFetch.toLocaleTimeString()}">·</span>
    {/if}
  </span>

  <form method="POST" action="/logout" class="logout-form">
    <button type="submit" class="logout-btn" title="Sign out of FKS Terminal">
      <span aria-hidden="true">⏻</span>
      <span class="logout-label">logout</span>
    </button>
  </form>
</footer>

<style>
  .statusbar {
    height: var(--status-h);
    background: var(--bg1);
    border-top: 1px solid var(--b1);
    display: flex;
    align-items: center;
    padding: 0 12px;
    gap: 16px;
    font-size: 10px;
    color: var(--t3);
    flex-shrink: 0;
  }

  .status-item {
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
  }

  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 0.4s ease;
  }

  /* Subtle breathing animation when service is healthy */
  .dot-pulse {
    animation: breathe 3s ease-in-out infinite;
  }

  @keyframes breathe {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.55; }
  }

  .health-val {
    font-size: 9px;
    color: var(--t3);
    opacity: 0.7;
  }

  .status-right {
    margin-left: auto;
    color: var(--t3);
  }

  .last-fetch {
    cursor: help;
    opacity: 0.5;
  }

  .logout-form {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .logout-btn {
    display: flex;
    align-items: center;
    gap: 3px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--r);
    color: var(--t3);
    font-family: inherit;
    font-size: 9px;
    padding: 1px 5px;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
    white-space: nowrap;
    line-height: 1;
    height: 16px;
  }

  .logout-btn:hover {
    color: var(--red);
    border-color: var(--red-brd);
    background: var(--red-dim);
  }

  .logout-label {
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
</style>
