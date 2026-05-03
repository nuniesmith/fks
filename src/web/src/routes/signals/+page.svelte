<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { api } from "$api/client";
    import Panel from "$components/ui/Panel.svelte";
    import Badge from "$components/ui/Badge.svelte";
    import Skeleton from "$components/ui/Skeleton.svelte";
    import FilterChips from "$components/ui/FilterChips.svelte";
    import { fmtDateTime } from "$lib/utils/format";

    // ─── Types ──────────────────────────────────────────────────────────

    interface Signal {
        id: string;
        symbol: string;
        type: "entry" | "tp" | "sl" | string;
        side?: string;
        status: "staging" | "approved" | "rejected" | string;
        price?: number;
        timestamp?: string;
        message?: string;
    }

    interface Alert {
        id?: string;
        title?: string;
        message?: string;
        severity?: "error" | "warning" | "info" | string;
        timestamp?: string;
    }

    interface SignalsResponse {
        signals: Signal[];
    }
    interface AlertsResponse {
        alerts: Alert[];
    }

    // ─── Filter state ────────────────────────────────────────────────────

    const STATUS_FILTERS = [
        { id: "staging", label: "Staging" },
        { id: "approved", label: "Approved" },
        { id: "", label: "All" },
    ];

    let statusFilter = $state("staging");

    // ─── Signals data ────────────────────────────────────────────────────

    let signals = $state<Signal[]>([]);
    let signalsLoading = $state(true);
    let signalsError = $state("");

    let alerts = $state<Alert[]>([]);
    let alertsLoading = $state(true);
    let alertsError = $state("");

    let actionBusy: Record<string, boolean> = $state({});

    // ─── Fetch ───────────────────────────────────────────────────────────

    async function fetchSignals() {
        signalsError = "";
        try {
            const url = statusFilter
                ? `/api/signals?status=${statusFilter}`
                : "/api/signals";
            const data = await api<SignalsResponse>(url);
            signals = data.signals ?? [];
        } catch (e: any) {
            signalsError = e.message ?? "Failed to load signals";
        } finally {
            signalsLoading = false;
        }
    }

    async function fetchAlerts() {
        alertsError = "";
        try {
            const data = await api<AlertsResponse>("/api/alerts");
            alerts = data.alerts ?? [];
        } catch (e: any) {
            alertsError = e.message ?? "Failed to load alerts";
        } finally {
            alertsLoading = false;
        }
    }

    async function refresh() {
        await Promise.all([fetchSignals(), fetchAlerts()]);
    }

    // ─── Actions ─────────────────────────────────────────────────────────

    async function approveSignal(id: string) {
        actionBusy = { ...actionBusy, [id]: true };
        try {
            await api(`/api/signals/${id}/approve`, { method: "POST" });
            await fetchSignals();
        } catch (e: unknown) {
            const err = e instanceof Error ? e : new Error(String(e));
            alert(`Approve failed: ${err.message}`);
        } finally {
            const next = { ...actionBusy };
            delete next[id];
            actionBusy = next;
        }
    }

    async function rejectSignal(id: string) {
        if (!confirm("Reject this signal?")) return;
        actionBusy = { ...actionBusy, [id]: true };
        try {
            await api(`/api/signals/${id}/reject`, { method: "POST" });
            await fetchSignals();
        } catch (e: unknown) {
            const err;
            const next = { ...actionBusy };
            delete next[id];
            actionBusy = next;
        }
    }

    // ─── Helpers ─────────────────────────────────────────────────────────

    function typeBadge(type: string): "green" | "red" | "amber" | "default" {
        if (type === "entry") return "green";
        if (type === "tp") return "amber";
        if (type === "sl") return "red";
        return "default";
    }

    function severityBadge(
        severity: string | undefined,
    ): "red" | "amber" | "green" {
        if (severity === "error") return "red";
        if (severity === "warning") return "amber";
        return "green";
    }

    // ─── Polling ─────────────────────────────────────────────────────────

    let timer: ReturnType<typeof setInterval>;

    $effect(() => {
        signalsLoading = true;
        fetchSignals();
    });

    onMount(() => {
        fetchAlerts();
        timer = setInterval(refresh, 5_000);
        return () => clearInterval(timer);
    });
</script>

<svelte:head>
    <title>Signals — FKS Terminal</title>
</svelte:head>

<div class="page">
    <!-- ─── Signal Staging ──────────────────────────────────────────────── -->
    <Panel title="Signal Staging Area" fill>
        {#snippet header()}
            <FilterChips
                chips={STATUS_FILTERS}
                active={statusFilter}
                onselect={(id) => {
                    statusFilter = id;
                }}
            />
            <span class="poll-badge">{signals.length} signals · 5s</span>
        {/snippet}

        {#if signalsLoading}
            <div class="skeleton-rows">
                {#each Array(6) as _}
                    <Skeleton height="40px" />
                {/each}
            </div>
        {:else if signalsError}
            <p class="err-text">{signalsError}</p>
        {:else if signals.length === 0}
            <p class="empty">No {statusFilter || ""} signals.</p>
        {:else}
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>Price</th>
                            <th>Message</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each signals as sig}
                            <tr>
                                <td class="dim mono"
                                    >{sig.timestamp
                                        ? fmtDateTime(sig.timestamp)
                                        : "—"}</td
                                >
                                <td class="symbol">{sig.symbol}</td>
                                <td
                                    ><Badge variant={typeBadge(sig.type)}
                                        >{sig.type.toUpperCase()}</Badge
                                    ></td
                                >
                                <td
                                    ><Badge
                                        variant={sig.status === "approved"
                                            ? "green"
                                            : sig.status === "rejected"
                                              ? "red"
                                              : "default"}>{sig.status}</Badge
                                    ></td
                                >
                                <td class="mono"
                                    >{sig.price != null
                                        ? `$${sig.price.toFixed(2)}`
                                        : "—"}</td
                                >
                                <td class="message dim">{sig.message ?? "—"}</td
                                >
                                <td class="actions">
                                    {#if sig.status === "staging"}
                                        <button
                                            class="act-btn approve"
                                            onclick={() =>
                                                approveSignal(sig.id)}
                                            disabled={actionBusy[sig.id]}
                                            >✓</button
                                        >
                                        <button
                                            class="act-btn reject"
                                            onclick={() => rejectSignal(sig.id)}
                                            disabled={actionBusy[sig.id]}
                                            >✕</button
                                        >
                                    {/if}
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        {/if}
    </Panel>

    <!-- ─── Alerts ──────────────────────────────────────────────────────── -->
    <Panel title="Alerts">
        {#snippet header()}
            <span class="poll-badge">{alerts.length} active · 5s</span>
        {/snippet}

        {#if alertsLoading}
            <div class="skeleton-rows">
                {#each Array(3) as _}
                    <Skeleton height="40px" />
                {/each}
            </div>
        {:else if alertsError}
            <p class="err-text">{alertsError}</p>
        {:else if alerts.length === 0}
            <p class="empty">No alerts.</p>
        {:else}
            <div class="alerts-list">
                {#each alerts as alert}
                    <div class="alert-row alert-{alert.severity ?? 'info'}">
                        <div class="alert-left">
                            <Badge variant={severityBadge(alert.severity)}
                                >{alert.severity ?? "info"}</Badge
                            >
                            <span class="alert-title"
                                >{alert.title ?? "Alert"}</span
                            >
                        </div>
                        <span class="dim mono"
                            >{alert.timestamp
                                ? fmtDateTime(alert.timestamp)
                                : ""}</span
                        >
                        {#if alert.message}
                            <p class="alert-msg dim">{alert.message}</p>
                        {/if}
                    </div>
                {/each}
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
    }

    .poll-badge {
        font-size: 8px;
        color: var(--t3);
        background: var(--bg3);
        padding: 1px 5px;
        border-radius: var(--r);
    }

    /* ── Table ───────────────────────────────────────────── */
    .table-wrap {
        overflow: auto;
        height: 100%;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
    }
    thead th {
        padding: 5px 8px;
        text-align: left;
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--t3);
        border-bottom: 1px solid var(--b2);
        white-space: nowrap;
        position: sticky;
        top: 0;
        background: var(--bg1);
    }
    tbody tr {
        border-bottom: 1px solid var(--b1);
        transition: background 0.1s;
    }
    tbody tr:hover {
        background: var(--bg3);
    }
    td {
        padding: 5px 8px;
        color: var(--t1);
        white-space: nowrap;
    }
    .dim {
        color: var(--t2);
    }
    .mono {
        font-family: inherit;
    }
    .symbol {
        color: var(--cyan);
        font-weight: 600;
    }
    .message {
        max-width: 260px;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 10px;
        color: var(--t3);
        white-space: nowrap;
    }
    .actions {
        white-space: nowrap;
    }

    /* ── Action buttons ──────────────────────────────────── */
    .act-btn {
        padding: 2px 8px;
        border-radius: var(--r);
        font-size: 10px;
        font-family: inherit;
        cursor: pointer;
        border: none;
        margin-left: 4px;
        transition: opacity 0.15s;
    }
    .act-btn:disabled {
        opacity: 0.35;
        cursor: not-allowed;
    }
    .act-btn.approve {
        background: var(--green-dim);
        color: var(--green);
        border: 1px solid var(--green-brd);
    }
    .act-btn.reject {
        background: var(--red-dim);
        color: var(--red);
        border: 1px solid var(--red-brd);
    }

    /* ── Alerts list ─────────────────────────────────────── */
    .alerts-list {
        display: flex;
        flex-direction: column;
        gap: 1px;
    }
    .alert-row {
        display: grid;
        grid-template-columns: 1fr auto;
        grid-template-rows: auto auto;
        align-items: start;
        gap: 2px 8px;
        padding: 8px 10px;
        border-bottom: 1px solid var(--b1);
        font-size: 11px;
    }
    .alert-left {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .alert-title {
        color: var(--t1);
        font-weight: 500;
    }
    .alert-msg {
        grid-column: 1 / -1;
        font-size: 10px;
        color: var(--t2);
        margin-top: 2px;
    }

    .skeleton-rows {
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 8px;
    }
    .empty {
        padding: 20px;
        font-size: 11px;
        color: var(--t3);
    }
    .err-text {
        font-size: 11px;
        color: var(--red);
        padding: 12px;
    }
</style>
