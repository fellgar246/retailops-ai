import { NextResponse } from 'next/server';

import { AUTH_PROVIDER, VERIFIER_COOKIE, assertCognitoConfigured } from '@/lib/server/auth-config';
import { authorizeUrl, createPkce, issueLocalToken } from '@/lib/server/oidc';
import { writeToken } from '@/lib/server/session';

const LOCAL_TTL_SECONDS = 8 * 60 * 60;

/**
 * Start a sign-in.
 *
 * The hosted provider is sent an authorization-code request with PKCE. The
 * local provider signs a development token directly, because there is no
 * external service to redirect to.
 */
export async function POST(request: Request): Promise<NextResponse> {
  if (AUTH_PROVIDER === 'cognito') {
    assertCognitoConfigured();
    const pkce = await createPkce();
    const response = NextResponse.json({ redirect: authorizeUrl(pkce.challenge) });
    response.cookies.set(VERIFIER_COOKIE, pkce.verifier, {
      httpOnly: true,
      sameSite: 'lax',
      secure: process.env.NODE_ENV === 'production',
      path: '/',
      maxAge: 600,
    });
    return response;
  }

  const form = (await request.json().catch(() => ({}))) as {
    name?: string;
    role?: string;
  };
  const name = (form.name ?? '').trim();
  if (!name) {
    return NextResponse.json({ detail: 'a name is required' }, { status: 400 });
  }
  const role = form.role === 'viewer' ? 'viewer' : 'reviewer';
  const token = await issueLocalToken(`local:${name}`, name, [role], LOCAL_TTL_SECONDS);
  await writeToken(token, LOCAL_TTL_SECONDS);
  return NextResponse.json({ redirect: '/' });
}
