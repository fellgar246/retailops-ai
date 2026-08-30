import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiRequest } from '@/lib/api-client';
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
});
