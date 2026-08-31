'use client';

import { getOverview } from '@/lib/api';
import { formatDateTime, formatMoney, formatNumber, formatRelative } from '@/lib/format';
import { FORECAST_STATUS_LABELS, labelOf } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { KpiCard } from '@/components/ui/KpiCard';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

export function OverviewPage() {
  const resource = useResource((signal) => getOverview(signal), []);

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando el overview operativo…" />;
  }
  if (resource.status === 'error' && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }
  const data = resource.data;
  if (!data) {
    return (
      <EmptyState
        description="Aún no hay hechos persistidos para armar el overview."
        title="Sin datos operativos"
      />
    );
  }

  return (
    <>
      <PageHeader
        description="Dónde intervenir hoy, con números tomados de la API."
        title="Overview operativo"
        actions={
          <button className="btn" onClick={resource.reload} type="button">
            Actualizar
          </button>
        }
      />
      <p className="muted">Actualizado {formatRelative(data.generated_at)}</p>
      <div className="kpi-grid">
        <KpiCard
          href="/reviews?status=open&status=in_review"
          label="Revisiones abiertas"
          meta={`${data.reviews.in_review ?? 0} en curso · ${formatNumber(data.reviews.decided_cases)} decididas`}
          value={formatNumber(data.reviews.open_cases)}
        />
        <KpiCard
          href="/documents?status=review_ready"
          label="Documentos por revisar"
          meta={`${formatNumber(data.documents.parse_failed)} con extracción fallida`}
          value={formatNumber(data.documents.awaiting_review)}
        />
        <KpiCard
          href="/reconciliations"
          label="Excepciones abiertas"
          meta={`${formatNumber(data.reconciliation.error_exceptions)} de alta severidad`}
          value={formatNumber(data.reconciliation.open_exceptions)}
        />
        <KpiCard
          href="/forecasts"
          label="Ejecuciones de forecast"
          meta={
            data.forecasts.latest
              ? `${data.forecasts.latest.model_id} · ${labelOf(FORECAST_STATUS_LABELS, data.forecasts.latest.status)}`
              : 'Sin ejecuciones persistidas'
          }
          value={formatNumber(data.forecasts.run_count)}
        />
      </div>
      <div className="split">
        <section className="panel">
          <h2>Flujo operativo</h2>
          <p>
            Documentos totales: <strong className="tabular">{data.documents.total}</strong>.
            Conciliaciones: <strong className="tabular">{data.reconciliation.run_count}</strong>.
            Impacto abierto:{' '}
            <strong className="tabular">
              {formatMoney(data.reconciliation.total_financial_impact)}
            </strong>
            .
          </p>
          {data.forecasts.latest ? (
            <p>
              Último forecast {data.forecasts.latest.model_id} generado{' '}
              {formatDateTime(data.forecasts.latest.generated_at)}, horizonte{' '}
              {data.forecasts.latest.horizon} semanas.
            </p>
          ) : (
            <p className="muted">Todavía no hay un forecast persistido.</p>
          )}
        </section>
        <section className="panel">
          <h2>Desempeño de revisión</h2>
          <p>
            Aceptación {Math.round(data.reviews.acceptance_rate * 100)}% · rechazo{' '}
            {Math.round(data.reviews.rejection_rate * 100)}% · corrección{' '}
            {Math.round(data.reviews.correction_rate * 100)}% sobre {data.reviews.decided_cases}{' '}
            casos decididos.
          </p>
        </section>
      </div>
    </>
  );
}
