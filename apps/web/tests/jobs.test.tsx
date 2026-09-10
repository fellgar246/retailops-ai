import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentUpload } from '@/components/documents/DocumentUpload';
import { JobStatus } from '@/components/jobs/JobStatus';
import type { Job } from '@/lib/types';

const uploadSupplierDocument = vi.fn();
const getJob = vi.fn();

vi.mock('@/lib/api', () => ({
  uploadSupplierDocument: (...args: unknown[]) => uploadSupplierDocument(...args),
  getJob: (...args: unknown[]) => getJob(...args),
}));

let roles = ['reviewer'];

vi.mock('@/lib/use-session', () => ({
  useSession: () => ({
    session: { provider: 'local', user: { name: 'Ana', email: null, roles } },
    loading: false,
    signOut: vi.fn(),
  }),
  canDecide: () => roles.includes('reviewer'),
}));

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: 7,
    kind: 'document_intake',
    state: 'queued',
    requested_by: 'Ana',
    requested_by_verified: true,
    request: { supplier_code: 'SUP-1' },
    result: null,
    failure_reason: null,
    attempts: 0,
    max_attempts: 3,
    created_at: '2026-09-09T10:00:00Z',
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

describe('JobStatus', () => {
  it('explains a failure instead of showing a generic error', () => {
    render(<JobStatus job={job({ state: 'failed', failure_reason: 'unknown supplier' })} />);

    expect(screen.getByText('Falló')).toBeInTheDocument();
    expect(screen.getByText('unknown supplier')).toBeInTheDocument();
  });

  it('links to what the job produced once it succeeds', () => {
    render(
      <JobStatus
        job={job({ state: 'succeeded', result: { document_id: 12 } })}
        resultHref="/documents/12"
        resultLabel="Ver documento"
      />,
    );

    expect(screen.getByRole('link', { name: 'Ver documento' })).toHaveAttribute(
      'href',
      '/documents/12',
    );
  });

  it('says nothing about retries while the work is still going well', () => {
    render(<JobStatus job={job({ state: 'running' })} />);

    expect(screen.queryByText(/Intento/)).not.toBeInTheDocument();
  });
});

describe('DocumentUpload', () => {
  beforeEach(() => {
    roles = ['reviewer'];
    uploadSupplierDocument.mockReset();
    getJob.mockReset();
  });

  it('shows a viewer no control rather than one that would fail', () => {
    roles = ['viewer'];

    const { container } = render(<DocumentUpload />);

    expect(container).toBeEmptyDOMElement();
  });

  it('submits the supplier and file, then follows the job', async () => {
    uploadSupplierDocument.mockResolvedValue(job());
    getJob.mockResolvedValue(job({ state: 'succeeded', result: { document_id: 3 } }));
    const user = userEvent.setup();

    render(<DocumentUpload />);
    await user.type(screen.getByLabelText('Proveedor'), 'SUP-BEVCO');
    await user.upload(
      screen.getByLabelText('Archivo'),
      new File(['sku,description\n'], 'offer.csv', { type: 'text/csv' }),
    );
    await user.click(screen.getByRole('button', { name: 'Cargar' }));

    await waitFor(() => expect(uploadSupplierDocument).toHaveBeenCalledOnce());
    expect(uploadSupplierDocument.mock.calls[0]?.[0]).toBe('SUP-BEVCO');
    expect(await screen.findByText('En cola')).toBeInTheDocument();
  });

  it('refuses to submit without a file', async () => {
    const user = userEvent.setup();

    render(<DocumentUpload />);
    await user.type(screen.getByLabelText('Proveedor'), 'SUP-BEVCO');
    await user.click(screen.getByRole('button', { name: 'Cargar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Elige un archivo');
    expect(uploadSupplierDocument).not.toHaveBeenCalled();
  });
});
