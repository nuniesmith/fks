<script lang="ts">
  import { onMount, getContext } from 'svelte';
  import { createPoll } from '$stores/poll';
  import Panel from '$components/ui/Panel.svelte';
  import Badge from '$components/ui/Badge.svelte';
  import ProgressBar from '$components/ui/ProgressBar.svelte';
  import StatCard from '$components/ui/StatCard.svelte';
  import Skeleton from '$components/ui/Skeleton.svelte';
  import { fmtFixed, fmtConfidence } from '$lib/utils/format';
  import type { WorkspaceConfig } from '$lib/workspaces';

  const ws = getContext<WorkspaceConfig>('workspace');

  // ─── Types ──────────────────────────────────────────────────────────

  interface ModelMeta {
    trained_at?: string;
    val_accuracy?: number;
    val_f1?: number;
    epochs?: number;
    lookback?: number;
  }

  interface AssetCnn {
    cnn_enabled: boolean;
    cnn_signal: string;
    cnn_confidence: number;
    master_risk_score: number;
    master_halted: boolean;
    model_meta: ModelMeta | null;
  }

  interface MlConfig {
    enabled: boolean;
    min_confidence: number;
    master_risk_threshold: number;
  }

  interface CnnData {
    assets: Record<string, AssetCnn>;
    ml_config: MlConfig;
  }

  // ─── Poll ─────────────────────────────────────────────────────────────

  const cnnPoll = createPoll<CnnData>(`${ws.apiBase}/cnn/status`, 10_000);

  let data      = $derived($cnnPoll);
  let assets    = $derived(Object.entries(data?.assets ?? {}));
  let cfg       = $derived(data?.ml_config);
  let avgRisk   = $derived(assets.length ? assets.reduce((s, [, a]) => s + a.master_risk_score, 0) / assets.length : 0);
  let anyHalted = $derived(assets.some(([, a]) => a.master_halted));

  // ─── Helpers ─────────────────────────────────────────────────────────

  function signalBadge(sig: string): 'green' | 'red' | 'amber' | 'default' {
    const s = sig?.toUpperCase();
    if (s === 'LONG' || s === 'BUY')   return 'green';
    if (s === 'SHORT' || s === 'SELL') return 'red';
    if (s === 'HOLD')                  return 'amber';
    return 'default';
  }

  function riskColor(score: number): 'green' | 'amber' | 'red' {
    if (score < 0.35) return 'green';
    if (score < 0.65) return 'amber';
    return 'red';
  }

  onMount(() => {
    cnnPoll.start();
    return () => cnnPoll.stop();
  });
</script>

<div class="page">
  {#if !ws.hasCnn}
    <div class="unsupported">
      <p>CNN / ML signals are not configured for the <strong>{ws.label}</strong> workspace.</p>
      <p class="dim">Set <code>hasCnn: true</code> in <code>src/lib/workspaces.ts</code> to enable this tab.</p>
    </div>
  {:else}
    <!-- Summary bar -->
    <div class="stats-row">
      {#if !data}
        {#each Array(3) as _}<Skeleton width="130px" height="54px" />{/each}
      {:else}
        <StatCard
          label="Avg Risk Score"
          value={fmtFixed(avgRisk, 3)}
          color={riskColor(avgRisk)}
        />
        <StatCard
          label="System Status"
          value={anyHalted ? 'HALTED' : cfg?.enabled ? 'Active' : 'Disabled'}
          color={anyHalted ? 'red' : cfg?.enabled ? 'green' : 'default'}
        />
        <StatCard
          label="Min Confidence"
          value={cfg?.min_confidence != null ? fmtFixed(cfg.min_confidence, 2) : '—'}
        />
        <StatCard
          label="Risk Threshold"
          value={cfg?.master_risk_threshold != null ? fmtFixed(cfg.master_risk_threshold, 2) : '—'}
          color="amber"
        />
      {/if}
    </div>

    <!-- Per-asset cards -->
    <div class="asset-grid">
      {#if !data}
        {#each Array(4) as _}<Skeleton height="160px" />{/each}
      {:else if assets.length === 0}
        <p class="empty">No CNN assets reporting.</p>
      {:else}
        {#each assets as [symbol, a]}
          <Panel>
            {#snippet header()}
              <span class="asset-name">{symbol.toUpperCase()}</span>
              {#if a.master_halted}
                <Badge variant="red">HALTED</Badge>
              {:else if a.cnn_enabled}
                <Badge variant="green">active</Badge>
              {:else}
                <Badge variant="default">disabled</Badge>
              {/if}
              <Badge variant={signalBadge(a.cnn_signal)}>{a.cnn_signal ?? '—'}</Badge>
            {/snippet}

            <div class="card-body">
              <!-- Confidence bar -->
              <div class="metric-row">
                <span class="lbl">Confidence</span>
                <ProgressBar value={a.cnn_confidence * 100} color="cyan" height="5px" />
                <span class="val">{fmtConfidence(a.cnn_confidence)}</span>
              </div>

              <!-- Risk bar -->
              <div class="metric-row">
                <span class="lbl">Risk</span>
                <ProgressBar value={a.master_risk_score * 100} color={riskColor(a.master_risk_score)} height="5px" />
                <span class="val">{fmtFixed(a.master_risk_score, 3)}</span>
              </div>

              <!-- Model meta -->
              {#if a.model_meta}
                {@const m = a.model_meta}
                <div class="kv-grid">
                  {#if m.val_accuracy != null}
                    <span class="lbl">Val Acc</span>
                    <span class="val">{fmtFixed(m.val_accuracy * 100, 1)}%</span>
                  {/if}
                  {#if m.val_f1 != null}
                    <span class="lbl">Val F1</span>
                    <span class="val">{fmtFixed(m.val_f1, 3)}</span>
                  {/if}
                  {#if m.epochs != null}
                    <span class="lbl">Epochs</span>
                    <span class="val">{m.epochs}</span>
                  {/if}
                  {#if m.lookback != null}
                    <span class="lbl">Lookback</span>
                    <span class="val">{m.lookback}</span>
                  {/if}
                  {#if m.trained_at}
                    <span class="lbl">Trained</span>
                    <span class="val dim" title={m.trained_at}>{m.trained_at.slice(0, 10)}</span>
                  {/if}
                </div>
              {:else}
                <p class="no-model">No model trained yet.</p>
              {/if}
            </div>
          </Panel>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .page { display: flex; flex-direction: column; gap: 10px; padding: 10px; height: 100%; overflow: auto; }

  .stats-row { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }

  .asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }

  .asset-name { font-size: 12px; font-weight: 700; color: var(--t1); letter-spacing: 0.06em; }

  .card-body { display: flex; flex-direction: column; gap: 8px; padding: 4px 0; }

  .metric-row { display: flex; align-items: center; gap: 8px; }

  .kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px 10px; }

  .lbl { font-size: 9px; color: var(--t3); text-transform: uppercase; letter-spacing: 0.05em; }
  .val { font-size: 11px; color: var(--t1); text-align: right; }
  .dim { color: var(--t2); }

  .no-model { font-size: 10px; color: var(--t3); padding: 4px 0; }

  .unsupported {
    display: flex; flex-direction: column; gap: 8px;
    padding: 40px; color: var(--t2); font-size: 12px; line-height: 1.6;
  }
  .unsupported code { color: var(--cyan); font-size: 11px; }

  .empty { padding: 20px; font-size: 11px; color: var(--t3); }
</style>
