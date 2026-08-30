'use client';

import { useCallback, useEffect, useState } from 'react';

import { getHealth } from '@/lib/api-client';

type ConnectionState = 'checking' | 'online' | 'offline';

const LABELS: Record<ConnectionState, string> = {
  checking: 'Checking API…',
  online: 'API connected',
  offline: 'API unreachable',
};

export function ApiHealthIndicator() {
  const [state, setState] = useState<ConnectionState>('checking');

  const check = useCallback(async () => {
    try {
      const health = await getHealth();
      setState(health.status === 'ok' ? 'online' : 'offline');
    } catch {
      setState('offline');
    }
  }, []);

  useEffect(() => {
    // The state update happens after the request resolves, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void check();
  }, [check]);

  const retry = () => {
    setState('checking');
    void check();
  };

  return (
    <div className="indicator" data-state={state}>
      <span aria-hidden="true" className="indicator__dot" />
      <span role="status">{LABELS[state]}</span>
      <button className="indicator__retry" onClick={retry} type="button">
        Retry
      </button>
    </div>
  );
}
