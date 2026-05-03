import type { LayoutLoad } from './$types';
import { resolveWorkspace } from '$lib/workspaces';

export const load: LayoutLoad = ({ params }) => {
  return {
    workspaceName: params.workspace,
    workspace: resolveWorkspace(params.workspace),
  };
};
