'use client';

import Link from 'next/link';
import { useState } from 'react';

import { getDocument } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { DOCUMENT_STATUS_LABELS, SEVERITY_LABELS, STATUS_LABELS } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { ErrorState } from '@/components/ui/ErrorState';
import { FreshnessBar } from '@/components/ui/FreshnessBar';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Provenance } from '@/components/ui/Provenance';

export function DocumentDetailPage({ id }: { id: number }) {
  const resource = useResource((signal) => getDocument(id, signal), [id]);
  const [selectedRow, setSelectedRow] = useState<number | null>(null);

  if (!resource.data) {
    if (resource.status === 'loading') {
      return <LoadingState label="Cargando el documento…" />;
    }
    return (
      <ErrorState
        error={resource.error ?? new Error('Documento no encontrado')}
        onRetry={resource.reload}
      />
    );
  }

  const document = resource.data;
  const findings = selectedRow
    ? document.findings.filter((item) => item.row_reference === selectedRow)
    : document.findings;

  return (
    <>
      <PageHeader
        breadcrumb="Documentos / detalle"
        description={`${document.supplier_code ?? 'Proveedor'} · procesado ${formatDateTime(document.processed_at)}`}
        title={document.filename}
      />
      <FreshnessBar
        error={resource.error}
        onRefresh={resource.reload}
        stale={resource.status === 'loading'}
        updatedAt={document.processed_at}
      />
      <div className="filters">
        <Badge kind="status" labels={DOCUMENT_STATUS_LABELS} value={document.status} />
        <span className="chip">{document.finding_count} hallazgos</span>
        <span className="chip mono">{document.checksum.slice(0, 12)}</span>
      </div>
      <div className="workspace">
        <section className="panel">
          <h2>Filas normalizadas</h2>
          {document.rows_available ? (
            <DataTable
              caption="Oferta extraída"
              columns={[
                { key: 'row', header: 'Fila', numeric: true, render: (row) => row.row_number },
                { key: 'sku', header: 'SKU proveedor', render: (row) => row.supplier_sku ?? '—' },
                { key: 'desc', header: 'Descripción', render: (row) => row.description ?? '—' },
                { key: 'cat', header: 'Categoría', render: (row) => row.category ?? '—' },
                { key: 'cost', header: 'Costo', numeric: true, render: (row) => row.cost ?? '—' },
                { key: 'vat', header: 'VAT', numeric: true, render: (row) => row.vat ?? '—' },
              ]}
              onRowClick={(row) => setSelectedRow(row.row_number)}
              rowKey={(row) => row.row_number}
              rows={document.rows}
              selectedKey={selectedRow ?? undefined}
            />
          ) : (
            <p className="muted">
              El archivo fuente no está disponible en este entorno; se conservan los hallazgos
              persistidos.
            </p>
          )}
        </section>
        <section className="panel">
          <h2>Hallazgos y sugerencias</h2>
          {findings.length === 0 ? (
            <p className="muted">No hay hallazgos para la fila seleccionada.</p>
          ) : (
            findings.map((finding) => (
              <article className="panel" key={finding.id} style={{ boxShadow: 'none' }}>
                <div className="provenance">
                  <Provenance source="rule" />
                  <Badge kind="severity" labels={SEVERITY_LABELS} value={finding.severity} />
                </div>
                <h3 style={{ margin: '0 0 8px', fontSize: 15 }}>{finding.message}</h3>
                <p className="muted">
                  {finding.field ?? 'documento'} · fila {finding.row_reference ?? '—'} ·{' '}
                  {finding.code}
                </p>
                {finding.proposed_value ? (
                  <p>
                    Valor propuesto por regla: <strong>{finding.proposed_value}</strong>
                  </p>
                ) : null}
              </article>
            ))
          )}
          <h2>Casos de revisión</h2>
          {document.review_cases.length === 0 ? (
            <p className="muted">Ningún caso humano está ligado a estos hallazgos.</p>
          ) : (
            <ul>
              {document.review_cases.map((item) => (
                <li key={item.id}>
                  <Link href={`/reviews/${item.id}`}>
                    Caso {item.id} · {STATUS_LABELS[item.status]}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
