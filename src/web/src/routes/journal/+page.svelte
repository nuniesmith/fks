<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import Panel from '$components/ui/Panel.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';

  // ─── Types ──────────────────────────────────────────────────────────
  interface Trade {
    id: number;
    created_at: string;
    asset: string;
    direction: string;
    entry: number;
    sl: number | null;
    tp: number | null;
    contracts: number;
    status: string;
    close_price: number | null;
    close_time: string | null;
    pnl: number | null;
    rr: number | null;
    notes: string;
    strategy: string;
    grade: string | null;
    source: string | null;
  }

  interface TradesResponse {
    trades: Trade[];
    count: number;
  }

  interface JournalStats {
    total_days: number;
    win_days: number;
    loss_days: number;
    win_rate: number;
    total_net: number;
    avg_daily_net: number;
    best_day: number;
    worst_day: number;
    current_streak: number;
    expectancy: number;
    profit_factor: number;
    sharpe_ratio: number;
    max_drawdown: number;
    avg_win: number;
    avg_loss: number;
  }

  interface NotesResponse {
    notes: string;
    date: string;
  }

  // ─── State ──────────────────────────────────────────────────────────

  // Trade log
  let selectedTradeId = $state<number | null>(null);

  // Daily notes
  let noteDate = $state(todayStr());
  let noteText = $state('');
  let noteStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
  let noteStatusTimer: ReturnType<typeof setTimeout> | null = null;
  let notesLoading = $state(false);
  let blurSaveTimer: ReturnType<typeof setTimeout> | null = null;

  // ─── Polling Stores ─────────────────────────────────────────────────
  const tradesStore = createPoll<TradesResponse>(
    '/api/journal/trades?limit=25',
    60_000,
  );
  let tradesRaw = $derived($tradesStore);
  let trades = $derived(tradesRaw?.trades ?? []);
  let tradeCount = $derived(tradesRaw?.count ?? 0);

  const statsStore = createPoll<JournalStats>(
    '/api/journal/stats',
    60_000,
  );
  let stats = $derived($statsStore);

  // ─── Derived: Summary Footer ────────────────────────────────────────
  let totalPnl = $derived.by(() => {
    return trades.reduce((sum, t) => sum + (t.pnl ?? 0), 0);
  });

  let winCount = $derived.by(() => {
    return trades.filter(t => (t.pnl ?? 0) > 0).length;
  });

  let closedCount = $derived.by(() => {
    return trades.filter(t => t.pnl != null).length;
  });

  let winRate = $derived.by(() => {
    if (closedCount === 0) return 0;
    return (winCount / closedCount) * 100;
  });

  // ─── Helpers ────────────────────────────────────────────────────────
  function todayStr(): string {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function fmtDate(ts: string | null | undefined): string {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return ts;
    }
  }

  function fmtPrice(n: number | null | undefined): string {
    if (n == null) return '—';
    const abs = Math.abs(n);
    const digits = abs < 1 ? 6 : abs < 100 ? 4 : 2;
    return n.toLocaleString('en-US', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function fmtPnl(n: number | null | undefined): string {
    if (n == null) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}$${n.toFixed(2)}`;
  }

  function fmtDollar(n: number | null | undefined): string {
    if (n == null) return '—';
    const sign = n >= 0 ? '+' : '';
    return `${sign}$${n.toFixed(2)}`;
  }

  function fmtPct(n: number | null | undefined): string {
    if (n == null) return '—';
    return n.toFixed(1) + '%';
  }

  function fmtRatio(n: number | null | undefined): string {
    if (n == null) return '—';
    return n.toFixed(2);
  }

  function fmtRR(n: number | null | undefined): string {
    if (n == null) return '—';
    return n.toFixed(2) + 'R';
  }

  function fmtStreak(n: number | null | undefined): string {
    if (n == null) return '—';
    if (n > 0) return `${n}W`;
    if (n < 0) return `${Math.abs(n)}L`;
    return '0';
  }

  function pnlColor(n: number | null | undefined): 'green' | 'red' | 'default' {
    if (n == null) return 'default';
    if (n > 0) return 'green';
    if (n < 0) return 'red';
    return 'default';
  }

  function sideVariant(dir: string | null | undefined): 'green' | 'red' | 'default' {
    if (!dir) return 'default';
    const d = dir.toUpperCase();
    if (['BUY', 'LONG'].includes(d)) return 'green';
    if (['SELL', 'SHORT'].includes(d)) return 'red';
    return 'default';
  }

  function sideLabel(dir: string | null | undefined): string {
    if (!dir) return '—';
    return dir.toUpperCase();
  }

  function selectTrade(id: number) {
    selectedTradeId = selectedTradeId === id ? null : id;
  }

  // ─── Notes ──────────────────────────────────────────────────────────
  async function loadNotes(date: string) {
    notesLoading = true;
    noteStatus = 'idle';
    try {
      const res = await api.get<NotesResponse>(
        `/api/journal/notes?date=${encodeURIComponent(date)}`,
      );
      noteText = res.notes ?? '';
    } catch {
      noteText = '';
    } finally {
      notesLoading = false;
    }
  }

  async function saveNotes() {
    if (noteStatus === 'saving') return;
    noteStatus = 'saving';
    if (noteStatusTimer) clearTimeout(noteStatusTimer);

    try {
      await api.post<{ status: string }>('/api/journal/notes', {
        date: noteDate,
        notes: noteText,
      });
      noteStatus = 'saved';
      noteStatusTimer = setTimeout(() => {
        noteStatus = 'idle';
      }, 3000);
    } catch {
      noteStatus = 'error';
      noteStatusTimer = setTimeout(() => {
        noteStatus = 'idle';
      }, 5000);
    }
  }

  function handleNotesBlur() {
    if (blurSaveTimer) clearTimeout(blurSaveTimer);
    blurSaveTimer = setTimeout(() => {
      saveNotes();
    }, 300);
  }

  function handleNotesInput() {
    if (noteStatus === 'saved' || noteStatus === 'idle') {
      noteStatus = 'idle';
    }
  }

  function handleDateChange(e: Event) {
    const target = e.target as HTMLInputElement;
    noteDate = target.value;
    loadNotes(noteDate);
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  onMount(() => {
    tradesStore.start();
    statsStore.start();
    loadNotes(noteDate);
  });

  onDestroy(() => {
    tradesStore.stop();
    statsStore.stop();
    if (noteStatusTimer) clearTimeout(noteStatusTimer);
    if (blurSaveTimer) clearTimeout(blurSaveTimer);
  });
</script>

<svelte:head>
  <title>Journal — FKS Terminal</title>
</svelte:head>

<div class="page">
  <!-- ═══════════════════════════════════════════════════════════════════
       LEFT PANE (60%) — Trade Log Table
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-left">

    <Panel title="Trade Log" badge="60s" noPad fill>
      {#snippet header()}
        <Badge variant="default">{tradeCount} trades</Badge>
      {/snippet}
      <div class="trade-inner">
        <div class="trade-scroll">
          {#if !tradesRaw}
            <div style="padding:16px;">
              <Skeleton lines={10} height="18px" />
            </div>
          {:else if trades.length === 0}
            <div class="empty-state">No trades recorded yet.</div>
          {:else}
            <div class="table-scroll">
            <table class="tbl">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>P&L</th>
                  <th>R:R</th>
                  <th>Grade</th>
                  <th>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {#each trades as trade (trade.id)}
                  <tr
                    class="trade-row"
                    class:selected={selectedTradeId === trade.id}
                    onclick={() => selectTrade(trade.id)}
                  >
                    <td class="mono dim">{fmtDate(trade.created_at)}</td>
                    <td class="accent">{trade.asset}</td>
                    <td>
                      <Badge variant={sideVariant(trade.direction)}>
                        {sideLabel(trade.direction)}
                      </Badge>
                    </td>
                    <td class="mono">{fmtPrice(trade.entry)}</td>
                    <td class="mono">{fmtPrice(trade.close_price)}</td>
                    <td
                      class="mono"
                      class:green={(trade.pnl ?? 0) > 0}
                      class:red={(trade.pnl ?? 0) < 0}
                    >
                      {fmtPnl(trade.pnl)}
                    </td>
                    <td class="mono dim">{fmtRR(trade.rr)}</td>
                    <td>
                      {#if trade.grade}
                        <span class="grade-badge grade-{trade.grade.toLowerCase()}">{trade.grade}</span>
                      {:else}
                        <span class="dim">—</span>
                      {/if}
                    </td>
                    <td class="dim">{trade.strategy || '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <!-- Selected Trade Detail -->
          {#if selectedTradeId != null}
            {@const sel = trades.find(t => t.id === selectedTradeId)}
            {#if sel}
              <div class="trade-detail">
                <div class="detail-head">
                  <span class="accent" style="font-weight:700;">{sel.asset}</span>
                  <Badge variant={sideVariant(sel.direction)}>{sideLabel(sel.direction)}</Badge>
                  <span class="dim" style="font-size:10px;">ID #{sel.id}</span>
                  <span class="dim" style="font-size:10px; margin-left:auto;">{sel.status}</span>
                </div>
                {#if sel.notes}
                  <div class="detail-notes">{sel.notes}</div>
                {/if}
                <div class="detail-grid">
                  <div class="detail-item">
                    <span class="detail-label">Contracts</span>
                    <span class="detail-value mono">{sel.contracts}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">SL</span>
                    <span class="detail-value mono">{fmtPrice(sel.sl)}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">TP</span>
                    <span class="detail-value mono">{fmtPrice(sel.tp)}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Source</span>
                    <span class="detail-value">{sel.source ?? '—'}</span>
                  </div>
                  {#if sel.close_time}
                    <div class="detail-item">
                      <span class="detail-label">Closed</span>
                      <span class="detail-value mono">{fmtDate(sel.close_time)}</span>
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          {/if}
          {/if}
        </div>
        {#if tradesRaw && trades.length > 0}
          <div class="summary-footer">
            <div class="summary-item">
              <span class="summary-label">Trades</span>
              <span class="summary-value mono">{closedCount}</span>
            </div>
            <div class="summary-sep"></div>
            <div class="summary-item">
              <span class="summary-label">Total P&L</span>
              <span
                class="summary-value mono"
                class:green={totalPnl > 0}
                class:red={totalPnl < 0}
              >
                {fmtPnl(totalPnl)}
              </span>
            </div>
            <div class="summary-sep"></div>
            <div class="summary-item">
              <span class="summary-label">Win Rate</span>
              <span
                class="summary-value mono"
                class:green={winRate >= 50}
                class:red={winRate < 50}
              >
                {fmtPct(winRate)}
              </span>
            </div>
            <div class="summary-sep"></div>
            <div class="summary-item">
              <span class="summary-label">Wins</span>
              <span class="summary-value mono green">{winCount}</span>
            </div>
            <div class="summary-sep"></div>
            <div class="summary-item">
              <span class="summary-label">Losses</span>
              <span class="summary-value mono red">{closedCount - winCount}</span>
            </div>
          </div>
        {/if}
      </div>
    </Panel>

  </div><!-- /.pane-left -->

  <!-- ═══════════════════════════════════════════════════════════════════
       RIGHT PANE (40%) — Analytics + Daily Notes
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="pane pane-right">

    <!-- ── Analytics Panel ─────────────────────────────────────────── -->
    <div style="flex-shrink:0;">
      <Panel title="Analytics" badge="60s">
        {#if !stats}
          <Skeleton lines={4} height="40px" />
        {:else}
          <div class="stat-grid">
            <StatCard
              label="Win Rate"
              value={fmtPct(stats.win_rate)}
              color={stats.win_rate >= 50 ? 'green' : 'red'}
            />
            <StatCard
              label="Total P&L"
              value={fmtDollar(stats.total_net)}
              color={pnlColor(stats.total_net)}
            />
            <StatCard
              label="Avg Daily"
              value={fmtDollar(stats.avg_daily_net)}
              color={pnlColor(stats.avg_daily_net)}
            />
            <StatCard
              label="Profit Factor"
              value={fmtRatio(stats.profit_factor)}
              color={stats.profit_factor >= 1.5 ? 'green' : stats.profit_factor >= 1.0 ? 'amber' : 'red'}
            />
            <StatCard
              label="Sharpe Ratio"
              value={fmtRatio(stats.sharpe_ratio)}
              color={stats.sharpe_ratio >= 1.0 ? 'green' : stats.sharpe_ratio >= 0.5 ? 'amber' : 'red'}
            />
            <StatCard
              label="Max Drawdown"
              value={fmtDollar(stats.max_drawdown)}
              color="red"
            />
            <StatCard
              label="Expectancy"
              value={fmtDollar(stats.expectancy)}
              color={pnlColor(stats.expectancy)}
            />
            <StatCard
              label="Best Day"
              value={fmtDollar(stats.best_day)}
              color="green"
            />
            <StatCard
              label="Worst Day"
              value={fmtDollar(stats.worst_day)}
              color="red"
            />
            <StatCard
              label="Streak"
              value={fmtStreak(stats.current_streak)}
              color={stats.current_streak > 0 ? 'green' : stats.current_streak < 0 ? 'red' : 'default'}
            />
            <StatCard
              label="Avg Win"
              value={fmtDollar(stats.avg_win)}
              color="green"
            />
            <StatCard
              label="Avg Loss"
              value={fmtDollar(stats.avg_loss)}
              color="red"
            />
          </div>

          <!-- Win/Loss Day Summary -->
          <div class="day-summary">
            <div class="day-bar-track">
              <div
                class="day-bar-fill win-fill"
                style="width:{stats.total_days > 0 ? (stats.win_days / stats.total_days) * 100 : 0}%;"
              ></div>
            </div>
            <div class="day-labels">
              <span class="green" style="font-size:10px;">{stats.win_days}W</span>
              <span class="dim" style="font-size:10px;">{stats.total_days} days</span>
              <span class="red" style="font-size:10px;">{stats.loss_days}L</span>
            </div>
          </div>
        {/if}
      </Panel>
    </div>

    <!-- ── Daily Notes Panel ───────────────────────────────────────── -->
    <div style="flex:1; min-height:200px; display:flex; flex-direction:column;">
      <Panel title="Daily Notes" noPad fill>
        {#snippet header()}
          <input
            type="date"
            class="date-input"
            value={noteDate}
            onchange={handleDateChange}
          />
          <span class="save-indicator" class:saved={noteStatus === 'saved'} class:saving={noteStatus === 'saving'} class:error={noteStatus === 'error'}>
            {#if noteStatus === 'saving'}
              Saving…
            {:else if noteStatus === 'saved'}
              Saved ✓
            {:else if noteStatus === 'error'}
              Error ✕
            {:else}
              &nbsp;
            {/if}
          </span>
        {/snippet}
        <div class="notes-body">
          {#if notesLoading}
            <Skeleton lines={4} height="14px" />
          {:else}
            <textarea
              class="notes-textarea"
              placeholder="Write your thoughts, observations, lessons learned…"
              bind:value={noteText}
              onblur={handleNotesBlur}
              oninput={handleNotesInput}
              spellcheck="true"
            ></textarea>
          {/if}
        </div>
      </Panel>
    </div>

  </div><!-- /.pane-right -->
</div>

<style>
  /* ═══════════════════════════════════════════════════════════════════
     Layout
     ═══════════════════════════════════════════════════════════════════ */
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
    gap: 0;
  }

  .pane {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }

  .pane-left {
    flex: 6;
    border-right: 1px solid var(--b1);
    min-width: 0;
  }

  .pane-right {
    flex: 4;
    min-width: 300px;
    overflow-y: auto;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Trade Log inner layout
     ═══════════════════════════════════════════════════════════════════ */
  .trade-inner {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  .trade-scroll {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }

  .empty-state {
    color: var(--t3);
    font-size: 11px;
    text-align: center;
    padding: 24px 0;
  }

  .dim { color: var(--t3); }
  .mono { font-family: var(--font-mono, monospace); }
  .accent { color: var(--accent); font-weight: 600; }
  .green { color: var(--green); }
  .red { color: var(--red); }

  /* ═══════════════════════════════════════════════════════════════════
     Trade Log Table
     ═══════════════════════════════════════════════════════════════════ */
  .table-scroll {
    overflow: auto;
    flex: 1;
    min-height: 0;
  }

  .tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  .tbl thead th {
    text-align: left;
    padding: 4px 8px;
    color: var(--t3);
    font-size: 9px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--b2);
    white-space: nowrap;
    position: sticky;
    top: 0;
    background: var(--bg1);
    z-index: 2;
  }

  .tbl td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--b1);
    white-space: nowrap;
  }

  .trade-row {
    cursor: pointer;
    transition: background 0.1s;
  }

  .trade-row:hover {
    background: var(--bg3);
  }

  .trade-row.selected {
    background: var(--bg3);
    box-shadow: inset 2px 0 0 var(--accent);
  }

  /* Grade badge */
  .grade-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: var(--r);
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .grade-a { background: var(--green-dim, rgba(22, 199, 132, 0.12)); color: var(--green); }
  .grade-b { background: var(--cyan-dim, rgba(0, 188, 212, 0.12)); color: var(--cyan, #00bcd4); }
  .grade-c { background: var(--amber-dim, rgba(255, 183, 77, 0.12)); color: var(--amber); }
  .grade-d { background: var(--red-dim, rgba(234, 57, 67, 0.12)); color: var(--red); }
  .grade-f { background: var(--red-dim, rgba(234, 57, 67, 0.12)); color: var(--red); }

  /* ═══════════════════════════════════════════════════════════════════
     Trade Detail (expanded row)
     ═══════════════════════════════════════════════════════════════════ */
  .trade-detail {
    border-top: 1px solid var(--b2);
    background: var(--bg2);
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    animation: slide-down 0.15s ease;
  }

  @keyframes slide-down {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .detail-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .detail-notes {
    font-size: 11px;
    color: var(--t2);
    background: var(--bg1);
    padding: 6px 10px;
    border-radius: var(--r);
    border-left: 2px solid var(--accent);
    line-height: 1.5;
  }

  .detail-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 16px;
  }

  .detail-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .detail-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .detail-value {
    font-size: 11px;
    color: var(--t1);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Summary Footer
     ═══════════════════════════════════════════════════════════════════ */
  .summary-footer {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 12px;
    background: var(--bg2);
    border-top: 1px solid var(--b1);
    flex-shrink: 0;
  }

  .summary-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .summary-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .summary-value {
    font-size: 12px;
    font-weight: 700;
    color: var(--t1);
  }

  .summary-sep {
    width: 1px;
    height: 16px;
    background: var(--b2);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Stat Grid (Analytics)
     ═══════════════════════════════════════════════════════════════════ */
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 6px;
  }

  /* Win/Loss day bar */
  .day-summary {
    margin-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .day-bar-track {
    height: 6px;
    background: var(--red-dim, rgba(234, 57, 67, 0.15));
    border-radius: 3px;
    overflow: hidden;
  }

  .day-bar-fill.win-fill {
    height: 100%;
    background: var(--green);
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  .day-labels {
    display: flex;
    justify-content: space-between;
    font-weight: 600;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Daily Notes
     ═══════════════════════════════════════════════════════════════════ */
  .date-input {
    background: var(--bg3);
    border: 1px solid var(--b2);
    color: var(--t1);
    padding: 2px 6px;
    border-radius: var(--r);
    font-family: var(--font-mono, monospace);
    font-size: 10px;
    cursor: pointer;
  }

  .date-input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .date-input::-webkit-calendar-picker-indicator {
    filter: invert(0.7);
    cursor: pointer;
  }

  .save-indicator {
    font-size: 9px;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: var(--r);
    transition: color 0.2s, background 0.2s;
    color: transparent;
    min-width: 56px;
    text-align: center;
  }

  .save-indicator.saving {
    color: var(--amber);
    background: var(--amber-dim, rgba(255, 183, 77, 0.12));
  }

  .save-indicator.saved {
    color: var(--green);
    background: var(--green-dim, rgba(22, 199, 132, 0.12));
  }

  .save-indicator.error {
    color: var(--red);
    background: var(--red-dim, rgba(234, 57, 67, 0.12));
  }

  .notes-body {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  .notes-textarea {
    flex: 1;
    min-height: 140px;
    width: 100%;
    background: var(--bg1);
    border: none;
    color: var(--t1);
    font-family: inherit;
    font-size: 12px;
    line-height: 1.6;
    padding: 10px 12px;
    resize: none;
    outline: none;
  }

  .notes-textarea::placeholder {
    color: var(--t3);
  }

  .notes-textarea:focus {
    background: var(--bg2);
  }
</style>
