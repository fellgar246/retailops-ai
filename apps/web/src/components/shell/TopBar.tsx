'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';

import { ApiHealthIndicator } from '@/components/ApiHealthIndicator';
import { ENVIRONMENT_LABELS, labelOf } from '@/lib/labels';
import { useSession } from '@/lib/use-session';

interface TopBarProps {
  environment: string;
}

export function TopBar({ environment }: TopBarProps) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const { session, signOut } = useSession();

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    const value = query.trim();
    if (!value) {
      return;
    }
    router.push(`/search?q=${encodeURIComponent(value)}`);
  };

  return (
    <header className="topbar">
      <form className="topbar__search" onSubmit={onSearch} role="search">
        <label className="sr-only" htmlFor="global-search">
          Buscar
        </label>
        <input
          id="global-search"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="SKU, proveedor, PO, factura o documento"
          type="search"
          value={query}
        />
      </form>
      <div className="topbar__meta">
        <span className="env-badge">{labelOf(ENVIRONMENT_LABELS, environment)}</span>
        <ApiHealthIndicator />
        {session?.user ? (
          <div className="profile">
            <span className="profile__identity">
              <strong title={session.user.name}>{session.user.name}</strong>
              <span className="muted">
                {session.user.roles.includes('reviewer') ? 'Revisor' : 'Solo lectura'}
              </span>
            </span>
            <button className="btn btn--compact" onClick={() => void signOut()} type="button">
              Cerrar sesión
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
