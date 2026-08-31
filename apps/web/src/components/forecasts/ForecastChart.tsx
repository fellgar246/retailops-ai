import type { ForecastPrediction } from '@/lib/types';

interface SeriesPoint {
  label: string;
  predicted: number;
  actual: number | null;
}

export function aggregateByPeriod(predictions: ForecastPrediction[]): SeriesPoint[] {
  const groups = new Map<string, SeriesPoint>();
  for (const item of predictions) {
    const current = groups.get(item.period_start) ?? {
      label: item.period_start,
      predicted: 0,
      actual: null,
    };
    current.predicted += item.predicted;
    if (item.actual !== null) {
      current.actual = (current.actual ?? 0) + item.actual;
    }
    groups.set(item.period_start, current);
  }
  return [...groups.values()].sort((left, right) => left.label.localeCompare(right.label));
}

export function ForecastChart({ predictions }: { predictions: ForecastPrediction[] }) {
  const points = aggregateByPeriod(predictions);
  if (points.length === 0) {
    return <p className="muted">Esta ejecución no tiene predicciones.</p>;
  }
  const width = 720;
  const height = 260;
  const pad = { top: 16, right: 16, bottom: 36, left: 48 };
  const values = points.flatMap((point) =>
    point.actual === null ? [point.predicted] : [point.predicted, point.actual],
  );
  const max = Math.max(...values, 1);
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const x = (index: number) =>
    pad.left + (points.length === 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth);
  const y = (value: number) => pad.top + innerHeight - (value / max) * innerHeight;
  const predictedPath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(point.predicted)}`)
    .join(' ');
  const actualPoints = points
    .map((point, index) => (point.actual === null ? null : `${x(index)},${y(point.actual)}`))
    .filter((value): value is string => value !== null);

  return (
    <figure>
      <svg
        aria-label="Serie de demanda real y pronosticada por semana"
        className="chart"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        <line
          stroke="#d9e0e7"
          x1={pad.left}
          x2={width - pad.right}
          y1={height - pad.bottom}
          y2={height - pad.bottom}
        />
        <line stroke="#d9e0e7" x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} />
        <path d={predictedPath} fill="none" stroke="#176b5b" strokeWidth="2" />
        {actualPoints.length > 1 ? (
          <polyline fill="none" points={actualPoints.join(' ')} stroke="#17202a" strokeWidth="2" />
        ) : null}
        {points.map((point, index) => (
          <g key={point.label}>
            <circle cx={x(index)} cy={y(point.predicted)} fill="#176b5b" r="3" />
            {point.actual !== null ? (
              <circle cx={x(index)} cy={y(point.actual)} fill="#17202a" r="3" />
            ) : null}
            <text textAnchor="middle" x={x(index)} y={height - 12}>
              {point.label.slice(5)}
            </text>
          </g>
        ))}
        <text x={8} y={20}>
          {max.toFixed(0)}
        </text>
      </svg>
      <figcaption className="muted">
        Línea oscura: real observado. Línea de marca: forecast. Las semanas sin real quedan solo
        proyectadas.
      </figcaption>
    </figure>
  );
}
