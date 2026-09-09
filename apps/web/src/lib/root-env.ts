import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Read the repository-root environment file into `process.env`.
 *
 * Configuration lives in one file that the backend also reads. Next only looks
 * inside this package, so it is loaded explicitly at startup. A variable
 * already present in the real environment always wins, which is what a
 * container and a deployed task rely on.
 *
 * Not marked server-only: it runs while the configuration is evaluated, before
 * any React context exists.
 */
/** A mutable environment map. Narrower than `NodeJS.ProcessEnv`, which
 * requires keys a caller has no reason to supply. */
type EnvMap = Record<string, string | undefined>;

export function loadRootEnv(
  root: string = join(process.cwd(), '..', '..'),
  env: EnvMap = process.env,
): void {
  let contents: string;
  try {
    contents = readFileSync(join(root, '.env'), 'utf8');
  } catch {
    // Absent in a container, where the platform supplies the environment.
    return;
  }

  for (const line of contents.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }
    const separator = trimmed.indexOf('=');
    if (separator === -1) {
      continue;
    }
    const key = trimmed.slice(0, separator).trim();
    if (!key || key in env) {
      continue;
    }
    env[key] = unquote(trimmed.slice(separator + 1).trim());
  }
}

function unquote(value: string): string {
  const quoted =
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"));
  return quoted && value.length >= 2 ? value.slice(1, -1) : value;
}
