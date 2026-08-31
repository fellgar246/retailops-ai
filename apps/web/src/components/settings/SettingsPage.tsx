'use client';

import { useState } from 'react';

import { API_BASE_URL } from '@/lib/config';
import { readReviewer, writeReviewer } from '@/lib/reviewer';
import { PageHeader } from '@/components/ui/PageHeader';

export function SettingsPage() {
  const [reviewer, setReviewer] = useState(() => readReviewer());
  const [saved, setSaved] = useState(false);

  return (
    <>
      <PageHeader
        description="Identidad local de revisión y el entorno al que apunta este cliente."
        title="Configuración"
      />
      <section className="panel">
        <h2>Identidad de revisión</h2>
        <p className="muted">
          No hay inicio de sesión. El nombre se envía con cada decisión y queda en el historial.
        </p>
        <form
          className="field"
          onSubmit={(event) => {
            event.preventDefault();
            setReviewer(writeReviewer(reviewer));
            setSaved(true);
          }}
        >
          <label htmlFor="reviewer">Revisor</label>
          <input
            id="reviewer"
            onChange={(event) => {
              setReviewer(event.target.value);
              setSaved(false);
            }}
            value={reviewer}
          />
          <button className="btn btn--primary" type="submit">
            Guardar nombre
          </button>
          {saved ? <p role="status">Nombre guardado en este navegador.</p> : null}
        </form>
      </section>
      <section className="panel">
        <h2>Entorno</h2>
        <p>
          API: <span className="mono">{API_BASE_URL}</span>
        </p>
        <p className="muted">
          Permisos por rol, edición de tolerancias y promoción de modelos no están disponibles en
          esta interfaz. Esas políticas se aplican en el backend y en los comandos de operaciones.
        </p>
      </section>
    </>
  );
}
