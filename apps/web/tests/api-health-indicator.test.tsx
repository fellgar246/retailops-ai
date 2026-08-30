import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiHealthIndicator } from '@/components/ApiHealthIndicator';

function mockFetch(implementation: () => Promise<Response>) {
  const fetchMock = vi.fn(implementation);
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiHealthIndicator', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reports a healthy API', async () => {
    mockFetch(async () => jsonResponse({ status: 'ok' }));

    render(<ApiHealthIndicator />);

    expect(await screen.findByText('API connected')).toBeInTheDocument();
  });

  it('handles connectivity errors gracefully', async () => {
    mockFetch(async () => {
      throw new TypeError('Failed to fetch');
    });

    render(<ApiHealthIndicator />);

    expect(await screen.findByText('API unreachable')).toBeInTheDocument();
  });

  it('re-checks connectivity when retrying', async () => {
    let healthy = false;
    const fetchMock = mockFetch(async () =>
      healthy ? jsonResponse({ status: 'ok' }) : jsonResponse({ detail: 'down' }, 503),
    );

    render(<ApiHealthIndicator />);
    expect(await screen.findByText('API unreachable')).toBeInTheDocument();

    healthy = true;
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(screen.getByText('API connected')).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
