<script lang="ts">
  let {
    label,
    value,
    unit,
    color = 'default',
    warn,
    crit,
  } = $props<{
    label: string;
    value: string | number;
    unit?: string;
    color?: 'green' | 'red' | 'amber' | 'cyan' | 'default';
    warn?: number;
    crit?: number;
  }>();

  let resolvedColor = $derived.by(() => {
    if (warn != null && crit != null && typeof value === 'number') {
      if (value >= crit) return 'red';
      if (value >= warn) return 'amber';
      return 'green';
    }
    return color;
  });
</script>

<div class="stat-card">
  <span class="stat-label">{label}</span>
  <span class="stat-value {resolvedColor}">
    {value}{#if unit}<span class="stat-unit">{unit}</span>{/if}
  </span>
</div>

<style>
  .stat-card {
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r-md);
    padding: 10px 14px;
    min-width: 100px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-label {
    font-size: 9px;
    font-weight: 600;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1;
  }

  .stat-value {
    font-size: 18px;
    font-weight: 700;
    line-height: 1.2;
  }

  .stat-unit {
    font-size: 10px;
    font-weight: 500;
    color: var(--t2);
    margin-left: 2px;
  }

  .default { color: var(--t1); }
  .green   { color: var(--green); }
  .red     { color: var(--red); }
  .amber   { color: var(--amber); }
  .cyan    { color: var(--cyan); }
</style>
