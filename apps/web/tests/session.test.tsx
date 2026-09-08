import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AppShell } from '@/components/shell/AppShell';
import { API_BASE_URL } from '@/lib/config';
import { hasFailed } from '@/lib/use-resource';

import { overviewFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getOverview: vi.fn(async () => overviewFixture),
}));

vi.mock('@/components/ApiHealthIndicator', () => ({
  ApiHealthIndicator: () => <div>API connected</div>,
}));

const replace = vi.fn();

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn(), replace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/use-session', () => ({
  useSession: () => ({
    session: { provider: 'local', user: null },
    loading: false,
    signOut: vi.fn(),
  }),
  canDecide: () => false,
}));

describe('session handling', () => {
  it('sends a visitor without a session to sign in instead of rendering data', async () => {
    render(
      <AppShell>
        <p>contenido</p>
      </AppShell>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/signin'));
    expect(screen.queryByText('contenido')).not.toBeInTheDocument();
  });

  it('keeps the API origin out of the browser bundle', () => {
    // A same-origin path means no build-time knowledge of where the API lives.
    expect(API_BASE_URL).toBe('/api/proxy');
    expect(API_BASE_URL.startsWith('http')).toBe(false);
  });

  it('treats a rejected credential as a failure, not as an endless load', () => {
    expect(hasFailed('unauthenticated')).toBe(true);
    expect(hasFailed('forbidden')).toBe(true);
    expect(hasFailed('error')).toBe(true);
    expect(hasFailed('loading')).toBe(false);
    expect(hasFailed('ready')).toBe(false);
  });
});
