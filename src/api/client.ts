/**
 * Thin typed transport over the mission-control HTTP API.
 *
 * Every call funnels through here so retries, base-URL resolution and error
 * shape stay in one place rather than being re-implemented per call site.
 */

/**
 * Same-origin in production (the Python server serves the built bundle);
 * Vite's dev proxy forwards `/api` to the backend, so the empty base works
 * in both modes. Override with VITE_API_BASE when hosting the UI elsewhere.
 */
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), init);
  } catch (cause) {
    // Status 0 distinguishes "never reached the server" from an HTTP error.
    const err = new ApiError(`Network failure calling ${path}`, 0, path);
    err.cause = cause;
    throw err;
  }
  if (!res.ok) {
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, path);
  }
  return (await res.json()) as T;
}

export function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal });
}

export function post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
}
