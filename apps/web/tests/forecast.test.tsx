import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ForecastChart } from '@/components/forecasts/ForecastChart';
import { ForecastDetailPage } from '@/components/forecasts/ForecastDetailPage';
import { getForecast } from '@/lib/api';

import { forecastDetailFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getForecast: vi.fn(),
}));

describe('forecast rendering', () => {
  it('shows history, forecast, horizon and WAPE', async () => {
    vi.mocked(getForecast).mockResolvedValue(forecastDetailFixture);
    render(<ForecastDetailPage id={1} />);

    expect(await screen.findByRole('heading', { name: 'naive' })).toBeInTheDocument();
    expect(screen.getByText(/horizonte 2 semanas/)).toBeInTheDocument();
    expect(
      screen.getByLabelText('Serie de demanda real y pronosticada por semana'),
    ).toBeInTheDocument();
    expect(screen.getByText(/WAPE 11%/)).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '10' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '9' })).toBeInTheDocument();
  });

  it('draws a chart from aggregated predictions', () => {
    render(<ForecastChart predictions={forecastDetailFixture.predictions} />);
    expect(
      screen.getByLabelText('Serie de demanda real y pronosticada por semana'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Línea oscura: real observado/)).toBeInTheDocument();
  });
});
