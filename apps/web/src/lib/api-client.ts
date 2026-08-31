import { API_BASE_URL } from './config';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly detail?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export type QueryValue = string | number | boolean | Array<string | number> | undefined | null;

export interface RequestOptions extends Omit<RequestInit, 'body' | 'signal'> {
  body?: unknown;
  query?: Record<string, QueryValue>;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export function buildQuery(query: Record<string, QueryValue> | undefined): string {
  if (!query) {
    return '';
  }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, String(item));
      }
    } else {
      params.append(key, String(value));
    }
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, query, timeoutMs = 8000, headers, signal, ...rest } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort);

  try {
    const response = await fetch(`${API_BASE_URL}${path}${buildQuery(query)}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });

    if (!response.ok) {
      const detail = await readDetail(response);
      throw new ApiError(detail ?? `Request to ${path} failed`, response.status, detail);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request was cancelled');
    }
    throw new ApiError(error instanceof Error ? error.message : `Request to ${path} failed`);
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', onAbort);
  }
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === 'string') {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
        .join('; ');
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export interface HealthResponse {
  status: string;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal });
}
