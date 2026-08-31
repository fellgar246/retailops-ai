'use client';

import { useCallback, useEffect, useState } from 'react';

import { ApiError } from './api-client';

export type ResourceState<T> =
  | { status: 'loading'; data: T | null; error: ApiError | null }
  | { status: 'ready'; data: T; error: null }
  | { status: 'error'; data: T | null; error: ApiError }
  | { status: 'empty'; data: T; error: null };

export function useResource<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<unknown>,
  isEmpty: (value: T) => boolean = () => false,
): ResourceState<T> & { reload: () => void } {
  const [state, setState] = useState<ResourceState<T>>({
    status: 'loading',
    data: null,
    error: null,
  });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    // Keep the previous payload visible while a replacement request is in flight.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((current) => ({
      status: 'loading',
      data: current.data,
      error: null,
    }));
    loader(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) {
          return;
        }
        setState(
          isEmpty(data)
            ? { status: 'empty', data, error: null }
            : { status: 'ready', data, error: null },
        );
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const apiError =
          error instanceof ApiError
            ? error
            : new ApiError(error instanceof Error ? error.message : 'Error');
        setState((current) => ({ status: 'error', data: current.data, error: apiError }));
      });
    return () => controller.abort();
    // The caller owns the dependency list, including the loader identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { ...state, reload };
}
