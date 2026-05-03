<script lang="ts">
  import '../app.css';
  import Strip from '$components/shell/Strip.svelte';
  import TabBar from '$components/shell/TabBar.svelte';
  import StatusBar from '$components/shell/StatusBar.svelte';

  let { children } = $props();
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
<script lang="ts">
  import { setContext } from 'svelte';
  import type { WorkspaceConfig } from '$lib/workspaces';

  // Data is loaded by +layout.ts — workspace is already resolved there.
  let { data, children } = $props();

  // Push the resolved config into context so every sub-page can read it
  // without prop-drilling. The context key is a symbol to avoid collisions.
  setContext<WorkspaceConfig>('workspace', data.workspace);
</script>

{@render children()}
