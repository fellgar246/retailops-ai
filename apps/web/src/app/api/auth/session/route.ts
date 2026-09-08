import { NextResponse } from 'next/server';

import { AUTH_PROVIDER } from '@/lib/server/auth-config';
import { readSession } from '@/lib/server/session';

/** Describe the current session so the shell can render it. */
export async function GET(): Promise<NextResponse> {
  const user = await readSession();
  return NextResponse.json({ provider: AUTH_PROVIDER, user });
}
