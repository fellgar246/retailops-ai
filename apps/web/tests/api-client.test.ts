import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiRequest, buildQuery } from '@/lib/api-client';
import { API_BASE_URL } from '@/lib/config';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiRequest', () => {
  it('calls the configured API base URL', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(JSON.stringify({ status: 'ok' })),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiRequest('/health')).resolves.toEqual({ status: 'ok' });
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/health`, expect.anything());
  });

  it('raises an ApiError carrying the HTTP status', async () => {
    vi.stubGlobal('fetch', async () => new Response('nope', { status: 500 }));

    await expect(apiRequest('/health')).rejects.toMatchObject({
      name: 'ApiError',
      status: 500,
    });
  });

  it('wraps network failures in an ApiError', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('Failed to fetch');
    });

    await expect(apiRequest('/health')).rejects.toBeInstanceOf(ApiError);
  });

  it('encodes pagination and repeated filters', () => {
    expect(buildQuery({ limit: 50, offset: 0, status: ['open', 'in_review'] })).toBe(
      '?limit=50&offset=0&status=open&status=in_review',
    );
  });

  it('reads FastAPI error detail and honours cancellation', async () => {
    vi.stubGlobal(
      'fetch',
      async () =>
        new Response(JSON.stringify({ detail: 'limit must be between 1 and 200' }), {
          status: 400,
        }),
    );
    await expect(apiRequest('/forecasts')).rejects.toMatchObject({
      status: 400,
      detail: 'limit must be between 1 and 200',
    });

    const controller = new AbortController();
    vi.stubGlobal('fetch', async (_url: string, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () =>
          reject(new DOMException('Aborted', 'AbortError')),
        );
      });
    });
    const pending = apiRequest('/forecasts', { signal: controller.signal, timeoutMs: 50 });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'ApiError' });
  });
});
