import type { LayoutLoad } from './$types';
import { resolveWorkspace } from '$lib/workspaces';

export const load: LayoutLoad = () => {
  return {
    workspaceName: 'futures',
    workspace: resolveWorkspace('futures'),
  };
};
