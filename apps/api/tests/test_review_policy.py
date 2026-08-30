from retailops_api.review.policy import (
    ALLOWED_USES,
    DEFAULT_USAGE_POLICY,
    FORBIDDEN_USES,
)


def test_policy_lists_are_closed_and_disjoint() -> None:
    assert "classify_uncertain_category_text" in ALLOWED_USES
    assert "summarize_findings" in ALLOWED_USES
    assert "explain_reconciliation_exceptions" in ALLOWED_USES
    assert "suggest_next_actions" in ALLOWED_USES
    assert "assign_semantic_confidence" in ALLOWED_USES
    assert "deterministic_financial_arithmetic" in FORBIDDEN_USES
    assert "silent_source_mutation" in FORBIDDEN_USES
    assert "bypass_validation" in FORBIDDEN_USES
    assert "auto_resolve_high_risk_without_policy" in FORBIDDEN_USES
    assert set(ALLOWED_USES).isdisjoint(FORBIDDEN_USES)


def test_usage_policy_answers_allows_and_forbids() -> None:
    assert DEFAULT_USAGE_POLICY.allows("summarize_findings")
    assert DEFAULT_USAGE_POLICY.forbids("silent_source_mutation")
    assert not DEFAULT_USAGE_POLICY.allows("silent_source_mutation")
