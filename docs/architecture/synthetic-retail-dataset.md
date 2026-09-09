# Synthetic Retail Dataset

- **Scope:** Portable catalog and daily-sales files, generation and ingestion
- **Decisions:** [ADR-003](../adr/ADR-003-synthetic-data-and-ingestion.md)

A dataset is a directory of CSV files that use business codes, not database
surrogate ids. The same files can be inspected, checksummed, and ingested
more than once.

Regenerate the development dataset and load it:

```bash
make synthetic
```

That writes `data/synthetic/`, validates it, and upserts the catalog and
sales history into the configured database. The command is safe to re-run.

## Files

| File | Natural key |
|---|---|
| `categories.csv` | `code` |
| `products.csv` | `sku` |
| `suppliers.csv` | `code` |
| `supplier_products.csv` | `(supplier_code, product_sku)` |
| `stores.csv` | `code` |
| `daily_sales.csv` | `(store_code, product_sku, business_date)` |
| `calendar.csv` | `business_date` |
| `manifest.json` | SHA-256 checksum and row counts |

`calendar.csv` is feature metadata for modelling (weekends, month boundaries,
Christmas, New Year, Buen Fin, configurable holidays). It is not a database
table.

## Formats

| Kind | Rule |
|---|---|
| Dates | ISO-8601 calendar days, `YYYY-MM-DD`. No time, no timezone. |
| Money (`cost`, `unit_price`, `discount_amount`) | Decimal, exactly four places, `.` as the point, no thousands separator. |
| Integers | Whole numbers: quantities, case packs, lead times. |
| Booleans | `true` / `false` |
| Absent optionals | Empty field |
| Identifiers | Verbatim, case-sensitive |

`unit_price` is the per-unit price charged that day. `discount_amount` is the
per-unit promotional discount (zero when not on promotion). `stock_on_hand` is
closing units after the day's sales.

## Identifier shapes

| Field | Pattern |
|---|---|
| category `code` | `^[A-Z][A-Z0-9-]{0,49}$` |
| product `sku` | `^SKU-[0-9]{4,}$` |
| supplier `code` | `^SUP-[A-Z0-9]+$` |
| store `code` | `^ST-[0-9]{3,}$` |
| `ean` (when present) | 8 to 14 digits |

## Columns

**categories:** `code`, `name`, `parent_code`, `active`

**products:** `sku`, `name`, `description`, `ean`, `category_code`, `active`

**suppliers:** `code`, `name`, `tax_id`, `active`

**supplier_products:** `supplier_code`, `product_sku`, `supplier_sku`, `cost`,
`case_pack`, `minimum_order_quantity`, `lead_time_days`, `active`

**stores:** `code`, `name`, `region`, `store_type`, `active`

**daily_sales:** `store_code`, `product_sku`, `business_date`, `units_sold`,
`unit_price`, `discount_amount`, `promotion`, `stock_on_hand`

**calendar:** `business_date`, `weekday`, `weekday_name`, `is_weekend`,
`is_month_start`, `is_month_end`, `is_mid_month`, `is_christmas`,
`is_new_year`, `is_buen_fin`, `is_holiday`, `demand_multiplier`

Required fields must be present. `parent_code`, `description`, `ean`,
`tax_id` and `supplier_sku` may be empty. Money and quantities must be
non-negative; `case_pack` must be greater than zero.

## Generator

Typed configuration (`GeneratorConfig`) covers seed, date range, store /
product / supplier / category counts, promotion and stockout probabilities,
and extra holidays. Named scales:

| Preset | Intent |
|---|---|
| `tiny` | Fast tests (2 stores, 8 products, 21 days) |
| `development` | Local year of history (default for `make synthetic`) |
| `benchmark` | Two-year, larger-catalog run |

The same seed and remaining fields always produce the same catalog, the same
sales, and the same checksum. Catalog draws and sales draws use separate
streams, so changing the date range does not reshuffle the catalog.

Demand combines product popularity, category and store effects, weekday and
seasonal curves, calendar events, promotional lift, price jitter and noise.
Stock censors sales: a stocked-out day can show zero units sold even when
unconstrained demand was positive.

## Ingestion

Catalog rows upsert by business code inside one caller-owned transaction. A
broken reference raises and the caller rolls the whole catalog write back.

Sales rows resolve codes in bulk and upsert on
`(store_id, product_id, business_date)`. A key that already exists is counted
as a duplicate and its measures are replaced. Invalid rows are rejected with
an actionable message; they do not abort the accepted rows. Writes use the
bulk upsert helper, not one ORM insert per row.

Each run emits a report with source, run id, start and end, rows read /
accepted / rejected, duplicate count and validation errors
(`data/synthetic/ingestion_report.json`).

## Where the code lives

| Concern | Path |
|---|---|
| Row types, formats, identifier patterns | `apps/api/src/retailops_api/dataset/contract.py` |
| Validation | `apps/api/src/retailops_api/dataset/validate.py` |
| CSV snapshot and checksum | `apps/api/src/retailops_api/dataset/snapshot.py` |
| Generator config and presets | `apps/api/src/retailops_api/synthetic/config.py` |
| Catalog, calendar, demand | `apps/api/src/retailops_api/synthetic/` |
| Catalog and sales ingestion, CLI | `apps/api/src/retailops_api/ingestion/` |
| Weekly demand frame built from these files | `apps/api/src/retailops_api/forecasting/` |
