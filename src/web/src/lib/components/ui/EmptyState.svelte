<!--
  EmptyState — a consistent placeholder for empty / no-data / error panels.

  Replaces the ad-hoc one-off "no data" markup scattered across routes with a
  single themed primitive. Use inside a Panel body, a table area, or an
  absolutely-positioned chart overlay (wrap in a positioned container for the
  latter).

  Usage:
    <EmptyState icon="∅" title="No data" hint="Nothing to show yet." />
    <EmptyState icon="⚠️" title="Failed to load" variant="error" hint={msg} />
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  interface Props {
    /** Optional emoji / glyph shown above the title. */
    icon?: string;
    /** Primary line (required). */
    title: string;
    /** Optional secondary explanatory line. */
    hint?: string;
    /** 'error' tints the title red; 'default' is neutral. */
    variant?: 'default' | 'error';
    /** Optional call-to-action (e.g. a button) rendered below the hint. */
    action?: Snippet;
  }
  let { icon, title, hint, variant = 'default', action }: Props = $props();
</script>

<div class="empty-state" class:error={variant === 'error'} role="status">
  {#if icon}<span class="es-icon" aria-hidden="true">{icon}</span>{/if}
  <span class="es-title">{title}</span>
  {#if hint}<span class="es-hint">{hint}</span>{/if}
  {#if action}<div class="es-action">{@render action()}</div>{/if}
</div>

<style>
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 24px 16px;
    text-align: center;
  }
  .es-icon {
    font-size: 22px;
    line-height: 1;
    opacity: 0.7;
  }
  .es-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--t2);
  }
  .empty-state.error .es-title {
    color: var(--red, #ea3943);
  }
  .es-hint {
    font-size: 11px;
    color: var(--t3);
    max-width: 320px;
    line-height: 1.5;
  }
  .es-action {
    margin-top: 8px;
  }
</style>
