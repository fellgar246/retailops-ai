'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { getJob } from './api';
import { ApiError } from './api-client';
import type { Job } from './types';

const TERMINAL: ReadonlySet<string> = new Set(['succeeded', 'failed', 'cancelled']);
const POLL_INTERVAL_MS = 1500;

export function isSettled(job: Job | null): boolean {
  return job !== null && TERMINAL.has(job.state);
}

/**
 * Follow a job until it settles.
 *
 * Each state schedules the next look, so there is no loop to leave running:
 * a terminal job schedules nothing, unmounting cancels what was pending, and a
 * rejected request stops the chase rather than retrying forever against a
 * session that has gone.
 */
export function useJob(onSettled?: () => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const notified = useRef<number | null>(null);
  const settledCallback = useRef(onSettled);

  useEffect(() => {
    settledCallback.current = onSettled;
  }, [onSettled]);

  useEffect(() => {
    if (job === null || isSettled(job) || error !== null) {
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      getJob(job.id)
        .then((next) => {
          if (!cancelled) {
            setJob(next);
          }
        })
        .catch((cause: unknown) => {
          if (cancelled) {
            return;
          }
          setError(
            cause instanceof ApiError ? cause : new ApiError('No se pudo consultar el trabajo'),
          );
        });
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [job, error]);

  // Telling the caller is a side effect, so it happens after a render, once.
  useEffect(() => {
    if (job === null || !isSettled(job) || notified.current === job.id) {
      return;
    }
    notified.current = job.id;
    settledCallback.current?.();
  }, [job]);

  const track = useCallback((started: Job) => {
    notified.current = null;
    setError(null);
    setJob(started);
  }, []);

  const reset = useCallback(() => {
    notified.current = null;
    setJob(null);
    setError(null);
  }, []);

  return { job, error, track, reset, settled: isSettled(job) };
}
