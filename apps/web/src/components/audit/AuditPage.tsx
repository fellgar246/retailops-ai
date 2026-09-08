'use client';

import Link from 'next/link';

import { getAudit } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { EVENT_LABELS, STATUS_LABELS, labelOf } from '@/lib/labels';
import { hasFailed, useResource } from '@/lib/use-resource';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

export function AuditPage() {
  const resource = useResource(
    (signal) => getAudit({ limit: 100 }, signal),
    [],
    (page) => page.total === 0,
  );

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando el historial de auditoría…" />;
  }
  if (hasFailed(resource.status) && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }
  if (resource.status === 'empty' || !resource.data?.items.length) {
    return (
      <>
        <PageHeader
          description="Eventos append-only de las decisiones humanas."
          title="Auditoría"
        />
        <EmptyState
          description="Todavía no hay eventos. Las decisiones de revisión aparecen aquí."
          title="Sin eventos"
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        description="Los eventos no se editan ni se borran. Una corrección posterior crea un evento nuevo."
        title="Auditoría"
      />
      <DataTable
        caption="Eventos recientes"
        columns={[
          { key: 'when', header: 'Fecha', render: (row) => formatDateTime(row.created_at) },
          { key: 'actor', header: 'Actor', render: (row) => row.actor },
          {
            key: 'action',
            header: 'Acción',
            render: (row) => labelOf(EVENT_LABELS, row.event_type),
          },
          {
            key: 'change',
            header: 'Antes → después',
            render: (row) =>
              row.from_status || row.to_status
                ? `${labelOf(STATUS_LABELS, row.from_status)} → ${labelOf(STATUS_LABELS, row.to_status)}`
                : '—',
          },
          {
            key: 'case',
            header: 'Caso',
            render: (row) =>
              row.review_case_id ? (
                <Link href={`/reviews/${row.review_case_id}`}>#{row.review_case_id}</Link>
              ) : (
                '—'
              ),
          },
        ]}
        rowKey={(row) => row.id}
        rows={resource.data.items}
      />
    </>
  );
}
