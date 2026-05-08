<!--
  /bots — Bot Spawner WebUI

  Three-pane layout:
    ┌──────────────┬───────────────────────────────────┐
    │              │                                   │
    │  Spawn form  │      Running containers           │
    │              │                                   │
    │              ├───────────────────────────────────┤
    │              │                                   │
    │  Run history │      Logs (SSE, follows tail)     │
    │              │                                   │
    └──────────────┴───────────────────────────────────┘

  All API calls go through the typed `spawner` client in $api/spawner.
  Live updates via 3s poll (containers + history) and per-bot SSE log
  streams that the user opens by clicking a row.
-->
<script lang="ts">
    import { onMount } from "svelte";
    import { createPoll } from "$stores/poll";
    import { spawner } from "$api/spawner";
    import { ApiError } from "$api/client";
    import Panel from "$components/ui/Panel.svelte";
    import Badge from "$components/ui/Badge.svelte";
    import Skeleton from "$components/ui/Skeleton.svelte";
    import ProgressBar from "$components/ui/ProgressBar.svelte";
    import { fmtDateTime, fmtInt } from "$lib/utils/format";
    import type {
        ContainerInfo,
        ContainersResponse,
        BotRun,
        RunsResponse,
    } from "$lib/types/spawner";

    // ─── Live polls ───────────────────────────────────────────────────────

    const containersPoll = createPoll<ContainersResponse>(
        "/api/spawner/containers",
        3_000,
    );
    const runsPoll = createPoll<RunsResponse>(
        "/api/spawner/runs?limit=50",
        5_000,
    );

    let containers = $derived<ContainerInfo[]>(
        $containersPoll?.containers ?? [],
    );
    let runs = $derived<BotRun[]>($runsPoll?.runs ?? []);
    let dbEnabled = $derived<boolean>($runsPoll?.db_enabled ?? false);
    let runningCount = $derived<number>($containersPoll?.running ?? 0);

    // ─── Spawn form ───────────────────────────────────────────────────────

    let spawnImage = $state("fks-bot-");
    let spawnBotId = $state("");
    let spawnMode = $state("paper");
    let spawnCpu = $state("");
    let spawnMem = $state("");
    let spawnEnvText = $state(""); // raw "KEY=value" lines, one per row
    let submitting = $state(false);
    let feedback = $state<{ msg: string; ok: boolean } | null>(null);

    function parseEnv(text: string): Record<string, string> {
        const out: Record<string, string> = {};
        for (const line of text.split("\n")) {
            const t = line.trim();
            if (!t || t.startsWith("#")) continue;
            const eq = t.indexOf("=");
            if (eq <= 0) continue;
            const k = t.slice(0, eq).trim();
            const v = t.slice(eq + 1).trim();
            if (k) out[k] = v;
        }
        return out;
    }

    async function submitSpawn(e: Event) {
        e.preventDefault();
        if (submitting) return;
        submitting = true;
        feedback = null;
        try {
            const cpu = spawnCpu.trim() ? Number(spawnCpu) : undefined;
            const mem = spawnMem.trim() ? Number(spawnMem) : undefined;
            const res = await spawner.spawn({
                image: spawnImage.trim(),
                bot_id: spawnBotId.trim() || undefined,
                mode: spawnMode,
                env: parseEnv(spawnEnvText),
                cpu_limit: Number.isFinite(cpu) ? cpu : undefined,
                memory_limit_mb: Number.isFinite(mem) ? mem : undefined,
            });
            feedback = {
                msg: `Spawned ${res.container_name} (${res.container_id})`,
                ok: true,
            };
            // Reset bot_id so the next spawn auto-generates a new UUID, but
            // keep image/mode so the user can iterate quickly.
            spawnBotId = "";
            containersPoll.refresh();
            runsPoll.refresh();
        } catch (e) {
            const detail =
                e instanceof ApiError
                    ? `${e.status} ${e.statusText}` +
                      (e.body ? ` — ${e.body}` : "")
                    : String(e);
            feedback = { msg: `Spawn failed: ${detail}`, ok: false };
        } finally {
            submitting = false;
        }
    }

    // ─── Lifecycle actions ────────────────────────────────────────────────

    let actingOn = $state<string | null>(null); // container_id currently being acted on

    async function withAction(
        id: string,
        label: string,
        fn: () => Promise<unknown>,
    ) {
        actingOn = id;
        try {
            await fn();
            feedback = { msg: `${label}: ${id} — ok`, ok: true };
        } catch (e) {
            feedback = { msg: `${label} ${id} failed: ${e}`, ok: false };
        } finally {
            actingOn = null;
            containersPoll.refresh();
            runsPoll.refresh();
        }
    }

    const stopBot = (id: string) =>
        withAction(id, "stop", () => spawner.stop(id));
    const restartBot = (id: string) =>
        withAction(id, "restart", () => spawner.restart(id));
    const removeBot = (id: string) => {
        if (!confirm(`Remove container ${id}? (Force, including running.)`))
            return;
        return withAction(id, "remove", () => spawner.remove(id));
    };

    // ─── Log viewer (SSE) ─────────────────────────────────────────────────

    let viewingId = $state<string | null>(null);
    let logLines = $state<string[]>([]);
    let logsConnected = $state(false);
    let sse: EventSource | null = null;

    function viewLogs(id: string) {
        if (sse) {
            sse.close();
            sse = null;
        }
        viewingId = id;
        logLines = [];
        logsConnected = false;

        const ev = spawner.openLogStream(id, 200);
        sse = ev;
        ev.addEventListener("log", (e: MessageEvent) => {
            logsConnected = true;
            logLines = [...logLines, e.data];
            // Cap the buffer so the DOM doesn't grow unbounded.
            if (logLines.length > 2000) {
                logLines = logLines.slice(-1500);
            }
        });
        ev.onerror = () => {
            logsConnected = false;
        };
        ev.onopen = () => {
            logsConnected = true;
        };
    }

    function closeLogs() {
        if (sse) sse.close();
        sse = null;
        viewingId = null;
        logLines = [];
        logsConnected = false;
    }

    // ─── Display helpers ──────────────────────────────────────────────────

    function stateBadge(
        state: string,
    ): "green" | "red" | "amber" | "cyan" | "default" {
        const s = state.toLowerCase();
        if (s === "running") return "green";
        if (s === "exited" || s === "dead") return "red";
        if (s === "created" || s === "restarting") return "amber";
        if (s === "paused") return "cyan";
        return "default";
    }

    function runStatusBadge(
        status: string,
    ): "green" | "red" | "amber" | "cyan" | "default" {
        switch (status) {
            case "running":
                return "green";
            case "stopped":
            case "pruned":
                return "default";
            case "error":
                return "red";
            case "spawning":
            case "stopping":
                return "amber";
            default:
                return "default";
        }
    }

    function fmtBytes(b: number | null): string {
        if (b == null) return "—";
        if (b < 1024) return `${b} B`;
        if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
        if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
        return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
    }

    function fmtRuntime(secs: number | null): string {
        if (secs == null) return "—";
        if (secs < 60) return `${secs}s`;
        if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        return `${h}h ${m}m`;
    }

    // ─── Lifecycle ────────────────────────────────────────────────────────

    onMount(() => {
        containersPoll.start();
        runsPoll.start();
        return () => {
            containersPoll.stop();
            runsPoll.stop();
            if (sse) sse.close();
        };
    });
</script>

<div class="page">
    <!-- Left column: spawn form + run history -->
    <div class="left-col">
        <Panel title="Spawn Bot">
            <form class="spawn-form" onsubmit={submitSpawn}>
                <label class="field">
                    <span class="lbl">Image</span>
                    <input
                        class="inp"
                        type="text"
                        bind:value={spawnImage}
                        placeholder="fks-bot-arbitrage:latest"
                        required
                    />
                    <span class="help"
                        >Must start with the spawner's allowed prefix.</span
                    >
                </label>

                <label class="field">
                    <span class="lbl">Bot ID (optional)</span>
                    <input
                        class="inp"
                        type="text"
                        bind:value={spawnBotId}
                        placeholder="auto-generated UUID"
                    />
                </label>

                <label class="field">
                    <span class="lbl">Mode</span>
                    <select class="sel" bind:value={spawnMode}>
                        <option value="paper">paper</option>
                        <option value="live">live</option>
                        <option value="backtest">backtest</option>
                        <option value="optimise">optimise</option>
                        <option value="train">train</option>
                    </select>
                </label>

                <div class="row">
                    <label class="field">
                        <span class="lbl">CPU limit</span>
                        <input
                            class="inp"
                            type="number"
                            step="0.1"
                            min="0.1"
                            bind:value={spawnCpu}
                            placeholder="1.0"
                        />
                        <span class="help">Fractional cores</span>
                    </label>
                    <label class="field">
                        <span class="lbl">Memory MB</span>
                        <input
                            class="inp"
                            type="number"
                            min="64"
                            step="64"
                            bind:value={spawnMem}
                            placeholder="512"
                        />
                    </label>
                </div>

                <label class="field">
                    <span class="lbl">Env (KEY=value, one per line)</span>
                    <textarea
                        class="inp env"
                        bind:value={spawnEnvText}
                        rows="4"
                        placeholder="EXCHANGE=kucoin&#10;ASSET=BTC-USDT"
                    ></textarea>
                </label>

                <button
                    class="btn run"
                    disabled={submitting || !spawnImage.trim()}
                >
                    {submitting ? "Spawning…" : "▶ Spawn"}
                </button>

                {#if feedback}
                    <p class="feedback" class:ok={feedback.ok}>
                        {feedback.msg}
                    </p>
                {/if}
            </form>
        </Panel>

        <Panel title="Run History" fill>
            {#if !$runsPoll}
                <div class="skel-col">
                    {#each Array(4) as _}
                        <Skeleton height="32px" />
                    {/each}
                </div>
            {:else if !dbEnabled}
                <p class="empty dim">
                    DB persistence not configured — set
                    <code>SPAWNER_DATABASE_URL</code> on the spawner to enable history.
                </p>
            {:else if runs.length === 0}
                <p class="empty">No runs recorded yet.</p>
            {:else}
                <div class="run-list">
                    {#each runs as r}
                        <div class="run-row">
                            <Badge variant={runStatusBadge(r.status)}
                                >{r.status}</Badge
                            >
                            <span class="run-img" title={r.image}
                                >{r.image}</span
                            >
                            <span class="run-mode dim">{r.mode}</span>
                            <span class="run-rt mono dim"
                                >{fmtRuntime(r.runtime_secs)}</span
                            >
                            <span class="run-time dim">
                                {fmtDateTime(r.started_at)}
                            </span>
                        </div>
                        {#if r.error_message}
                            <p class="run-err">{r.error_message}</p>
                        {/if}
                    {/each}
                </div>
            {/if}
        </Panel>
    </div>

    <!-- Right column: containers + logs -->
    <div class="right-col">
        <Panel title="Running ({runningCount})">
            {#snippet header()}
                <button
                    class="btn small"
                    onclick={() => containersPoll.refresh()}
                    disabled={actingOn !== null}
                >
                    ↻ Refresh
                </button>
            {/snippet}
            {#if !$containersPoll}
                <div class="skel-col">
                    {#each Array(3) as _}
                        <Skeleton height="44px" />
                    {/each}
                </div>
            {:else if containers.length === 0}
                <p class="empty">No bot containers running.</p>
            {:else}
                <div class="container-list">
                    {#each containers as c}
                        <div
                            class="container-row"
                            class:viewing={viewingId === c.id}
                            class:acting={actingOn === c.id}
                        >
                            <div class="container-main">
                                <Badge variant={stateBadge(c.state)}
                                    >{c.state}</Badge
                                >
                                <span class="c-name" title={c.name}
                                    >{c.name}</span
                                >
                                <span class="c-img dim" title={c.image}
                                    >{c.image}</span
                                >
                                <span class="c-mode dim">{c.mode}</span>
                            </div>
                            <div class="container-meta">
                                {#if c.memory_bytes != null}
                                    <span class="meta-cell mono"
                                        >{fmtBytes(c.memory_bytes)}</span
                                    >
                                {/if}
                                {#if c.cpu_percent != null}
                                    <span class="meta-cell mono"
                                        >{c.cpu_percent.toFixed(1)}%</span
                                    >
                                {/if}
                                <span class="meta-cell dim">
                                    {c.created_at
                                        ? fmtDateTime(c.created_at)
                                        : "—"}
                                </span>
                            </div>
                            <div class="container-actions">
                                <button
                                    class="btn small"
                                    onclick={() => viewLogs(c.id)}
                                >
                                    Logs
                                </button>
                                {#if c.state === "running"}
                                    <button
                                        class="btn small"
                                        onclick={() => stopBot(c.id)}
                                        disabled={actingOn !== null}
                                    >
                                        Stop
                                    </button>
                                    <button
                                        class="btn small"
                                        onclick={() => restartBot(c.id)}
                                        disabled={actingOn !== null}
                                    >
                                        Restart
                                    </button>
                                {/if}
                                <button
                                    class="btn small danger"
                                    onclick={() => removeBot(c.id)}
                                    disabled={actingOn !== null}
                                >
                                    ✕
                                </button>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </Panel>

        <Panel
            title={viewingId ? `Logs — ${viewingId.slice(0, 12)}` : "Logs"}
            fill
        >
            {#snippet header()}
                {#if viewingId}
                    <span class="conn-pill" class:live={logsConnected}>
                        {logsConnected ? "● live" : "○ idle"}
                    </span>
                    <button class="btn small" onclick={closeLogs}>Close</button>
                {/if}
            {/snippet}
            {#if !viewingId}
                <p class="empty dim">
                    Click a container's <strong>Logs</strong> button to stream output.
                </p>
            {:else}
                {#if logsConnected && logLines.length === 0}
                    <ProgressBar value={100} color="cyan" height="2px" />
                    <p class="empty dim">Waiting for output…</p>
                {/if}
                <div class="log-pane">
                    {#each logLines as line, i (i + ":" + line.slice(0, 16))}
                        <div class="log-line">{line}</div>
                    {/each}
                </div>
                {#if logLines.length > 0}
                    <p class="log-info dim">
                        {fmtInt(logLines.length)} line{logLines.length === 1
                            ? ""
                            : "s"} (capped at 2,000)
                    </p>
                {/if}
            {/if}
        </Panel>
    </div>
</div>

<style>
    .page {
        display: grid;
        grid-template-columns: 360px 1fr;
        gap: 8px;
        padding: 10px;
        height: 100%;
        min-height: 0;
    }

    .left-col,
    .right-col {
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-height: 0;
    }

    /* ─── Spawn form ───────────────────────────────────────────────────── */
    .spawn-form {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .field {
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }
    .lbl {
        font-size: 9px;
        color: var(--t3);
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .help {
        font-size: 9px;
        color: var(--t3);
        line-height: 1.3;
    }
    .inp,
    .sel {
        background: var(--bg3);
        border: 1px solid var(--b3);
        border-radius: var(--r);
        color: var(--t1);
        font-family: inherit;
        font-size: 10px;
        padding: 4px 6px;
        width: 100%;
        outline: none;
    }
    .inp:focus,
    .sel:focus {
        border-color: var(--accent-brd);
    }
    .inp.env {
        font-family: var(--mono, ui-monospace, monospace);
        line-height: 1.5;
        resize: vertical;
    }

    /* ─── Buttons ──────────────────────────────────────────────────────── */
    .btn {
        background: var(--bg3);
        border: 1px solid var(--b3);
        border-radius: var(--r);
        color: var(--t1);
        font-family: inherit;
        font-size: 10px;
        font-weight: 500;
        padding: 4px 10px;
        cursor: pointer;
        transition:
            background 0.1s,
            border-color 0.1s;
    }
    .btn:hover:not(:disabled) {
        background: var(--bg4, #2a2a2a);
        border-color: var(--accent-brd);
    }
    .btn:disabled {
        opacity: 0.4;
        cursor: default;
    }
    .btn.run {
        background: var(--accent-dim);
        border-color: var(--accent-brd);
        font-weight: 600;
        padding: 6px 12px;
        margin-top: 2px;
    }
    .btn.run:hover:not(:disabled) {
        background: var(--accent-glow);
    }
    .btn.small {
        padding: 2px 7px;
        font-size: 9px;
    }
    .btn.danger {
        color: var(--red);
    }
    .btn.danger:hover:not(:disabled) {
        background: var(--red-dim);
        border-color: var(--red-brd);
    }

    /* ─── Feedback toast ───────────────────────────────────────────────── */
    .feedback {
        font-size: 10px;
        padding: 5px 8px;
        border-radius: var(--r);
        background: var(--red-dim);
        color: var(--red);
        word-break: break-word;
    }
    .feedback.ok {
        background: var(--green-dim);
        color: var(--green);
    }

    /* ─── Container list ───────────────────────────────────────────────── */
    .container-list {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .container-row {
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 8px;
        align-items: center;
        padding: 6px 8px;
        background: var(--bg2);
        border: 1px solid var(--b2);
        border-radius: var(--r);
        transition: background 0.1s;
    }
    .container-row:hover {
        background: var(--bg3);
    }
    .container-row.viewing {
        border-color: var(--accent-brd);
        background: var(--accent-dim);
    }
    .container-row.acting {
        opacity: 0.6;
    }
    .container-main {
        display: flex;
        align-items: center;
        gap: 8px;
        overflow: hidden;
    }
    .c-name {
        font-size: 11px;
        color: var(--t1);
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 220px;
    }
    .c-img,
    .c-mode {
        font-size: 9px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .c-img {
        max-width: 240px;
    }
    .container-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 9px;
    }
    .meta-cell {
        white-space: nowrap;
    }
    .container-actions {
        display: flex;
        gap: 4px;
    }

    /* ─── Run history ──────────────────────────────────────────────────── */
    .run-list {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .run-row {
        display: grid;
        grid-template-columns: auto 1fr auto auto auto;
        gap: 8px;
        align-items: center;
        padding: 4px 6px;
        border-radius: var(--r);
    }
    .run-row:hover {
        background: var(--bg3);
    }
    .run-img {
        font-size: 10px;
        color: var(--t1);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }
    .run-mode,
    .run-rt,
    .run-time {
        font-size: 9px;
        white-space: nowrap;
    }
    .run-err {
        font-size: 9px;
        color: var(--red);
        padding: 2px 8px 4px 28px;
        margin: 0;
        line-height: 1.3;
    }

    /* ─── Logs ─────────────────────────────────────────────────────────── */
    .log-pane {
        height: 100%;
        overflow: auto;
        padding: 4px 0;
        display: flex;
        flex-direction: column;
        gap: 1px;
    }
    .log-line {
        font-family: var(--mono, ui-monospace, monospace);
        font-size: 10px;
        color: var(--t1);
        padding: 1px 6px;
        white-space: pre-wrap;
        word-break: break-all;
        line-height: 1.45;
    }
    .log-line:nth-child(odd) {
        background: var(--bg2);
    }
    .log-info {
        font-size: 9px;
        padding: 4px 8px 0;
        border-top: 1px solid var(--b2);
    }
    .conn-pill {
        font-size: 9px;
        padding: 2px 6px;
        border-radius: var(--r);
        background: var(--bg3);
        color: var(--t3);
        margin-right: 4px;
    }
    .conn-pill.live {
        color: var(--green);
        background: var(--green-dim);
    }

    /* ─── Misc ─────────────────────────────────────────────────────────── */
    .skel-col {
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding: 4px;
    }
    .empty {
        padding: 16px;
        font-size: 11px;
        color: var(--t2);
        line-height: 1.5;
    }
    .empty code {
        background: var(--bg3);
        color: var(--cyan);
        font-size: 10px;
        padding: 1px 4px;
        border-radius: var(--r);
    }
    .dim {
        color: var(--t2);
    }
    .mono {
        font-family: var(--mono, ui-monospace, monospace);
    }
</style>
