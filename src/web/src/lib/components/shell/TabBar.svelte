<script lang="ts">
    import { page } from "$app/stores";
    import { goto } from "$app/navigation";
    import { workspaceList } from "$lib/workspaces";

    type Tab = {
        id: string;
        label: string;
        dot?: string;
        key?: string;
        shiftKey?: string;
        href: string;
    };

    type Group = {
        label: string;
        color: string;
        tabs: Tab[];
    };

    // ── Static nav groups ─────────────────────────────────────────────────

    // Only janus/Prometheus/QuestDB-backed pages are listed; the Ruby-only tabs
    // (news, crypto, dom, paper, sims, positions, journal, analysis, chains, data,
    // db, backup) were pruned in the WebUI→janus repoint (Phase 4). Their route
    // dirs still exist (reachable by URL) until a later cleanup slice removes them.
    const staticGroups: Group[] = [
        {
            label: "Markets",
            color: "var(--cyan, #00e5ff)",
            tabs: [
                {
                    id: "overview",
                    label: "Overview",
                    dot: "var(--cyan)",
                    key: "1",
                    href: "/",
                },
                { id: "charts", label: "Charts", key: "2", href: "/charts" },
            ],
        },
        {
            label: "Trading",
            color: "var(--green, #16c784)",
            tabs: [
                {
                    id: "trading",
                    label: "Trading",
                    dot: "var(--green)",
                    key: "3",
                    href: "/trading",
                },
                {
                    id: "signals",
                    label: "Signals",
                    dot: "var(--amber)",
                    key: "4",
                    href: "/signals",
                },
                { id: "performance", label: "Perf", key: "5", href: "/performance" },
            ],
        },
        {
            label: "Analysis",
            color: "var(--purple, #b388ff)",
            tabs: [
                {
                    id: "janus-ai",
                    label: "Janus AI",
                    dot: "var(--green)",
                    key: "6",
                    href: "/janus-ai",
                },
                { id: "docs", label: "Docs", shiftKey: "1", href: "/docs" },
            ],
        },
    ];

    /**
     * Build one tab list per registered workspace.
     * CNN and Tasks tabs are always included; the page itself shows a
     * "not configured" message when the workspace doesn't support them.
     */
    function workspaceTabs(id: string): Tab[] {
        return [
            {
                id: `${id}-dash`,
                label: "Dashboard",
                dot: "var(--amber)",
                href: `/${id}`,
            },
            {
                id: `${id}-signals`,
                label: "Signals",
                dot: "var(--green)",
                href: `/${id}/signals`,
            },
            { id: `${id}-pnl`, label: "PnL", href: `/${id}/pnl` },
            { id: `${id}-trades`, label: "Trades", href: `/${id}/trades` },
            {
                id: `${id}-cnn`,
                label: "CNN",
                dot: "var(--purple)",
                href: `/${id}/cnn`,
            },
            { id: `${id}-logging`, label: "Logs", href: `/${id}/logging` },
            { id: `${id}-tasks`, label: "Tasks", href: `/${id}/tasks` },
            { id: `${id}-assets`, label: "Assets", href: `/${id}/assets` },
            {
                id: `${id}-reporting`,
                label: "Reports",
                href: `/${id}/reporting`,
            },
        ];
    }

    const workspaceGroups: Group[] = workspaceList.map((ws) => ({
        label: ws.label,
        color: ws.color,
        tabs: workspaceTabs(ws.id),
    }));

    const systemGroup: Group = {
        label: "System",
        color: "var(--t3, #555)",
        tabs: [
            { id: "settings", label: "Settings", key: "7", href: "/settings" },
            {
                id: "monitoring",
                label: "Monitoring",
                dot: "var(--purple)",
                key: "8",
                href: "/monitoring",
            },
            {
                id: "bots",
                label: "Bots",
                dot: "var(--cyan)",
                key: "9",
                href: "/bots",
            },
        ],
    };

    const groups: Group[] = [...staticGroups, ...workspaceGroups, systemGroup];

    // ── Active-state helpers ──────────────────────────────────────────────

    const allTabs = groups.flatMap((g) => g.tabs);
    const wsDashHrefs = new Set(workspaceList.map((ws) => `/${ws.id}`));

    let currentPath = $derived($page.url.pathname);

    function isActive(href: string): boolean {
        if (href === "/") return currentPath === "/";
        // Workspace dashboard tabs: exact match only so /futures/trades
        // does not also light up the /futures dashboard tab.
        if (wsDashHrefs.has(href)) return currentPath === href;
        return currentPath.startsWith(href);
    }

    // ── Keyboard shortcuts ────────────────────────────────────────────────

    function handleKeydown(e: KeyboardEvent) {
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        const tag = document.activeElement?.tagName ?? "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

        const digit = e.code.startsWith("Digit") ? e.code.slice(5) : null;

        if (e.shiftKey) {
            const tab = digit
                ? allTabs.find((t) => t.shiftKey === digit)
                : undefined;
            if (tab) {
                e.preventDefault();
                goto(tab.href);
            }
        } else {
            const tab =
                allTabs.find((t) => t.key === e.key) ??
                (digit ? allTabs.find((t) => t.key === digit) : undefined);
            if (tab) {
                e.preventDefault();
                goto(tab.href);
            }
        }
    }

    $effect(() => {
        document.addEventListener("keydown", handleKeydown, true);
        return () =>
            document.removeEventListener("keydown", handleKeydown, true);
    });
</script>

<nav class="tabbar" aria-label="Workspace navigation">
    {#each groups as group, gi}
        {#if gi > 0}
            <div class="group-sep" aria-hidden="true"></div>
        {/if}
        <div class="group" role="group" aria-label="{group.label} workspaces">
            <span
                class="group-lbl"
                aria-hidden="true"
                style="color: {group.color}">{group.label}</span
            >
            {#each group.tabs as tab}
                <a
                    class="tab"
                    class:active={isActive(tab.href)}
                    href={tab.href}
                    aria-current={isActive(tab.href) ? "page" : undefined}
                    data-sveltekit-preload-data="hover"
                >
                    {#if tab.dot}
                        <span class="dot" style="background: {tab.dot}"></span>
                    {/if}
                    {tab.label}
                    {#if tab.key}
                        <kbd class="shortcut" aria-hidden="true">{tab.key}</kbd>
                    {:else if tab.shiftKey}
                        <kbd class="shortcut" aria-hidden="true"
                            >⇧{tab.shiftKey}</kbd
                        >
                    {/if}
                </a>
            {/each}
        </div>
    {/each}
</nav>

<style>
    .tabbar {
        height: var(--tabbar-h);
        background: var(--bg1);
        border-bottom: 1px solid var(--b2);
        display: flex;
        align-items: stretch;
        padding-top: 14px;
        overflow-x: auto;
        overflow-y: hidden;
        flex-shrink: 0;
        scrollbar-width: none;
    }
    .tabbar::-webkit-scrollbar {
        display: none;
    }

    .group {
        display: flex;
        align-items: flex-end;
        position: relative;
        padding-bottom: 2px;
    }

    .group-lbl {
        position: absolute;
        top: -12px;
        left: 0;
        font-size: 7px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        opacity: 0.7;
        white-space: nowrap;
        pointer-events: none;
        line-height: 1;
    }

    .group-sep {
        width: 1px;
        background: var(--b2);
        margin: 8px 2px 4px;
        align-self: stretch;
        flex-shrink: 0;
    }

    .tab {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 0 11px;
        font-size: 11px;
        color: var(--t2);
        text-decoration: none;
        white-space: nowrap;
        border-bottom: 2px solid transparent;
        transition:
            color 0.15s,
            border-color 0.15s;
        cursor: pointer;
    }
    .tab:hover {
        color: var(--t1);
        background: var(--bg3);
    }
    .tab.active {
        color: var(--t1);
        border-bottom-color: var(--accent);
    }

    .dot {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .shortcut {
        font-size: 8px;
        color: var(--t3);
        opacity: 0.5;
        margin-left: 2px;
        font-family: inherit;
    }
</style>
