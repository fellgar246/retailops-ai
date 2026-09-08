"""Status transitions and derived review attributes."""

from decimal import Decimal

import pytest

from retailops_api.review.cases import (
    ReviewPriority,
    ReviewStatus,
    ReviewValidationError,
    all_transition_pairs,
    can_transition,
    derive_priority,
    parse_correction,
    require_reason,
    risk_from_severity,
)
from retailops_api.review.types import RiskLevel


def test_the_transition_matrix_is_complete() -> None:
    pairs = all_transition_pairs()
    assert len(pairs) == len(ReviewStatus) ** 2
    allowed = {(source, target) for source, target, ok in pairs if ok}
    assert allowed == {
        (ReviewStatus.open, ReviewStatus.in_review),
        (ReviewStatus.open, ReviewStatus.cancelled),
        (ReviewStatus.in_review, ReviewStatus.approved),
        (ReviewStatus.in_review, ReviewStatus.rejected),
        (ReviewStatus.in_review, ReviewStatus.corrected),
        (ReviewStatus.in_review, ReviewStatus.cancelled),
    }


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (ReviewStatus.approved, ReviewStatus.open),
        (ReviewStatus.rejected, ReviewStatus.in_review),
        (ReviewStatus.corrected, ReviewStatus.approved),
        (ReviewStatus.cancelled, ReviewStatus.open),
        (ReviewStatus.open, ReviewStatus.approved),
    ],
)
def test_terminal_and_skip_ahead_moves_are_rejected(
    source: ReviewStatus, target: ReviewStatus
) -> None:
    assert can_transition(source, target) is False


def test_priority_escalates_with_risk_and_money() -> None:
    assert derive_priority(RiskLevel.low, Decimal("0")) is ReviewPriority.low
    assert derive_priority(RiskLevel.medium, Decimal("0")) is ReviewPriority.medium
    assert derive_priority(RiskLevel.high, Decimal("0")) is ReviewPriority.high
    assert derive_priority(RiskLevel.low, Decimal("150")) is ReviewPriority.high
    assert derive_priority(RiskLevel.high, Decimal("150")) is ReviewPriority.urgent
    assert derive_priority(RiskLevel.low, Decimal("2000")) is ReviewPriority.urgent


def test_risk_follows_source_severity() -> None:
    assert risk_from_severity("error") is RiskLevel.high
    assert risk_from_severity("warning") is RiskLevel.medium
    assert risk_from_severity("info") is RiskLevel.low


def test_correction_keeps_structured_values() -> None:
    payload = parse_correction(
        {"suggested_value": "BEV-WATER", "fields": {"category": "BEV-WATER"}}
    )
    assert payload["suggested_value"] == "BEV-WATER"
    assert payload["fields"]["category"] == "BEV-WATER"


def test_empty_or_unknown_correction_is_rejected() -> None:
    with pytest.raises(ReviewValidationError):
        parse_correction({})
    with pytest.raises(ReviewValidationError, match="unknown"):
        parse_correction({"invented": "x"})


def test_reason_must_be_present() -> None:
    with pytest.raises(ReviewValidationError):
        require_reason("")
