'use client';

import { useRouter, useSearchParams } from 'next/navigation';

import { getReviews } from '@/lib/api';
import { confidenceBand, formatConfidence, formatMoney, formatRelative } from '@/lib/format';
import { PRIORITY_LABELS, RISK_LABELS, STATUS_LABELS, SUBJECT_LABELS } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

const STATUSES = Object.keys(STATUS_LABELS);
const PRIORITIES = Object.keys(PRIORITY_LABELS);

export function ReviewQueuePage() {
  const router = useRouter();
  const params = useSearchParams();
  const status = params.getAll('status');
  const priority = params.getAll('priority');
  const query = params.get('q') ?? '';
  const resource = useResource(
    (signal) => getReviews({ status, priority, limit: 50 }, signal),
    [status.join(','), priority.join(',')],
    (page) => page.total === 0,
  );

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    next.delete(key);
    if (value) {
      next.set(key, value);
    }
    router.replace(`/reviews?${next.toString()}`);
  };

  const rows = (resource.data?.items ?? []).filter((item) => {
    if (!query) {
      return true;
    }
    const haystack =
      `${item.supplier_code ?? ''} ${item.subject_summary ?? ''} ${item.id}`.toLowerCase();
    return haystack.includes(query.toLowerCase());
  });

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando la cola de revisión…" />;
  }
  if (resource.status === 'error' && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }

  return (
    <>
      <PageHeader
        description="Ordenada por prioridad e impacto. Estado, severidad y confianza van en columnas distintas."
        title="Cola de revisiones"
      />
      <div className="filters">
        <label>
          Estado
          <select
            onChange={(event) => setParam('status', event.target.value)}
            value={status[0] ?? ''}
          >
            <option value="">Todos</option>
            {STATUSES.map((item) => (
              <option key={item} value={item}>
                {STATUS_LABELS[item as keyof typeof STATUS_LABELS]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Prioridad
          <select
            onChange={(event) => setParam('priority', event.target.value)}
            value={priority[0] ?? ''}
          >
            <option value="">Todas</option>
            {PRIORITIES.map((item) => (
              <option key={item} value={item}>
                {PRIORITY_LABELS[item as keyof typeof PRIORITY_LABELS]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Buscar en resultados
          <input
            onChange={(event) => setParam('q', event.target.value)}
            placeholder="Proveedor o resumen"
            value={query}
          />
        </label>
        {status.length || priority.length || query ? (
          <button className="btn" onClick={() => router.replace('/reviews')} type="button">
            Limpiar todo
          </button>
        ) : null}
      </div>
      {resource.status === 'empty' || rows.length === 0 ? (
        <EmptyState
          action={
            <button
              className="btn"
              onClick={() => router.replace('/reviews?status=approved')}
              type="button"
            >
              Ver completadas
            </button>
          }
          description={
            status.length || query
              ? 'Ningún caso coincide con los filtros. Puedes limpiarlos o ver los decididos.'
              : 'No quedan casos abiertos. Puedes revisar los ya decididos.'
          }
          title={status.length || query ? 'Sin resultados por filtros' : 'Cola vacía'}
        />
      ) : (
        <DataTable
          caption="Casos de revisión humana"
          columns={[
            {
              key: 'risk',
              header: 'Severidad',
              render: (row) => <Badge kind="risk" labels={RISK_LABELS} value={row.risk} />,
            },
            { key: 'type', header: 'Tipo', render: (row) => SUBJECT_LABELS[row.subject_type] },
            { key: 'entity', header: 'Entidad', render: (row) => row.supplier_code ?? '—' },
            {
              key: 'summary',
              header: 'Resumen',
              render: (row) => row.subject_summary ?? row.recommended_action ?? '—',
            },
            {
              key: 'impact',
              header: 'Impacto',
              numeric: true,
              render: (row) => formatMoney(row.financial_impact),
            },
            {
              key: 'confidence',
              header: 'Confianza',
              render: (row) => {
                const band = confidenceBand(row.confidence);
                return `${formatConfidence(row.confidence)}${band ? ` · ${band}` : ''}`;
              },
            },
            {
              key: 'assignee',
              header: 'Asignado',
              render: (row) => row.reviewer ?? 'Sin asignación',
            },
            { key: 'age', header: 'Antigüedad', render: (row) => formatRelative(row.created_at) },
            {
              key: 'status',
              header: 'Estado',
              render: (row) => <Badge kind="status" labels={STATUS_LABELS} value={row.status} />,
            },
            {
              key: 'priority',
              header: 'Prioridad',
              render: (row) => (
                <Badge kind="priority" labels={PRIORITY_LABELS} value={row.priority} />
              ),
            },
          ]}
          onRowClick={(row) =>
            router.push(
              `/reviews/${row.id}${params.toString() ? `?from=${encodeURIComponent(`/reviews?${params}`)}` : ''}`,
            )
          }
          rowKey={(row) => row.id}
          rows={rows}
        />
      )}
    </>
  );
}
