<script lang="ts">
  import { createSSE } from '$stores/sse';
  import { focusSymbol } from '$stores/focusSymbol';
  import { onMount } from 'svelte';
  import type { StripData } from '$lib/types';
  import { fmtPrice, fmtPct } from '$lib/utils/format';

  const sse = createSSE<StripData>('/sse/strip');

  let data = $derived($sse);

  $effect(() => {
    const sym = data?.focus?.symbol;
    if (sym) {
      focusSymbol.set(sym);
    }
  });

  // ─── Live clock ─────────────────────────────────────────────────────
  let clock = $state('');

  function updateClock() {
    clock = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      timeZoneName: 'short',
    });
  }

  onMount(() => {
    sse.connect();
    updateClock();
    const clockInterval = setInterval(updateClock, 1_000);

    return () => {
      sse.disconnect();
      clearInterval(clockInterval);
    };
  });
</script>

<header class="strip" aria-label="Trading status strip">
  <div class="strip-cell" aria-label="Focus symbol">
    <span class="lbl">FOCUS</span>
    <a href="/trading" class="val accent focus-link">{data?.focus?.symbol ?? '—'}</a>
    <span class="val">{fmtPrice(data?.focus?.price)}</span>
    <span
      class="val"
      class:green={data?.focus?.change_pct != null && data.focus.change_pct >= 0}
      class:red={data?.focus?.change_pct != null && data.focus.change_pct < 0}
    >
      {fmtPct(data?.focus?.change_pct)}
    </span>
  </div>

  <div class="strip-cell" aria-label="Profit and loss">
    <span class="lbl">P&L</span>
    <span
      class="val"
      class:green={(data?.pnl?.daily ?? 0) >= 0}
      class:red={(data?.pnl?.daily ?? 0) < 0}
    >
      ${data?.pnl?.daily?.toFixed(2) ?? '—'}
    </span>
  </div>

  <div class="strip-cell" aria-label="Risk drawdown">
    <span class="lbl">RISK</span>
    <span
      class="val"
      class:amber={(data?.risk?.dd_pct ?? 0) > 2}
      class:red={(data?.risk?.dd_pct ?? 0) > 5}
    >
      DD {data?.risk?.dd_pct?.toFixed(1) ?? '—'}%
    </span>
  </div>

  <div class="strip-cell" aria-label="Market regime">
    <span class="lbl">REGIME</span>
    <span class="val muted">{data?.regime?.label ?? '—'}</span>
  </div>

  <div class="strip-cell clock" aria-label="Clock" aria-live="off">
    <span class="val muted" id="fks-clock">{clock}</span>
  </div>
</header>

<style>
  .strip {
    height: var(--strip-h);
    background: var(--bg1);
    border-bottom: 1px solid var(--b1);
    display: flex;
    align-items: center;
    padding: 0 12px;
    gap: 2px;
    overflow: hidden;
    flex-shrink: 0;
  }
  .strip-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 12px;
    border-right: 1px solid var(--b1);
    height: 100%;
    white-space: nowrap;
  }
  .strip-cell:last-child { border-right: none; margin-left: auto; }
  .lbl {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .val {
    font-size: 13px;
    font-weight: 600;
  }
  .clock { margin-left: auto; }
  .focus-link {
    color: var(--accent);
    text-decoration: none;
    cursor: pointer;
  }
  .focus-link:hover { text-decoration: underline; }
</style>
