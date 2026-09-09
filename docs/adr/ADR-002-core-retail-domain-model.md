# ADR-002 — Core Retail Domain Model and Persistence Conventions

- **Status:** Accepted
- **Date:** 2026-08-30
- **Scope:** Core retail domain and persistence

## Context

This work establishes the canonical retail catalog and the historical-sales
table that everything downstream depends on: synthetic-data generation,
ingestion, forecasting, supplier review and procurement. Because those consumers
read and write these tables constantly, the shape of the schema is expensive to
change later — a forecasting job that assumes one row per store/product/day
breaks if that assumption is relaxed after data exists.

Six entities are in scope: `Category`, `Product`, `Supplier`,
`SupplierProduct`, `Store` and `SalesRecord`. No forecasting logic, no AI and no
AWS service belongs here.

The decisions below had to be settled before writing the first migration.

## Decision

### Identifier strategy

Every table uses a database-generated surrogate primary key named `id`, typed
`BigInteger` (with an `Integer` variant on SQLite so unit tests can use an
in-memory database). Business identifiers — `Product.sku`, `Category.code`,
`Supplier.code`, `Store.code` — are separate columns with their own unique
constraints.

Surrogate keys were chosen over natural keys because retail business codes are
routinely re-issued or corrected by the people who own them, and a foreign key
that points at a mutable SKU forces a cascading update across the sales history.
UUIDs were rejected: `SalesRecord` is the highest-volume table in the system and
a 16-byte random key inflates every index on it for no benefit in a single-writer
local database.

### Timestamps

`created_at` and `updated_at` are `TIMESTAMP WITH TIME ZONE`, never nullable,
defaulted by the database via `now()`. `updated_at` also carries an SQLAlchemy
`onupdate`, so it advances on any ORM flush.

Timezone-aware columns are used everywhere so that ingestion from multiple
regions cannot silently mix local wall-clock times. All application code works
in UTC.

`SalesRecord` is the exception: it carries only `created_at`. A sales fact is
immutable once ingested — a correction is a new ingestion of the same natural
key, handled as an upsert — so an `updated_at` column would only ever restate
`created_at`.

### Active / soft-state handling

The five catalog entities carry a non-nullable `active` boolean defaulting to
true. Deactivating a product or supplier keeps historical sales joinable while
removing the record from forecasting and procurement candidate sets.

This is deliberately *not* a soft delete: there is no `deleted_at`, and rows are
never filtered out implicitly. Callers that want only live records ask for them.
`SalesRecord` has no `active` flag — history is not deactivated.

### Uniqueness

| Entity | Unique key |
|---|---|
| Category | `code` |
| Product | `sku`; `ean` when present |
| Supplier | `code` |
| SupplierProduct | `(supplier_id, product_id)` |
| Store | `code` |
| SalesRecord | `(store_id, product_id, business_date)` |

`Product.ean` is nullable and unique. PostgreSQL treats `NULL`s as distinct in a
unique index, so many products without a barcode coexist while a present barcode
stays unique — no partial index needed.

### Decimal and money handling

Money and cost columns are `Numeric(12, 4)` and map to Python `Decimal`. Floats
are never used for money: repeated float arithmetic over a year of sales lines
produces cent-level drift that then shows up in margin calculations.

Four decimal places, rather than two, because supplier cost is frequently quoted
per-unit inside a case (a 24-unit case at 19.99 is 0.8329 per unit) and unit
prices after promotional allocation are not whole cents. Twelve total digits
leaves eight before the decimal point, which is ample for line-level retail
amounts.

Quantities that cannot be fractional — `units_sold`, `case_pack`,
`minimum_order_quantity`, `lead_time_days`, `stock_on_hand` — are integers.

### Date handling

`SalesRecord.business_date` is a plain `DATE`, not a timestamp. It represents the
store's trading day as the business reports it, which is a calendar concept: a
sale rung up at 00:30 during a late shift belongs to the previous trading day,
and forecasting aggregates by day regardless. Storing an instant would invite
timezone conversion to move a sale between days.

### Category hierarchy

Categories form a self-referencing tree via a nullable `parent_id`. A `NULL`
parent is a root category. The relation is indexed, and a check constraint
forbids a row from being its own parent.

An adjacency list was chosen over nested sets or materialised paths because
retail category trees are shallow (typically department → category →
subcategory) and are read far more often than they are restructured. Deeper
cycles are not enforced in the database; the seed data and ingestion code own
that invariant.

`Product.category_id` is required. Every product belongs to exactly one
category, because category is the grouping key for forecast aggregation and an
uncategorised product would silently drop out of those reports.

### Supplier–product relationship

`SupplierProduct` is an explicit association entity rather than a plain
many-to-many table, because the commercial terms live on the relationship, not
on either side of it: `cost`, `case_pack`, `minimum_order_quantity`,
`lead_time_days` and the supplier's own `supplier_sku`.

The same product may be offered by several suppliers, which is what makes
supplier comparison possible at all; `(supplier_id, product_id)` is
unique so each pairing has exactly one set of live terms. Check constraints
enforce `cost >= 0`, `case_pack > 0`, `minimum_order_quantity >= 0` and
`lead_time_days >= 0` at the database level, so bad terms cannot enter through
any path — ORM, raw SQL or migration.

There is no "preferred supplier" flag. Supplier selection is a decision
procurement makes from current terms, not a stored attribute.

### Referential integrity

All foreign keys are `RESTRICT` on delete. Catalog rows referenced by sales
history cannot be deleted; deactivation is the supported operation. Foreign key
columns are indexed, since every read path filters on them.

### Naming conventions

A single SQLAlchemy `MetaData` naming convention generates every constraint and
index name (`pk_`, `fk_`, `uq_`, `ix_`, `ck_` prefixes). Autogenerated Alembic
migrations therefore produce stable, predictable names, and a downgrade can drop
a constraint by name without inspecting the live database.

## Consequences

**Positive**

- Forecasting and ingestion can rely on one row per store/product/day, upserted by natural key, making re-ingestion of a corrected file safe and repeatable.
- Money is exact end to end; no rounding reconciliation step is needed.
- Business codes can be corrected without touching sales history.
- Constraints live in the database, so synthetic-data generation gets immediate feedback when it produces impossible rows.

**Negative**

- The natural sales key forbids storing individual transaction lines. Basket-level analysis would need a new table rather than a change to this one.
- `RESTRICT` everywhere means test and seed teardown must delete in dependency order.
- The adjacency-list hierarchy needs a recursive query to fetch a whole subtree.
- `Numeric(12, 4)` returns `Decimal`, so every consumer must avoid mixing it with floats.

**Deferred**

- Inventory movements get their own tables when they are needed.
  Purchase orders, receipts, invoices and reconciliation are covered by
  ADR-007. Supplier documents are covered by ADR-006.
- Table partitioning for `SalesRecord` is unnecessary at local-development volumes and will be revisited when data volume justifies it.
- Cycle detection deeper than self-reference in the category tree is left to application code.
