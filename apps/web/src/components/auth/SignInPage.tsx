'use client';

import { useSearchParams } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

const ERRORS: Record<string, string> = {
  incomplete: 'El proveedor de identidad no devolvió un código válido.',
  exchange: 'No se pudo canjear el código con el proveedor de identidad.',
};

export function SignInPage() {
  const params = useSearchParams();
  const [provider, setProvider] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [role, setRole] = useState('reviewer');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch('/api/auth/session', { cache: 'no-store' })
      .then((response) => response.json())
      .then((value: { provider: string }) => setProvider(value.provider))
      .catch(() => setProvider('local'));
  }, []);

  const failure = params.get('error');

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(provider === 'cognito' ? {} : { name, role }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setError(payload.detail ?? 'No se pudo iniciar sesión');
        return;
      }
      const payload = (await response.json()) as { redirect: string };
      window.location.href = payload.redirect;
    } catch {
      setError('No se pudo contactar con el servicio de identidad');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="signin">
      <section className="panel">
        <h1>RetailOps AI</h1>
        <p className="muted">Consola de operaciones. Se requiere iniciar sesión.</p>
        {failure ? <p role="alert">{ERRORS[failure] ?? 'No se pudo iniciar sesión.'}</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        <form onSubmit={submit}>
          {provider === 'cognito' ? (
            <p className="muted">Continúa con el proveedor de identidad corporativo.</p>
          ) : (
            <>
              <p className="muted">
                Proveedor de desarrollo. Solo disponible fuera de un entorno desplegado.
              </p>
              <div className="field">
                <label htmlFor="name">Nombre</label>
                <input
                  id="name"
                  onChange={(event) => setName(event.target.value)}
                  required
                  value={name}
                />
              </div>
              <div className="field">
                <label htmlFor="role">Permisos</label>
                <select id="role" onChange={(event) => setRole(event.target.value)} value={role}>
                  <option value="reviewer">Revisor (puede decidir)</option>
                  <option value="viewer">Solo lectura</option>
                </select>
              </div>
            </>
          )}
          <button className="btn btn--primary" disabled={busy} type="submit">
            {busy ? 'Entrando…' : 'Iniciar sesión'}
          </button>
        </form>
      </section>
    </main>
  );
}
