<script lang="ts">
  import ChartGrid from '$components/ui/ChartGrid.svelte';

  const layouts = [
    { id: '1', label: '1×1', count: 1 },
    { id: '2', label: '1×2', count: 2 },
    { id: '4', label: '2×2', count: 4 },
  ];

  let activeLayout = $state('4');
  let interval = $state('5m');

  const timeframes = [
    { id: '1m', label: '1m' },
    { id: '5m', label: '5m' },
    { id: '15m', label: '15m' },
    { id: '1h', label: '1H' },
    { id: '4h', label: '4H' },
    { id: '1D', label: '1D' },
  ];

  const defaultSymbols = ['MGC', 'MES', 'MNQ', 'BTC/USD'];

  // Editable symbol slots
  let symbols = $state([...defaultSymbols]);
  let editIdx = $state<number | null>(null);
  let editVal = $state('');
  let editInputEl: HTMLInputElement | null = $state(null);

  $effect(() => {
    if (editIdx !== null && editInputEl) {
      editInputEl.focus();
    }
  });

  let layoutCount = $derived(layouts.find(l => l.id === activeLayout)?.count ?? 4);
  let visibleSymbols = $derived(symbols.slice(0, layoutCount));

  let editStartTime = 0;

  function startEdit(idx: number) {
    editIdx = idx;
    editVal = symbols[idx];
    editStartTime = Date.now();
  }

  function commitEdit() {
    // Guard: ignore blur events that fire within 100ms of starting edit
    // (caused by DOM swap between button and input)
    if (Date.now() - editStartTime < 100) return;

    if (editIdx !== null && editVal.trim()) {
      symbols[editIdx] = editVal.trim().toUpperCase();
      symbols = [...symbols]; // trigger reactivity
    }
    editIdx = null;
    editVal = '';
  }

  function cancelEdit() {
    editIdx = null;
    editVal = '';
  }
</script>

<div class="page">
  <div class="grid-toolbar">
    <span class="toolbar-label">MULTI-CHART</span>

    <!-- Layout selector -->
    <div class="layout-btns" role="radiogroup" aria-label="Chart grid layout">
      {#each layouts as l}
        <button
          class="layout-btn"
          class:active={activeLayout === l.id}
          onclick={() => { activeLayout = l.id; }}
          role="radio"
          aria-checked={activeLayout === l.id ? 'true' : 'false'}
          aria-label="{l.label} layout"
        >
          {l.label}
        </button>
      {/each}
    </div>

    <!-- Timeframe -->
    <div class="tf-tabs" role="radiogroup" aria-label="Timeframe">
      {#each timeframes as tf}
        <button
          class="tf-tab"
          class:active={interval === tf.id}
          onclick={() => { interval = tf.id; }}
          role="radio"
          aria-checked={interval === tf.id ? 'true' : 'false'}
        >
          {tf.label}
        </button>
      {/each}
    </div>

    <!-- Symbol slots -->
    <div class="symbol-slots">
      {#each visibleSymbols as sym, i}
        {#if editIdx === i}
          <input
            class="slot-input"
            bind:value={editVal}
            bind:this={editInputEl}
            onkeydown={(e) => {
              if (e.key === 'Enter') commitEdit();
              if (e.key === 'Escape') cancelEdit();
            }}
            onblur={commitEdit}
            aria-label="Edit symbol {i + 1}"
          />
        {:else}
          <button
            class="slot-btn"
            onclick={() => startEdit(i)}
            title="Click to change symbol"
            aria-label="Symbol slot {i + 1}: {sym}"
          >
            {sym}
          </button>
        {/if}
      {/each}
    </div>
  </div>

  <div class="grid-area">
    <ChartGrid symbols={visibleSymbols} {interval} />
  </div>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .grid-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 12px;
    background: var(--bg1);
    border-bottom: 1px solid var(--b2);
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .toolbar-label {
    font-size: 10px;
    font-weight: 700;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .layout-btns {
    display: flex;
    gap: 2px;
  }
  .layout-btn {
    all: unset;
    padding: 3px 10px;
    font-size: 10px;
    color: var(--t3);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }
  .layout-btn:hover { color: var(--t2); background: var(--bg3); }
  .layout-btn.active {
    color: var(--t1);
    background: var(--accent-dim, rgba(99, 102, 241, 0.15));
    border-color: var(--accent, #6366f1);
  }

  .tf-tabs {
    display: flex;
    gap: 2px;
  }
  .tf-tab {
    all: unset;
    padding: 2px 7px;
    font-size: 10px;
    color: var(--t3);
    border-radius: var(--r);
    cursor: pointer;
    font-family: inherit;
    transition: color 0.15s, background 0.15s;
  }
  .tf-tab:hover { color: var(--t2); background: var(--bg3); }
  .tf-tab.active { color: var(--t1); background: var(--accent-dim, rgba(99, 102, 241, 0.15)); }

  .symbol-slots {
    display: flex;
    gap: 4px;
    margin-left: auto;
  }
  .slot-btn {
    all: unset;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
    color: var(--accent);
    background: var(--bg2);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }
  .slot-btn:hover { background: var(--bg3); border-color: var(--accent); }
  .slot-input {
    width: 70px;
    padding: 3px 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--t1);
    background: var(--bg2);
    border: 1px solid var(--accent);
    border-radius: var(--r);
    font-family: inherit;
    outline: none;
    text-transform: uppercase;
  }

  .grid-area {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    padding: 2px;
  }
</style>
