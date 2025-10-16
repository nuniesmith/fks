// Lightweight API stub for triggering a web build (placeholder for CI/CD integration)
export interface WebBuildResponse { success: boolean; error?: string; }

export async function startWebBuild(): Promise<WebBuildResponse> {
  // In a real implementation, call an internal endpoint or dispatch a webhook.
  await new Promise(r => setTimeout(r, 1200));
  return { success: true };
}
