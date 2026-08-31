import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ReviewDecisionPage } from '@/components/reviews/ReviewDecisionPage';
import { approveReview, getReview, getReviewAudit } from '@/lib/api';
import { ApiError } from '@/lib/api-client';

import { reviewDetailFixture } from './fixtures';

vi.mock('@/lib/api', () => ({
  getReview: vi.fn(),
  getReviewAudit: vi.fn(),
  approveReview: vi.fn(),
  rejectReview: vi.fn(),
  correctReview: vi.fn(),
  startReview: vi.fn(),
  getReviews: vi.fn(),
}));

describe('review decision UI', () => {
  it('keeps deterministic facts apart from the AI proposal and records approve', async () => {
    vi.mocked(getReview).mockResolvedValue(reviewDetailFixture);
    vi.mocked(getReviewAudit).mockResolvedValue({
      items: [
        {
          id: 1,
          review_case_id: 12,
          event_type: 'created',
          actor: 'system',
          from_status: null,
          to_status: 'open',
          payload: null,
          created_at: '2026-08-30T17:00:00+00:00',
        },
      ],
    });
    vi.mocked(approveReview).mockResolvedValue({
      ...reviewDetailFixture,
      status: 'approved',
    });

    render(<ReviewDecisionPage id={12} />);

    expect(await screen.findByText('Hechos determinísticos')).toBeInTheDocument();
    expect(screen.getByText('description is required')).toBeInTheDocument();
    expect(screen.getByText('Propuesta de IA')).toBeInTheDocument();
    expect(screen.getByText('La categoría parece bebidas.')).toBeInTheDocument();
    expect(screen.getByText('Interpretación de IA')).toBeInTheDocument();
    expect(screen.getByText('Regla determinística')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Comentario'), 'ok');
    await userEvent.click(screen.getByRole('button', { name: 'Aprobar recomendación' }));

    expect(approveReview).toHaveBeenCalledWith(
      12,
      expect.objectContaining({ comment: 'ok', snapshot_id: 4 }),
    );
    expect(await screen.findByText(/La decisión quedó registrada/)).toBeInTheDocument();
  });

  it('surfaces a conflict so the reviewer can retry', async () => {
    vi.mocked(getReview).mockResolvedValue(reviewDetailFixture);
    vi.mocked(getReviewAudit).mockResolvedValue({ items: [] });
    vi.mocked(approveReview).mockRejectedValue(new ApiError('conflict', 409, 'already decided'));

    render(<ReviewDecisionPage id={12} />);
    await screen.findByText('Propuesta de IA');
    await userEvent.click(screen.getByRole('button', { name: 'Aprobar recomendación' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('already decided');
    expect(screen.getByRole('button', { name: 'Recargar caso' })).toBeInTheDocument();
  });
});
