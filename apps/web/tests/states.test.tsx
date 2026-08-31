import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ForecastListPage } from '@/components/forecasts/ForecastListPage';
import { getForecasts } from '@/lib/api';
import { ApiError } from '@/lib/api-client';

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
});
