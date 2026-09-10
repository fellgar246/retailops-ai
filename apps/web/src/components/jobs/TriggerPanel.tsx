'use client';

import { FormEvent, ReactNode, useState } from 'react';

import { JobStatus } from '@/components/jobs/JobStatus';
import { ApiError } from '@/lib/api-client';
import type { Job } from '@/lib/types';
import { useJob } from '@/lib/use-job';
import { canDecide, useSession } from '@/lib/use-session';

interface TriggerPanelProps {
  title: string;
  description: string;
  submitLabel: string;
  children: ReactNode;
  start: () => Promise<Job>;
  resultHref?: (job: Job) => string | undefined;
  resultLabel?: string;
  onSettled?: () => void;
}

/** Shared shell for starting a piece of work and following it. */
export function TriggerPanel({
  title,
  description,
  submitLabel,
  children,
  start,
  resultHref,
  resultLabel,
  onSettled,
}: TriggerPanelProps) {
  const { session } = useSession();
  const { job, track, reset } = useJob(onSettled);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A viewer is shown no control rather than one that fails on use.
  if (!canDecide(session)) {
    return null;
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    reset();
    try {
      track(await start());
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? (cause.detail ?? cause.message)
          : 'No se pudo iniciar el trabajo',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="muted">{description}</p>
      <form className="trigger-form" onSubmit={submit}>
        {children}
        <button className="btn btn--primary" disabled={busy} type="submit">
          {busy ? 'Enviando…' : submitLabel}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {job ? (
        <JobStatus job={job} resultHref={resultHref?.(job)} resultLabel={resultLabel} />
      ) : null}
    </section>
  );
}
