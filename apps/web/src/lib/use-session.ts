'use client';

import { useCallback, useEffect, useState } from 'react';

export interface SessionUser {
  name: string;
  email: string | null;
  roles: string[];
}

export interface SessionState {
  provider: string;
  user: SessionUser | null;
}

/** The signed-in person, as far as the interface needs to know. */
export function useSession() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetch('/api/auth/session', { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((value: SessionState | null) => {
        if (active) {
          setSession(value);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const signOut = useCallback(async () => {
    const response = await fetch('/api/auth/logout', { method: 'POST' });
    const payload = (await response.json()) as { redirect?: string };
    window.location.href = payload.redirect ?? '/signin';
  }, []);

  return { session, loading, signOut };
}

export function canDecide(session: SessionState | null): boolean {
  return session?.user?.roles.includes('reviewer') ?? false;
}
