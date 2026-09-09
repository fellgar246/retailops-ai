# ADR-006 — Supplier Document Intake and Deterministic Validation

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Supplier-document records, local object storage, sheet parsing, rule engine

## Context

Suppliers send offer sheets (CSV, XLSX, occasionally a text PDF) that need to
be stored and reviewed before anyone changes catalog terms. The review that
can be done without a model is mechanical: required cells, identifier shape,
numeric bounds, configured VAT rates, duplicates inside the file, and a
comparison to the live catalog (identity collisions, cost increases, category
drift).

Bytes should not live in PostgreSQL. Storage and document analysis must stay
replaceable so a hosted object store or a document-analysis API can implement
the same operations later. Image-only and scanned PDFs are out of scope for
the local adapter.

## Decision

### Documents and findings are first-class rows

`SupplierDocument` records the supplier, original filename, media type,
storage key, SHA-256 checksum, document type and status. It is a mutable
catalog-adjacent row (`updated_at`, `active`).

`DocumentFinding` is an immutable fact owned by the document (`ON DELETE
CASCADE`): code, field, source row, severity, message and an optional
proposed value. Re-processing replaces the set.

Happy-path status: `received` → `parsed` → `validated` → `review_ready`.
`parse_failed` is terminal when the bytes cannot be turned into rows.
Findings do not block `review_ready`; they *are* the review.

The only processed type today is `supplier_sheet`.

### Storage is a contract

`DocumentStorage` exposes save, read, open, exists, metadata and delete.
`LocalDocumentStorage` writes under a configured root using a generated
32-hex key. The original filename is stored in a sidecar and never used as a
path component. Illegal keys are rejected so a caller cannot walk out of the
root.

The same operations map onto object storage (put / get / head / delete)
without changing callers.

### One canonical sheet

Headers fold through an alias map onto:

`supplier_sku`, `ean`, `description`, `category`, `cost`, `vat`,
`case_pack`, `minimum_order_quantity`, `lead_time_days`.

CSV and XLSX share one row builder. The text-PDF adapter extracts page text
and, only when a line maps onto at least two canonical columns, parses the
rest as a delimited table. It does not reconstruct tables from drawing
positions.

### Rules are functions

Intra-document rules and catalog cross-checks are independently testable.
They return structured findings. They do not write the catalog. Optional
semantic review of those findings is a separate contract
([ADR-008](ADR-008-ai-review-contracts.md)).

Default allowed VAT rates are 0, 8 and 16. Cost is `Decimal`; quantities are
integers. EAN shape matches the portable dataset (8–14 digits).

## Consequences

**Positive**

- A supplier file can be ingested and reviewed locally with `make documents`.
- Storage and PDF analysis stay behind interfaces.
- Findings are queryable and survive a process restart.

**Negative**

- The text-PDF adapter only accepts a controlled tabular layout.
- VAT is not a catalog column, so the rate check is configuration, not a
  join.

**Deferred**

- Calling a live bucket or Textract from the running API.
- Applying accepted findings back onto `supplier_products`.
