export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:4000';
async function fetchJson<T>(url: string, options: RequestInit = {}, timeoutMs = 120000): Promise<T> {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    if (!res.ok) {
      const txt = await res.text().catch(() => res.statusText);
      throw new Error(`${res.status} ${res.statusText}: ${txt}`);
    }
    return res.json() as Promise<T>;
  } finally { clearTimeout(t); }
}
export interface BuildResponse { success: boolean; stdout?: string; stderr?: string; error?: string; }
export interface PackageResponse { success: boolean; size?: number; error?: string; }
export const startBuild = () => fetchJson<BuildResponse>(`${API_BASE}/api/build`, { method: 'POST', headers: { 'Content-Type': 'application/json' } }, 300000);
export const packageAddon = () => fetchJson<PackageResponse>(`${API_BASE}/api/package`, { method: 'POST', headers: { 'Content-Type': 'application/json' } }, 120000);
export const generateTemplate = (type: string, fileName: string) => fetchJson<any>(`${API_BASE}/api/template`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, fileName }) }, 60000);
export async function downloadAddon(): Promise<Blob> { const res = await fetch(`${API_BASE}/api/download/fks_addon.zip`); if (!res.ok) throw new Error('Download failed'); return res.blob(); }
export async function checkHealth(): Promise<boolean> { try { const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(5000) }); return res.ok; } catch { return false; } }
