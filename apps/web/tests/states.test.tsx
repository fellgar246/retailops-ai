import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ForecastListPage } from '@/components/forecasts/ForecastListPage';
import { getForecasts } from '@/lib/api';
import { ApiError } from '@/lib/api-client';

import { forecastPageFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getForecasts: vi.fn(),
}));

describe('ForecastListPage states', () => {
  it('renders a loading state', () => {
    vi.mocked(getForecasts).mockReturnValue(new Promise(() => undefined));
    render(<ForecastListPage />);
    expect(screen.getByText('Cargando ejecuciones de forecast…')).toBeInTheDocument();
  });

  it('renders an empty state when there are no runs', async () => {
    vi.mocked(getForecasts).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    render(<ForecastListPage />);
    expect(await screen.findByText('Sin ejecuciones de forecast')).toBeInTheDocument();
  });

  it('renders an API failure with retry', async () => {
    vi.mocked(getForecasts).mockRejectedValue(new ApiError('down', 503, 'API unavailable'));
    render(<ForecastListPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable');
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });

  it('keeps the last payload visible while a refresh is in flight', async () => {
    vi.mocked(getForecasts).mockResolvedValueOnce(forecastPageFixture);
    render(<ForecastListPage />);
    expect(await screen.findByText('naive')).toBeInTheDocument();

    vi.mocked(getForecasts).mockReturnValue(new Promise(() => undefined));
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));

    expect(screen.getByText('naive')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/Actualizando/);
  });

  it('keeps the last payload visible when a refresh fails', async () => {
    vi.mocked(getForecasts).mockResolvedValueOnce(forecastPageFixture);
    render(<ForecastListPage />);
    expect(await screen.findByText('naive')).toBeInTheDocument();

    vi.mocked(getForecasts).mockRejectedValueOnce(new ApiError('down', 503, 'API unavailable'));
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo actualizar. Se muestra la última versión cargada.',
    );
    expect(screen.getByText('naive')).toBeInTheDocument();
  });
});

describe('decision workspace layout', () => {
  it('stacks the workspace below 1200px so 1280px at 200% zoom stays usable', () => {
    const css = readFileSync(resolve(__dirname, '../src/app/globals.css'), 'utf8');
    const start = css.indexOf('@media (max-width: 1199px)');
    expect(start).toBeGreaterThan(-1);
    const block = css.slice(start, css.indexOf('@media (max-width: 767px)', start));
    expect(block).toMatch(/\.workspace/);
    expect(block).toMatch(/grid-template-columns:\s*1fr/);
  });
});
