/**
 * Workspace Registry
 *
 * A "workspace" is a named trading environment that has its own API backend.
 * Pages under /[workspace]/* read their API base from the resolved WorkspaceConfig
 * so the same Svelte components work for any asset class — futures, crypto, equities.
 *
 * To add a new asset class:
 *   1. Add an entry to WORKSPACES below.
 *   2. Spin up the corresponding API service (same contract as web/app.py).
 *   3. Add a /[prefix]/ proxy to vite.config.ts (dev) and nginx conf (prod).
 *   4. The TabBar will automatically generate a nav group for it.
 */

export interface WorkspaceConfig {
    /** Human-readable name shown in the TabBar group label. */
    label: string;

    /**
     * Base path for the main API.
     * e.g. '/fapi/api' → calls go to /fapi/api/dashboard, /fapi/api/trades, …
     */
    apiBase: string;

    /**
     * Base path for the task-runner API (if this workspace has one).
     * e.g. '/fapi/tasks' → /fapi/tasks/api/list, /fapi/tasks/api/run, …
     * Leave undefined to hide the Tasks tab and disable backtesting.
     */
    tasksBase?: string;

    /**
     * Whether to show the CNN / ML signals tab.
     * Only meaningful for workspaces whose API exposes /cnn/status.
     */
    hasCnn?: boolean;

    /** CSS color token used for the TabBar group label dot. */
    color: string;
}

/** Registry of all configured trading workspaces. */
export const WORKSPACES: Record<string, WorkspaceConfig> = {
    // ── KuCoin Futures ───────────────────────────────────────────────
    futures: {
        label: "Futures",
        apiBase: "/fapi/api",
        tasksBase: "/fapi/tasks",
        hasCnn: true,
        color: "var(--amber)",
    },

    // ── Kraken Crypto Spot ─────────────────────────────────────────
    // Uncomment when fks_crypto service is running.
    // crypto_spot: {
    //   label:   'Crypto Spot',
    //   apiBase: '/capi/api',
    //   hasCnn:  false,
    //   color:   'var(--cyan)',
    // },

    // ── Rithmic CME Futures ────────────────────────────────────────
    // Uncomment when Rithmic credentials are available.
    // rithmic: {
    //   label:     'Rithmic',
    //   apiBase:   '/rapi/api',
    //   tasksBase: '/rapi/tasks',
    //   hasCnn:    true,
    //   color:     'var(--purple)',
    // },
};

/**
 * Resolve a workspace name to its config.
 * Returns a sensible fallback so unknown workspaces never hard-crash.
 */
export function resolveWorkspace(name: string): WorkspaceConfig {
    return (
        WORKSPACES[name] ?? {
            label: name
                ? name.charAt(0).toUpperCase() + name.slice(1)
                : "Unknown",
            apiBase: "/api",
            color: "var(--t2)",
        }
    );
}

/** Ordered list of all registered workspaces. */
export const workspaceList = Object.entries(WORKSPACES).map(([id, cfg]) => ({
    id,
    ...cfg,
}));
