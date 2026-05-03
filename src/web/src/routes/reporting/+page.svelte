<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface ReportResponse {
    report: string | null;
    period: string;
    selected_date: string | null;
    available_dates: string[];
    generated_at?: string;
  }

  // ─── State ───────────────────────────────────────────────────────────

  type Period = 'day' | 'week' | 'month';

  let period       = $state<Period>('day');
  let selectedDate = $state<string>('');
  let data         = $state<ReportResponse | null>(null);
  let loading      = $state(true);
  let error        = $state('');

  // ─── Fetch ───────────────────────────────────────────────────────────

  async function fetchReport() {
    loading = true;
    error   = '';
    try {
      const params = new URLSearchParams({ period });
      if (selectedDate) params.set('date', selectedDate);
      // NOTE: api is an object — use api.get(), not api() directly.
      data = await api.get<ReportResponse>(`${ws.apiBase}/reports?${params}`);
      if (data.selected_date && !selectedDate) selectedDate = data.selected_date;
    } catch (e: any) {
      error = e.message ?? 'Failed to load report';
    } finally {
      loading = false;
    }
  }

  function setPeriod(p: Period) {
    period       = p;
    selectedDate = '';
    fetchReport();
  }

  function onDateChange(e: Event) {
    selectedDate = (e.target as HTMLSelectElement).value;
    fetchReport();
  }

  // ─── Helpers ─────────────────────────────────────────────────────────

  const PERIODS: { id: Period; label: string }[] = [
    { id: 'day',   label: 'Day'   },
    { id: 'week',  label: 'Week'  },
    { id: 'month', label: 'Month' },
  ];

  function periodLabel(p: Period): string {
    return p === 'day' ? 'Daily' : p === 'week' ? 'Weekly' : 'Monthly';
  }

  function fmtDate(iso: string | null | undefined): string {
    if (!iso) return '—';
    try {
      return new Intl.DateTimeFormat('en-CA', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      }).format(new Date(iso));
    } catch { return iso; }
  }

  onMount(fetchReport);
</script>

<svelte:head>
  <title>{ws.label} Reports — FKS Terminal</title>
</svelte:head>

<div class="page">
  <Panel title="AI Reports" fill>
    {#snippet header()}
      <div class="period-tabs" role="tablist">
        {#each PERIODS as p}
          <button
            role="tab"
            aria-selected={period === p.id}
            class="period-tab"
            class:active={period === p.id}
            onclick={() => setPeriod(p.id)}
          >{p.label}</button>
        {/each}
      </div>

      {#if (data?.available_dates ?? []).length > 1}
        <div class="date-wrap">
          <span class="date-label">Date</span>
          <select class="date-select" value={selectedDate} onchange={onDateChange}>
            {#each data!.available_dates as d, i}
              <option value={d}>{d}{i === 0 ? ' (latest)' : ''}</option>
            {/each}
          </select>
        </div>
      {/if}
    {/snippet}

    <div class="report-card">
      <div class="report-header">
        <div class="report-header-left">
          <span class="report-title">{periodLabel(period)} Report</span>
          {#if data?.selected_date}
            <span class="date-badge">{data.selected_date}</span>
          {/if}
        </div>
        <div class="report-header-right">
          <Badge variant="default">{period}</Badge>
          {#if data?.generated_at}
            <span class="generated-at dim">Generated {fmtDate(data.generated_at)}</span>
          {/if}
        </div>
      </div>

      <div class="report-body">
        {#if loading}
          <div class="loading-state">
            <div class="spinner"></div>
            <span class="dim">Loading {periodLabel(period).toLowerCase()} report…</span>
          </div>
        {:else if error}
          <div class="empty-state">
            <span class="empty-icon">⚠</span>
            <span class="empty-title">Failed to load report</span>
            <span class="empty-note">{error}</span>
            <button class="retry-btn" onclick={fetchReport}>↻ Retry</button>
          </div>
        {:else if data?.report}
          <pre class="report-text">{data.report}</pre>
        {:else}
          <div class="empty-state">
            <span class="empty-icon">◎</span>
            <span class="empty-title">No {period} report available yet</span>
            <span class="empty-note">
              Reports are generated automatically at the end of each {period}.<br/>
              Check back later or wait for the AI analyst to complete its run.
            </span>
          </div>
        {/if}
      </div>
    </div>
  </Panel>
</div>

<style>
  .page { display: flex; flex-direction: column; height: 100%; padding: 10px; }

  .period-tabs {
    display: flex; gap: 2px; background: var(--bg2);
    border: 1px solid var(--b2); border-radius: var(--r-md); padding: 2px;
  }
  .period-tab {
    font-family: inherit; font-size: 10px; font-weight: 500; padding: 3px 10px;
    border: none; border-radius: var(--r); background: none; color: var(--t2);
    cursor: pointer; transition: background 0.15s, color 0.15s;
  }
  .period-tab:hover, .period-tab.active { color: var(--t1); background: var(--bg3); }

  .date-wrap {
    display: flex; align-items: center; gap: 6px;
    padding-left: 12px; border-left: 1px solid var(--b2);
  }
  .date-label {
    font-size: 9px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--t3); white-space: nowrap;
  }
  .date-select {
    background: var(--bg3); border: 1px solid var(--b2); border-radius: var(--r);
    color: var(--t1); font-family: inherit; font-size: 10px; padding: 2px 6px;
    cursor: pointer; outline: none; transition: border-color 0.15s;
  }
  .date-select:focus { border-color: var(--accent); }

  .report-card {
    display: flex; flex-direction: column; height: 100%;
    border: 1px solid var(--b2); border-radius: var(--r-md); overflow: hidden;
  }
  .report-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px; border-bottom: 1px solid var(--b2);
    background: rgba(0, 0, 0, 0.15); flex-wrap: wrap; gap: 8px;
  }
  .report-header-left, .report-header-right { display: flex; align-items: center; gap: 8px; }
  .report-title { font-size: 10px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--t3); }
  .date-badge  { font-size: 10px; color: var(--t3); letter-spacing: 0.03em; }
  .generated-at { font-size: 9px; color: var(--t3); }
  .dim { color: var(--t2); }

  .report-body { flex: 1; overflow-y: auto; padding: 16px 20px; min-height: 200px; }

  .report-text {
    font-family: inherit; font-size: 11px; line-height: 1.75;
    color: var(--t1); white-space: pre-wrap; word-break: break-word;
  }

  .loading-state { display: flex; align-items: center; gap: 10px; padding: 20px 0; font-size: 11px; color: var(--t2); }
  .spinner {
    width: 14px; height: 14px; border: 2px solid var(--b2);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.7s linear infinite; flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .empty-state { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 20px 0; }
  .empty-icon  { font-size: 26px; opacity: 0.35; line-height: 1; }
  .empty-title { font-size: 13px; font-weight: 600; color: var(--t1); }
  .empty-note  { font-size: 11px; color: var(--t3); line-height: 1.65; }

  .retry-btn {
    margin-top: 6px; font-family: inherit; font-size: 10px; background: var(--bg3);
    border: 1px solid var(--b2); border-radius: var(--r); color: var(--t2);
    padding: 3px 10px; cursor: pointer;
  }
  .retry-btn:hover { color: var(--t1); }
</style>
