<script lang="ts">
  let { tabs, active, onchange } = $props<{
    tabs: { id: string; label: string }[];
    active: string;
    onchange: (id: string) => void;
  }>();
</script>

<div class="tabs" role="tablist">
  {#each tabs as tab (tab.id)}
    <button
      class="tab"
      class:active={tab.id === active}
      role="tab"
      aria-selected={tab.id === active}
      tabindex={tab.id === active ? 0 : -1}
      onclick={() => onchange(tab.id)}
    >
      {tab.label}
    </button>
  {/each}
</div>

<style>
  .tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--b1);
    margin-bottom: 8px;
  }

  .tab {
    all: unset;
    padding: 4px 10px;
    font-size: 10px;
    font-family: inherit;
    cursor: pointer;
    color: var(--t3);
    border-bottom: 2px solid transparent;
    transition: color 0.15s ease, border-color 0.15s ease;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--t2);
  }

  .tab.active {
    color: var(--t1);
    border-bottom-color: var(--accent);
  }
</style>
