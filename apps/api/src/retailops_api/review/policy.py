"""What a reviewer may and may not do.

The reviewer is an optional semantic layer on top of deterministic work.
Arithmetic, validation and source records stay with ordinary code.
"""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_USES = (
    "classify_uncertain_category_text",
    "summarize_findings",
    "explain_reconciliation_exceptions",
    "suggest_next_actions",
    "assign_semantic_confidence",
)

FORBIDDEN_USES = (
    "deterministic_financial_arithmetic",
    "silent_source_mutation",
    "bypass_validation",
    "auto_resolve_high_risk_without_policy",
)


@dataclass(frozen=True)
class AIUsagePolicy:
    """Closed lists so tests and docs share one definition."""

    allowed: tuple[str, ...] = ALLOWED_USES
    forbidden: tuple[str, ...] = FORBIDDEN_USES

    def allows(self, use: str) -> bool:
        return use in self.allowed

    def forbids(self, use: str) -> bool:
        return use in self.forbidden


DEFAULT_USAGE_POLICY = AIUsagePolicy()
