'use client';

import { useRouter } from 'next/navigation';

import { getForecasts } from '@/lib/api';
import { formatDate, formatDateTime, formatNumber, formatPercent } from '@/lib/format';
import { FORECAST_STATUS_LABELS } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FreshnessBar } from '@/components/ui/FreshnessBar';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

export function ForecastListPage() {
  const router = useRouter();
  const resource = useResource(
    (signal) => getForecasts({ limit: 50 }, signal),
    [],
    (page) => page.total === 0,
  );

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando ejecuciones de forecast…" />;
  }
  if (resource.status === 'error' && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }
  if (resource.status === 'empty' || !resource.data?.items.length) {
    return (
      <>
        <PageHeader
          description="Cada fila es una ejecución persistida: modelo, origen y métricas."
          title="Pronósticos"
        />
        <EmptyState
          description="Todavía no hay ejecuciones persistidas. Entrena o camina un backtest y vuelve a esta lista."
          title="Sin ejecuciones de forecast"
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        description={`${resource.data.total} ejecuciones. WAPE y sesgo aparecen cuando hay evaluación.`}
        title="Pronósticos"
      />
      <FreshnessBar
        error={resource.error}
        onRefresh={resource.reload}
        stale={resource.status === 'loading'}
        updatedAt={resource.data.items[0]?.generated_at}
      />
      <DataTable
        caption="Ejecuciones de forecast"
        columns={[
          { key: 'model', header: 'Modelo', render: (row) => row.model_id },
          { key: 'version', header: 'Versión', render: (row) => row.model_version ?? '—' },
          {
            key: 'period',
            header: 'Periodo',
            render: (row) => `${formatDate(row.cutoff)} · ${row.horizon} sem.`,
          },
          {
            key: 'wape',
            header: 'WAPE',
            numeric: true,
            render: (row) => formatPercent(row.metrics?.wape),
          },
          {
            key: 'bias',
            header: 'Sesgo',
            numeric: true,
            render: (row) => formatNumber(row.metrics?.bias),
          },
          {
            key: 'status',
            header: 'Estado',
            render: (row) => (
              <Badge kind="status" labels={FORECAST_STATUS_LABELS} value={row.status} />
            ),
          },
          {
            key: 'generated',
            header: 'Generado',
            render: (row) => formatDateTime(row.generated_at),
          },
        ]}
        onRowClick={(row) => router.push(`/forecasts/${row.id}`)}
        rowKey={(row) => row.id}
        rows={resource.data.items}
      />
    </>
  );
}
