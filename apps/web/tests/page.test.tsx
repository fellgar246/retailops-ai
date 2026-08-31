import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import HomePage from '@/app/page';

import { overviewFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getOverview: vi.fn(async () => overviewFixture),
}));

describe('HomePage', () => {
  it('identifies the application as RetailOps AI and shows backend metrics', async () => {
    render(<HomePage />);

    expect(await screen.findByRole('heading', { name: 'Overview operativo' })).toBeInTheDocument();
    expect(screen.getByText('Revisiones abiertas')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });
});
