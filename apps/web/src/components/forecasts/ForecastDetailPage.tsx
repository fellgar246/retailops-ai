'use client';

import { useMemo, useState } from 'react';

import { getForecast } from '@/lib/api';
import { formatDate, formatDateTime, formatNumber, formatPercent } from '@/lib/format';
import { FORECAST_STATUS_LABELS } from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { DataTable } from '@/components/ui/DataTable';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';
import { ForecastChart } from './ForecastChart';

export function ForecastDetailPage({ id }: { id: number }) {
  const resource = useResource((signal) => getForecast(id, signal), [id]);
  const [store, setStore] = useState('');
  const [category, setCategory] = useState('');

  const filtered = useMemo(() => {
    const predictions = resource.data?.predictions ?? [];
    return predictions.filter(
      (item) =>
        (!store || item.store_code === store) && (!category || item.category_code === category),
    );
  }, [resource.data, store, category]);

  if (resource.status === 'loading' && !resource.data) {
    return <LoadingState label="Cargando el detalle del forecast…" />;
  }
  if (resource.status === 'error' || !resource.data) {
    return (
      <ErrorState
        error={resource.error ?? new Error('Ejecución no encontrada')}
        onRetry={resource.reload}
      />
    );
  }

  const run = resource.data;
  const stores = [...new Set(run.predictions.map((item) => item.store_code))];
  const categories = [...new Set(run.predictions.map((item) => item.category_code))];

  return (
    <>
      <PageHeader
        breadcrumb="Pronósticos / detalle"
        description={`${run.problem_id} · horizonte ${run.horizon} semanas desde ${formatDate(run.cutoff)}.`}
        title={run.model_id}
      />
      <div className="filters">
        <Badge kind="status" labels={FORECAST_STATUS_LABELS} value={run.status} />
        <span className="chip">Generado {formatDateTime(run.generated_at)}</span>
        {run.model_version ? <span className="chip">Versión {run.model_version}</span> : null}
        <span className="chip">WAPE {formatPercent(run.metrics?.wape)}</span>
        <span className="chip">Sesgo {formatNumber(run.metrics?.bias)}</span>
      </div>
      <section className="panel">
        <h2>Serie</h2>
        <p className="muted">
          WAPE es el error absoluto ponderado por la demanda real. El sesgo es el error medio con
          signo: positivo significa sobrepronóstico.
        </p>
        <div className="filters">
          <label>
            Tienda
            <select onChange={(event) => setStore(event.target.value)} value={store}>
              <option value="">Todas</option>
              {stores.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Categoría
            <select onChange={(event) => setCategory(event.target.value)} value={category}>
              <option value="">Todas</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
        <ForecastChart predictions={filtered} />
      </section>
      <DataTable
        caption="Valores semanales"
        columns={[
          { key: 'store', header: 'Tienda', render: (row) => row.store_code },
          { key: 'category', header: 'Categoría', render: (row) => row.category_code },
          { key: 'week', header: 'Semana', render: (row) => formatDate(row.period_start) },
          {
            key: 'pred',
            header: 'Forecast',
            numeric: true,
            render: (row) => formatNumber(row.predicted),
          },
          {
            key: 'actual',
            header: 'Real',
            numeric: true,
            render: (row) => formatNumber(row.actual),
          },
        ]}
        rowKey={(row) => `${row.store_code}-${row.category_code}-${row.period_start}`}
        rows={filtered}
      />
    </>
  );
}
