import { formatRelative } from '@/lib/format';

interface FreshnessBarProps {
  updatedAt?: string | null;
  stale: boolean;
  error?: Error | null;
  onRefresh: () => void;
}

export function FreshnessBar({ updatedAt, stale, error, onRefresh }: FreshnessBarProps) {
  return (
    <div className="freshness">
      {stale ? (
        <div className="notice notice--stale" role="status">
          Actualizando… se muestra la última versión cargada.
        </div>
      ) : null}
      {error ? (
        <div className="notice notice--error" role="alert">
          No se pudo actualizar. Se muestra la última versión cargada.
        </div>
      ) : null}
      <div className="freshness__meta">
        <p className="muted">
          Actualizado {updatedAt ? formatRelative(updatedAt) : 'hace un momento'}
        </p>
        <button className="btn" onClick={onRefresh} type="button">
          Actualizar
        </button>
      </div>
    </div>
  );
}
