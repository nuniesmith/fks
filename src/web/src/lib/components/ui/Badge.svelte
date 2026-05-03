<script lang="ts">
  let { variant = 'default', children } = $props<{
    variant?: 'default' | 'green' | 'red' | 'amber' | 'cyan' | 'purple';
    children: any;
  }>();
</script>

<span class="badge {variant}" role="status">
  {@render children()}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 1px 6px;
    border-radius: var(--r);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .default { background: var(--bg3); color: var(--t2); }
  .green { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-brd); }
  .red { background: var(--red-dim); color: var(--red); border: 1px solid var(--red-brd); }
  .amber { background: var(--amber-dim); color: var(--amber); border: 1px solid var(--amber-brd); }
  .cyan { background: var(--cyan-dim); color: var(--cyan); border: 1px solid var(--cyan-brd); }
  .purple { background: var(--purple-dim); color: var(--purple); border: 1px solid var(--purple-brd); }
</style>
