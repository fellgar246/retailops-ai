import { NextResponse } from 'next/server';

import { AUTH_PROVIDER, COGNITO_CLIENT_ID, COGNITO_DOMAIN } from '@/lib/server/auth-config';
import { signOutUrl } from '@/lib/server/oidc';
import { clearToken } from '@/lib/server/session';

/** Drop the session here, then end it at the provider when there is one. */
export async function POST(): Promise<NextResponse> {
  await clearToken();
  const hosted = AUTH_PROVIDER === 'cognito' && COGNITO_DOMAIN && COGNITO_CLIENT_ID;
  return NextResponse.json({ redirect: hosted ? signOutUrl() : '/signin' });
}
