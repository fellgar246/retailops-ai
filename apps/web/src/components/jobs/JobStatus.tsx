'use client';

import type { Job } from '@/lib/types';

const STATE_LABELS: Record<string, string> = {
  queued: 'En cola',
  running: 'Procesando',
  succeeded: 'Completado',
  failed: 'Falló',
  cancelled: 'Cancelado',
};

const STATE_TONE: Record<string, string> = {
  queued: 'chip',
  running: 'chip',
  succeeded: 'chip chip--ok',
  failed: 'chip chip--danger',
  cancelled: 'chip',
};

interface JobStatusProps {
  job: Job;
  /** Where the finished work can be seen, when there is somewhere to go. */
  resultHref?: string;
  resultLabel?: string;
}

export function JobStatus({ job, resultHref, resultLabel }: JobStatusProps) {
  return (
    <div className="job-status" role="status">
      <span className={STATE_TONE[job.state] ?? 'chip'}>
        {STATE_LABELS[job.state] ?? job.state}
      </span>
      {job.state === 'failed' && job.failure_reason ? (
        <span className="job-status__reason">{job.failure_reason}</span>
      ) : null}
      {job.state === 'succeeded' && resultHref ? (
        <a className="btn" href={resultHref}>
          {resultLabel ?? 'Ver resultado'}
        </a>
      ) : null}
      {job.attempts > 1 && job.state !== 'succeeded' ? (
        <span className="muted">
          Intento {job.attempts} de {job.max_attempts}
        </span>
      ) : null}
    </div>
  );
}
