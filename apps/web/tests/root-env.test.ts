import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { loadRootEnv } from '@/lib/root-env';

function rootWith(contents: string): string {
  const dir = mkdtempSync(join(tmpdir(), 'retailops-env-'));
  writeFileSync(join(dir, '.env'), contents);
  return dir;
}

describe('root environment file', () => {
  it('loads the variables the identity flow needs', () => {
    const root = rootWith(
      [
        'AUTH_PROVIDER=cognito',
        'COGNITO_CLIENT_ID=abc123',
        'COGNITO_DOMAIN=https://example.auth.us-east-1.amazoncognito.com',
      ].join('\n'),
    );
    const env: Record<string, string | undefined> = {};

    loadRootEnv(root, env);

    expect(env.AUTH_PROVIDER).toBe('cognito');
    expect(env.COGNITO_CLIENT_ID).toBe('abc123');
    // A value containing separators must survive intact.
    expect(env.COGNITO_DOMAIN).toBe('https://example.auth.us-east-1.amazoncognito.com');
  });

  it('never overrides a variable the platform already set', () => {
    const root = rootWith('AUTH_PROVIDER=local');
    const env: Record<string, string | undefined> = { AUTH_PROVIDER: 'cognito' };

    loadRootEnv(root, env);

    expect(env.AUTH_PROVIDER).toBe('cognito');
  });

  it('ignores comments, blank lines and malformed entries', () => {
    const root = rootWith(['# a comment', '', 'NO_SEPARATOR', '  SPACED = value  '].join('\n'));
    const env: Record<string, string | undefined> = {};

    loadRootEnv(root, env);

    expect(env.SPACED).toBe('value');
    expect(Object.keys(env)).toEqual(['SPACED']);
  });

  it('strips surrounding quotes', () => {
    const root = rootWith(['A="quoted"', "B='single'", 'C=bare'].join('\n'));
    const env: Record<string, string | undefined> = {};

    loadRootEnv(root, env);

    expect(env.A).toBe('quoted');
    expect(env.B).toBe('single');
    expect(env.C).toBe('bare');
  });

  it('is silent when there is no file, as in a container', () => {
    const env: Record<string, string | undefined> = {};

    expect(() => loadRootEnv(join(tmpdir(), 'retailops-absent'), env)).not.toThrow();
    expect(env).toEqual({});
  });
});
