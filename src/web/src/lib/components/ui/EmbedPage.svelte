<script lang="ts">
  import { onMount } from 'svelte';

  let {
    src,
    title,
    popOutHref,
    accent = 'var(--cyan)',
  } = $props<{
    /** URL to load inside the iframe. */
    src: string;
    /** Accessible title for the iframe element. */
    title: string;
    /** URL for the "Pop Out" link that opens the page in a new tab. */
    popOutHref: string;
    /**
     * CSS colour value for the pop-out button accent (border + text).
     * Defaults to `var(--cyan)`.  Pass `var(--green)`, `var(--purple)`, etc.
     * to match each workspace's theme.
     */
    accent?: string;
  }>();

  let iframeEl = $state<HTMLIFrameElement | null>(null);
  let loaded = $state(false);

  function handleLoad() {
    loaded = true;
    // Attempt to hide the embedded app's own top-bar (same-origin only).
    try {
      const doc = iframeEl?.contentDocument;
      if (doc) {
        const topbar =
          doc.querySelector<HTMLElement>('#topbar') ??
          doc.querySelector<HTMLElement>('nav.nav');
        if (topbar) topbar.style.display = 'none';
      }
    } catch {
      // Cross-origin frame — silently ignore.
    }
  }

  onMount(() => {
    return () => {
      iframeEl = null;
    };
  });
</script>

<div class="embed-pane">
  {#if !loaded}
    <div class="loading-overlay">
      <span class="loading-text">Loading…</span>
    </div>
  {/if}

  <a
    class="pop-out"
    href={popOutHref}
    target="_blank"
    rel="noopener noreferrer"
    style="--pop-accent: {accent}"
  >
    ⧉ Pop Out
  </a>

  <iframe
    bind:this={iframeEl}
    {src}
    {title}
    loading="lazy"
    onload={handleLoad}
  ></iframe>
</div>

<style>
  .embed-pane {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  /* ── Pop-out button ─────────────────────────────────────────────────── */
  .pop-out {
    position: absolute;
    top: 8px;
    right: 12px;
    z-index: 50;
    font-size: 10px;
    color: var(--pop-accent, var(--cyan));
    text-decoration: none;
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    padding: 2px 8px;
    opacity: 0.7;
    transition: opacity 0.15s ease, border-color 0.15s ease;
  }

  .pop-out:hover {
    opacity: 1;
    border-color: var(--pop-accent, var(--cyan));
  }

  /* ── iframe ─────────────────────────────────────────────────────────── */
  iframe {
    width: 100%;
    height: 100%;
    border: none;
    background: var(--bg1);
    display: block;
  }

  /* ── Loading overlay ────────────────────────────────────────────────── */
  .loading-overlay {
    position: absolute;
    inset: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg1);
  }

  .loading-text {
    font-size: 11px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    animation: pulse 1.8s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }
</style>
