'use client';

import Link from 'next/link';

import { getReviewFeedback, getReviewMetrics } from '@/lib/api';
import { formatConfidence, formatDuration, formatNumber, formatPercent } from '@/lib/format';
import { useResource } from '@/lib/use-resource';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

export function EvaluationPage() {
  const metrics = useResource((signal) => getReviewMetrics(signal), []);
  const feedback = useResource(
    (signal) => getReviewFeedback(signal),
    [],
    (page) => page.count === 0,
  );

  if (
    (metrics.status === 'loading' && !metrics.data) ||
    (feedback.status === 'loading' && !feedback.data)
  ) {
    return <LoadingState label="Cargando la evaluación de IA…" />;
  }
  if (metrics.status === 'error' && !metrics.data) {
    return <ErrorState error={metrics.error} onRetry={metrics.reload} />;
  }

  const data = metrics.data;
  if (!data) {
    return <EmptyState description="No hay métricas de revisión." title="Sin evaluación" />;
  }

  return (
    <>
      <PageHeader
        description="Aceptación, override y versiones de modelo sobre casos ya decididos."
        title="Evaluación de IA"
      />
      <div className="kpi-grid">
        <div className="kpi">
          <p className="kpi__label">Aceptación</p>
          <p className="kpi__value tabular">{formatPercent(data.acceptance_rate)}</p>
          <p className="kpi__meta">n = {formatNumber(data.decided_cases)}</p>
        </div>
        <div className="kpi">
          <p className="kpi__label">Override (rechazo + corrección)</p>
          <p className="kpi__value tabular">
            {formatPercent(data.rejection_rate + data.correction_rate)}
          </p>
          <p className="kpi__meta">
            {formatNumber(data.rejected_cases + data.corrected_cases)} de{' '}
            {formatNumber(data.decided_cases)}
          </p>
        </div>
        <div className="kpi">
          <p className="kpi__label">Tiempo medio de revisión</p>
          <p className="kpi__value tabular">
            {formatDuration(data.average_review_duration_seconds)}
          </p>
          <p className="kpi__meta">Solo casos con apertura y cierre</p>
        </div>
        <div className="kpi">
          <p className="kpi__label">Abiertos</p>
          <p className="kpi__value tabular">{formatNumber(data.open_cases)}</p>
          <p className="kpi__meta">Pendientes de decisión</p>
        </div>
      </div>
      {feedback.status === 'empty' || !feedback.data?.items.length ? (
        <EmptyState
          description="Exporta o decide casos para ver filas de evaluación con modelo y prompt."
          title="Sin casos evaluados"
        />
      ) : (
        <DataTable
          caption="Casos decididos"
          columns={[
            {
              key: 'id',
              header: 'Caso',
              render: (row) => (
                <Link href={`/reviews/${row.review_case_id}`}>#{row.review_case_id}</Link>
              ),
            },
            { key: 'model', header: 'Modelo', render: (row) => row.model ?? '—' },
            {
              key: 'prompt',
              header: 'Prompt',
              render: (row) => `${row.prompt_id ?? '—'} ${row.prompt_version ?? ''}`,
            },
            {
              key: 'confidence',
              header: 'Confianza',
              render: (row) => formatConfidence(row.confidence),
            },
            { key: 'decision', header: 'Decisión', render: (row) => row.decision },
            { key: 'ref', header: 'Referencia', render: (row) => row.input_reference },
          ]}
          rowKey={(row) => row.review_case_id}
          rows={feedback.data.items}
        />
      )}
    </>
  );
}
