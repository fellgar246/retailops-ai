"""Versioned prompts. Callers look up a spec; they do not embed prompt text."""

from __future__ import annotations

from dataclasses import dataclass

from retailops_api.review.schemas import OUTPUT_SCHEMA_VERSION
from retailops_api.review.types import PromptError, ReviewType

INPUT_SCHEMA_VERSIONS = {
    ReviewType.category_suggestion: "1",
    ReviewType.supplier_summary: "1",
    ReviewType.reconciliation_explanation: "1",
}


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version: str
    purpose: str
    input_schema_version: str
    output_schema_version: str
    template: str

    def to_dict(self) -> dict[str, str]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "purpose": self.purpose,
            "input_schema_version": self.input_schema_version,
            "output_schema_version": self.output_schema_version,
            "template": self.template,
        }


CATEGORY_SUGGESTION_V1 = PromptSpec(
    prompt_id="supplier.category_suggestion",
    version="1",
    purpose="Classify uncertain category text against known catalog codes.",
    input_schema_version=INPUT_SCHEMA_VERSIONS[ReviewType.category_suggestion],
    output_schema_version=OUTPUT_SCHEMA_VERSION,
    template=(
        "Given submitted category text, an item description and catalog codes, "
        "suggest the best catalog code. Do not invent a code that is not listed. "
        "Do not change costs, quantities or other numeric fields. "
        "Return the structured review result only."
    ),
)

SUPPLIER_SUMMARY_V1 = PromptSpec(
    prompt_id="supplier.summary",
    version="1",
    purpose="Summarize deterministic supplier-sheet findings and recommend a next action.",
    input_schema_version=INPUT_SCHEMA_VERSIONS[ReviewType.supplier_summary],
    output_schema_version=OUTPUT_SCHEMA_VERSION,
    template=(
        "Summarize the supplied deterministic findings. They are the factual "
        "source of truth; do not drop, rewrite or invent findings. "
        "Prioritize errors over warnings over info. Suggest a next action. "
        "Do not mutate source records or recompute money. "
        "Return the structured review result only."
    ),
)

RECONCILIATION_EXPLANATION_V1 = PromptSpec(
    prompt_id="reconciliation.explanation",
    version="1",
    purpose="Explain a reconciliation exception and suggest an operational action.",
    input_schema_version=INPUT_SCHEMA_VERSIONS[ReviewType.reconciliation_explanation],
    output_schema_version=OUTPUT_SCHEMA_VERSION,
    template=(
        "Explain why the supplied exception exists using the expected value, "
        "actual value and financial impact already computed by the match. "
        "Do not recalculate amounts or quantities. Assess operational risk "
        "and suggest an action. Return the structured review result only."
    ),
)

_PROMPTS: dict[tuple[str, str], PromptSpec] = {
    (CATEGORY_SUGGESTION_V1.prompt_id, CATEGORY_SUGGESTION_V1.version): CATEGORY_SUGGESTION_V1,
    (SUPPLIER_SUMMARY_V1.prompt_id, SUPPLIER_SUMMARY_V1.version): SUPPLIER_SUMMARY_V1,
    (
        RECONCILIATION_EXPLANATION_V1.prompt_id,
        RECONCILIATION_EXPLANATION_V1.version,
    ): RECONCILIATION_EXPLANATION_V1,
}

_CURRENT: dict[str, str] = {
    CATEGORY_SUGGESTION_V1.prompt_id: CATEGORY_SUGGESTION_V1.version,
    SUPPLIER_SUMMARY_V1.prompt_id: SUPPLIER_SUMMARY_V1.version,
    RECONCILIATION_EXPLANATION_V1.prompt_id: RECONCILIATION_EXPLANATION_V1.version,
}

PROMPT_FOR_REVIEW_TYPE: dict[ReviewType, PromptSpec] = {
    ReviewType.category_suggestion: CATEGORY_SUGGESTION_V1,
    ReviewType.supplier_summary: SUPPLIER_SUMMARY_V1,
    ReviewType.reconciliation_explanation: RECONCILIATION_EXPLANATION_V1,
}


def get_prompt(prompt_id: str, version: str | None = None) -> PromptSpec:
    chosen = version or _CURRENT.get(prompt_id)
    if chosen is None:
        raise PromptError(f"unknown prompt {prompt_id!r}")
    spec = _PROMPTS.get((prompt_id, chosen))
    if spec is None:
        raise PromptError(f"unknown prompt {prompt_id!r} version {chosen!r}")
    return spec


def list_prompts() -> tuple[PromptSpec, ...]:
    return tuple(sorted(_PROMPTS.values(), key=lambda item: (item.prompt_id, item.version)))


def prompt_for(review_type: ReviewType) -> PromptSpec:
    return PROMPT_FOR_REVIEW_TYPE[review_type]
