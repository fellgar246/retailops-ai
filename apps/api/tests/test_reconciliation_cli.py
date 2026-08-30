from retailops_api.procurement.cli import main
from retailops_api.procurement.types import ReconciliationError, ReconciliationScope


def test_cli_requires_an_invoice_or_a_purchase_order() -> None:
    code = main(["--supplier", "SUP-BEVCO"])

    assert code == 1


def test_scope_without_a_document_is_rejected() -> None:
    try:
        ReconciliationScope(supplier_code="SUP-BEVCO")
    except ReconciliationError as error:
        assert "purchase order" in str(error)
    else:
        raise AssertionError("expected ReconciliationError")
