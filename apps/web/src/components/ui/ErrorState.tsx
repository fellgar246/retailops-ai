import { ApiError } from '@/lib/api-client';

interface ErrorStateProps {
  error: ApiError | Error;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const detail = error instanceof ApiError ? error.detail : undefined;
  return (
    <div className="state" role="alert">
      <h2>No se pudo cargar esta vista</h2>
      <p>
        {detail ?? error.message}. Los datos ya visibles se conservan. Puedes reintentar o comprobar
        la conexión con la API.
      </p>
      {onRetry ? (
        <button className="btn btn--primary" onClick={onRetry} type="button">
          Reintentar
        </button>
      ) : null}
    </div>
  );
}
