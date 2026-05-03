<script lang="ts">
  let {
    value = 0,
    color = 'cyan',
    height = '6px',
    label = undefined,
  } = $props<{
    value: number;
    color?: 'green' | 'red' | 'amber' | 'cyan' | 'purple' | 'blue';
    height?: string;
    label?: string;
  }>();

  let clamped = $derived(Math.max(0, Math.min(100, value)));
</script>

<div class="progress-wrap">
  <div
    class="progress-track"
    style:height={height}
    role="progressbar"
    aria-valuenow={clamped}
    aria-valuemin={0}
    aria-valuemax={100}
    aria-label={label ?? 'Progress'}
  >
    <div
      class="progress-fill {color}"
      style:width="{clamped}%"
    ></div>
  </div>
  {#if label}
    <span class="progress-label">{label}</span>
  {/if}
</div>

<style>
  .progress-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }

  .progress-track {
    flex: 1;
    min-width: 0;
    background: var(--bg0);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    border-radius: var(--r);
    transition: width 0.3s ease;
  }

  .progress-fill.green  { background: var(--green); }
  .progress-fill.red    { background: var(--red); }
  .progress-fill.amber  { background: var(--amber); }
  .progress-fill.cyan   { background: var(--cyan); }
  .progress-fill.purple { background: var(--purple); }
  .progress-fill.blue   { background: var(--blue); }

  .progress-label {
    font-size: 10px;
    color: var(--t2);
    white-space: nowrap;
    flex-shrink: 0;
  }
</style>
