import { NextResponse } from 'next/server';

import { APP_ORIGIN, VERIFIER_COOKIE } from '@/lib/server/auth-config';
import { exchangeCode } from '@/lib/server/oidc';
import { writeToken } from '@/lib/server/session';

/** Complete the hosted sign-in and store the session server-side. */
export async function GET(request: Request): Promise<NextResponse> {
  const url = new URL(request.url);
  const error = url.searchParams.get('error');
  if (error) {
    return NextResponse.redirect(`${APP_ORIGIN}/signin?error=${encodeURIComponent(error)}`);
  }

  const code = url.searchParams.get('code');
  const verifier = request.headers
    .get('cookie')
    ?.split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${VERIFIER_COOKIE}=`))
    ?.split('=')[1];

  if (!code || !verifier) {
    return NextResponse.redirect(`${APP_ORIGIN}/signin?error=incomplete`);
  }

  try {
    const tokens = await exchangeCode(code, verifier);
    await writeToken(tokens.idToken, tokens.expiresIn);
  } catch {
    return NextResponse.redirect(`${APP_ORIGIN}/signin?error=exchange`);
  }

  const response = NextResponse.redirect(APP_ORIGIN);
  response.cookies.delete(VERIFIER_COOKIE);
  return response;
}
