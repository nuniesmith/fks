// Lightweight AI client for backend /api/ai endpoints (Ollama proxy)
// Reads base URL and token from localStorage (fallbacks to /api)

export type ChatMessage = {
  role: 'system' | 'user' | 'assistant';
  content: string;
};

function getApiBase(): string {
  if (typeof window === 'undefined') return '/api';
  return localStorage.getItem('fks_api_base_url') || (import.meta as any)?.env?.VITE_API_BASE_URL || '/api';
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('fks_api_token') || '';
    if (token) {
      h['Authorization'] = `Bearer ${token}`;
      h['X-API-Key'] = token;
    }
  }
  return h;
}

export async function aiHealth(): Promise<{ ok: boolean; error?: string }> {
  const base = getApiBase();
  try {
    const r = await fetch(`${base}/ai/ollama/health`, { headers: authHeaders() });
    return await r.json();
  } catch (e: any) {
    return { ok: false, error: e?.message || String(e) };
  }
}

export async function aiPullModel(model?: string): Promise<any> {
  const base = getApiBase();
  const body = model ? { model } : {};
  const r = await fetch(`${base}/ai/ollama/pull`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function chat(messages: ChatMessage[], opts?: { model?: string; stream?: boolean; options?: Record<string, any> }): Promise<string> {
  const base = getApiBase();
  const r = await fetch(`${base}/ai/chat`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ messages, model: opts?.model, stream: false, options: opts?.options || {} }),
  });
  const data = await r.json();
  // Ollama chat returns either { message: { content } } in stream or aggregated in response
  // Proxy may return different shapes; best effort extraction:
  const content = data?.message?.content || data?.content || data?.response || '';
  return typeof content === 'string' ? content : JSON.stringify(data);
}

export async function generate(prompt: string, opts?: { model?: string; stream?: boolean; options?: Record<string, any> }): Promise<string> {
  const base = getApiBase();
  const r = await fetch(`${base}/ai/generate`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ prompt, model: opts?.model, stream: false, options: opts?.options || {} }),
  });
  const data = await r.json();
  return data?.response || data?.content || '';
}

export async function chatStream(
  messages: ChatMessage[],
  opts: { model?: string; options?: Record<string, any>; signal?: AbortSignal } = {},
  onToken?: (t: string) => void
): Promise<string> {
  const base = getApiBase();
  const res = await fetch(`${base}/ai/chat/stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ messages, model: opts.model, options: opts.options || {} }),
    signal: opts.signal,
  });
  const reader = res.body?.getReader();
  const decoder = new TextDecoder('utf-8');
  let full = '';
  if (!reader) return full;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    // Ollama streams NDJSON lines; each line has { message: { content: '...' }, done: boolean }
    const lines = chunk.split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        const piece = obj?.message?.content || obj?.response || '';
        if (piece) {
          full += piece;
          onToken?.(piece);
        }
      } catch {
        // Fallback: treat as raw text
        full += line;
        onToken?.(line);
      }
    }
  }
  return full;
}

export async function generateStream(
  prompt: string,
  opts: { model?: string; options?: Record<string, any>; signal?: AbortSignal } = {},
  onToken?: (t: string) => void
): Promise<string> {
  const base = getApiBase();
  const res = await fetch(`${base}/ai/generate/stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ prompt, model: opts.model, options: opts.options || {} }),
    signal: opts.signal,
  });
  const reader = res.body?.getReader();
  const decoder = new TextDecoder('utf-8');
  let full = '';
  if (!reader) return full;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        const piece = obj?.response || obj?.message?.content || '';
        if (piece) {
          full += piece;
          onToken?.(piece);
        }
      } catch {
        full += line;
        onToken?.(line);
      }
    }
  }
  return full;
}

export async function embeddings(input: string, opts?: { model?: string }): Promise<number[] | number[][]> {
  const base = getApiBase();
  const r = await fetch(`${base}/ai/embeddings`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ input, model: opts?.model }),
  });
  const data = await r.json();
  // Ollama embeddings usually { embedding: number[] }
  return data?.embedding || data?.embeddings || [];
}
