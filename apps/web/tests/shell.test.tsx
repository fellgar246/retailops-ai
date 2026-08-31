import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AppShell } from '@/components/shell/AppShell';

import { overviewFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getOverview: vi.fn(async () => overviewFixture),
}));

vi.mock('@/components/ApiHealthIndicator', () => ({
  ApiHealthIndicator: () => <div>API connected</div>,
}));

describe('AppShell', () => {
  it('renders the primary operations navigation', async () => {
    render(
      <AppShell>
        <p>contenido</p>
      </AppShell>,
    );

    expect(screen.getByRole('navigation', { name: 'Navegación principal' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Overview/ })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /Revisiones/ })).toHaveAttribute('href', '/reviews');
    expect(screen.getByRole('link', { name: /Pronósticos/ })).toHaveAttribute('href', '/forecasts');
    expect(screen.getByRole('link', { name: /Documentos de proveedor/ })).toHaveAttribute(
      'href',
      '/documents',
    );
    expect(screen.getByRole('link', { name: /Conciliaciones/ })).toHaveAttribute(
      'href',
      '/reconciliations',
    );
    expect(screen.getByRole('link', { name: /Evaluación de IA/ })).toHaveAttribute(
      'href',
      '/evaluation',
    );
    expect(screen.getByRole('link', { name: /Auditoría/ })).toHaveAttribute('href', '/audit');
    expect(screen.getByRole('link', { name: /Configuración/ })).toHaveAttribute(
      'href',
      '/settings',
    );
    expect(await screen.findByText('4')).toBeInTheDocument();
  });
});
