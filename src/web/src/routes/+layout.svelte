<!--
  Root layout — wraps every route in the terminal chrome.

  - Reads the workspace config loaded by +layout.ts and pushes it into
    Svelte context under the key 'workspace' so any descendant page can
    `getContext<WorkspaceConfig>('workspace')` without prop-drilling.
  - Renders the persistent shell: Strip (top), TabBar (nav), workspace
    (main slot), StatusBar (bottom).

  History note: this file briefly had two <script> blocks (and two
  {@render children()} calls) after a bad merge — kept the markup from
  the first version and the data/context wiring from the second.
-->
<script lang="ts">
    import "../app.css";
    import { setContext } from "svelte";
    import Strip from "$components/shell/Strip.svelte";
    import TabBar from "$components/shell/TabBar.svelte";
    import StatusBar from "$components/shell/StatusBar.svelte";
    import type { WorkspaceConfig } from "$lib/workspaces";

    // Data is loaded by +layout.ts — workspace is already resolved there.
    let { data, children } = $props();

    // Push the resolved config into context so every sub-page can read it
    // without prop-drilling.
    setContext<WorkspaceConfig>("workspace", data.workspace);
</script>

<div class="terminal">
    <Strip />
    <TabBar />
    <main class="workspace">
        {@render children()}
    </main>
    <StatusBar />
</div>

<style>
    .terminal {
        display: flex;
        flex-direction: column;
        height: 100vh;
        overflow: hidden;
    }
    .workspace {
        flex: 1;
        min-height: 0;
        overflow: hidden;
        position: relative;
    }
</style>
