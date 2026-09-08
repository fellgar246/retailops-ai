'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, useMemo, useState } from 'react';

import {
  approveReview,
  correctReview,
  getReview,
  getReviewAudit,
  getReviews,
  rejectReview,
  startReview,
} from '@/lib/api';
import { ApiError } from '@/lib/api-client';
import { confidenceBand, formatConfidence, formatDateTime, formatMoney } from '@/lib/format';
import {
  ACTION_LABELS,
  EVENT_LABELS,
  PRIORITY_LABELS,
  RISK_LABELS,
  SEVERITY_LABELS,
  STATUS_LABELS,
  labelOf,
} from '@/lib/labels';
import { useResource } from '@/lib/use-resource';
import { Badge } from '@/components/ui/Badge';
import { ErrorState } from '@/components/ui/ErrorState';
import { FreshnessBar } from '@/components/ui/FreshnessBar';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageHeader } from '@/components/ui/PageHeader';
import { Provenance } from '@/components/ui/Provenance';

export function ReviewDecisionPage({ id }: { id: number }) {
  const router = useRouter();
  const params = useSearchParams();
  const back = params.get('from') || '/reviews';
  const resource = useResource((signal) => getReview(id, signal), [id]);
  const audit = useResource(
    (signal) => getReviewAudit(id, signal),
    [id, resource.data?.updated_at],
  );
  const [comment, setComment] = useState('');
  const [reason, setReason] = useState('');
  const [correction, setCorrection] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  const output = resource.data?.snapshot?.original_output;
  const suggestion = useMemo(() => {
    if (!output) {
      return null;
    }
    return {
      summary: String(output.summary ?? ''),
      reasoning: String(output.reasoning_summary ?? ''),
      suggested: output.suggested_value == null ? null : String(output.suggested_value),
    };
  }, [output]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setNotice(null);
    setConflict(null);
    try {
      await action();
      resource.reload();
      audit.reload();
      setNotice('La decisión quedó registrada en el historial de auditoría.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setConflict(error.detail ?? error.message);
        return;
      }
      setNotice(error instanceof Error ? error.message : 'No se pudo completar la acción');
    } finally {
      setBusy(false);
    }
  };

  const goNext = async () => {
    const page = await getReviews({ status: ['open', 'in_review'], limit: 20 });
    const next = page.items.find((item) => item.id !== id);
    if (next) {
      router.push(`/reviews/${next.id}?from=${encodeURIComponent(back)}`);
    } else {
      router.push(back);
    }
  };

  if (!resource.data) {
    if (resource.status === 'loading') {
      return <LoadingState label="Cargando el caso…" />;
    }
    return (
      <ErrorState
        error={resource.error ?? new Error('Caso no encontrado')}
        onRetry={resource.reload}
      />
    );
  }

  const item = resource.data;
  const finding = item.subject.finding;
  const exception = item.subject.exception;
  const canStart = item.status === 'open';
  const canDecide = item.status === 'in_review';
  const decided = ['approved', 'rejected', 'corrected'].includes(item.status);

  const onApprove = (event: FormEvent) => {
    event.preventDefault();
    void run(() =>
      approveReview(id, {
        comment: comment || undefined,
        snapshot_id: item.snapshot?.id,
      }),
    );
  };

  const onReject = (event: FormEvent) => {
    event.preventDefault();
    void run(() => rejectReview(id, { reason, comment: comment || undefined }));
  };

  const onCorrect = (event: FormEvent) => {
    event.preventDefault();
    void run(() =>
      correctReview(id, {
        comment: comment || undefined,
        correction: { suggested_value: correction },
      }),
    );
  };

  return (
    <>
      <PageHeader
        breadcrumb="Revisiones / caso"
        description={`${item.supplier_code ?? 'Sin proveedor'} · impacto ${formatMoney(item.financial_impact)}`}
        title={`Caso ${item.id}`}
        actions={
          <Link className="btn" href={back}>
            Volver a la cola
          </Link>
        }
      />
      <FreshnessBar
        error={resource.error}
        onRefresh={resource.reload}
        stale={resource.status === 'loading'}
        updatedAt={item.updated_at}
      />
      <div className="filters">
        <Badge kind="status" labels={STATUS_LABELS} value={item.status} />
        <Badge kind="risk" labels={RISK_LABELS} value={item.risk} />
        <Badge kind="priority" labels={PRIORITY_LABELS} value={item.priority} />
        <span className="chip">
          Confianza {formatConfidence(item.confidence)}
          {confidenceBand(item.confidence) ? ` · ${confidenceBand(item.confidence)}` : ''}
        </span>
        {item.reviewer ? <span className="chip">Asignado a {item.reviewer}</span> : null}
      </div>
      {conflict ? (
        <div className="notice notice--error" role="alert">
          El caso cambió mientras decidías: {conflict}. Recarga y vuelve a intentar.
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={resource.reload} type="button">
              Recargar caso
            </button>
          </div>
        </div>
      ) : null}
      {notice ? (
        <div className="notice" role="status">
          {notice}
        </div>
      ) : null}
      <div className="workspace">
        <div className="stack">
          <section className="panel">
            <h2>Hechos determinísticos</h2>
            <Provenance source="rule" />
            {finding ? (
              <>
                <p>{finding.message}</p>
                <p className="muted">
                  {finding.field ?? 'campo'} · fila {finding.row_reference ?? '—'} · {finding.code}
                </p>
                {finding.proposed_value ? (
                  <p>Propuesta de regla: {finding.proposed_value}</p>
                ) : null}
                {item.subject.document ? (
                  <p>
                    Fuente:{' '}
                    <Link href={`/documents/${item.subject.document.id}`}>
                      {item.subject.document.filename}
                    </Link>
                  </p>
                ) : null}
              </>
            ) : null}
            {exception ? (
              <>
                <p>{exception.message}</p>
                <p>
                  Esperado <strong>{exception.expected_value}</strong> · real{' '}
                  <strong>{exception.actual_value}</strong> · impacto{' '}
                  {formatMoney(exception.financial_impact)}
                </p>
                <Badge kind="severity" labels={SEVERITY_LABELS} value={exception.severity} />
                <p>
                  <Link href={`/reconciliations/${exception.reconciliation_run_id}`}>
                    Ver conciliación
                  </Link>
                </p>
              </>
            ) : null}
          </section>
          <section className="panel">
            <h2>Propuesta de IA</h2>
            {item.snapshot ? (
              <>
                <div className="provenance">
                  <Provenance source="ai" />
                  <span className="chip">
                    {item.snapshot.provider} · {item.snapshot.model}
                  </span>
                  <span className="chip">
                    {item.snapshot.prompt_id} {item.snapshot.prompt_version}
                  </span>
                </div>
                <p>{suggestion?.summary || item.snapshot.recommendation}</p>
                <p className="muted">{suggestion?.reasoning}</p>
                <p>
                  Recomendación:{' '}
                  <strong>{labelOf(ACTION_LABELS, item.snapshot.recommendation)}</strong>
                  {suggestion?.suggested ? ` · valor sugerido ${suggestion.suggested}` : ''}
                </p>
                <p className="muted">
                  En evaluación, una confianza de {formatConfidence(item.snapshot.confidence)} se
                  interpreta como banda {confidenceBand(item.snapshot.confidence) ?? 'desconocida'}.
                  No es un sello de verdad.
                </p>
              </>
            ) : (
              <p className="muted">Este caso no tiene una instantánea de IA.</p>
            )}
          </section>
          {item.decision ? (
            <section className="panel">
              <h2>Decisión humana</h2>
              <Provenance source="human" />
              <p>
                {STATUS_LABELS[item.status]} por {item.decision.reviewer} el{' '}
                {formatDateTime(item.decision.created_at)}
              </p>
              {item.decision.reason ? <p>Motivo: {item.decision.reason}</p> : null}
              {item.decision.comment ? <p>Comentario: {item.decision.comment}</p> : null}
              {item.decision.correction ? (
                <div className="diff">
                  <div className="diff__box">
                    <p className="muted">Antes (IA)</p>
                    <p>{suggestion?.suggested ?? item.snapshot?.recommendation ?? '—'}</p>
                  </div>
                  <div className="diff__box">
                    <p className="muted">Después (humano)</p>
                    <p>
                      {String(
                        item.decision.correction.suggested_value ??
                          JSON.stringify(item.decision.correction),
                      )}
                    </p>
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
        <aside className="panel">
          <h2>Acción</h2>
          {canStart ? (
            <button
              className="btn btn--primary"
              disabled={busy}
              onClick={() => void run(() => startReview(id))}
              type="button"
            >
              Tomar caso
            </button>
          ) : null}
          {canDecide ? (
            <form className="stack" onSubmit={onApprove}>
              <div className="field">
                <label htmlFor="comment">Comentario</label>
                <textarea
                  id="comment"
                  onChange={(event) => setComment(event.target.value)}
                  value={comment}
                />
              </div>
              <div className="btn-row">
                <button className="btn btn--primary" disabled={busy} type="submit">
                  Aprobar recomendación
                </button>
              </div>
              <div className="field">
                <label htmlFor="reason">Motivo de rechazo</label>
                <input
                  id="reason"
                  onChange={(event) => setReason(event.target.value)}
                  value={reason}
                />
              </div>
              <button
                className="btn btn--danger"
                disabled={busy || !reason.trim()}
                onClick={onReject}
                type="button"
              >
                Rechazar propuesta
              </button>
              <div className="field">
                <label htmlFor="correction">Corregir valor sugerido</label>
                <input
                  id="correction"
                  onChange={(event) => setCorrection(event.target.value)}
                  value={correction}
                />
              </div>
              {correction ? (
                <div className="diff">
                  <div className="diff__box">
                    <p className="muted">Antes</p>
                    <p>{suggestion?.suggested ?? '—'}</p>
                  </div>
                  <div className="diff__box">
                    <p className="muted">Después</p>
                    <p>{correction}</p>
                  </div>
                </div>
              ) : null}
              <button
                className="btn"
                disabled={busy || !correction.trim()}
                onClick={onCorrect}
                type="button"
              >
                Confirmar corrección
              </button>
            </form>
          ) : null}
          {!canStart && !canDecide ? (
            <p className="muted">
              {decided
                ? 'Este caso ya está cerrado. El historial queda a la derecha.'
                : 'No hay una acción disponible en el estado actual.'}
            </p>
          ) : null}
          {decided ? (
            <button className="btn btn--primary" onClick={() => void goNext()} type="button">
              Ir al siguiente caso
            </button>
          ) : null}
        </aside>
      </div>
      <section className="panel">
        <h2>Historial de auditoría</h2>
        {audit.data?.items.length ? (
          <ol>
            {audit.data.items.map((event) => (
              <li key={event.id}>
                <strong>{labelOf(EVENT_LABELS, event.event_type)}</strong> · {event.actor} ·{' '}
                {formatDateTime(event.created_at)}
                {event.from_status && event.to_status
                  ? ` · ${labelOf(STATUS_LABELS, event.from_status)} → ${labelOf(STATUS_LABELS, event.to_status)}`
                  : ''}
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">Sin eventos todavía.</p>
        )}
      </section>
    </>
  );
}
