'use client';

import { PageHeader } from '@/components/ui/PageHeader';
import { useSession } from '@/lib/use-session';

export function SettingsPage() {
  const { session } = useSession();

  return (
    <>
      <PageHeader
        description="La sesión actual y el entorno al que apunta este cliente."
        title="Configuración"
      />
      <section className="panel">
        <h2>Sesión</h2>
        {session?.user ? (
          <>
            <p>
              Sesión iniciada como <strong>{session.user.name}</strong>
              {session.user.email ? <span className="muted"> ({session.user.email})</span> : null}
            </p>
            <p>
              Permisos:{' '}
              {session.user.roles.length ? (
                session.user.roles.map((role) => (
                  <span className="chip" key={role}>
                    {role === 'reviewer' ? 'Puede decidir' : 'Solo lectura'}
                  </span>
                ))
              ) : (
                <span className="muted">sin permisos asignados</span>
              )}
            </p>
            <p className="muted">
              La identidad procede del proveedor de identidad y queda registrada con cada decisión.
              No puede cambiarse desde esta interfaz.
            </p>
          </>
        ) : (
          <p className="muted">No hay ninguna sesión activa.</p>
        )}
      </section>
      <section className="panel">
        <h2>Entorno</h2>
        <p>
          Proveedor de identidad: <span className="mono">{session?.provider ?? 'desconocido'}</span>
        </p>
        <p className="muted">
          Las llamadas a la API pasan por este mismo origen; la credencial se adjunta en el servidor
          y nunca es accesible desde el navegador.
        </p>
        <p className="muted">
          La edición de tolerancias y la promoción de modelos no están disponibles en esta interfaz.
          Esas políticas se aplican en el backend y en los comandos de operaciones.
        </p>
      </section>
    </>
  );
}
