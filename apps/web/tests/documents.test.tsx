import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DocumentDetailPage } from '@/components/documents/DocumentDetailPage';
import { getDocument } from '@/lib/api';

import { documentDetailFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getDocument: vi.fn(),
}));

describe('supplier document findings', () => {
  it('separates extracted rows from deterministic findings', async () => {
    vi.mocked(getDocument).mockResolvedValue(documentDetailFixture);
    render(<DocumentDetailPage id={9} />);

    expect(await screen.findByRole('heading', { name: 'offer.csv' })).toBeInTheDocument();
    expect(screen.getByText('New Cola 330ml')).toBeInTheDocument();
    expect(screen.getByText('description is required')).toBeInTheDocument();
    expect(screen.getByText('Regla determinística')).toBeInTheDocument();
    expect(screen.getByText('Alta')).toBeInTheDocument();
  });
});
