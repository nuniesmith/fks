<script lang="ts">
    /**
     * Reusable filter-chip group — radiogroup of pill-shaped buttons.
     *
     * Props match the contract callers (e.g. signals/+page.svelte) actually
     * use: `chips` (with `{id, label}` shape), `active` (the currently
     * selected id), and `onselect(id)` callback.
     */
    interface ChipOption {
        value: string;
        label: string;
    }

    let { options, active, onchange } = $props<{
        options: ChipOption[];
        active: string;
        onchange: (value: string) => void;
    }>();
</script>

<div class="chips" role="radiogroup" aria-label="Filter options">
    {#each options as opt (opt.value)}
        <button
            type="button"
            class="chip"
            class:active={active === opt.value}
            role="radio"
            aria-checked={active === opt.value}
            onclick={() => onchange(opt.value)}
        >
            {opt.label}
        </button>
    {/each}
</div>

<style>
    .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        align-items: center;
    }

    .chip {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 10px;
        font-weight: 600;
        font-family: inherit;
        letter-spacing: 0.03em;
        cursor: pointer;
        white-space: nowrap;
        user-select: none;
        background: transparent;
        color: var(--t3);
        border: 1px solid var(--b1);
        transition:
            background 0.15s,
            color 0.15s,
            border-color 0.15s;
    }

    .chip:hover:not(.active) {
        background: var(--bg3);
        color: var(--t2);
    }

    .chip.active {
        background: var(--accent-dim);
        color: var(--accent);
        border-color: var(--accent-brd);
    }
</style>
