import 'server-only';

import { SignJWT } from 'jose';

import {
  APP_ORIGIN,
  COGNITO_CLIENT_ID,
  COGNITO_DOMAIN,
  LOCAL_SECRET,
  callbackUrl,
} from './auth-config';

/** Proof key for the authorization-code exchange. */
export interface Pkce {
  verifier: string;
  challenge: string;
}

export async function createPkce(): Promise<Pkce> {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const verifier = base64Url(bytes);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return { verifier, challenge: base64Url(new Uint8Array(digest)) };
}

export function authorizeUrl(challenge: string): string {
  const params = new URLSearchParams({
    client_id: COGNITO_CLIENT_ID,
    response_type: 'code',
    scope: 'openid email profile',
    redirect_uri: callbackUrl(),
    code_challenge: challenge,
    code_challenge_method: 'S256',
  });
  return `${COGNITO_DOMAIN}/oauth2/authorize?${params.toString()}`;
}

export function signOutUrl(): string {
  const params = new URLSearchParams({
    client_id: COGNITO_CLIENT_ID,
    logout_uri: APP_ORIGIN,
  });
  return `${COGNITO_DOMAIN}/logout?${params.toString()}`;
}

export interface TokenSet {
  idToken: string;
  expiresIn: number;
}

export async function exchangeCode(code: string, verifier: string): Promise<TokenSet> {
  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: COGNITO_CLIENT_ID,
      code,
      redirect_uri: callbackUrl(),
      code_verifier: verifier,
    }),
  });
  if (!response.ok) {
    throw new Error(`the identity provider refused the code exchange (${response.status})`);
  }
  const payload = (await response.json()) as { id_token?: string; expires_in?: number };
  if (!payload.id_token) {
    throw new Error('the identity provider returned no identity token');
  }
  return { idToken: payload.id_token, expiresIn: payload.expires_in ?? 3600 };
}

/**
 * Mint a development token.
 *
 * Only reachable when the local provider is configured. It exists so the
 * application runs with no identity provider and no cost; a deployed
 * environment uses the hosted flow above.
 */
export async function issueLocalToken(
  subject: string,
  name: string,
  roles: string[],
  ttlSeconds: number,
): Promise<string> {
  if (!LOCAL_SECRET) {
    throw new Error('AUTH_LOCAL_SECRET is required for local sign-in');
  }
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ name, roles })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject(subject)
    .setIssuer('retailops-local')
    .setAudience('retailops-api')
    .setIssuedAt(now)
    .setExpirationTime(now + ttlSeconds)
    .sign(new TextEncoder().encode(LOCAL_SECRET));
}

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}
