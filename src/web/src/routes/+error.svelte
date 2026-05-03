<script lang="ts">
  import { page } from '$app/stores';
</script>

<svelte:head>
  <title>Error {$page.status} — FKS Terminal</title>
</svelte:head>

<div class="error-page" role="main">
  <div class="error-panel">
    <div class="error-header">
      <span class="error-tag">ERR</span>
      <span class="error-code">{$page.status}</span>
    </div>

    <div class="error-body">
      <p class="error-message">{$page.error?.message ?? 'An unexpected error occurred.'}</p>

      {#if $page.status === 404}
        <p class="error-detail muted">The requested route does not exist in this terminal.</p>
      {:else if $page.status === 403}
        <p class="error-detail muted">Access denied — check your Tailscale connection.</p>
      {:else if $page.status >= 500}
        <p class="error-detail muted">A server-side error occurred. Check the service logs.</p>
      {/if}

      <div class="error-trace">
        <span class="trace-label">PATH</span>
        <span class="trace-value">{$page.url?.pathname ?? '—'}</span>
      </div>
    </div>

    <div class="error-footer">
      <a href="/" class="btn-home">← Return to Terminal</a>
    </div>
  </div>
</div>

<style>
  .error-page {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    background: var(--bg0);
    padding: 24px;
    box-sizing: border-box;
  }

  .error-panel {
    width: 100%;
    max-width: 480px;
    background: var(--bg1);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    overflow: hidden;
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
  }

  .error-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    background: var(--bg2);
    border-bottom: 1px solid var(--b2);
  }

  .error-tag {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--red);
    background: color-mix(in srgb, var(--red) 15%, transparent);
    border: 1px solid color-mix(in srgb, var(--red) 40%, transparent);
    border-radius: 2px;
    padding: 1px 5px;
  }

  .error-code {
    font-size: 20px;
    font-weight: 700;
    color: var(--red);
    line-height: 1;
  }

  .error-body {
    padding: 16px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .error-message {
    font-size: 13px;
    color: var(--t1);
    margin: 0;
    line-height: 1.5;
  }

  .error-detail {
    font-size: 11px;
    color: var(--t3);
    margin: 0;
    line-height: 1.5;
  }

  .error-trace {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
    padding: 6px 10px;
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
  }

  .trace-label {
    font-size: 8px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--t3);
    flex-shrink: 0;
  }

  .trace-value {
    font-size: 11px;
    color: var(--t2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .error-footer {
    padding: 10px 14px;
    border-top: 1px solid var(--b1);
    background: var(--bg2);
  }

  .btn-home {
    display: inline-block;
    font-size: 11px;
    color: var(--accent);
    text-decoration: none;
    padding: 4px 10px;
    border: 1px solid var(--accent);
    border-radius: var(--r);
    transition: background 0.15s ease, color 0.15s ease;
  }

  .btn-home:hover {
    background: var(--accent);
    color: var(--bg0);
  }

  .muted {
    color: var(--t3);
  }
</style>
