<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface LogEntry {
    ts: number;
    level: string;
    name: string;
    msg: string;
  }

  interface LiveData {
    entries: LogEntry[];
    has_live: boolean;
    ts: number;
  }

  interface FileData {
    entries: LogEntry[];
    date: string;
    available_dates: string[];
    has_files: boolean;
  }

  // ─── Filter state ─────────────────────────────────────────────────────

  type Mode = 'live' | 'file';

  let mode        = $state<Mode>('live');
  let levelFilter = $state('');
  let nameFilter  = $state('');
  let fileDate    = $state('');
  let since       = $state(0);

  // ─── Live polling ─────────────────────────────────────────────────────

  function liveUrl() {
    const p = new URLSearchParams();
    p.set('since', String(since));
    if (levelFilter) p.set('level', levelFilter);
    if (nameFilter)  p.set('name',  nameFilter);
    return `${ws.apiBase}/logs/live?${p}`;
  }

  let livePoll = $state(createPoll<LiveData>(liveUrl(), 3_000));

  $effect(() => {
    if (mode !== 'live') { livePoll.stop(); return; }
    livePoll.stop();
    livePoll = createPoll<LiveData>(liveUrl(), 3_000);
    livePoll.start();
  });

  let liveData    = $derived($livePoll);
  let liveEntries = $derived(liveData?.entries ?? []);
  let hasLive     = $derived(liveData?.has_live ?? true);

  // ─── File log fetching ────────────────────────────────────────────────

  let fileData       = $state<FileData | null>(null);
  let fileLoading    = $state(false);
  let availableDates = $derived(fileData?.available_dates ?? []);

  async function fetchFile() {
    fileLoading = true;
    try {
      const p = new URLSearchParams();
      if (fileDate)    p.set('date',  fileDate);
      if (levelFilter) p.set('level', levelFilter);
      if (nameFilter)  p.set('name',  nameFilter);
      fileData = await api.get<FileData>(`${ws.apiBase}/logs/file?${p}`);
      if (!fileDate && fileData.date) fileDate = fileData.date;
    } catch {
      fileData = null;
    } finally {
      fileLoading = false;
    }
  }

  $effect(() => { if (mode === 'file') fetchFile(); });

  function exportUrl(): string {
    const p = new URLSearchParams();
    if (fileDate) p.set('date', fileDate);
    return `${ws.apiBase}/logs/export?${p}`;
  }

  // ─── Log entry styling ────────────────────────────────────────────────

  function levelVariant(level: string): 'red' | 'amber' | 'default' | 'cyan' {
    switch (level.toUpperCase()) {
      case 'ERROR': case 'CRITICAL': return 'red';
      case 'WARNING': case 'WARN':   return 'amber';
      case 'DEBUG':                  return 'cyan';
      default:                       return 'default';
    }
  }

  onMount(() => {
    if (mode === 'live') livePoll.start();
    else fetchFile();
    return () => livePoll.stop();
  });
</script>

<div class="page">
  <Panel title="Log Viewer" fill>
    {#snippet header()}
      <button class="mode-btn" class:active={mode === 'live'} onclick={() => (mode = 'live')}>Live</button>
      <button class="mode-btn" class:active={mode === 'file'} onclick={() => (mode = 'file')}>File</button>

      <span class="sep">|</span>

      <select class="filter-select" bind:value={levelFilter}>
        <option value="">All levels</option>
        {#each ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as l}
          <option value={l}>{l}</option>
        {/each}
      </select>

      <input class="filter-input" type="text" placeholder="filter by name…" bind:value={nameFilter} />

      {#if mode === 'file'}
        <select class="filter-select" bind:value={fileDate} onchange={fetchFile}>
          {#each availableDates as d}
            <option value={d}>{d}</option>
          {/each}
        </select>
        <a class="export-btn" href={exportUrl()} download>↓ txt</a>
      {:else}
        <span class="poll-badge">{liveEntries.length} entries · 3s</span>
      {/if}
    {/snippet}

    <div class="log-wrap">
      {#if mode === 'live'}
        {#if !hasLive}
          <p class="empty">Live ring buffer not available. Switch to File mode.</p>
        {:else if liveEntries.length === 0}
          <p class="empty">No log entries yet…</p>
        {:else}
          {#each [...liveEntries].reverse() as entry}
            <div class="log-line" class:error-line={entry.level === 'ERROR' || entry.level === 'CRITICAL'}>
              <Badge variant={levelVariant(entry.level)}>{entry.level}</Badge>
              {#if entry.name}<span class="log-name">{entry.name}</span>{/if}
              <span class="log-msg">{entry.msg}</span>
            </div>
          {/each}
        {/if}
      {:else}
        {#if fileLoading}
          <p class="empty dim">Loading…</p>
        {:else if !fileData || fileData.entries.length === 0}
          <p class="empty">No log entries for {fileDate || 'today'}.</p>
        {:else}
          {#each fileData.entries as entry}
            <div class="log-line" class:error-line={entry.level === 'ERROR' || entry.level === 'CRITICAL'}>
              <Badge variant={levelVariant(entry.level)}>{entry.level}</Badge>
              <span class="log-msg">{entry.msg}</span>
            </div>
          {/each}
        {/if}
      {/if}
    </div>
  </Panel>
</div>

<style>
  .page { display: flex; flex-direction: column; height: 100%; padding: 10px; }

  .mode-btn {
    background: var(--bg3); border: 1px solid var(--b2); border-radius: var(--r);
    color: var(--t2); font-family: inherit; font-size: 9px; text-transform: uppercase;
    letter-spacing: 0.06em; padding: 2px 7px; cursor: pointer; transition: background 0.15s;
  }
  .mode-btn.active { background: var(--accent-dim); border-color: var(--accent-brd); color: var(--t1); }

  .sep { color: var(--t3); font-size: 10px; }

  .filter-select {
    background: var(--bg3); border: 1px solid var(--b3); border-radius: var(--r);
    color: var(--t1); font-family: inherit; font-size: 10px; padding: 2px 6px; cursor: pointer;
  }

  .filter-input {
    background: var(--bg3); border: 1px solid var(--b3); border-radius: var(--r);
    color: var(--t1); font-family: inherit; font-size: 10px; padding: 2px 6px;
    outline: none; width: 120px;
  }
  .filter-input::placeholder { color: var(--t3); }
  .filter-input:focus { border-color: var(--accent-brd); }

  .export-btn {
    font-size: 9px; padding: 2px 7px; background: var(--bg3); border: 1px solid var(--b3);
    border-radius: var(--r); color: var(--cyan); text-decoration: none;
  }
  .export-btn:hover { background: var(--cyan-dim); border-color: var(--cyan-brd); }

  .poll-badge { font-size: 8px; color: var(--t3); background: var(--bg3); padding: 1px 5px; border-radius: var(--r); }

  .log-wrap {
    height: 100%; overflow: auto; display: flex; flex-direction: column;
    gap: 2px; padding: 4px 0; font-size: 10px;
  }

  .log-line {
    display: flex; align-items: flex-start; gap: 8px; padding: 3px 6px;
    border-radius: var(--r); line-height: 1.5;
  }
  .log-line:hover      { background: var(--bg3); }
  .log-line.error-line { background: var(--red-dim); }

  .log-name { color: var(--cyan); font-size: 9px; flex-shrink: 0; white-space: nowrap; }
  .log-msg  { color: var(--t1); word-break: break-all; white-space: pre-wrap; font-size: 10px; }

  .empty { padding: 20px; font-size: 11px; color: var(--t3); }
  .dim   { color: var(--t2); }
</style>
