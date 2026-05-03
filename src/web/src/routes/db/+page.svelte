<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$api/client';
  import Badge from '$components/ui/Badge.svelte';
  import InnerTabs from '$components/ui/InnerTabs.svelte';
  import Panel from '$components/ui/Panel.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';

  // ─── Types ──────────────────────────────────────────────────────────

  // Redis
  interface RedisInfoResponse {
    [section: string]: Record<string, string>;
  }

  interface RedisScanResponse {
    cursor: string;
    keys: string[];
    count: number;
  }

  interface RedisKeyValue {
    type: string;
    value: unknown;
    ttl?: number;
  }

  interface RedisPubSubResponse {
    channels: string[];
    total_channels: number;
  }

  interface RedisPattern {
    pattern: string;
    count: number;
    description: string;
  }

  // Postgres
  interface PgTable {
    schema: string;
    table: string;
    rows: number;
    size: string;
  }

  interface PgTableDetail {
    columns: { name: string; type: string; nullable: boolean; default_value: string | null }[];
    sample_rows: Record<string, unknown>[];
  }

  interface PgQueryResult {
    columns: string[];
    rows: Record<string, unknown>[];
    row_count: number;
    elapsed_ms?: number;
  }

  // QuestDB
  interface QdbTable {
    name: string;
    partitioned: boolean;
  }

  interface QdbTableDetail {
    columns: { name: string; type: string }[];
  }

  interface QdbQueryResult {
    columns: string[];
    rows: Record<string, unknown>[];
    row_count: number;
    elapsed_ms: number;
  }

  // Janus
  interface JanusBrainHealth {
    healthy: boolean;
    boot_passed: boolean;
    components: Record<string, { alive: boolean; last_seen?: string }>;
    uptime_seconds?: number;
  }

  interface JanusServiceStatus {
    name: string;
    status: string;
    uptime?: number;
  }

  // ─── Tab State ──────────────────────────────────────────────────────
  const dbTabs = [
    { id: 'redis', label: 'Redis' },
    { id: 'postgres', label: 'Postgres' },
    { id: 'questdb', label: 'QuestDB' },
    { id: 'janus', label: 'Janus' },
  ];

  let activeTab = $state('redis');

  function onTabChange(id: string) {
    activeTab = id;
    loadTabData(id);
  }

  // ─── Redis State ────────────────────────────────────────────────────
  let redisInfo = $state<RedisInfoResponse | null>(null);
  let redisInfoLoading = $state(true);
  let redisInfoError = $state('');

  let redisScanPattern = $state('*');
  let redisScanResult = $state<RedisScanResponse | null>(null);
  let redisScanLoading = $state(false);
  let redisScanError = $state('');

  let redisSelectedKey = $state('');
  let redisKeyValue = $state<RedisKeyValue | null>(null);
  let redisKeyLoading = $state(false);
  let redisKeyError = $state('');

  let redisPubSub = $state<RedisPubSubResponse | null>(null);
  let redisPubSubLoading = $state(true);
  let redisPubSubError = $state('');

  let redisPatterns = $state<RedisPattern[]>([]);
  let redisPatternsLoading = $state(true);
  let redisPatternsError = $state('');

  // ─── Postgres State ─────────────────────────────────────────────────
  let pgTables = $state<PgTable[]>([]);
  let pgTablesLoading = $state(true);
  let pgTablesError = $state('');

  let pgSelectedTable = $state<{ schema: string; table: string } | null>(null);
  let pgTableDetail = $state<PgTableDetail | null>(null);
  let pgTableDetailLoading = $state(false);
  let pgTableDetailError = $state('');

  let pgQuery = $state('SELECT 1;');
  let pgQueryResult = $state<PgQueryResult | null>(null);
  let pgQueryLoading = $state(false);
  let pgQueryError = $state('');

  // ─── QuestDB State ──────────────────────────────────────────────────
  let qdbTables = $state<QdbTable[]>([]);
  let qdbTablesLoading = $state(true);
  let qdbTablesError = $state('');

  let qdbSelectedTable = $state('');
  let qdbTableDetail = $state<QdbTableDetail | null>(null);
  let qdbTableDetailLoading = $state(false);
  let qdbTableDetailError = $state('');

  let qdbQuery = $state('SELECT 1;');
  let qdbQueryResult = $state<QdbQueryResult | null>(null);
  let qdbQueryLoading = $state(false);
  let qdbQueryError = $state('');

  // ─── Janus State ────────────────────────────────────────────────────
  let janusHealth = $state<JanusBrainHealth | null>(null);
  let janusHealthLoading = $state(true);
  let janusHealthError = $state('');

  let janusServices = $state<JanusServiceStatus[]>([]);
  let janusServicesLoading = $state(true);
  let janusServicesError = $state('');

  // ─── Lazy-load tracking ─────────────────────────────────────────────
  let redisLoaded = $state(false);
  let postgresLoaded = $state(false);
  let questdbLoaded = $state(false);
  let janusLoaded = $state(false);

  // ─── Redis Key Stats (derived) ──────────────────────────────────────
  let redisVersion = $derived(redisInfo?.server?.redis_version ?? '—');
  let redisMemory = $derived(redisInfo?.memory?.used_memory_human ?? '—');
  let redisClients = $derived(redisInfo?.clients?.connected_clients ?? '—');
  let redisConnsReceived = $derived(redisInfo?.stats?.total_connections_received ?? '—');
  let redisHits = $derived(redisInfo?.stats?.keyspace_hits ?? '—');
  let redisMisses = $derived(redisInfo?.stats?.keyspace_misses ?? '—');

  // ─── Redis API ──────────────────────────────────────────────────────

  async function loadRedisInfo() {
    redisInfoLoading = true;
    redisInfoError = '';
    try {
      redisInfo = await api.get<RedisInfoResponse>('/api/db/redis/info');
    } catch (e: any) {
      redisInfoError = e.message || 'Failed to load Redis info';
    } finally {
      redisInfoLoading = false;
    }
  }

  async function scanRedisKeys() {
    redisScanLoading = true;
    redisScanError = '';
    redisSelectedKey = '';
    redisKeyValue = null;
    try {
      const pattern = encodeURIComponent(redisScanPattern || '*');
      redisScanResult = await api.get<RedisScanResponse>(`/api/db/redis/scan?pattern=${pattern}&count=100`);
    } catch (e: any) {
      redisScanError = e.message || 'Scan failed';
    } finally {
      redisScanLoading = false;
    }
  }

  async function loadRedisKey(key: string) {
    redisSelectedKey = key;
    redisKeyLoading = true;
    redisKeyError = '';
    redisKeyValue = null;
    try {
      redisKeyValue = await api.get<RedisKeyValue>(`/api/db/redis/get/${encodeURIComponent(key)}`);
    } catch (e: any) {
      redisKeyError = e.message || 'Failed to load key';
    } finally {
      redisKeyLoading = false;
    }
  }

  async function loadRedisPubSub() {
    redisPubSubLoading = true;
    redisPubSubError = '';
    try {
      redisPubSub = await api.get<RedisPubSubResponse>('/api/db/redis/pubsub');
    } catch (e: any) {
      redisPubSubError = e.message || 'Failed to load pub/sub channels';
    } finally {
      redisPubSubLoading = false;
    }
  }

  async function loadRedisPatterns() {
    redisPatternsLoading = true;
    redisPatternsError = '';
    try {
      redisPatterns = await api.get<RedisPattern[]>('/api/db/redis/patterns');
    } catch (e: any) {
      redisPatternsError = e.message || 'Failed to load patterns';
    } finally {
      redisPatternsLoading = false;
    }
  }

  function onPatternClick(pattern: string) {
    redisScanPattern = pattern;
    scanRedisKeys();
  }

  // ─── Postgres API ───────────────────────────────────────────────────

  async function loadPgTables() {
    pgTablesLoading = true;
    pgTablesError = '';
    try {
      pgTables = await api.get<PgTable[]>('/api/db/postgres/tables');
    } catch (e: any) {
      pgTablesError = e.message || 'Failed to load tables';
    } finally {
      pgTablesLoading = false;
    }
  }

  async function loadPgTableDetail(schema: string, table: string) {
    pgSelectedTable = { schema, table };
    pgTableDetailLoading = true;
    pgTableDetailError = '';
    pgTableDetail = null;
    try {
      pgTableDetail = await api.get<PgTableDetail>(
        `/api/db/postgres/tables/${encodeURIComponent(schema)}/${encodeURIComponent(table)}`
      );
    } catch (e: any) {
      pgTableDetailError = e.message || 'Failed to load table detail';
    } finally {
      pgTableDetailLoading = false;
    }
  }

  async function runPgQuery() {
    if (!pgQuery.trim()) return;
    pgQueryLoading = true;
    pgQueryError = '';
    pgQueryResult = null;
    try {
      pgQueryResult = await api.post<PgQueryResult>('/api/db/postgres/query', { query: pgQuery });
    } catch (e: any) {
      pgQueryError = e.message || 'Query failed';
    } finally {
      pgQueryLoading = false;
    }
  }

  function handlePgKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runPgQuery();
    }
  }

  // ─── QuestDB API ───────────────────────────────────────────────────

  async function loadQdbTables() {
    qdbTablesLoading = true;
    qdbTablesError = '';
    try {
      qdbTables = await api.get<QdbTable[]>('/api/db/questdb/tables');
    } catch (e: any) {
      qdbTablesError = e.message || 'Failed to load tables';
    } finally {
      qdbTablesLoading = false;
    }
  }

  async function loadQdbTableDetail(name: string) {
    qdbSelectedTable = name;
    qdbTableDetailLoading = true;
    qdbTableDetailError = '';
    qdbTableDetail = null;
    try {
      qdbTableDetail = await api.get<QdbTableDetail>(`/api/db/questdb/table/${encodeURIComponent(name)}`);
    } catch (e: any) {
      qdbTableDetailError = e.message || 'Failed to load table detail';
    } finally {
      qdbTableDetailLoading = false;
    }
  }

  async function runQdbQuery() {
    if (!qdbQuery.trim()) return;
    qdbQueryLoading = true;
    qdbQueryError = '';
    qdbQueryResult = null;
    try {
      qdbQueryResult = await api.post<QdbQueryResult>('/api/db/questdb/query', { query: qdbQuery, limit: 200 });
    } catch (e: any) {
      qdbQueryError = e.message || 'Query failed';
    } finally {
      qdbQueryLoading = false;
    }
  }

  function handleQdbKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runQdbQuery();
    }
  }

  // ─── Helpers ────────────────────────────────────────────────────────

  function formatValue(val: unknown): string {
    if (val === null || val === undefined) return 'null';
    if (typeof val === 'object') return JSON.stringify(val, null, 2);
    return String(val);
  }

  function truncate(s: string, max: number): string {
    return s.length > max ? s.slice(0, max) + '…' : s;
  }

  function formatUptime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${Math.floor(s)}s`;
    return `${Math.floor(s)}s`;
  }

  // ─── Janus API ─────────────────────────────────────────────────────

  async function loadJanusHealth() {
    janusHealthLoading = true;
    janusHealthError = '';
    try {
      janusHealth = await api.get<JanusBrainHealth>('/api/janus/brain/health');
    } catch (e: any) {
      janusHealthError = e.message || 'Failed to load brain health';
    } finally {
      janusHealthLoading = false;
    }
  }

  async function loadJanusServices() {
    janusServicesLoading = true;
    janusServicesError = '';
    try {
      janusServices = await api.get<JanusServiceStatus[]>('/api/janus/services');
    } catch (e: any) {
      janusServicesError = e.message || 'Failed to load Janus services';
    } finally {
      janusServicesLoading = false;
    }
  }

  // ─── Lazy Tab Loader ───────────────────────────────────────────────

  function loadTabData(tab: string, force = false) {
    switch (tab) {
      case 'redis':
        if (!redisLoaded || force) {
          redisLoaded = true;
          loadRedisInfo();
          loadRedisPubSub();
          loadRedisPatterns();
        }
        break;
      case 'postgres':
        if (!postgresLoaded || force) {
          postgresLoaded = true;
          loadPgTables();
        }
        break;
      case 'questdb':
        if (!questdbLoaded || force) {
          questdbLoaded = true;
          loadQdbTables();
        }
        break;
      case 'janus':
        if (!janusLoaded || force) {
          janusLoaded = true;
          loadJanusHealth();
          loadJanusServices();
        }
        break;
    }
  }

  // ─── Lifecycle ──────────────────────────────────────────────────────

  onMount(() => {
    loadTabData(activeTab);
  });
</script>

<svelte:head>
  <title>DB Explorer — FKS Terminal</title>
</svelte:head>

<!-- ═══════════════════════════════════════════════════════════════════
     MARKUP
     ═══════════════════════════════════════════════════════════════════ -->
<div class="page">
  <div class="pane">

    <!-- Tabs -->
    <div class="tabs-bar">
      <InnerTabs tabs={dbTabs} active={activeTab} onchange={onTabChange} />
    </div>

    <!-- ═══════════════════════════════════════════════════════════════
         REDIS TAB
         ═══════════════════════════════════════════════════════════════ -->
    {#if activeTab === 'redis'}
      <div class="tab-content">

        <!-- Panel 1: Redis Info -->
        <Panel title="Redis Info">
          {#snippet header()}
            <button class="btn-ghost" onclick={() => loadRedisInfo()}>↻ Refresh</button>
          {/snippet}
          {#if redisInfoLoading}
            <Skeleton lines={4} height="12px" />
          {:else if redisInfoError}
            <span class="error-text">{redisInfoError}</span>
          {:else}
            <div class="stat-grid">
              <div class="stat-item">
                <span class="stat-label">Version</span>
                <span class="stat-value mono">{redisVersion}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Memory</span>
                <span class="stat-value mono">{redisMemory}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Clients</span>
                <span class="stat-value mono">{redisClients}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Conns Received</span>
                <span class="stat-value mono">{redisConnsReceived}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Keyspace Hits</span>
                <span class="stat-value mono hit">{redisHits}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Keyspace Misses</span>
                <span class="stat-value mono miss">{redisMisses}</span>
              </div>
            </div>

            <!-- Collapsible raw sections -->
            {#if redisInfo}
              <details class="raw-details">
                <summary class="raw-summary">All Sections</summary>
                <div class="raw-sections">
                  {#each Object.entries(redisInfo) as [section, data]}
                    <details class="section-details">
                      <summary class="section-summary">{section}</summary>
                      <div class="section-kv">
                        {#each Object.entries(data) as [k, v]}
                          <div class="kv-row">
                            <span class="kv-key">{k}</span>
                            <span class="kv-val mono">{v}</span>
                          </div>
                        {/each}
                      </div>
                    </details>
                  {/each}
                </div>
              </details>
            {/if}
          {/if}
        </Panel>

        <!-- Panel 2: Key Browser -->
        <div style="flex:2; min-height:0;">
          <Panel title="Key Browser">
            {#snippet header()}
              {#if redisScanResult}
                <Badge variant="default">{redisScanResult.count} keys</Badge>
              {/if}
            {/snippet}
            <div style="display:flex; flex-direction:column; gap:6px; height:100%;">
              <!-- Scan controls -->
              <div class="scan-bar">
                <input
                  class="scan-input mono"
                  type="text"
                  placeholder="Pattern (e.g. fks:*)"
                  bind:value={redisScanPattern}
                  onkeydown={(e) => { if (e.key === 'Enter') scanRedisKeys(); }}
                />
                <button class="btn-primary" onclick={() => scanRedisKeys()} disabled={redisScanLoading}>
                  {redisScanLoading ? '…' : 'Scan'}
                </button>
              </div>

              {#if redisScanError}
                <span class="error-text">{redisScanError}</span>
              {/if}

              <div class="key-browser-split">
                <!-- Key list -->
                <div class="key-list-wrap">
                  {#if redisScanLoading}
                    <Skeleton lines={6} height="12px" />
                  {:else if redisScanResult && redisScanResult.keys.length > 0}
                    <div class="key-list">
                      {#each redisScanResult.keys as key (key)}
                        <button
                          class="key-item"
                          class:active={key === redisSelectedKey}
                          onclick={() => loadRedisKey(key)}
                        >
                          {truncate(key, 60)}
                        </button>
                      {/each}
                    </div>
                  {:else if redisScanResult}
                    <div class="empty-state">No keys found for pattern "{redisScanPattern}"</div>
                  {:else}
                    <div class="empty-state">Enter a pattern and click Scan</div>
                  {/if}
                </div>

                <!-- Key value display -->
                <div class="key-value-wrap">
                  {#if redisKeyLoading}
                    <Skeleton lines={4} height="12px" />
                  {:else if redisKeyError}
                    <span class="error-text">{redisKeyError}</span>
                  {:else if redisKeyValue}
                    <div class="key-value-header">
                      <span class="mono dim" style="font-size:10px;">{redisSelectedKey}</span>
                      <Badge variant="cyan">{redisKeyValue.type}</Badge>
                      {#if redisKeyValue.ttl !== undefined && redisKeyValue.ttl >= 0}
                        <Badge variant="amber">TTL {redisKeyValue.ttl}s</Badge>
                      {/if}
                    </div>
                    <pre class="value-pre">{formatValue(redisKeyValue.value)}</pre>
                  {:else}
                    <div class="empty-state">Select a key to view its value</div>
                  {/if}
                </div>
              </div>
            </div>
          </Panel>
        </div>

        <!-- Row with Pub/Sub + Patterns side-by-side -->
        <div class="panel-row">
          <!-- Panel 3: Pub/Sub Channels -->
          <div style="flex:1; min-height:0;">
            <Panel title="Pub/Sub Channels">
              {#snippet header()}
                {#if redisPubSub}
                  <Badge variant="default">{redisPubSub.total_channels}</Badge>
                {/if}
                <button class="btn-ghost" onclick={() => loadRedisPubSub()}>↻</button>
              {/snippet}
              {#if redisPubSubLoading}
                <Skeleton lines={3} height="12px" />
              {:else if redisPubSubError}
                <span class="error-text">{redisPubSubError}</span>
              {:else if redisPubSub && redisPubSub.channels.length > 0}
                <div class="channel-list">
                  {#each redisPubSub.channels as ch (ch)}
                    <div class="channel-item mono">{ch}</div>
                  {/each}
                </div>
              {:else}
                <div class="empty-state">No active channels</div>
              {/if}
            </Panel>
          </div>

          <!-- Panel 4: FKS Key Patterns -->
          <div style="flex:1.5; min-height:0;">
            <Panel title="FKS Key Patterns" noPad>
              {#snippet header()}
                <button class="btn-ghost" onclick={() => loadRedisPatterns()}>↻</button>
              {/snippet}
              {#if redisPatternsLoading}
                <div style="padding:8px;">
                  <Skeleton lines={4} height="12px" />
                </div>
              {:else if redisPatternsError}
                <div style="padding:8px;">
                  <span class="error-text">{redisPatternsError}</span>
                </div>
              {:else if redisPatterns.length > 0}
                <table class="db-table">
                  <thead>
                    <tr>
                      <th>Pattern</th>
                      <th class="r">Count</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each redisPatterns as p (p.pattern)}
                      <tr class="clickable" onclick={() => onPatternClick(p.pattern)}>
                        <td class="mono">{p.pattern}</td>
                        <td class="r mono">{p.count}</td>
                        <td class="dim">{p.description}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {:else}
                <div class="empty-state" style="padding:8px;">No patterns found</div>
              {/if}
            </Panel>
          </div>
        </div>
      </div>

    <!-- ═══════════════════════════════════════════════════════════════
         POSTGRES TAB
         ═══════════════════════════════════════════════════════════════ -->
    {:else if activeTab === 'postgres'}
      <div class="tab-content">

        <!-- Panel 1: Tables -->
        <div style="flex:1; min-height:0;">
          <Panel title="Tables" noPad fill>
            {#snippet header()}
              {#if pgTables.length > 0}
                <Badge variant="default">{pgTables.length} tables</Badge>
              {/if}
              <button class="btn-ghost" onclick={() => loadPgTables()}>↻ Refresh</button>
            {/snippet}
            {#if pgTablesLoading}
              <div style="padding:8px;">
                <Skeleton lines={5} height="12px" />
              </div>
            {:else if pgTablesError}
              <div style="padding:8px;">
                <span class="error-text">{pgTablesError}</span>
              </div>
            {:else if pgTables.length > 0}
              <div class="table-scroll">
                <table class="db-table">
                  <thead>
                    <tr>
                      <th>Schema</th>
                      <th>Table</th>
                      <th class="r">Rows</th>
                      <th class="r">Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each pgTables as t (`${t.schema}.${t.table}`)}
                      <tr
                        class="clickable"
                        class:selected={pgSelectedTable?.schema === t.schema && pgSelectedTable?.table === t.table}
                        onclick={() => loadPgTableDetail(t.schema, t.table)}
                      >
                        <td class="dim">{t.schema}</td>
                        <td class="mono">{t.table}</td>
                        <td class="r mono">{t.rows.toLocaleString()}</td>
                        <td class="r mono">{t.size}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <div class="empty-state" style="padding:8px;">No tables found</div>
            {/if}

            <!-- Table detail sub-panel -->
            {#if pgSelectedTable}
              <div class="sub-panel">
                <div class="sub-panel-head">
                  <span class="panel-lbl">{pgSelectedTable.schema}.{pgSelectedTable.table}</span>
                  {#if pgTableDetail}
                    <Badge variant="cyan">{pgTableDetail.columns.length} cols</Badge>
                  {/if}
                </div>
                <div class="sub-panel-body">
                  {#if pgTableDetailLoading}
                    <Skeleton lines={3} height="12px" />
                  {:else if pgTableDetailError}
                    <span class="error-text">{pgTableDetailError}</span>
                  {:else if pgTableDetail}
                    <!-- Column schema -->
                    <div class="sub-section-label">Columns</div>
                    <table class="db-table compact">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Type</th>
                          <th>Nullable</th>
                          <th>Default</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each pgTableDetail.columns as col (col.name)}
                          <tr>
                            <td class="mono">{col.name}</td>
                            <td class="mono dim">{col.type}</td>
                            <td>{col.nullable ? '✓' : '—'}</td>
                            <td class="mono dim">{col.default_value ?? '—'}</td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>

                    <!-- Sample rows -->
                    {#if pgTableDetail.sample_rows.length > 0}
                      <div class="sub-section-label" style="margin-top:8px;">Sample Rows ({pgTableDetail.sample_rows.length})</div>
                      <div class="sample-scroll">
                        <table class="db-table compact">
                          <thead>
                            <tr>
                              {#each Object.keys(pgTableDetail.sample_rows[0]) as colName}
                                <th>{colName}</th>
                              {/each}
                            </tr>
                          </thead>
                          <tbody>
                            {#each pgTableDetail.sample_rows as row, i (i)}
                              <tr>
                                {#each Object.values(row) as val}
                                  <td class="mono">{truncate(formatValue(val), 40)}</td>
                                {/each}
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      </div>
                    {/if}
                  {/if}
                </div>
              </div>
            {/if}
          </Panel>
        </div>

        <!-- Panel 2: Ad-hoc Query Runner -->
        <div style="flex:1; min-height:0;">
          <Panel title="Query Runner">
            {#snippet header()}
              <span class="dim" style="font-size:9px;">SELECT only · Ctrl+Enter to run</span>
              {#if pgQueryResult}
                <Badge variant="green" >{pgQueryResult.row_count} rows</Badge>
                {#if pgQueryResult.elapsed_ms !== undefined}
                  <Badge variant="cyan">{pgQueryResult.elapsed_ms}ms</Badge>
                {/if}
              {/if}
            {/snippet}
            <div style="display:flex; flex-direction:column; gap:6px; height:100%;">
              <div class="query-area">
                <textarea
                  class="query-input mono"
                  bind:value={pgQuery}
                  placeholder="SELECT * FROM ..."
                  rows={4}
                  onkeydown={handlePgKeydown}
                ></textarea>
                <div class="query-actions">
                  <button class="btn-primary" onclick={() => runPgQuery()} disabled={pgQueryLoading}>
                    {pgQueryLoading ? 'Running…' : '▶ Run'}
                  </button>
                </div>
              </div>

              {#if pgQueryError}
                <div class="error-box mono">{pgQueryError}</div>
              {/if}

              {#if pgQueryLoading}
                <Skeleton lines={4} height="12px" />
              {:else if pgQueryResult && pgQueryResult.columns.length > 0}
                <div class="result-scroll">
                  <table class="db-table result-table">
                    <thead>
                      <tr>
                        {#each pgQueryResult.columns as col}
                          <th>{col}</th>
                        {/each}
                      </tr>
                    </thead>
                    <tbody>
                      {#each pgQueryResult.rows as row, i (i)}
                        <tr>
                          {#each pgQueryResult.columns as col}
                            <td class="mono">{truncate(formatValue(row[col]), 60)}</td>
                          {/each}
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {:else if pgQueryResult}
                <div class="empty-state">Query returned no columns</div>
              {/if}
            </div>
          </Panel>
        </div>
      </div>

    <!-- ═══════════════════════════════════════════════════════════════
         QUESTDB TAB
         ═══════════════════════════════════════════════════════════════ -->
    {:else if activeTab === 'questdb'}
      <div class="tab-content">

        <!-- Panel 1: Tables -->
        <div style="flex:1; min-height:0;">
          <Panel title="Tables" noPad fill>
            {#snippet header()}
              {#if qdbTables.length > 0}
                <Badge variant="default">{qdbTables.length} tables</Badge>
              {/if}
              <button class="btn-ghost" onclick={() => loadQdbTables()}>↻ Refresh</button>
            {/snippet}
            {#if qdbTablesLoading}
              <div style="padding:8px;">
                <Skeleton lines={4} height="12px" />
              </div>
            {:else if qdbTablesError}
              <div style="padding:8px;">
                <span class="error-text">{qdbTablesError}</span>
              </div>
            {:else if qdbTables.length > 0}
              <div class="table-scroll">
                <table class="db-table">
                  <thead>
                    <tr>
                      <th>Table</th>
                      <th>Partitioned</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each qdbTables as t (t.name)}
                      <tr
                        class="clickable"
                        class:selected={qdbSelectedTable === t.name}
                        onclick={() => loadQdbTableDetail(t.name)}
                      >
                        <td class="mono">{t.name}</td>
                        <td>
                          {#if t.partitioned}
                            <Badge variant="green">Yes</Badge>
                          {:else}
                            <Badge variant="default">No</Badge>
                          {/if}
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {:else}
              <div class="empty-state" style="padding:8px;">No tables found</div>
            {/if}

            <!-- Table detail sub-panel -->
            {#if qdbSelectedTable}
              <div class="sub-panel">
                <div class="sub-panel-head">
                  <span class="panel-lbl">{qdbSelectedTable}</span>
                  {#if qdbTableDetail}
                    <Badge variant="cyan">{qdbTableDetail.columns.length} cols</Badge>
                  {/if}
                </div>
                <div class="sub-panel-body">
                  {#if qdbTableDetailLoading}
                    <Skeleton lines={3} height="12px" />
                  {:else if qdbTableDetailError}
                    <span class="error-text">{qdbTableDetailError}</span>
                  {:else if qdbTableDetail}
                    <table class="db-table compact">
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th>Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each qdbTableDetail.columns as col (col.name)}
                          <tr>
                            <td class="mono">{col.name}</td>
                            <td class="mono dim">{col.type}</td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  {/if}
                </div>
              </div>
            {/if}
          </Panel>
        </div>

        <!-- Panel 2: Ad-hoc Query Runner -->
        <div style="flex:1; min-height:0;">
          <Panel title="Query Runner">
            {#snippet header()}
              <span class="dim" style="font-size:9px;">Ctrl+Enter to run</span>
              {#if qdbQueryResult}
                <Badge variant="green">{qdbQueryResult.row_count} rows</Badge>
                <Badge variant="cyan">{qdbQueryResult.elapsed_ms}ms</Badge>
              {/if}
            {/snippet}
            <div style="display:flex; flex-direction:column; gap:6px; height:100%;">
              <div class="query-area">
                <textarea
                  class="query-input mono"
                  bind:value={qdbQuery}
                  placeholder="SELECT * FROM ..."
                  rows={4}
                  onkeydown={handleQdbKeydown}
                ></textarea>
                <div class="query-actions">
                  <button class="btn-primary" onclick={() => runQdbQuery()} disabled={qdbQueryLoading}>
                    {qdbQueryLoading ? 'Running…' : '▶ Run'}
                  </button>
                </div>
              </div>

              {#if qdbQueryError}
                <div class="error-box mono">{qdbQueryError}</div>
              {/if}

              {#if qdbQueryLoading}
                <Skeleton lines={4} height="12px" />
              {:else if qdbQueryResult && qdbQueryResult.columns.length > 0}
                <div class="result-scroll">
                  <table class="db-table result-table">
                    <thead>
                      <tr>
                        {#each qdbQueryResult.columns as col}
                          <th>{col}</th>
                        {/each}
                      </tr>
                    </thead>
                    <tbody>
                      {#each qdbQueryResult.rows as row, i (i)}
                        <tr>
                          {#each qdbQueryResult.columns as col}
                            <td class="mono">{truncate(formatValue(row[col]), 60)}</td>
                          {/each}
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {:else if qdbQueryResult}
                <div class="empty-state">Query returned no columns</div>
              {/if}
            </div>
          </Panel>
        </div>
      </div>

    <!-- ═══════════════════════════════════════════════════════════════
         JANUS TAB
         ═══════════════════════════════════════════════════════════════ -->
    {:else if activeTab === 'janus'}
      <div class="tab-content">

        <!-- Panel 1: Brain Health -->
        <Panel title="Brain Health">
          {#snippet header()}
            {#if janusHealth}
              <Badge variant={janusHealth.healthy ? 'green' : 'red'}>
                {janusHealth.healthy ? 'Healthy' : 'Unhealthy'}
              </Badge>
            {/if}
            <button class="btn-ghost" onclick={() => loadJanusHealth()}>↻ Refresh</button>
          {/snippet}
          {#if janusHealthLoading}
            <Skeleton lines={4} height="12px" />
          {:else if janusHealthError}
            <span class="error-text">{janusHealthError}</span>
          {:else if janusHealth}
            <div class="stat-grid">
              <div class="stat-item">
                <span class="stat-label">Status</span>
                <span class="stat-value" class:hit={janusHealth.healthy} class:miss={!janusHealth.healthy}>
                  {janusHealth.healthy ? 'Healthy' : 'Unhealthy'}
                </span>
              </div>
              <div class="stat-item">
                <span class="stat-label">Boot</span>
                <span class="stat-value" class:hit={janusHealth.boot_passed} class:miss={!janusHealth.boot_passed}>
                  {janusHealth.boot_passed ? 'Passed' : 'Failed'}
                </span>
              </div>
              {#if janusHealth.uptime_seconds !== undefined}
                <div class="stat-item">
                  <span class="stat-label">Uptime</span>
                  <span class="stat-value mono">{formatUptime(janusHealth.uptime_seconds)}</span>
                </div>
              {/if}
            </div>

            <!-- Component list -->
            {#if Object.keys(janusHealth.components).length > 0}
              <div class="sub-section-label" style="margin-top:8px;">Components</div>
              <div class="component-list">
                {#each Object.entries(janusHealth.components) as [name, comp] (name)}
                  <div class="component-row">
                    <span class="status-dot" class:alive={comp.alive} class:dead={!comp.alive}></span>
                    <span class="component-name mono">{name}</span>
                    {#if comp.last_seen}
                      <span class="component-seen dim">seen {comp.last_seen}</span>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <div class="empty-state">No components reported</div>
            {/if}
          {:else}
            <div class="empty-state">No health data available</div>
          {/if}
        </Panel>

        <!-- Panel 2: Services -->
        <div style="flex:1; min-height:0;">
          <Panel title="Services" noPad fill>
            {#snippet header()}
              {#if janusServices.length > 0}
                <Badge variant="default">{janusServices.length}</Badge>
              {/if}
              <button class="btn-ghost" onclick={() => loadJanusServices()}>↻ Refresh</button>
            {/snippet}
            {#if janusServicesLoading}
              <div style="padding:8px;">
                <Skeleton lines={4} height="12px" />
              </div>
            {:else if janusServicesError}
              <div style="padding:8px;">
                <span class="error-text">{janusServicesError}</span>
              </div>
            {:else if janusServices.length > 0}
              <table class="db-table">
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Status</th>
                    <th class="r">Uptime</th>
                  </tr>
                </thead>
                <tbody>
                  {#each janusServices as svc (svc.name)}
                    <tr>
                      <td class="mono">{svc.name}</td>
                      <td>
                        <Badge variant={svc.status === 'running' ? 'green' : svc.status === 'stopped' ? 'red' : 'amber'}>
                          {svc.status}
                        </Badge>
                      </td>
                      <td class="r mono">{svc.uptime !== undefined ? formatUptime(svc.uptime) : '—'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {:else}
              <div class="empty-state" style="padding:8px;">No services found</div>
            {/if}
          </Panel>
        </div>
      </div>
    {/if}

  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════
     STYLES
     ═══════════════════════════════════════════════════════════════════ -->
<style>
  /* ═══════════════════════════════════════════════════════════════════
     Layout
     ═══════════════════════════════════════════════════════════════════ */
  .page {
    display: flex;
    height: 100%;
    overflow: hidden;
  }

  .pane {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    flex: 1;
    min-width: 0;
    padding: 10px;
    gap: 8px;
  }

  .tabs-bar {
    padding: 0 2px;
    flex-shrink: 0;
  }

  .tab-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    gap: 8px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Panel chrome (sub-panel label still uses .panel-lbl)
     ═══════════════════════════════════════════════════════════════════ */
  .panel-lbl {
    font-size: 10px;
    color: var(--t2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }

  .panel-row {
    display: flex;
    gap: 8px;
    min-height: 0;
    flex-shrink: 0;
    max-height: 220px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Sub-panel (inside a panel for detail views)
     ═══════════════════════════════════════════════════════════════════ */
  .sub-panel {
    border-top: 1px solid var(--b1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    flex-shrink: 0;
    max-height: 300px;
  }

  .sub-panel-head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    background: var(--bg2);
    border-bottom: 1px solid var(--b1);
    flex-shrink: 0;
  }

  .sub-panel-body {
    padding: 6px 8px;
    overflow: auto;
    flex: 1;
    min-height: 0;
  }

  .sub-section-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
    margin-bottom: 4px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Redis Info Stats Grid
     ═══════════════════════════════════════════════════════════════════ */
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 6px;
    margin-bottom: 8px;
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 6px 10px;
  }

  .stat-label {
    font-size: 9px;
    color: var(--t3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
  }

  .stat-value {
    font-size: 14px;
    font-weight: 700;
    color: var(--t1);
  }

  .stat-value.hit { color: var(--green); }
  .stat-value.miss { color: var(--red); }

  /* ─── Raw info sections ─────────────────────────────────────────── */
  .raw-details {
    border-top: 1px solid var(--b1);
    padding-top: 6px;
  }

  .raw-summary {
    font-size: 10px;
    color: var(--t3);
    cursor: pointer;
    user-select: none;
  }

  .raw-summary:hover { color: var(--t2); }

  .raw-sections {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-top: 6px;
  }

  .section-details {
    border: 1px solid var(--b1);
    border-radius: var(--r);
    overflow: hidden;
  }

  .section-summary {
    font-size: 10px;
    color: var(--t2);
    padding: 3px 8px;
    background: var(--bg2);
    cursor: pointer;
    user-select: none;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .section-summary:hover { color: var(--t1); }

  .section-kv {
    padding: 4px 8px;
    max-height: 180px;
    overflow: auto;
  }

  .kv-row {
    display: flex;
    gap: 12px;
    padding: 1px 0;
    font-size: 10px;
    border-bottom: 1px solid var(--b1);
  }

  .kv-row:last-child { border-bottom: none; }

  .kv-key {
    color: var(--t2);
    min-width: 180px;
    flex-shrink: 0;
  }

  .kv-val {
    color: var(--t1);
    word-break: break-all;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Redis Key Browser
     ═══════════════════════════════════════════════════════════════════ */
  .scan-bar {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .scan-input {
    all: unset;
    flex: 1;
    font-size: 11px;
    padding: 4px 8px;
    background: var(--bg0);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t1);
  }

  .scan-input::placeholder { color: var(--t3); }

  .scan-input:focus {
    border-color: var(--accent);
    outline: none;
  }

  .key-browser-split {
    display: flex;
    gap: 8px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .key-list-wrap {
    flex: 1;
    min-width: 0;
    overflow: auto;
    border: 1px solid var(--b1);
    border-radius: var(--r);
    background: var(--bg0);
  }

  .key-list {
    display: flex;
    flex-direction: column;
  }

  .key-item {
    all: unset;
    font-size: 10px;
    font-family: var(--font-mono, monospace);
    padding: 3px 8px;
    color: var(--t2);
    cursor: pointer;
    border-bottom: 1px solid var(--b1);
    word-break: break-all;
    transition: background 0.1s, color 0.1s;
  }

  .key-item:hover {
    background: var(--bg2);
    color: var(--t1);
  }

  .key-item.active {
    background: var(--bg3);
    color: var(--accent);
  }

  .key-value-wrap {
    flex: 1;
    min-width: 0;
    overflow: auto;
    border: 1px solid var(--b1);
    border-radius: var(--r);
    background: var(--bg0);
    padding: 6px 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .key-value-header {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .value-pre {
    font-family: var(--font-mono, monospace);
    font-size: 10px;
    color: var(--t1);
    background: var(--bg1);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    padding: 8px;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    overflow: auto;
    flex: 1;
    min-height: 0;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Pub/Sub Channels
     ═══════════════════════════════════════════════════════════════════ */
  .channel-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .channel-item {
    font-size: 10px;
    color: var(--t1);
    padding: 3px 6px;
    background: var(--bg2);
    border-radius: var(--r);
    border: 1px solid var(--b1);
  }

  /* ═══════════════════════════════════════════════════════════════════
     Tables — shared
     ═══════════════════════════════════════════════════════════════════ */
  .table-scroll,
  .sample-scroll,
  .result-scroll {
    overflow: auto;
    flex: 1;
    min-height: 0;
  }

  .db-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    font-family: var(--font-mono, monospace);
  }

  .db-table thead th {
    padding: 4px 8px;
    text-align: left;
    color: var(--t3);
    font-weight: 500;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--b1);
    position: sticky;
    top: 0;
    background: var(--bg1);
    z-index: 1;
  }

  .db-table tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--b1);
    vertical-align: middle;
    font-size: 10px;
  }

  .db-table.compact thead th { padding: 3px 6px; }
  .db-table.compact tbody td { padding: 3px 6px; font-size: 10px; }

  .db-table tbody tr.clickable {
    cursor: pointer;
    transition: background 0.1s;
  }

  .db-table tbody tr.clickable:hover {
    background: var(--bg2);
  }

  .db-table tbody tr.selected {
    background: var(--bg3);
  }

  .result-table {
    font-size: 10px;
  }

  .result-table thead th {
    font-size: 9px;
  }

  .result-table tbody td {
    font-size: 10px;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Query Runner
     ═══════════════════════════════════════════════════════════════════ */
  .query-area {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex-shrink: 0;
  }

  .query-input {
    all: unset;
    font-size: 12px;
    line-height: 1.5;
    padding: 8px 10px;
    background: var(--bg0);
    border: 1px solid var(--b2);
    border-radius: var(--r);
    color: var(--t1);
    resize: vertical;
    min-height: 60px;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    box-sizing: border-box;
    width: 100%;
  }

  .query-input::placeholder { color: var(--t3); }

  .query-input:focus {
    border-color: var(--accent);
    outline: none;
  }

  .query-actions {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
  }

  .error-box {
    font-size: 10px;
    color: var(--red);
    background: var(--red-dim);
    border: 1px solid var(--red-brd);
    border-radius: var(--r);
    padding: 6px 10px;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Buttons
     ═══════════════════════════════════════════════════════════════════ */
  .btn-ghost {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--t2);
    padding: 2px 8px;
    border-radius: var(--r);
    transition: background 0.12s, color 0.12s;
  }

  .btn-ghost:hover { background: var(--bg3); color: var(--t1); }

  .btn-primary {
    all: unset;
    cursor: pointer;
    font-size: 10px;
    font-family: inherit;
    color: var(--bg0);
    background: var(--accent);
    padding: 3px 12px;
    border-radius: var(--r);
    font-weight: 600;
    transition: opacity 0.12s;
  }

  .btn-primary:hover { opacity: 0.85; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ═══════════════════════════════════════════════════════════════════
     Utility
     ═══════════════════════════════════════════════════════════════════ */
  .r { text-align: right !important; }
  .mono { font-family: var(--font-mono, monospace); }
  .dim { color: var(--t3); }

  .empty-state {
    color: var(--t3);
    font-size: 11px;
    text-align: center;
    padding: 24px 0;
  }

  .error-text {
    color: var(--red);
    font-size: 10px;
  }

  /* ═══════════════════════════════════════════════════════════════════
     Janus Components
     ═══════════════════════════════════════════════════════════════════ */
  .component-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .component-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    background: var(--bg2);
    border: 1px solid var(--b1);
    border-radius: var(--r);
    font-size: 11px;
  }

  .component-name {
    color: var(--t1);
    font-size: 11px;
  }

  .component-seen {
    margin-left: auto;
    font-size: 9px;
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-dot.alive {
    background: var(--green);
    box-shadow: 0 0 4px var(--green);
  }

  .status-dot.dead {
    background: var(--red);
    box-shadow: 0 0 4px var(--red);
  }
</style>
