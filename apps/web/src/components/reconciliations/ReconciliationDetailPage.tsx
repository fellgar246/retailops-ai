'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { getReconciliation } from '@/lib/api';
import { formatDateTime, formatMoney, formatNumber } from '@/lib/format';
import { RESOLUTION_LABELS, SEVERITY_LABELS, STATUS_LABELS } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { ErrorState } from '@/components/ui/ErrorState';
import { FreshnessBar } from '@/components/ui/FreshnessBar';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Provenance } from '@/components/ui/Provenance';

export function ReconciliationDetailPage({ id }: { id: number }) {
  const resource = useResource((signal) => getReconciliation(id, signal), [id]);
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const rows = useMemo(() => {
    const exceptions = resource.data?.exceptions ?? [];
    return onlyOpen ? exceptions.filter((item) => item.resolution_status === 'open') : exceptions;
  }, [resource.data, onlyOpen]);
  const selected = rows.find((item) => item.id === selectedId) ?? rows[0];

  if (!resource.data) {
    if (resource.status === 'loading') {
      return <LoadingState label="Cargando la conciliación…" />;
    }
    return (
      <ErrorState
        error={resource.error ?? new Error('Conciliación no encontrada')}
        onRetry={resource.reload}
      />
    );
  }

  const run = resource.data;
  const difference = run.total_financial_impact;

  return (
    <>
      <PageHeader
        breadcrumb="Conciliaciones / detalle"
        description={`Versión ${run.version} · generada ${formatDateTime(run.generated_at)}`}
        title={run.scope_key}
      />
      <FreshnessBar
        error={resource.error}
        onRefresh={resource.reload}
        stale={resource.status === 'loading'}
        updatedAt={run.generated_at}
      />
      <section className="panel">
        <p>
          Pedido {run.purchase_order_count} − recibido {run.goods_receipt_count} − facturado{' '}
          {run.supplier_invoice_count} ={' '}
          <strong className="tabular">{formatMoney(difference)}</strong> en discrepancia
        </p>
        <p className="muted">
          {formatNumber(run.exception_count)} líneas con excepción · {run.error_count} de alta
          severidad · tolerancia de cantidad {String(run.tolerances.quantity_tolerance ?? '0')}
        </p>
      </section>
      <div className="filters">
        <label>
          <input
            checked={onlyOpen}
            onChange={(event) => setOnlyOpen(event.target.checked)}
            type="checkbox"
          />{' '}
          Solo abiertas
        </label>
      </div>
      <div className="workspace">
        <DataTable
          caption="Excepciones"
          columns={[
            {
              key: 'severity',
              header: 'Severidad',
              render: (row) => (
                <Badge kind="severity" labels={SEVERITY_LABELS} value={row.severity} />
              ),
            },
            { key: 'code', header: 'Código', render: (row) => row.code },
            { key: 'po', header: 'PO', render: (row) => row.purchase_order?.number ?? '—' },
            { key: 'gr', header: 'Recepción', render: (row) => row.goods_receipt?.number ?? '—' },
            { key: 'inv', header: 'Factura', render: (row) => row.supplier_invoice?.number ?? '—' },
            {
              key: 'expected',
              header: 'Esperado',
              numeric: true,
              render: (row) => row.expected_value,
            },
            { key: 'actual', header: 'Real', numeric: true, render: (row) => row.actual_value },
            {
              key: 'impact',
              header: 'Impacto',
              numeric: true,
              render: (row) => formatMoney(row.financial_impact),
            },
            {
              key: 'review',
              header: 'Revisión',
              render: (row) =>
                row.review_status
                  ? STATUS_LABELS[row.review_status]
                  : RESOLUTION_LABELS[row.resolution_status],
            },
          ]}
          onRowClick={(row) => setSelectedId(row.id)}
          rowKey={(row) => row.id}
          rows={rows}
          selectedKey={selected?.id}
        />
        <aside className="panel">
          <h2>Inspector</h2>
          {selected ? (
            <>
              <div className="provenance">
                <Provenance source="rule" />
                <Badge kind="severity" labels={SEVERITY_LABELS} value={selected.severity} />
              </div>
              <p>{selected.message}</p>
              <p>
                Esperado <strong>{selected.expected_value}</strong> · real{' '}
                <strong>{selected.actual_value}</strong>
              </p>
              {selected.review_case_id ? (
                <Link className="btn btn--primary" href={`/reviews/${selected.review_case_id}`}>
                  Abrir caso {selected.review_case_id}
                </Link>
              ) : (
                <p className="muted">Esta excepción no tiene un caso de revisión humana.</p>
              )}
            </>
          ) : (
            <p className="muted">Selecciona una excepción.</p>
          )}
        </aside>
      </div>
    </>
  );
}
