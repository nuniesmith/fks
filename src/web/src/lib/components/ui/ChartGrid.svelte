<script lang="ts">
  import MiniChart from './MiniChart.svelte';

  let {
    symbols = ['MGC'],
    interval = '5m',
  } = $props<{
    symbols?: string[];
    interval?: string;
  }>();

  let gridClass = $derived(
    symbols.length <= 1 ? 'grid-1x1'
    : symbols.length === 2 ? 'grid-1x2'
    : 'grid-2x2'
  );
</script>

<div class="chart-grid {gridClass}">
  {#each symbols.slice(0, 4) as sym (sym)}
    <MiniChart symbol={sym} {interval} />
  {/each}
</div>

<style>
  .chart-grid {
    display: grid;
    gap: 2px;
    width: 100%;
    height: 100%;
    min-height: 0;
  }
  .grid-1x1 {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr;
  }
  .grid-1x2 {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr;
  }
  .grid-2x2 {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
  }
</style>
