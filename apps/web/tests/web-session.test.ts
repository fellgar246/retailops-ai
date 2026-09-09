import { beforeEach, describe, expect, it, vi } from 'vitest';

const store = new Map<string, string>();

vi.mock('next/headers', () => ({
  cookies: async () => ({
    get: (name: string) => {
      const value = store.get(name);
      return value === undefined ? undefined : { name, value };
    },
    set: vi.fn(),
    delete: vi.fn(),
  }),
}));

function base64Url(value: object): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

/**
 * Build a token the way the session reader consumes one.
 *
 * The reader decodes without verifying, because every authorization decision is
 * made by the API. A signature here would test nothing, so the segment is a
 * placeholder.
 */
function token(claims: Record<string, unknown>, secondsFromNow: number): string {
  const now = Math.floor(Date.now() / 1000);
  const payload = { iat: now, exp: now + secondsFromNow, ...claims };
  return `${base64Url({ alg: 'HS256', typ: 'JWT' })}.${base64Url(payload)}.signature`;
}

async function signedInWith(claims: Record<string, unknown>, seconds = 600) {
  store.set('retailops.session', token(claims, seconds));
  const { readSession } = await import('@/lib/server/session');
  return readSession();
}

describe('readSession', () => {
  beforeEach(() => {
    store.clear();
    vi.resetModules();
  });

  it('shows the email rather than the pool-generated username', async () => {
    // A pool that signs people in by email issues an opaque internal username.
    // Showing it would put an identifier where a person's name belongs, and it
    // would reach the audit trail through the same claim.
    const session = await signedInWith({
      sub: '00000000-1111-2222-3333-444444444444',
      email: 'reviewer@retailops.test',
      'cognito:username': '00000000-1111-2222-3333-444444444444',
      'cognito:groups': ['reviewer'],
    });

    expect(session?.name).toBe('reviewer@retailops.test');
    expect(session?.roles).toEqual(['reviewer']);
  });

  it('prefers an explicit display name when the pool has one', async () => {
    const session = await signedInWith({
      sub: 'abc',
      name: 'Ana Operator',
      email: 'ana@example.test',
    });

    expect(session?.name).toBe('Ana Operator');
  });

  it('falls back to the username only when nothing readable exists', async () => {
    const session = await signedInWith({ sub: 'abc', 'cognito:username': 'operator-42' });

    expect(session?.name).toBe('operator-42');
  });

  it('reads roles from the local provider claim too', async () => {
    const session = await signedInWith({ sub: 'x', name: 'Dev', roles: ['viewer'] });

    expect(session?.roles).toEqual(['viewer']);
  });

  it('reports no session once the token has expired', async () => {
    expect(await signedInWith({ sub: 'x', name: 'Dev' }, -60)).toBeNull();
  });

  it('reports no session when there is no cookie', async () => {
    const { readSession } = await import('@/lib/server/session');

    expect(await readSession()).toBeNull();
  });

  it('reports no session when the cookie is not a token', async () => {
    store.set('retailops.session', 'not-a-token');
    const { readSession } = await import('@/lib/server/session');

    expect(await readSession()).toBeNull();
  });
});
