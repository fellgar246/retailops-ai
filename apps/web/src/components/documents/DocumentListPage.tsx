'use client';

import { useRouter, useSearchParams } from 'next/navigation';

import { getDocuments } from '@/lib/api';
import { formatDateTime, formatNumber } from '@/lib/format';
import { DOCUMENT_STATUS_LABELS, SEVERITY_LABELS } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

const STATUSES = ['received', 'parsed', 'parse_failed', 'validated', 'review_ready'];

export function DocumentListPage() {
  const router = useRouter();
  const params = useSearchParams();
  const status = params.getAll('status');
  const supplier = params.get('supplier') ?? '';
  const resource = useResource(
    (signal) => getDocuments({ status, supplier: supplier || undefined, limit: 50 }, signal),
    [status.join(','), supplier],
    (page) => page.total === 0,
  );

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    router.replace(`/documents?${next.toString()}`);
  };

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando documentos de proveedor…" />;
  }
  if (resource.status === 'error' && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }

  return (
    <>
      <PageHeader
        description="Hojas de oferta procesadas, con hallazgos determinísticos."
        title="Documentos de proveedor"
      />
      <div className="filters">
        <label>
          Estado
          <select
            onChange={(event) => setFilter('status', event.target.value)}
            value={status[0] ?? ''}
          >
            <option value="">Todos</option>
            {STATUSES.map((item) => (
              <option key={item} value={item}>
                {DOCUMENT_STATUS_LABELS[item]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Proveedor
          <input
            onChange={(event) => setFilter('supplier', event.target.value)}
            placeholder="SUP-BEVCO"
            value={supplier}
          />
        </label>
        {status.length || supplier ? (
          <button className="btn" onClick={() => router.replace('/documents')} type="button">
            Limpiar filtros
          </button>
        ) : null}
        <span className="muted">{formatNumber(resource.data?.total ?? 0)} resultados</span>
      </div>
      {resource.status === 'empty' || !resource.data?.items.length ? (
        <EmptyState
          action={
            status.length || supplier ? (
              <button className="btn" onClick={() => router.replace('/documents')} type="button">
                Quitar filtros
              </button>
            ) : undefined
          }
          description={
            status.length || supplier
              ? 'Ningún documento coincide con los filtros activos.'
              : 'Aún no hay documentos almacenados.'
          }
          title={status.length || supplier ? 'Sin resultados' : 'Sin documentos'}
        />
      ) : (
        <DataTable
          caption="Documentos de proveedor"
          columns={[
            { key: 'supplier', header: 'Proveedor', render: (row) => row.supplier_code ?? '—' },
            { key: 'file', header: 'Archivo', render: (row) => row.filename },
            {
              key: 'status',
              header: 'Estado',
              render: (row) => (
                <Badge kind="status" labels={DOCUMENT_STATUS_LABELS} value={row.status} />
              ),
            },
            {
              key: 'findings',
              header: 'Hallazgos',
              numeric: true,
              render: (row) => formatNumber(row.finding_count),
            },
            {
              key: 'severity',
              header: 'Severidad',
              render: (row) =>
                `${SEVERITY_LABELS.error} ${row.severity_summary.error} · ${SEVERITY_LABELS.warning} ${row.severity_summary.warning}`,
            },
            {
              key: 'processed',
              header: 'Procesado',
              render: (row) => formatDateTime(row.processed_at),
            },
          ]}
          onRowClick={(row) => router.push(`/documents/${row.id}`)}
          rowKey={(row) => row.id}
          rows={resource.data.items}
        />
      )}
    </>
  );
}
