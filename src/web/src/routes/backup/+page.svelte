<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$api/client';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';

  // ─── Types ──────────────────────────────────────────────────────────

  interface BackupStatus {
    row_counts: Record<string, number>;
    last_backup_at: string | null;
  }

  interface PreviewSection {
    postgres?: Record<string, number | { rows: number; error?: string }>;
    redis?: Record<string, string>;
    browser?: Record<string, string>;
  }

  interface PreviewResult {
    intact: boolean;
    sections: PreviewSection;
    meta?: { checksum?: string; version?: string; created_at?: string };
  }

  interface RestoreResult {
    restored_at?: string;
    sections?: {
      postgres?: Record<string, { restored?: number; upserted?: number; error?: string }>;
      redis?: Record<string, string>;
    };
    browser?: Record<string, string>;
  }

  // ─── Browser keys included in every backup ──────────────────────────

  const BROWSER_KEYS = [
    'chart:indicators', 'chart:indicator_config', 'chart:layout',
    'chart:theme', 'chart:default_asset', 'dashboard:layout',
    'dashboard:visible_panels', 'dashMode', 'gate:min_confidence',
    'gate:rithmic_manual_mode', 'journalTab', 'settingsTab',
    'theme', 'settings:locale', 'settings:timezone', 'settings:notifications',
  ];

  // ─── Status ─────────────────────────────────────────────────────────

  let status         = $state<BackupStatus | null>(null);
  let statusLoading  = $state(true);
  let statusError    = $state('');

  async function loadStatus() {
    statusLoading = true;
    statusError   = '';
    try {
      status = await api<BackupStatus>('/api/backup/status');
    } catch (e: any) {
      statusError = e.message ?? 'Failed to load status';
    } finally {
      statusLoading = false;
    }
  }

  // ─── Export ─────────────────────────────────────────────────────────

  let exportPostgres = $state(true);
  let exportRedis    = $state(true);
  let exportBrowser  = $state(true);
  let exportCompress = $state(false);
  let exportRunning  = $state(false);
  let exportProgress = $state(0);
  let exportLog      = $state<{ msg: string; cls: string }[]>([]);
  let exportHint     = $state('');

  function logExport(msg: string, cls = '') {
    exportLog = [...exportLog, { msg, cls }];
  }

  async function doExport() {
    exportRunning  = true;
    exportProgress = 5;
    exportLog      = [];
    exportHint     = '';

    try {
      logExport('▸ Requesting server backup…', 'info');
      exportProgress = 20;

      const url  = `/api/backup/export${exportCompress ? '?compress=true' : ''}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Server error ${resp.status}: ${await resp.text()}`);

      exportProgress = 55;
      logExport('▸ Received server data', 'ok');

      const serverBuf = await resp.arrayBuffer();
      let serverData: any;

      if (exportCompress) {
        logExport('▸ Compressed mode: browser section skipped', 'warn');
        serverData = null;
      } else {
        serverData = JSON.parse(new TextDecoder().decode(serverBuf));
      }

      exportProgress = 70;

      // Collect & merge browser state
      if (exportBrowser && serverData) {
        const browser: Record<string, string> = {};
        for (const k of BROWSER_KEYS) {
          const v = localStorage.getItem(k);
          if (v !== null) browser[k] = v;
        }
        serverData.browser = browser;
        logExport(`▸ Collected ${Object.keys(browser).length} browser key(s)`, 'info');
      }

      exportProgress = 88;

      if (serverData) {
        if (!exportPostgres) delete serverData.postgres;
        if (!exportRedis)    delete serverData.redis;
      }

      const finalBuf = serverData
        ? new TextEncoder().encode(JSON.stringify(serverData, null, 2))
        : serverBuf;

      const ext      = exportCompress ? 'json.gz' : 'json';
      const filename = `fks-backup-${new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-')}.${ext}`;
      const mime     = exportCompress ? 'application/gzip' : 'application/json';
      const blob     = new Blob([finalBuf], { type: mime });

      exportProgress = 100;
      triggerDownload(blob, filename);
      logExport(`✓ Saved as ${filename} (${fmtBytes(finalBuf.byteLength)})`, 'ok');
      exportHint = `Exported ${fmtBytes(finalBuf.byteLength)}`;
      await loadStatus();
    } catch (e: any) {
      logExport(`✗ Export failed: ${e.message}`, 'err');
      exportHint    = 'Export failed — see log above';
      exportProgress = 0;
    } finally {
      exportRunning = false;
    }
  }

  // ─── Import / preview ────────────────────────────────────────────────

  let pendingParsed  = $state<any>(null);
  let isDragging     = $state(false);
  let importRunning  = $state(false);
  let importProgress = $state(0);
  let importLog      = $state<{ msg: string; cls: string }[]>([]);
  let preview        = $state<PreviewResult | null>(null);
  let dryRun         = $state(true);
  let restoreRunning = $state(false);

  function logImport(msg: string, cls = '') {
    importLog = [...importLog, { msg, cls }];
  }

  function onDragOver(e: DragEvent) {
    e.preventDefault();
    isDragging = true;
  }
  function onDragLeave() { isDragging = false; }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    isDragging = false;
    const file = e.dataTransfer?.files[0];
    if (file) loadFile(file);
  }
  function onFileInput(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (file) loadFile(file);
  }

  async function loadFile(file: File) {
    pendingParsed  = null;
    preview        = null;
    importLog      = [];
    importProgress = 10;

    logImport(`▸ Loading ${file.name} (${fmtBytes(file.size)})…`, 'info');

    try {
      const form = new FormData();
      form.append('file', file);

      const resp = await fetch('/api/backup/preview', { method: 'POST', body: form });
      importProgress = 65;
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }

      const prev = await resp.json() as PreviewResult;
      importProgress = 90;

      // Also parse locally for restore
      const buf = await file.arrayBuffer();
      let raw: string;
      if (file.name.endsWith('.gz')) {
        logImport('▸ Decompressing…', 'info');
        const ds  = new DecompressionStream('gzip');
        const out = new Response(new Blob([buf]).stream().pipeThrough(ds));
        raw = await out.text();
      } else {
        raw = new TextDecoder().decode(buf);
      }
      pendingParsed = JSON.parse(raw);

      importProgress = 100;
      logImport(
        `✓ Preview loaded — checksum ${prev.intact ? '✓ OK' : '✗ MISMATCH'}`,
        prev.intact ? 'ok' : 'warn'
      );
      preview = prev;
    } catch (e: any) {
      logImport(`✗ Failed: ${e.message}`, 'err');
      importProgress = 0;
    }
  }

  async function doRestore() {
    if (!pendingParsed) return;
    restoreRunning = true;
    importLog      = [];
    importProgress = 5;

    logImport(dryRun ? '▸ Dry run — no data will be written…' : '▸ Restoring…', 'info');

    try {
      const resp = await fetch(`/api/backup/import${dryRun ? '?dry_run=true' : ''}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pendingParsed),
      });
      importProgress = 70;
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }

      const result = await resp.json() as RestoreResult;
      importProgress = 90;

      const pgRes = result.sections?.postgres ?? {};
      for (const [section, info] of Object.entries(pgRes)) {
        const n   = info.restored ?? info.upserted ?? '?';
        const cls = info.error ? 'err' : 'ok';
        logImport(
          info.error ? `✗ ${section}: ${info.error}` : `✓ ${section}: ${n} row(s)${dryRun ? ' (dry run)' : ' restored'}`,
          cls
        );
      }
      const rdRes = result.sections?.redis ?? {};
      for (const [key, st] of Object.entries(rdRes)) {
        const cls = st.startsWith('error') ? 'err' : st === 'skipped (was null)' ? 'warn' : 'ok';
        logImport(`${cls === 'ok' ? '✓' : '!'} redis ${key}: ${st}`, cls);
      }

      const brData = result.browser ?? pendingParsed.browser ?? {};
      let brCount = 0;
      for (const [k, v] of Object.entries(brData)) {
        if (v != null && !dryRun) { localStorage.setItem(k, v as string); brCount++; }
      }
      if (brCount > 0) logImport(`✓ ${brCount} browser preference(s) restored`, 'ok');

      importProgress = 100;
      if (dryRun) {
        logImport('✓ Dry run complete — no data was written', 'ok');
        logImport('  Uncheck "Dry run first" and click Restore to proceed', 'info');
      } else {
        logImport(`✓ Restore complete`, 'ok');
        await loadStatus();
      }
    } catch (e: any) {
      logImport(`✗ Restore failed: ${e.message}`, 'err');
      importProgress = 0;
    } finally {
      restoreRunning = false;
    }
  }

  function clearImport() {
    pendingParsed  = null;
    preview        = null;
    importLog      = [];
    importProgress = 0;
  }

  // ─── Helpers ─────────────────────────────────────────────────────────

  function triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a   = Object.assign(document.createElement('a'), { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }

  function fmtBytes(b: number): string {
    if (b < 1024)       return b + ' B';
    if (b < 1_048_576)  return (b / 1024).toFixed(1) + ' KB';
    return (b / 1_048_576).toFixed(1) + ' MB';
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

  // ─── Derived preview rows ────────────────────────────────────────────

  interface PreviewRow { section: string; subsection: string; content: string; status: 'ok' | 'warn' | 'err' | 'info' }

  let previewRows = $derived<PreviewRow[]>(() => {
    if (!preview) return [];
    const rows: PreviewRow[] = [];
    const pg = preview.sections?.postgres ?? {};
    for (const [k, v] of Object.entries(pg)) {
      const rows_n = typeof v === 'number' ? v : (v as any)?.rows ?? '?';
      rows.push({ section: 'postgres', subsection: k.replace(/_/g, ' '), content: `${rows_n} row(s)`, status: rows_n > 0 ? 'ok' : 'warn' });
    }
    const rd = preview.sections?.redis ?? {};
    for (const [k, v] of Object.entries(rd)) {
      rows.push({ section: 'redis', subsection: k, content: String(v), status: v === 'present' ? 'ok' : 'warn' });
    }
    const br = preview.sections?.browser ?? {};
    const brN = Object.keys(br).length;
    rows.push({ section: 'browser', subsection: 'preferences', content: `${brN} key(s)`, status: brN > 0 ? 'ok' : 'warn' });
    const m = preview.meta;
    if (m?.checksum) rows.push({ section: 'manifest', subsection: 'checksum', content: m.checksum.slice(0, 12) + '…', status: preview.intact ? 'ok' : 'err' });
    if (m?.version)  rows.push({ section: 'manifest', subsection: 'version',  content: m.version, status: 'info' });
    if (m?.created_at) rows.push({ section: 'manifest', subsection: 'created', content: fmtDate(m.created_at), status: 'info' });
    return rows;
  });

  onMount(loadStatus);
</script>

<svelte:head>
  <title>Backup — FKS Terminal</title>
</svelte:head>

<div class="page">

  <!-- ─── Status ─────────────────────────────────────────────────────── -->
  <Panel title="Current State">
    {#snippet header()}
      <button class="ghost-btn" onclick={loadStatus} disabled={statusLoading}>↻ Refresh</button>
    {/snippet}

    {#if statusLoading}
      <div class="meta-row">
        <Skeleton width="120px" height="16px" />
        <Skeleton width="80px" height="16px" />
        <Skeleton width="100px" height="16px" />
      </div>
    {:else if statusError}
      <p class="err-text">{statusError}</p>
    {:else if status}
      <div class="meta-row">
        {#each Object.entries(status.row_counts ?? {}) as [k, v]}
          <span class="meta-item"><strong>{v ?? '—'}</strong> {k.replace(/_/g, ' ')}</span>
        {/each}
        <span class="meta-item meta-right">
          {#if status.last_backup_at}
            Last backup <strong>{fmtDate(status.last_backup_at)}</strong>
          {:else}
            <span class="amber">No backup recorded yet</span>
          {/if}
        </span>
      </div>
    {/if}
  </Panel>

  <!-- ─── Export ─────────────────────────────────────────────────────── -->
  <Panel title="Export Backup">
    <p class="hint">
      Creates a single <code>.json</code> file containing server state (Postgres + Redis)
      and browser state (chart preferences, dashboard layout). Enough to fully restore on a fresh install.
    </p>

    <div class="checks">
      <label class="check"><input type="checkbox" bind:checked={exportPostgres}> Database (journal, positions, alerts)</label>
      <label class="check"><input type="checkbox" bind:checked={exportRedis}>    Redis config (gate, circuit breaker)</label>
      <label class="check"><input type="checkbox" bind:checked={exportBrowser}>  Browser preferences (charts, layout)</label>
      <label class="check"><input type="checkbox" bind:checked={exportCompress}> Compress output (<code>.json.gz</code>)</label>
    </div>

    <div class="btn-row">
      <button class="action-btn primary" onclick={doExport} disabled={exportRunning}>
        {exportRunning ? '…' : '⬇'} Download backup
      </button>
      {#if exportHint}<span class="hint-text">{exportHint}</span>{/if}
    </div>

    {#if exportRunning || exportProgress > 0}
      <ProgressBar value={exportProgress} max={100} color="var(--cyan)" />
    {/if}

    {#if exportLog.length}
      <div class="log-console">
        {#each exportLog as line}
          <span class="log-{line.cls}">{line.msg}</span>
        {/each}
      </div>
    {/if}
  </Panel>

  <!-- ─── Import ─────────────────────────────────────────────────────── -->
  <Panel title="Import / Restore">
    <p class="hint">
      Upload a backup file to preview its contents or fully restore.
      Restore uses <code>INSERT … ON CONFLICT DO UPDATE</code> — existing rows are updated,
      nothing is deleted. Redis keys are overwritten.
    </p>

    <!-- Drop zone -->
    <div
      class="drop-zone"
      class:drag={isDragging}
      role="button"
      tabindex="0"
      onclick={() => document.getElementById('file-input')?.click()}
      onkeydown={(e) => e.key === 'Enter' && document.getElementById('file-input')?.click()}
      ondragover={onDragOver}
      ondragleave={onDragLeave}
      ondrop={onDrop}
    >
      <input id="file-input" type="file" accept=".json,.gz" oninput={onFileInput} />
      Drop a <code>.json</code> or <code>.json.gz</code> backup here, or click to browse
    </div>

    {#if importRunning || importProgress > 0}
      <ProgressBar value={importProgress} max={100} color="var(--green)" />
    {/if}

    {#if importLog.length}
      <div class="log-console">
        {#each importLog as line}
          <span class="log-{line.cls}">{line.msg}</span>
        {/each}
      </div>
    {/if}

    <!-- Preview table -->
    {#if preview && previewRows.length}
      <div class="preview-wrap">
        <table class="preview-table">
          <thead>
            <tr><th>Section</th><th>Subsection</th><th>Content</th><th>Status</th></tr>
          </thead>
          <tbody>
            {#each previewRows as row}
              <tr>
                <td class="dim">{row.section}</td>
                <td>{row.subsection}</td>
                <td class="mono">{row.content}</td>
                <td><Badge variant={row.status === 'ok' ? 'green' : row.status === 'err' ? 'red' : row.status === 'warn' ? 'amber' : 'default'}>{row.status}</Badge></td>
              </tr>
            {/each}
          </tbody>
        </table>

        <div class="warn-box">
          ⚠ Restore overwrites matching records. This cannot be undone without another backup.
        </div>

        <div class="btn-row" style="margin-top: 12px;">
          <button class="action-btn success" onclick={doRestore} disabled={restoreRunning || !pendingParsed}>
            {restoreRunning ? '…' : '✓'} Restore
          </button>
          <button class="action-btn ghost" onclick={clearImport}>✕ Cancel</button>
          <label class="check" style="margin-left: 4px;">
            <input type="checkbox" bind:checked={dryRun}> Dry run first
          </label>
        </div>
      </div>
    {/if}
  </Panel>

</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 10px;
    gap: 10px;
    overflow-y: auto;
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
  }

  .hint {
    font-size: 11px;
    color: var(--t2);
    margin-bottom: 14px;
    line-height: 1.7;
  }
  .hint code {
    font-family: inherit;
    font-size: 10px;
    background: var(--bg3);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    padding: 1px 5px;
    color: var(--cyan);
  }

  /* ── Status meta row ──────────────────────────────────── */
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 8px 0;
    font-size: 11px;
  }
  .meta-item { color: var(--t2); }
  .meta-item strong { color: var(--t1); font-weight: 500; }
  .meta-right { margin-left: auto; }
  .amber { color: var(--amber); }
  .err-text { font-size: 11px; color: var(--red); padding: 8px 0; }

  /* ── Checkboxes ───────────────────────────────────────── */
  .checks {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 24px;
    margin-bottom: 14px;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    color: var(--t1);
    cursor: pointer;
  }
  .check input[type=checkbox] {
    width: 13px;
    height: 13px;
    accent-color: var(--cyan);
    flex-shrink: 0;
  }

  /* ── Buttons ─────────────────────────────────────────── */
  .btn-row {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .action-btn {
    padding: 6px 16px;
    border-radius: var(--r-md);
    font-size: 11px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    border: none;
    transition: opacity 0.15s;
  }
  .action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .action-btn:hover:not(:disabled) { opacity: 0.82; }
  .action-btn.primary { background: var(--cyan-dim); color: var(--cyan); border: 1px solid var(--cyan-brd); }
  .action-btn.success { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-brd); }
  .action-btn.ghost   { background: var(--bg3); color: var(--t2); border: 1px solid var(--b2); }
  .ghost-btn {
    font-family: inherit;
    font-size: 10px;
    background: none;
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t2);
    padding: 2px 8px;
    cursor: pointer;
  }
  .ghost-btn:hover { color: var(--t1); }
  .hint-text { font-size: 10px; color: var(--t3); }

  /* ── Drop zone ───────────────────────────────────────── */
  .drop-zone {
    border: 2px dashed var(--b2);
    border-radius: var(--r-md);
    padding: 32px 20px;
    text-align: center;
    cursor: pointer;
    font-size: 11px;
    color: var(--t2);
    transition: border-color 0.2s, background 0.2s;
    margin-bottom: 10px;
  }
  .drop-zone:hover { border-color: var(--b3); }
  .drop-zone.drag  { border-color: var(--cyan); background: var(--cyan-dim); }
  .drop-zone code  {
    font-family: inherit; font-size: 10px;
    background: var(--bg3); border: 1px solid var(--b2);
    border-radius: var(--r); padding: 1px 5px; color: var(--cyan);
  }
  .drop-zone input { display: none; }

  /* ── Log console ─────────────────────────────────────── */
  .log-console {
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r-md);
    padding: 10px 14px;
    margin-top: 10px;
    font-size: 11px;
    font-family: inherit;
    line-height: 2;
    max-height: 200px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .log-ok   { color: var(--green); }
  .log-warn { color: var(--amber); }
  .log-err  { color: var(--red); }
  .log-info { color: var(--cyan); }

  /* ── Preview table ───────────────────────────────────── */
  .preview-wrap { margin-top: 14px; }
  .preview-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    margin-bottom: 12px;
  }
  .preview-table th {
    text-align: left;
    padding: 5px 8px;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--t3);
    border-bottom: 1px solid var(--b2);
  }
  .preview-table td {
    padding: 5px 8px;
    color: var(--t1);
    border-bottom: 1px solid var(--b1);
  }
  .preview-table tr:last-child td { border-bottom: none; }
  .dim  { color: var(--t2); }
  .mono { font-family: inherit; }

  /* ── Warning box ─────────────────────────────────────── */
  .warn-box {
    padding: 10px 12px;
    background: var(--amber-dim);
    border: 1px solid var(--amber-brd);
    border-radius: var(--r-md);
    font-size: 11px;
    color: var(--amber);
    line-height: 1.6;
  }
</style>
