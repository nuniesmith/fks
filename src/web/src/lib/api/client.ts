/**
 * FKS API Client — typed fetch wrapper for the Ruby Data Service.
 *
 * All requests go through the Vite dev proxy or the Nginx reverse proxy
 * in production, so we use relative URLs.
 */

const DEFAULT_TIMEOUT = 15_000;

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body?: unknown,
  ) {
    super(`API ${status}: ${statusText}`);
    this.name = 'ApiError';
  }
}

interface FetchOptions extends Omit<RequestInit, 'body'> {
  timeout?: number;
  body?: unknown;
}

async function request<T>(url: string, opts: FetchOptions = {}): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, body, ...init } = opts;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const headers: Record<string, string> = {
      Accept: 'application/json',
      ...(init.headers as Record<string, string> ?? {}),
    };

    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(url, {
      ...init,
      headers,
      signal: controller.signal,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      const errBody = await res.text().catch(() => undefined);
      throw new ApiError(res.status, res.statusText, errBody);
    }

    const text = await res.text();
    return text ? JSON.parse(text) : ({} as T);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: <T>(url: string, opts?: FetchOptions) => request<T>(url, { ...opts, method: 'GET' }),
  post: <T>(url: string, body?: unknown, opts?: FetchOptions) =>
    request<T>(url, { ...opts, method: 'POST', body }),
  put: <T>(url: string, body?: unknown, opts?: FetchOptions) =>
    request<T>(url, { ...opts, method: 'PUT', body }),
  delete: <T>(url: string, opts?: FetchOptions) => request<T>(url, { ...opts, method: 'DELETE' }),
};
