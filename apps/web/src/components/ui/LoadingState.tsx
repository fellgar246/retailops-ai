interface LoadingStateProps {
  label?: string;
  rows?: number;
}

export function LoadingState({ label = 'Cargando…', rows = 4 }: LoadingStateProps) {
  return (
    <div className="skeleton" aria-busy="true" aria-live="polite">
      <span className="muted">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton__bar" key={index} style={{ width: `${88 - index * 8}%` }} />
      ))}
    </div>
  );
}
