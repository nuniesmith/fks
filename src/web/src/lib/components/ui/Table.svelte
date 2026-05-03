<script lang="ts">
  import type { Snippet } from 'svelte';

  type Column = {
    key: string;
    label: string;
    align?: 'left' | 'center' | 'right';
    format?: (value: any, row: any) => string;
  };

  let {
    columns,
    rows,
    sortable = true,
    onRowClick,
    empty,
  } = $props<{
    columns: Column[];
    rows: Record<string, any>[];
    sortable?: boolean;
    onRowClick?: (row: Record<string, any>, index: number) => void;
    empty?: Snippet;
  }>();

  let sortKey = $state<string | null>(null);
  let sortDir = $state<'asc' | 'desc'>('asc');

  function handleSort(key: string) {
    if (!sortable) return;
    if (sortKey === key) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey = key;
      sortDir = 'asc';
    }
  }

  let sortedRows = $derived.by(() => {
    if (!sortKey) return rows;
    const key = sortKey;
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = a[key];
      const vb = b[key];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  });

  function cellValue(col: Column, row: Record<string, any>): string {
    const raw = row[col.key];
    if (col.format) return col.format(raw, row);
    return raw == null ? '—' : String(raw);
  }

  function handleRowKey(
    e: KeyboardEvent,
    row: Record<string, any>,
    index: number,
  ) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onRowClick?.(row, index);
    }
  }
</script>

<div class="table-wrap">
  {#if rows.length === 0 && empty}
    <div class="empty" role="status">
      {@render empty()}
    </div>
  {:else}
    <table>
      <thead>
        <tr>
          {#each columns as col}
            <th
              scope="col"
              class:sortable
              class:active={sortKey === col.key}
              style:text-align={col.align ?? 'left'}
              aria-sort={sortable
                ? sortKey === col.key
                  ? sortDir === 'asc'
                    ? 'ascending'
                    : 'descending'
                  : 'none'
                : undefined}
            >
              {#if sortable}
                <!--
                  Using role="columnheader" on <th> and a plain <button> inside
                  for the interactive sort target — avoids the invalid dual-role
                  "columnheader button" pattern while keeping full keyboard access.
                -->
                <button
                  class="sort-btn"
                  onclick={() => handleSort(col.key)}
                  onkeydown={(e: KeyboardEvent) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSort(col.key);
                    }
                  }}
                  aria-label="{col.label} — click to sort {sortKey === col.key
                    ? sortDir === 'asc'
                      ? 'descending'
                      : 'ascending'
                    : 'ascending'}"
                >
                  <span class="th-label">{col.label}</span>
                  {#if sortKey === col.key}
                    <span class="sort-arrow" aria-hidden="true">
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  {:else}
                    <span class="sort-arrow sort-arrow-idle" aria-hidden="true">⇅</span>
                  {/if}
                </button>
              {:else}
                <span class="th-label">{col.label}</span>
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each sortedRows as row, i}
          <tr
            class:clickable={!!onRowClick}
            onclick={() => onRowClick?.(row, i)}
            tabindex={onRowClick ? 0 : undefined}
            role={onRowClick ? 'button' : undefined}
            onkeydown={onRowClick ? (e: KeyboardEvent) => handleRowKey(e, row, i) : undefined}
          >
            {#each columns as col}
              <td style:text-align={col.align ?? 'left'}>
                {cellValue(col, row)}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .table-wrap {
    width: 100%;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    color: var(--t1);
  }

  thead tr {
    border-bottom: 1px solid var(--b2);
  }

  th {
    padding: 0;
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--t3);
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
    user-select: none;
  }

  th.active {
    color: var(--t2);
  }

  /* ── Sort button inside <th> ───────────────────────────────────────── */
  .sort-btn {
    /* Reset browser button styles so the cell looks identical to the
       non-sortable version, while still being keyboard-focusable. */
    all: unset;
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
    padding: 6px 10px;
    cursor: pointer;
    box-sizing: border-box;
    color: inherit;
    font: inherit;
    letter-spacing: inherit;
    text-transform: inherit;
    border-radius: 2px;
  }

  .sort-btn:hover {
    color: var(--t2);
  }

  .sort-btn:focus-visible {
    outline: 1px solid var(--accent);
    outline-offset: -1px;
  }

  th:not(.sortable) .th-label {
    display: inline-block;
    padding: 6px 10px;
  }

  .th-label {
    vertical-align: middle;
  }

  .sort-arrow {
    display: inline-block;
    font-size: 7px;
    vertical-align: middle;
    color: var(--accent);
    flex-shrink: 0;
  }

  .sort-arrow-idle {
    color: var(--t3);
    opacity: 0.5;
  }

  /* ── Body rows ─────────────────────────────────────────────────────── */
  tbody tr {
    border-bottom: 1px solid var(--b1);
    transition: background 0.1s ease;
  }

  tbody tr:hover {
    background: var(--bg3);
  }

  tbody tr.clickable {
    cursor: pointer;
  }

  tbody tr.clickable:focus-visible {
    outline: 1px solid var(--accent);
    outline-offset: -1px;
  }

  td {
    padding: 5px 10px;
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
  }

  .empty {
    padding: 24px 16px;
    text-align: center;
    font-size: 11px;
    color: var(--t3);
  }
</style>
