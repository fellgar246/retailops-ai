"""Coordinate a three-way match.

    select records → match → calculate → apply tolerances → create exceptions → summarize

The caller owns the transaction. A second call with the same documents and
tolerances returns the existing run (same fingerprint, same version).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from retailops_api.procurement.load import load_identity_index, load_scope, scope_key_for
from retailops_api.procurement.persist import (
    input_fingerprint,
    latest_run,
    persist_run,
    result_from_run,
)
from retailops_api.procurement.rules import evaluate
from retailops_api.procurement.types import (
    ReconciliationResult,
    ReconciliationScope,
    ReconciliationTolerances,
)


def reconcile(
    session: Session,
    scope: ReconciliationScope,
    *,
    tolerances: ReconciliationTolerances | None = None,
    generated_at: datetime | None = None,
) -> ReconciliationResult:
    settings = tolerances or ReconciliationTolerances()
    records = load_scope(session, scope)
    index = load_identity_index(session, supplier_id=records.supplier_id)
    draft = evaluate(records, index, settings)
    fingerprint = input_fingerprint(records, draft)
    key = scope_key_for(records, scope)
    existing = latest_run(session, key)
    if existing is not None and existing.input_fingerprint == fingerprint:
        return result_from_run(existing, reused=True)

    version = 1 if existing is None else existing.version + 1
    run = persist_run(
        session,
        scope_key=key,
        version=version,
        fingerprint=fingerprint,
        generated_at=generated_at or datetime.now(UTC),
        records=records,
        draft=draft,
    )
    return result_from_run(run, reused=False)
