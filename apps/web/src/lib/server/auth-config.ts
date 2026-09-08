import 'server-only';

/**
 * Server-side identity configuration.
 *
 * None of these values reach the browser. The access token is held in an
 * httpOnly cookie and attached by the proxy route, so page scripts never see a
 * credential and the API origin stays private.
 */

export type AuthProvider = 'local' | 'cognito';

export const AUTH_PROVIDER = (process.env.AUTH_PROVIDER ?? 'local') as AuthProvider;

/** Where the API actually listens. Read on the server only. */
export const API_ORIGIN = (process.env.API_ORIGIN ?? 'http://localhost:8000').replace(/\/$/, '');

/** Shared with the backend so development tokens validate. */
export const LOCAL_SECRET = process.env.AUTH_LOCAL_SECRET ?? '';

export const COGNITO_DOMAIN = (process.env.COGNITO_DOMAIN ?? '').replace(/\/$/, '');
export const COGNITO_CLIENT_ID = process.env.COGNITO_CLIENT_ID ?? '';
export const APP_ORIGIN = (process.env.APP_ORIGIN ?? 'http://localhost:3000').replace(/\/$/, '');

export const SESSION_COOKIE = 'retailops.session';
export const VERIFIER_COOKIE = 'retailops.verifier';

export function callbackUrl(): string {
  return `${APP_ORIGIN}/api/auth/callback`;
}

export function assertCognitoConfigured(): void {
  if (!COGNITO_DOMAIN || !COGNITO_CLIENT_ID) {
    throw new Error('COGNITO_DOMAIN and COGNITO_CLIENT_ID are required for hosted sign-in');
  }
}
