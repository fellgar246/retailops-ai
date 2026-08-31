'use client';

import { useRouter } from 'next/navigation';

import { getReconciliations } from '@/lib/api';
import { formatDateTime, formatMoney, formatNumber } from '@/lib/format';
import { useResource } from '@/lib/use-resource';
import { DataTable } from '@/components/ui/DataTable';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

export function ReconciliationListPage() {
  const router = useRouter();
  const resource = useResource(
    (signal) => getReconciliations({ limit: 50 }, signal),
    [],
    (page) => page.total === 0,
  );

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando conciliaciones…" />;
  }
  if (resource.status === 'error' && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }
  if (resource.status === 'empty' || !resource.data?.items.length) {
    return (
      <>
        <PageHeader
          description="Pedido − recibido − facturado, con excepciones persistidas."
          title="Conciliaciones"
        />
        <EmptyState
          description="No hay ejecuciones de conciliación. Corre un match de un pedido o factura y vuelve."
          title="Sin conciliaciones"
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        description={`${resource.data.total} ejecuciones. El impacto es la suma firmada de excepciones.`}
        title="Conciliaciones"
      />
      <DataTable
        caption="Ejecuciones de conciliación"
        columns={[
          { key: 'scope', header: 'Alcance', render: (row) => row.scope_key },
          { key: 'version', header: 'Versión', numeric: true, render: (row) => row.version },
          {
            key: 'docs',
            header: 'PO / recepción / factura',
            render: (row) =>
              `${row.purchase_order_count} / ${row.goods_receipt_count} / ${row.supplier_invoice_count}`,
          },
          {
            key: 'exceptions',
            header: 'Excepciones',
            numeric: true,
            render: (row) => `${row.open_exception_count} abiertas / ${row.exception_count}`,
          },
          {
            key: 'impact',
            header: 'Impacto',
            numeric: true,
            render: (row) => formatMoney(row.total_financial_impact),
          },
          { key: 'when', header: 'Generada', render: (row) => formatDateTime(row.generated_at) },
        ]}
        onRowClick={(row) => router.push(`/reconciliations/${row.id}`)}
        rowKey={(row) => row.id}
        rows={resource.data.items}
      />
      <p className="muted">{formatNumber(resource.data.total)} resultados</p>
    </>
  );
}
