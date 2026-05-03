<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    title,
    children,
    header,
    noPad = false,
    badge,
    fill = false,
  } = $props<{
    title?: string;
    children: Snippet;
    header?: Snippet;
    noPad?: boolean;
    badge?: string;
    fill?: boolean;
  }>();
</script>

<div class="panel" class:fill>
  {#if title || header}
    <div class="panel-head">
      {#if title}
        <span class="panel-title">{title}</span>
      {/if}
      {#if badge}
        <span class="poll-badge">{badge}</span>
      {/if}
      {#if header}
        <div class="panel-head-extra">
          {@render header()}
        </div>
      {/if}
    </div>
  {/if}
  <div class="panel-body" class:no-pad={noPad}>
    {@render children()}
  </div>
</div>

<style>
  .panel {
    background: var(--bg1);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .panel.fill {
    flex: 1;
  }
  .panel-head {
    padding: 6px 10px;
    background: var(--bg2);
    border-bottom: 1px solid var(--b1);
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .panel-title {
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .panel-head-extra {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .poll-badge {
    font-size: 8px;
    color: var(--t3);
    background: var(--bg3);
    padding: 1px 5px;
    border-radius: var(--r);
    margin-left: auto;
  }
  .panel-body {
    padding: 8px;
    flex: 1;
    overflow: auto;
    min-height: 0;
  }
  .panel-body.no-pad {
    padding: 0;
  }
</style>
