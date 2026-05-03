<script lang="ts">
  import { enhance } from '$app/forms';
  import { page } from '$app/stores';

  interface Props {
    form?: { error?: string } | null;
  }

  let { form }: Props = $props();

  let loading = $state(false);
  let password = $state('');

  // Preserve the ?next= redirect target through the form submission
  let next = $derived($page.url.searchParams.get('next') ?? '');
</script>

<svelte:head>
  <title>FKS Terminal — Login</title>
</svelte:head>

<div class="gate">
  <div class="panel">

    <!-- ASCII terminal icon -->
    <pre class="ascii" aria-hidden="true">
╔══════════════╗
║  &gt; FKS_     ║
║  $ terminal  ║
╚══════════════╝</pre>

    <h1 class="title">
      <span class="bracket">[</span>
      FKS Terminal
      <span class="bracket">]</span>
    </h1>
    <p class="subtitle">Restricted access. Authenticate to continue.</p>

    <form
      method="POST"
      action="?/login"
      use:enhance={() => {
        loading = true;
        return async ({ update }) => {
          loading = false;
          await update();
        };
      }}
    >
      {#if next}
        <input type="hidden" name="next" value={next} />
      {/if}

      <label class="field-label" for="password">Password</label>
      <div class="input-row" class:input-row-error={!!form?.error}>
        <span class="prompt" aria-hidden="true">$</span>
        <input
          id="password"
          name="password"
          type="password"
          class="input"
          placeholder="enter passphrase…"
          autocomplete="current-password"
          bind:value={password}
          disabled={loading}
        />
      </div>

      {#if form?.error}
        <p class="error-msg" role="alert">
          <span class="error-icon" aria-hidden="true">✗</span>
          {form.error}
        </p>
      {/if}

      <button
        type="submit"
        class="btn"
        class:btn-loading={loading}
        disabled={loading || password.length === 0}
      >
        {#if loading}
          <span class="spinner" aria-hidden="true"></span>
          Authenticating…
        {:else}
          <span class="btn-arrow" aria-hidden="true">→</span>
          Enter Terminal
        {/if}
      </button>
    </form>

    <p class="footer-note">
      <span class="dot dot-amber"></span>
      Access is logged. Authorised users only.
    </p>
  </div>
</div>

<style>
  /* ── Layout ──────────────────────────────────────────── */
  .gate {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--bg0);
    background-image:
      linear-gradient(rgba(91, 110, 245, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(91, 110, 245, 0.03) 1px, transparent 1px);
    background-size: 32px 32px;
  }

  .panel {
    width: 360px;
    padding: 32px 28px 24px;
    background: var(--bg1);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    box-shadow:
      0 0 0 1px rgba(91, 110, 245, 0.08),
      0 8px 40px rgba(0, 0, 0, 0.6),
      0 0 80px rgba(91, 110, 245, 0.06);
    display: flex;
    flex-direction: column;
    gap: 16px;
    animation: fade-in 0.25s ease both;
  }

  /* ── ASCII art ───────────────────────────────────────── */
  .ascii {
    font-family: inherit;
    font-size: 10px;
    line-height: 1.4;
    color: var(--accent);
    opacity: 0.55;
    text-align: center;
    white-space: pre;
    user-select: none;
    margin: 0;
  }

  /* ── Title ───────────────────────────────────────────── */
  .title {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--t1);
    text-align: center;
    line-height: 1;
    margin: 0;
  }

  .bracket {
    color: var(--accent);
    opacity: 0.7;
  }

  .subtitle {
    font-size: 10px;
    color: var(--t3);
    text-align: center;
    letter-spacing: 0.03em;
  }

  /* ── Form ────────────────────────────────────────────── */
  form {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 4px;
  }

  .field-label {
    font-size: 10px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .input-row {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    padding: 0 10px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  .input-row:focus-within {
    border-color: var(--accent-brd);
    box-shadow: 0 0 0 2px var(--accent-dim);
  }

  .input-row-error {
    border-color: var(--red-brd) !important;
    box-shadow: 0 0 0 2px var(--red-dim) !important;
  }

  .prompt {
    color: var(--cyan);
    font-size: 12px;
    flex-shrink: 0;
    user-select: none;
  }

  .input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--t1);
    font-family: inherit;
    font-size: 12px;
    height: 36px;
    caret-color: var(--cyan);
  }

  .input::placeholder {
    color: var(--t3);
    opacity: 0.6;
  }

  .input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Error message ───────────────────────────────────── */
  .error-msg {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: var(--red);
    background: var(--red-dim);
    border: 1px solid var(--red-brd);
    border-radius: var(--r);
    padding: 6px 10px;
    animation: fade-in 0.15s ease both;
  }

  .error-icon {
    font-size: 12px;
    flex-shrink: 0;
  }

  /* ── Submit button ───────────────────────────────────── */
  .btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    height: 36px;
    margin-top: 4px;
    background: var(--accent-dim);
    border: 1px solid var(--accent-brd);
    border-radius: var(--r);
    color: var(--accent);
    font-family: inherit;
    font-size: 12px;
    letter-spacing: 0.03em;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }

  .btn:hover:not(:disabled) {
    background: rgba(91, 110, 245, 0.2);
    border-color: var(--accent);
    color: var(--t1);
  }

  .btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-loading {
    opacity: 0.7;
  }

  .btn-arrow {
    font-size: 13px;
  }

  /* ── Spinner ─────────────────────────────────────────── */
  .spinner {
    display: inline-block;
    width: 11px;
    height: 11px;
    border: 1.5px solid var(--accent-brd);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  /* ── Footer note ─────────────────────────────────────── */
  .footer-note {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    font-size: 9px;
    color: var(--t3);
    opacity: 0.6;
    text-align: center;
    margin-top: 4px;
  }

  .dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .dot-amber {
    background: var(--amber);
    opacity: 0.7;
  }
</style>
