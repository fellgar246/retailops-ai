import 'server-only';

import { decodeJwt } from 'jose';
import { cookies } from 'next/headers';

import { SESSION_COOKIE } from './auth-config';

/** What the interface may know about the signed-in person. */
export interface SessionUser {
  name: string;
  email: string | null;
  roles: string[];
}

const ROLE_CLAIMS = ['cognito:groups', 'roles'] as const;

export async function readToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function writeToken(token: string, maxAgeSeconds: number): Promise<void> {
  const store = await cookies();
  store.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    // Set over TLS in any deployed environment; plain HTTP only for local work.
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: maxAgeSeconds,
  });
}

export async function clearToken(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}

/**
 * Describe the session for the interface.
 *
 * The claims are read without verifying the signature: this only decides what
 * to render. Every authorization decision is made by the API, which does verify.
 */
export async function readSession(): Promise<SessionUser | null> {
  const token = await readToken();
  if (!token) {
    return null;
  }
  try {
    const claims = decodeJwt(token);
    const expiry = typeof claims.exp === 'number' ? claims.exp : 0;
    if (expiry && expiry * 1000 <= Date.now()) {
      return null;
    }
    return {
      name: String(claims.name ?? claims['cognito:username'] ?? claims.sub ?? 'unknown'),
      email: typeof claims.email === 'string' ? claims.email : null,
      roles: readRoles(claims),
    };
  } catch {
    return null;
  }
}

function readRoles(claims: Record<string, unknown>): string[] {
  for (const claim of ROLE_CLAIMS) {
    const value = claims[claim];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === 'string');
    }
  }
  return [];
}
