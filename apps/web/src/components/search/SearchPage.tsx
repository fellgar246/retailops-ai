'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

import { searchOperations } from '@/lib/api';
import { useResource } from '@/lib/use-resource';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';

export function SearchPage() {
  const params = useSearchParams();
  const query = params.get('q') ?? '';
  const resource = useResource((signal) => searchOperations(query, signal), [query]);

  if (!query) {
    return (
      <>
        <PageHeader description="SKU, proveedor, PO, factura o documento." title="Búsqueda" />
        <EmptyState
          description="Escribe un término en la barra superior."
          title="Nada que buscar"
        />
      </>
    );
  }
  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Buscando…" />;
  }
  if (resource.status === 'error' && !resource.data) {
    return <ErrorState error={resource.error} onRetry={resource.reload} />;
  }
  const data = resource.data;
  const empty =
    !data ||
    (data.documents.length === 0 &&
      data.reviews.length === 0 &&
      data.exceptions.length === 0 &&
      data.forecasts.length === 0);
  if (empty) {
    return (
      <>
        <PageHeader title={`Resultados para “${query}”`} />
        <EmptyState
          description="Ningún documento, caso, excepción o forecast coincide."
          title="Sin coincidencias"
        />
      </>
    );
  }

  return (
    <>
      <PageHeader title={`Resultados para “${query}”`} />
      <div className="split">
        <section className="panel">
          <h2>Revisiones</h2>
          <ul>
            {data.reviews.map((item) => (
              <li key={item.id}>
                <Link href={`/reviews/${item.id}`}>Caso {item.id}</Link> · {item.status}
              </li>
            ))}
          </ul>
          <h2>Documentos</h2>
          <ul>
            {data.documents.map((item) => (
              <li key={item.id}>
                <Link href={`/documents/${item.id}`}>{item.filename}</Link> · {item.supplier_code}
              </li>
            ))}
          </ul>
        </section>
        <section className="panel">
          <h2>Conciliaciones</h2>
          <ul>
            {data.exceptions.map((item) => (
              <li key={item.id}>
                <Link href={`/reconciliations/${item.reconciliation_run_id}`}>{item.code}</Link> ·{' '}
                {item.severity}
              </li>
            ))}
          </ul>
          <h2>Pronósticos</h2>
          <ul>
            {data.forecasts.map((item) => (
              <li key={item.id}>
                <Link href={`/forecasts/${item.id}`}>{item.model_id}</Link> · {item.cutoff}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}
