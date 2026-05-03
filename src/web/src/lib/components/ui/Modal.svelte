<script lang="ts">
  import { onMount, tick } from 'svelte';

  let {
    open = false,
    title = '',
    onclose,
    children,
    actions,
  } = $props<{
    open: boolean;
    title?: string;
    onclose: () => void;
    children: any;
    actions?: any;
  }>();

  const titleId = 'modal-title-' + Math.random().toString(36).slice(2, 9);

  let cardEl = $state<HTMLDivElement | null>(null);
  let previouslyFocused: HTMLElement | null = null;

  function getFocusableElements(): HTMLElement[] {
    if (!cardEl) return [];
    return Array.from(
      cardEl.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  function trapFocus(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const focusable = getFocusableElements();
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) {
      onclose();
      return;
    }
    if (open) {
      trapFocus(e);
    }
  }

  function handleBackdrop() {
    onclose();
  }

  function handleCardClick(e: MouseEvent) {
    e.stopPropagation();
  }

  $effect(() => {
    if (open) {
      previouslyFocused = document.activeElement as HTMLElement | null;
      tick().then(() => {
        const focusable = getFocusableElements();
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          cardEl?.focus();
        }
      });
    } else {
      previouslyFocused?.focus();
      previouslyFocused = null;
    }
  });

  onMount(() => {
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  });
</script>

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="overlay" onclick={handleBackdrop} role="presentation">
    <div
      class="card"
      bind:this={cardEl}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      tabindex="-1"
      onclick={handleCardClick}
    >
      <div class="header">
        <span class="title" id={titleId}>{title}</span>
        <button class="close-btn" onclick={onclose} aria-label="Close dialog">×</button>
      </div>
      <div class="body">
        {@render children()}
      </div>
      {#if actions}
        <div class="footer">
          {@render actions()}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.6);
    animation: fade-in 150ms ease-out;
  }

  .card {
    background: var(--bg1);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    max-width: 520px;
    width: 90%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: slide-up 150ms ease-out;
  }

  .header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--b1);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: var(--t2);
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--t3);
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: var(--r);
    transition: color 120ms, background 120ms;
  }

  .close-btn:hover {
    color: var(--t1);
    background: var(--bg3);
  }

  .body {
    padding: 16px;
  }

  .footer {
    padding: 10px 16px;
    border-top: 1px solid var(--b1);
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  @keyframes slide-up {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @media (prefers-reduced-motion: reduce) {
    .overlay, .card {
      animation: none;
    }
  }
</style>
