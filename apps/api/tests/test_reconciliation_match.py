from decimal import Decimal

from retailops_api.procurement.match import match_invoice_line, match_receipt_line
from retailops_api.procurement.types import (
    AMBIGUOUS_LINE,
    UNMATCHED_LINE,
    GoodsReceiptLineView,
    IdentityIndex,
    PurchaseOrderLineView,
    PurchaseOrderView,
    SupplierInvoiceLineView,
)

COST = Decimal("7.4500")
ZERO = Decimal("0")


def _order(*lines: PurchaseOrderLineView) -> PurchaseOrderView:
    return PurchaseOrderView(
        id=1,
        number="PO-1001",
        supplier_id=10,
        store_id=20,
        currency="MXN",
        status="open",
        lines=lines,
    )


def _po_line(id_: int, product_id: int, line_number: int = 1) -> PurchaseOrderLineView:
    return PurchaseOrderLineView(
        id=id_,
        line_number=line_number,
        product_id=product_id,
        ordered_quantity=10,
        unit_cost=COST,
        tax_rate=ZERO,
        tax_amount=ZERO,
        line_total=COST * 10,
    )


def _invoice_line(
    *,
    product_id: int | None = None,
    supplier_sku: str | None = None,
    ean: str | None = None,
    line_number: int = 1,
) -> SupplierInvoiceLineView:
    return SupplierInvoiceLineView(
        id=50,
        supplier_invoice_id=5,
        line_number=line_number,
        product_id=product_id,
        supplier_sku=supplier_sku,
        ean=ean,
        invoiced_quantity=10,
        unit_cost=COST,
        tax_rate=ZERO,
        tax_amount=ZERO,
        line_total=COST * 10,
    )


def test_exact_product_identity_matches_the_only_po_line() -> None:
    order = _order(_po_line(1, 100))
    matched = match_invoice_line(_invoice_line(product_id=100), order, IdentityIndex({}, {}))

    assert matched.po_line is not None
    assert matched.po_line.id == 1
    assert matched.issue_code is None


def test_supplier_sku_maps_to_the_catalog_product() -> None:
    order = _order(_po_line(1, 100))
    index = IdentityIndex({}, {"BC-COLA": (100,)})
    matched = match_invoice_line(_invoice_line(supplier_sku="BC-COLA"), order, index)

    assert matched.po_line is not None
    assert matched.product_id == 100


def test_ean_maps_when_the_barcode_is_unique() -> None:
    order = _order(_po_line(1, 100))
    index = IdentityIndex({"7501000110018": 100}, {})
    matched = match_invoice_line(_invoice_line(ean="7501000110018"), order, index)

    assert matched.po_line is not None
    assert matched.product_id == 100


def test_disagreeing_strategies_are_ambiguous() -> None:
    order = _order(_po_line(1, 100), _po_line(2, 200, line_number=2))
    index = IdentityIndex({"7501000110018": 200}, {})
    matched = match_invoice_line(_invoice_line(product_id=100, ean="7501000110018"), order, index)

    assert matched.po_line is None
    assert matched.issue_code == AMBIGUOUS_LINE


def test_two_po_lines_for_the_same_product_are_ambiguous() -> None:
    order = _order(_po_line(1, 100), _po_line(2, 100, line_number=2))
    matched = match_invoice_line(_invoice_line(product_id=100), order, IdentityIndex({}, {}))

    assert matched.issue_code == AMBIGUOUS_LINE


def test_unknown_identity_is_unmatched() -> None:
    order = _order(_po_line(1, 100))
    matched = match_invoice_line(_invoice_line(supplier_sku="NOPE"), order, IdentityIndex({}, {}))

    assert matched.issue_code == UNMATCHED_LINE


def test_receipt_line_uses_the_cited_po_line() -> None:
    po_line = _po_line(7, 100)
    order = _order(po_line)
    receipt_line = GoodsReceiptLineView(
        id=3,
        goods_receipt_id=2,
        line_number=1,
        product_id=100,
        purchase_order_line_id=7,
        received_quantity=4,
    )

    matched = match_receipt_line(receipt_line, order)

    assert matched.po_line is not None
    assert matched.po_line.id == 7


def test_supplier_sku_mapped_to_two_products_is_ambiguous() -> None:
    order = _order(_po_line(1, 100))
    index = IdentityIndex({}, {"DUP": (100, 200)})
    matched = match_invoice_line(_invoice_line(supplier_sku="DUP"), order, index)

    assert matched.issue_code == AMBIGUOUS_LINE
