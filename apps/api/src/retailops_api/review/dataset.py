"""Versioned evaluation cases (JSON / JSONL) with structured expected fields."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from retailops_api.review.mock import MockFixture
from retailops_api.review.prompts import prompt_for
from retailops_api.review.types import (
    CategorySuggestionInput,
    MockBehavior,
    RecommendedAction,
    ReconciliationExplanationInput,
    ReviewEligibility,
    ReviewPayload,
    ReviewType,
    RiskLevel,
    SupplierSummaryInput,
)

DATASET_VERSION = "v001"
CASES_FILE = "cases.jsonl"
MANIFEST_FILE = "manifest.json"
CaseKind = Literal["review", "routing"]
ExpectedOutcome = Literal["ok", "schema_error", "provider_error"]


@dataclass(frozen=True)
class ExpectedAttributes:
    suggested_value: str | None = None
    recommended_action: RecommendedAction | None = None
    risk: RiskLevel | None = None
    eligibility: ReviewEligibility | None = None
    classification: str | None = None
    outcome: ExpectedOutcome = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggested_value": self.suggested_value,
            "recommended_action": (
                self.recommended_action.value if self.recommended_action else None
            ),
            "risk": self.risk.value if self.risk else None,
            "eligibility": self.eligibility.value if self.eligibility else None,
            "classification": self.classification,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ExpectedAttributes:
        action = raw.get("recommended_action")
        risk = raw.get("risk")
        eligibility = raw.get("eligibility")
        outcome = raw.get("outcome", "ok")
        if outcome not in ("ok", "schema_error", "provider_error"):
            raise ValueError(f"unknown expected outcome {outcome!r}")
        return cls(
            suggested_value=_optional_str(raw.get("suggested_value")),
            recommended_action=RecommendedAction(action) if action else None,
            risk=RiskLevel(risk) if risk else None,
            eligibility=ReviewEligibility(eligibility) if eligibility else None,
            classification=_optional_str(raw.get("classification")),
            outcome=outcome,
        )


@dataclass(frozen=True)
class RoutingCaseInput:
    confidence: float
    risk: RiskLevel
    recommended_action: RecommendedAction
    financial_impact: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "risk": self.risk.value,
            "recommended_action": self.recommended_action.value,
            "financial_impact": str(self.financial_impact),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RoutingCaseInput:
        return cls(
            confidence=float(raw["confidence"]),
            risk=RiskLevel(str(raw["risk"])),
            recommended_action=RecommendedAction(str(raw["recommended_action"])),
            financial_impact=Decimal(str(raw.get("financial_impact", "0"))),
        )


@dataclass(frozen=True)
class EvalCase:
    id: str
    kind: CaseKind
    dataset_version: str
    review_type: ReviewType | None
    payload: ReviewPayload | None
    routing_input: RoutingCaseInput | None
    expected: ExpectedAttributes
    mock: MockFixture | None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "dataset_version": self.dataset_version,
            "review_type": self.review_type.value if self.review_type else None,
            "input": _input_dict(self),
            "expected": self.expected.to_dict(),
        }
        if self.mock is not None:
            body["mock"] = {
                "behavior": self.mock.behavior.value,
                "output": self.mock.output,
            }
        return body


@dataclass(frozen=True)
class EvaluationDataset:
    version: str
    cases: tuple[EvalCase, ...]
    path: Path

    def fixtures(self) -> dict[str, MockFixture]:
        return {
            case.id: case.mock
            for case in self.cases
            if case.mock is not None and case.kind == "review"
        }


def packaged_dataset_dir(version: str = DATASET_VERSION) -> Path:
    return Path(__file__).resolve().parent / "datasets" / version


def load_dataset(path: Path | None = None, *, version: str = DATASET_VERSION) -> EvaluationDataset:
    directory = path or packaged_dataset_dir(version)
    if directory.is_file():
        cases_path = directory
        directory = directory.parent
    else:
        cases_path = directory / CASES_FILE
    raw_cases = _read_cases(cases_path)
    cases = tuple(case_from_dict(item, default_version=version) for item in raw_cases)
    return EvaluationDataset(version=version, cases=cases, path=directory)


def case_from_dict(raw: dict[str, Any], *, default_version: str = DATASET_VERSION) -> EvalCase:
    kind = raw.get("kind", "review")
    if kind not in ("review", "routing"):
        raise ValueError(f"unknown case kind {kind!r}")
    review_type_raw = raw.get("review_type")
    review_type = ReviewType(review_type_raw) if review_type_raw else None
    payload = None
    routing_input = None
    incoming = raw.get("input") or {}
    if kind == "routing":
        routing_input = RoutingCaseInput.from_dict(incoming)
    elif review_type is None:
        raise ValueError(f"case {raw.get('id')!r} is missing review_type")
    else:
        payload = payload_from_dict(review_type, incoming)
    mock_raw = raw.get("mock")
    mock = None
    if isinstance(mock_raw, dict):
        behavior = MockBehavior(str(mock_raw.get("behavior", MockBehavior.normal.value)))
        output = mock_raw.get("output")
        mock = MockFixture(
            behavior=behavior,
            output=output if isinstance(output, dict) else None,
        )
    return EvalCase(
        id=str(raw["id"]),
        kind=kind,
        dataset_version=str(raw.get("dataset_version", default_version)),
        review_type=review_type,
        payload=payload,
        routing_input=routing_input,
        expected=ExpectedAttributes.from_dict(raw.get("expected") or {}),
        mock=mock,
    )


def payload_from_dict(review_type: ReviewType, raw: dict[str, Any]) -> ReviewPayload:
    if review_type is ReviewType.category_suggestion:
        return CategorySuggestionInput.from_dict(raw)
    if review_type is ReviewType.supplier_summary:
        return SupplierSummaryInput.from_dict(raw)
    return ReconciliationExplanationInput.from_dict(raw)


def write_cases(cases: Sequence[EvalCase], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CASES_FILE
    lines = [json.dumps(case.to_dict(), sort_keys=True) for case in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {
        "version": cases[0].dataset_version if cases else DATASET_VERSION,
        "case_count": len(cases),
        "output_schema_version": prompt_for(ReviewType.category_suggestion).output_schema_version,
        "kinds": sorted({case.kind for case in cases}),
    }
    (directory / MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _read_cases(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json" and not path.name.endswith(".jsonl"):
        loaded = json.loads(text)
        if isinstance(loaded, list):
            return [item for item in loaded if isinstance(item, dict)]
        raise ValueError("JSON dataset must be an array of cases")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        loaded = json.loads(stripped)
        if isinstance(loaded, dict):
            rows.append(loaded)
    return rows


def _input_dict(case: EvalCase) -> dict[str, Any]:
    if case.routing_input is not None:
        return case.routing_input.to_dict()
    if case.payload is not None:
        return case.payload.to_dict()
    return {}


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
