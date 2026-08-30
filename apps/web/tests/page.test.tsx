import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import HomePage from '@/app/page';

vi.mock('@/components/ApiHealthIndicator', () => ({
  ApiHealthIndicator: () => <div data-testid="api-health-indicator" />,
}));

describe('HomePage', () => {
  it('identifies the application as RetailOps AI', () => {
    render(<HomePage />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('RetailOps AI');
  });

  it('renders the API connectivity indicator', () => {
    render(<HomePage />);

    expect(screen.getByTestId('api-health-indicator')).toBeInTheDocument();
  });
});
