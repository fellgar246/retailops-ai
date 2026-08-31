"""Supplier-sheet bytes used by the local demo dataset."""

from __future__ import annotations

from dataclasses import dataclass

HEADER = (
    "supplier_sku,ean,description,category,cost,vat,case_pack,minimum_order_quantity,lead_time_days"
)


@dataclass(frozen=True)
class DemoSheet:
    filename: str
    supplier_code: str
    body: str


COST_INCREASE = DemoSheet(
    filename="demo-cost-increase.csv",
    supplier_code="SUP-BEVCO",
    body="\n".join(
        [
            HEADER,
            "BC-COLA-355,7501000110018,Cola Classic 355ml Can,BEV-SOFT,9.0000,16,24,2,3",
            "",
        ]
    ),
)

NEW_ITEMS = DemoSheet(
    filename="demo-new-items.csv",
    supplier_code="SUP-BEVCO",
    body="\n".join(
        [
            HEADER,
            "NW-SODA-330,7501999000011,New Cola 330ml,BEV-SOFT,6.5000,16,24,1,5",
            "NW-WATER-500,7501999000028,Spring Water 500ml,BEV-WATER,4.2000,16,12,1,4",
            "",
        ]
    ),
)

MALFORMED = DemoSheet(
    filename="demo-malformed.csv",
    supplier_code="SUP-BEVCO",
    body="\n".join(
        [
            HEADER,
            "NW-SODA-330,7501999000011,New Cola 330ml,BEV-SOFT,not-a-price,16,24,1,5",
            "",
        ]
    ),
)

DEMO_SHEETS: tuple[DemoSheet, ...] = (COST_INCREASE, NEW_ITEMS, MALFORMED)
