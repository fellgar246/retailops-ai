'use client';

import { FormEvent, useRef, useState } from 'react';

import { JobStatus } from '@/components/jobs/JobStatus';
import { uploadSupplierDocument } from '@/lib/api';
import { ApiError } from '@/lib/api-client';
import { useJob } from '@/lib/use-job';
import { canDecide, useSession } from '@/lib/use-session';

interface DocumentUploadProps {
  /** Called once a job settles, so the list behind it can catch up. */
  onSettled?: () => void;
}

export function DocumentUpload({ onSettled }: DocumentUploadProps) {
  const { session } = useSession();
  const { job, track, reset } = useJob(onSettled);
  const [supplier, setSupplier] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // A viewer is shown no control rather than one that fails on use.
  if (!canDecide(session)) {
    return null;
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError('Elige un archivo');
      return;
    }
    setBusy(true);
    setError(null);
    reset();
    try {
      track(await uploadSupplierDocument(supplier.trim(), file));
      if (fileRef.current) {
        fileRef.current.value = '';
      }
    } catch (cause) {
      setError(
        cause instanceof ApiError ? (cause.detail ?? cause.message) : 'No se pudo subir el archivo',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel">
      <h2>Cargar hoja de proveedor</h2>
      <p className="muted">
        El archivo se valida en segundo plano. Puedes seguir el progreso aquí sin esperar en esta
        pantalla.
      </p>
      <form className="upload-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="upload-supplier">Proveedor</label>
          <input
            id="upload-supplier"
            onChange={(event) => setSupplier(event.target.value)}
            placeholder="SUP-BEVCO"
            required
            value={supplier}
          />
        </div>
        <div className="field">
          <label htmlFor="upload-file">Archivo</label>
          <input
            accept=".csv,.xlsx,.pdf,.png,.jpg,.jpeg,.tif,.tiff"
            id="upload-file"
            ref={fileRef}
            type="file"
          />
        </div>
        <button className="btn btn--primary" disabled={busy} type="submit">
          {busy ? 'Enviando…' : 'Cargar'}
        </button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {job ? (
        <JobStatus
          job={job}
          resultHref={
            job.result?.document_id ? `/documents/${String(job.result.document_id)}` : undefined
          }
          resultLabel="Ver documento"
        />
      ) : null}
    </section>
  );
}
