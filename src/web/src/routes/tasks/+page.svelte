<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtDateTime } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface ParamDef {
    name: string;
    type: 'number' | 'select' | 'text';
    default?: unknown;
    options?: string[];
    help?: string;
  }

  interface TaskTypeDef {
    id: string;
    label: string;
    description: string;
    needs_asset: boolean;
    params: ParamDef[];
  }

  interface Task {
    task_id: string;
    task_type: string;
    asset?: string;
    status: 'queued' | 'running' | 'done' | 'error' | 'cancelled';
    created_at?: number;
    started_at?: number;
    finished_at?: number;
    exit_code?: number;
    output_lines?: string[];
  }

  interface TaskListData { tasks: Task[]; count: number; }
  interface TypesData    { types: TaskTypeDef[]; }

  // ─── Guards — this page requires a tasksBase ──────────────────────────

  const hasTaskRunner = !!ws.tasksBase;
  const tb = ws.tasksBase ?? '';   // never accessed when hasTaskRunner is false

  // ─── Task list poll ───────────────────────────────────────────────────

  const tasksPoll = createPoll<TaskListData>(`${tb}/list`, 3_000);
  let tasks = $derived($tasksPoll?.tasks ?? []);

  // ─── Task types & known assets ────────────────────────────────────────

  let taskTypes   = $state<TaskTypeDef[]>([]);
  let knownAssets = $state<string[]>([]);

  async function loadMeta() {
    if (!hasTaskRunner) return;
    try {
      const typesRes = await api.get<TypesData>(`${tb}/types`);
      taskTypes = typesRes.types ?? [];
      const dash = await api.get<{ workers: Record<string, unknown> }>(`${ws.apiBase}/dashboard`);
      knownAssets = Object.keys(dash.workers ?? {}).sort();
    } catch { /* silent */ }
  }

  // ─── Submit form ──────────────────────────────────────────────────────

  let selectedTypeId = $state('');
  let selectedAsset  = $state('');
  let extraParams    = $state<Record<string, unknown>>({});
  let submitting     = $state(false);
  let submitFeedback = $state<{ msg: string; ok: boolean } | null>(null);

  let selectedType = $derived(taskTypes.find((t) => t.id === selectedTypeId) ?? null);

  $effect(() => {
    if (selectedType) {
      extraParams = Object.fromEntries(
        selectedType.params.map((p) => [p.name, p.default ?? ''])
      );
    }
  });

  async function submitTask() {
    if (!selectedTypeId || !hasTaskRunner) return;
    submitting     = true;
    submitFeedback = null;
    try {
      const res = await api.post<{ task_id: string }>(`${tb}/run`, {
        task_type: selectedTypeId,
        asset:     selectedAsset || undefined,
        params:    extraParams,
      });
      submitFeedback = { msg: `Submitted — task ${res.task_id}`, ok: true };
      tasksPoll.refresh();
    } catch (e) {
      submitFeedback = { msg: `Failed: ${e}`, ok: false };
    } finally {
      submitting = false;
    }
  }

  // ─── SSE output viewer ─────────────────────────────────────────────────

  let viewingTaskId = $state<string | null>(null);
  let outputLines   = $state<string[]>([]);
  let streaming     = $state(false);
  let sseSource: EventSource | null = null;

  function viewTask(taskId: string) {
    viewingTaskId = taskId;
    outputLines   = [];
    if (sseSource) sseSource.close();

    const cached = tasks.find((t) => t.task_id === taskId);
    if (cached?.output_lines?.length) outputLines = [...cached.output_lines];

    streaming  = true;
    sseSource  = new EventSource(`${tb}/${taskId}/stream`);
    sseSource.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        if (parsed.done)       { streaming = false; sseSource?.close(); }
        else if (parsed.line)  { outputLines = [...outputLines, parsed.line]; }
      } catch { /* ignore */ }
    };
    sseSource.onerror = () => { streaming = false; sseSource?.close(); };
  }

  async function cancelTask(taskId: string) {
    try {
      await api.post(`${tb}/${taskId}/cancel`);
      tasksPoll.refresh();
    } catch { /* ignore */ }
  }

  function statusBadge(status: string): 'green' | 'red' | 'amber' | 'cyan' | 'default' {
    switch (status) {
      case 'done':      return 'green';
      case 'error':     return 'red';
      case 'running':   return 'cyan';
      case 'queued':    return 'amber';
      case 'cancelled': return 'default';
      default:          return 'default';
    }
  }

  onMount(() => {
    if (!hasTaskRunner) return;
    loadMeta();
    tasksPoll.start();
    return () => { tasksPoll.stop(); sseSource?.close(); };
  });
</script>

<div class="page">
  {#if !hasTaskRunner}
    <div class="unsupported">
      <p>Task runner is not configured for the <strong>{ws.label}</strong> workspace.</p>
      <p class="dim">Add <code>tasksBase: '/your-tasks-api'</code> in <code>src/lib/workspaces.ts</code> to enable this tab.</p>
    </div>
  {:else}
    <div class="left-col">
      <!-- Submit form -->
      <Panel title="Run Task">
        <div class="form">
          <label class="field">
            <span class="lbl">Task Type</span>
            <select class="sel" bind:value={selectedTypeId}>
              <option value="">— select —</option>
              {#each taskTypes as t}
                <option value={t.id}>{t.label}</option>
              {/each}
            </select>
          </label>

          {#if selectedType}
            <p class="desc">{selectedType.description}</p>

            {#if selectedType.needs_asset}
              <label class="field">
                <span class="lbl">Asset</span>
                <select class="sel" bind:value={selectedAsset}>
                  <option value="">— all —</option>
                  {#each knownAssets as a}
                    <option value={a}>{a.toUpperCase()}</option>
                  {/each}
                </select>
              </label>
            {/if}

            {#each selectedType.params as p}
              <label class="field">
                <span class="lbl">{p.name}</span>
                {#if p.type === 'select'}
                  <select class="sel" bind:value={extraParams[p.name]}>
                    {#each p.options ?? [] as opt}
                      <option value={opt}>{opt}</option>
                    {/each}
                  </select>
                {:else}
                  <input
                    class="inp"
                    type={p.type === 'number' ? 'number' : 'text'}
                    bind:value={extraParams[p.name]}
                    placeholder={String(p.default ?? '')}
                  />
                {/if}
                {#if p.help}<span class="help">{p.help}</span>{/if}
              </label>
            {/each}
          {/if}

          <button class="run-btn" disabled={!selectedTypeId || submitting} onclick={submitTask}>
            {submitting ? 'Submitting…' : '▶ Run'}
          </button>

          {#if submitFeedback}
            <p class="feedback" class:ok={submitFeedback.ok}>{submitFeedback.msg}</p>
          {/if}
        </div>
      </Panel>

      <!-- Task list -->
      <Panel title="Recent Tasks" fill>
        {#if !$tasksPoll}
          <div class="skel-col">
            {#each Array(5) as _}<Skeleton height="36px" />{/each}
          </div>
        {:else if tasks.length === 0}
          <p class="empty">No tasks yet.</p>
        {:else}
          <div class="task-list">
            {#each tasks as t}
              <button
                class="task-row"
                class:viewing={viewingTaskId === t.task_id}
                onclick={() => viewTask(t.task_id)}
              >
                <Badge variant={statusBadge(t.status)}>{t.status}</Badge>
                <span class="task-type">{t.task_type}</span>
                {#if t.asset}<span class="task-asset">{t.asset.toUpperCase()}</span>{/if}
                <span class="task-time dim">
                  {t.created_at ? fmtDateTime(t.created_at * 1000) : ''}
                </span>
                {#if t.status === 'running'}
                  <button
                    class="cancel-btn"
                    onclick={(e) => { e.stopPropagation(); cancelTask(t.task_id); }}
                  >✕</button>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </Panel>
    </div>

    <!-- Output panel -->
    <Panel title={viewingTaskId ? `Output — ${viewingTaskId.slice(0, 8)}…` : 'Output'} fill>
      {#if !viewingTaskId}
        <p class="empty">Select a task to view output.</p>
      {:else}
        {#if streaming}<ProgressBar value={100} color="cyan" height="2px" />{/if}
        <div class="output-wrap">
          {#each outputLines as line}
            <div class="output-line">{line}</div>
          {/each}
          {#if outputLines.length === 0}
            <p class="empty dim">{streaming ? 'Waiting for output…' : 'No output.'}</p>
          {/if}
        </div>
      {/if}
    </Panel>
  {/if}
</div>

<style>
  .page {
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 8px; padding: 10px; height: 100%; min-height: 0;
  }

  .left-col { display: flex; flex-direction: column; gap: 8px; min-height: 0; }

  /* Form */
  .form  { display: flex; flex-direction: column; gap: 8px; }
  .field { display: flex; flex-direction: column; gap: 3px; }

  .lbl { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: 0.06em; }

  .sel, .inp {
    background: var(--bg3); border: 1px solid var(--b3); border-radius: var(--r);
    color: var(--t1); font-family: inherit; font-size: 10px; padding: 3px 6px;
    width: 100%; outline: none;
  }
  .sel:focus, .inp:focus { border-color: var(--accent-brd); }

  .help { font-size: 9px; color: var(--t3); line-height: 1.3; }

  .desc {
    font-size: 10px; color: var(--t2); line-height: 1.5;
    padding: 4px 0 4px 8px; border-left: 2px solid var(--b3);
  }

  .run-btn {
    margin-top: 4px; padding: 5px 12px; background: var(--accent-dim);
    border: 1px solid var(--accent-brd); border-radius: var(--r); color: var(--t1);
    font-family: inherit; font-size: 11px; font-weight: 600; cursor: pointer;
    transition: background 0.15s; text-align: center;
  }
  .run-btn:hover:not(:disabled) { background: var(--accent-glow); }
  .run-btn:disabled { opacity: 0.4; cursor: default; }

  .feedback { font-size: 10px; padding: 4px 8px; border-radius: var(--r); background: var(--red-dim); color: var(--red); }
  .feedback.ok { background: var(--green-dim); color: var(--green); }

  /* Task list */
  .task-list { display: flex; flex-direction: column; gap: 2px; overflow: auto; height: 100%; }

  .task-row {
    display: flex; align-items: center; gap: 6px; padding: 5px 6px; border-radius: var(--r);
    background: transparent; border: 1px solid transparent; text-align: left;
    cursor: pointer; font-family: inherit; width: 100%; transition: background 0.1s;
  }
  .task-row:hover    { background: var(--bg3); }
  .task-row.viewing  { background: var(--accent-dim); border-color: var(--accent-brd); }

  .task-type  { font-size: 10px; color: var(--t1); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .task-asset { font-size: 9px; color: var(--cyan); flex-shrink: 0; }
  .task-time  { font-size: 9px; color: var(--t3); flex-shrink: 0; }

  .cancel-btn {
    margin-left: auto; background: transparent; border: none;
    color: var(--red); cursor: pointer; font-size: 10px; padding: 0 2px; flex-shrink: 0;
  }

  /* Output */
  .output-wrap { height: 100%; overflow: auto; padding: 4px 0; display: flex; flex-direction: column; gap: 1px; }

  .output-line {
    font-size: 10px; color: var(--t1); padding: 2px 4px;
    white-space: pre-wrap; word-break: break-all; line-height: 1.5; border-radius: var(--r);
  }
  .output-line:hover { background: var(--bg3); }

  .unsupported {
    padding: 40px; display: flex; flex-direction: column;
    gap: 8px; color: var(--t2); font-size: 12px; line-height: 1.6;
    grid-column: 1 / -1;
  }
  .unsupported code { color: var(--cyan); font-size: 11px; }

  .skel-col { display: flex; flex-direction: column; gap: 4px; padding: 4px; }
  .empty { padding: 16px; font-size: 11px; color: var(--t3); }
  .dim   { color: var(--t2); }
</style>
