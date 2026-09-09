# ADR-007 — Procurement Documents and Deterministic Reconciliation

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Purchase orders, goods receipts, supplier invoices, three-way match

## Context

The catalog already holds who sells what, at what cost. Paying a supplier
requires a second set of documents: what was ordered, what arrived, and what
was billed. Differences between those three are operational facts — short
deliveries, over-billing, a tax rate that was not on the order — and they
must be found with ordinary arithmetic, not a model.

Explanations of those exceptions are a separate contract
([ADR-008](ADR-008-ai-review-contracts.md)). This decision is only about
persisting the documents and comparing them deterministically.

## Decision

### Three operational documents

`PurchaseOrder` / `PurchaseOrderLine` record an issued order for one supplier
and one store. `po_number` is unique per supplier. Line quantities are
positive integers; `unit_cost`, `tax_rate` (a percentage), `tax_amount` and
`line_total` are `NUMERIC(12, 4)`. Currency lives on the header.

`GoodsReceipt` / `GoodsReceiptLine` record a delivery. Several receipts may
reference the same order (a partial delivery). Receipts are quantity facts:
they carry no money. `receipt_number` is unique per supplier. The PO
reference is optional.

`SupplierInvoice` / `SupplierInvoiceLine` record a bill. `(supplier_id,
invoice_number)` is unique so an obvious duplicate cannot be stored. Invoice
lines may omit `product_id` and carry only a supplier SKU or EAN; matching
resolves identity afterwards.

Headers are mutable operational rows (`updated_at`, `active`). Lines are
owned by their header (`ON DELETE CASCADE`). Catalog foreign keys stay
`ON DELETE RESTRICT`. Cancelled documents are excluded from a match.

### Matching does not guess

The engine tries, in order:

1. exact supplier + purchase-order number
2. exact product identity
3. that supplier's SKU on `supplier_products`
4. EAN on the product catalog, when the barcode is present

A strategy that finds nothing is skipped. Two strategies that find different
products, or one strategy that finds more than one order line, create an
`ambiguous_line` exception. An identity that resolves to nothing creates
`unmatched_line`.

### Quantity, price and tolerances

Quantities compared: ordered, received (sum of receipt lines), invoiced
(sum of invoice lines). Detections: `short_receipt`, `over_receipt`,
`over_invoice`, `under_invoice`, `invoice_without_receipt`.

Price detections: `cost_mismatch`, `line_total_mismatch` (stored total vs
`qty × cost + tax`), `unexpected_tax`, `currency_mismatch`. All money uses
`Decimal` quantized to four places.

Tolerances default to zero — any difference is an exception:

| Setting | Default | Meaning |
|---|---|---|
| `quantity_tolerance` | `0` | whole units |
| `monetary_tolerance` | `0.0000` | absolute cost |
| `price_percent_tolerance` | `0.0000` | percent of the PO unit cost |

A price difference passes when it is inside the monetary band *or* the
percent band. Currency mismatches are never absorbed.

### Runs are versioned facts

`ReconciliationRun` is immutable. It is keyed by `scope_key` (the purchase
order once known, otherwise the invoice) and a `version`. The input
fingerprint covers the selected documents and the tolerances. A second call
with the same fingerprint returns the existing run. A change writes
`version + 1`.

`ReconciliationException` belongs to the run (`ON DELETE CASCADE`) and
stores code, severity, source references, expected/actual values, signed
financial impact and a `resolution_status` (`open` / `resolved` /
`dismissed`). Exceptions are mutable so a resolution can be recorded.

## Consequences

**Positive**

- A three-way match can be run locally with `make reconcile`.
- Impact is a signed `Decimal`, so over-billing and short receipts add
  correctly.
- Re-running an unchanged scope is idempotent.

**Negative**

- Two order lines for the same product cannot be matched automatically.
- Resolutions on an old version are not copied forward when inputs change.

**Deferred**

- HTTP API and a review UI for exceptions.
- Applying a resolution back onto invoice or receipt status.
