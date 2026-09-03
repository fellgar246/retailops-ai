"""Run any ``AIReviewer`` against the same versioned cases and write a report."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from retailops_api.review.contract import AIReviewer, SafeReview, build_request, review_safely
from retailops_api.review.dataset import EvalCase, EvaluationDataset
from retailops_api.review.routing import RoutingDecision, route, route_from_attributes
from retailops_api.review.schemas import ReviewResult
from retailops_api.review.types import ReviewType
from retailops_api.review.usage import ProviderUsage

EVALUATION_JSON = "evaluation.json"
EVALUATION_MARKDOWN = "evaluation.md"


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    kind: str
    schema_valid: bool
    provider_failed: bool
    confidence_present: bool
    classification_match: bool | None
    action_match: bool | None
    expected_outcome: str
    observed_outcome: str
    routing: RoutingDecision | None
    result: ReviewResult | None
    error: str | None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "kind": self.kind,
            "schema_valid": self.schema_valid,
            "provider_failed": self.provider_failed,
            "confidence_present": self.confidence_present,
            "classification_match": self.classification_match,
            "action_match": self.action_match,
            "expected_outcome": self.expected_outcome,
            "observed_outcome": self.observed_outcome,
            "routing": self.routing.to_dict() if self.routing else None,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass(frozen=True)
class EvaluationMetrics:
    case_count: int
    schema_validity: float
    classification_accuracy: float
    recommended_action_accuracy: float
    confidence_presence: float
    provider_failure_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "schema_validity": schema_validity_round(self.schema_validity),
            "classification_accuracy": schema_validity_round(self.classification_accuracy),
            "recommended_action_accuracy": schema_validity_round(self.recommended_action_accuracy),
            "confidence_presence": schema_validity_round(self.confidence_presence),
            "provider_failure_rate": schema_validity_round(self.provider_failure_rate),
        }


@dataclass(frozen=True)
class EvaluationReport:
    dataset_version: str
    reviewer: str
    generated_at: datetime
    metrics: EvaluationMetrics
    scores: tuple[CaseScore, ...]
    model_id: str | None = None
    region: str | None = None
    prompt_versions: tuple[str, ...] = ()
    mean_latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "reviewer": self.reviewer,
            "generated_at": self.generated_at.isoformat(),
            "model_id": self.model_id,
            "region": self.region,
            "prompt_versions": list(self.prompt_versions),
            "mean_latency_ms": self.mean_latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "metrics": self.metrics.to_dict(),
            "cases": [score.to_dict() for score in self.scores],
        }


def evaluate(
    reviewer: AIReviewer,
    dataset: EvaluationDataset,
    *,
    generated_at: datetime | None = None,
    region: str | None = None,
    model_id: str | None = None,
) -> EvaluationReport:
    scores = tuple(score_case(reviewer, case) for case in dataset.cases)
    latencies = [item.latency_ms for item in scores if item.latency_ms is not None]
    prompt_versions = tuple(
        sorted(
            {
                score.result.prompt_version
                for score in scores
                if score.result is not None and score.result.prompt_version
            }
        )
    )
    return EvaluationReport(
        dataset_version=dataset.version,
        reviewer=reviewer.provider_id,
        generated_at=generated_at or datetime.now(UTC),
        metrics=summarize(scores),
        scores=scores,
        model_id=model_id or _reviewer_model(reviewer),
        region=region,
        prompt_versions=prompt_versions,
        mean_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else None,
        input_tokens=_sum_optional(score.input_tokens for score in scores),
        output_tokens=_sum_optional(score.output_tokens for score in scores),
    )


def score_case(reviewer: AIReviewer, case: EvalCase) -> CaseScore:
    if case.kind == "routing":
        return _score_routing(case)
    return _score_review(reviewer, case)


def summarize(scores: Sequence[CaseScore]) -> EvaluationMetrics:
    review_scores = [item for item in scores if item.kind == "review"]
    schema_denom = [item for item in review_scores if item.expected_outcome == "ok"]
    classification = [
        item.classification_match for item in scores if item.classification_match is not None
    ]
    actions = [item.action_match for item in scores if item.action_match is not None]
    confidence = [item for item in review_scores if item.expected_outcome == "ok"]
    return EvaluationMetrics(
        case_count=len(scores),
        schema_validity=_ratio(
            sum(1 for item in schema_denom if item.schema_valid),
            len(schema_denom),
        ),
        classification_accuracy=_ratio(
            sum(1 for item in classification if item), len(classification)
        ),
        recommended_action_accuracy=_ratio(sum(1 for item in actions if item), len(actions)),
        confidence_presence=_ratio(
            sum(1 for item in confidence if item.confidence_present),
            len(confidence),
        ),
        provider_failure_rate=_ratio(
            sum(1 for item in review_scores if item.provider_failed),
            len(review_scores),
        ),
    )


def stamped_output_dir(base: Path, report: EvaluationReport) -> Path:
    stamp = report.generated_at.strftime("%Y%m%dT%H%M%SZ")
    return base / f"{report.reviewer}-{report.dataset_version}-{stamp}"


def write_evaluation(report: EvaluationReport, directory: Path, *, stamp: bool = False) -> Path:
    target = stamped_output_dir(directory, report) if stamp else directory
    target.mkdir(parents=True, exist_ok=True)
    (target / EVALUATION_JSON).write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (target / EVALUATION_MARKDOWN).write_text(render_markdown(report), encoding="utf-8")
    return target


def write_comparison(
    mock_report: EvaluationReport,
    live_report: EvaluationReport,
    directory: Path,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": mock_report.dataset_version,
        "mock": mock_report.to_dict(),
        "live": live_report.to_dict(),
    }
    path = directory / "comparison.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mock_m = mock_report.metrics
    live_m = live_report.metrics
    markdown = [
        "# Provider comparison",
        "",
        f"- **Dataset:** `{mock_report.dataset_version}`",
        f"- **Mock:** `{mock_report.reviewer}`",
        f"- **Live:** `{live_report.reviewer}` model `{live_report.model_id or '—'}`",
        f"- **Region:** `{live_report.region or '—'}`",
        "",
        "| Metric | Mock | Live |",
        "| --- | ---: | ---: |",
        _metric_row("Schema validity", mock_m.schema_validity, live_m.schema_validity),
        _metric_row(
            "Classification", mock_m.classification_accuracy, live_m.classification_accuracy
        ),
        _metric_row(
            "Action", mock_m.recommended_action_accuracy, live_m.recommended_action_accuracy
        ),
        _metric_row("Confidence", mock_m.confidence_presence, live_m.confidence_presence),
        _metric_row("Provider failure", mock_m.provider_failure_rate, live_m.provider_failure_rate),
        "",
    ]
    (directory / "comparison.md").write_text("\n".join(markdown), encoding="utf-8")
    return path


def render_markdown(report: EvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# AI review evaluation",
        "",
        f"- **Dataset:** `{report.dataset_version}`",
        f"- **Reviewer:** `{report.reviewer}`",
        f"- **Generated:** {report.generated_at.isoformat()}",
        f"- **Model:** `{report.model_id or '—'}`",
        f"- **Region:** `{report.region or '—'}`",
        f"- **Prompt versions:** {_prompt_version_label(report)}",
        f"- **Cases:** {metrics.case_count}",
        f"- **Mean latency (ms):** {_latency_label(report)}",
        f"- **Tokens in/out:** {report.input_tokens or 0}/{report.output_tokens or 0}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Schema validity | {metrics.schema_validity:.4f} |",
        f"| Classification accuracy | {metrics.classification_accuracy:.4f} |",
        f"| Recommended-action accuracy | {metrics.recommended_action_accuracy:.4f} |",
        f"| Confidence presence | {metrics.confidence_presence:.4f} |",
        f"| Provider failure rate | {metrics.provider_failure_rate:.4f} |",
        "",
        "## Cases",
        "",
        "| Id | Kind | Outcome | Schema | Classification | Action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for score in report.scores:
        lines.append(
            f"| `{score.case_id}` | {score.kind} | {score.observed_outcome} | "
            f"{_flag(score.schema_valid)} | {_optional_flag(score.classification_match)} | "
            f"{_optional_flag(score.action_match)} |"
        )
    lines.append("")
    return "\n".join(lines)


def schema_validity_round(value: float) -> float:
    return round(value, 4)


def _score_review(reviewer: AIReviewer, case: EvalCase) -> CaseScore:
    if case.review_type is None or case.payload is None:
        raise ValueError(f"review case {case.id!r} is missing a payload")
    request = build_request(case.review_type, case.payload, case_id=case.id)
    started = time.perf_counter()
    attempt = review_safely(reviewer, request)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    usage = _reviewer_usage(reviewer)
    observed = _observed_outcome(attempt)
    result = attempt.result
    routing = None
    if result is not None:
        impact = _impact(case)
        routing = route(result, financial_impact=impact, error=None)
    classification_match = _classification_match(case, result, routing)
    action_match = None
    if case.expected.recommended_action is not None and result is not None:
        action_match = result.recommended_action is case.expected.recommended_action
    return CaseScore(
        case_id=case.id,
        kind=case.kind,
        schema_valid=attempt.schema_valid,
        provider_failed=attempt.provider_failed,
        confidence_present=result is not None,
        classification_match=classification_match,
        action_match=action_match,
        expected_outcome=case.expected.outcome,
        observed_outcome=observed,
        routing=routing,
        result=result,
        error=str(attempt.error) if attempt.error else None,
        latency_ms=latency_ms,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
    )


def _score_routing(case: EvalCase) -> CaseScore:
    if case.routing_input is None:
        raise ValueError(f"routing case {case.id!r} is missing input")
    incoming = case.routing_input
    decision = route_from_attributes(
        confidence=incoming.confidence,
        risk=incoming.risk,
        recommended_action=incoming.recommended_action,
        financial_impact=incoming.financial_impact,
    )
    classification_match = None
    if case.expected.eligibility is not None:
        classification_match = decision.eligibility is case.expected.eligibility
    action_match = None
    if case.expected.recommended_action is not None:
        action_match = incoming.recommended_action is case.expected.recommended_action
    return CaseScore(
        case_id=case.id,
        kind=case.kind,
        schema_valid=True,
        provider_failed=False,
        confidence_present=True,
        classification_match=classification_match,
        action_match=action_match,
        expected_outcome=case.expected.outcome,
        observed_outcome="ok",
        routing=decision,
        result=None,
        error=None,
    )


def _observed_outcome(attempt: SafeReview) -> str:
    if attempt.provider_failed:
        return "provider_error"
    if attempt.schema_failed or not attempt.schema_valid:
        return "schema_error"
    return "ok"


def _classification_match(
    case: EvalCase,
    result: ReviewResult | None,
    routing: RoutingDecision | None,
) -> bool | None:
    expected = case.expected
    if expected.eligibility is not None and routing is not None:
        return routing.eligibility is expected.eligibility
    label = expected.classification or expected.suggested_value
    if label is None:
        return None
    if result is None:
        return False
    if case.review_type is ReviewType.category_suggestion:
        return result.suggested_value == label
    if expected.suggested_value is not None:
        return result.suggested_value == expected.suggested_value
    return result.suggested_value == label or result.risk.value == label


def _impact(case: EvalCase) -> Decimal:
    payload = case.payload
    if payload is not None and hasattr(payload, "financial_impact"):
        return payload.financial_impact
    return Decimal("0")


def _metric_row(name: str, mock_value: float, live_value: float) -> str:
    return f"| {name} | {mock_value:.4f} | {live_value:.4f} |"


def _prompt_version_label(report: EvaluationReport) -> str:
    if not report.prompt_versions:
        return "—"
    return ", ".join(f"`{item}`" for item in report.prompt_versions)


def _latency_label(report: EvaluationReport) -> str:
    if report.mean_latency_ms is None:
        return "—"
    return str(report.mean_latency_ms)


def _reviewer_usage(reviewer: AIReviewer) -> ProviderUsage | None:
    usage = getattr(reviewer, "last_usage", None)
    return usage if isinstance(usage, ProviderUsage) else None


def _reviewer_model(reviewer: AIReviewer) -> str | None:
    model = getattr(reviewer, "model_id", None)
    return str(model) if model else None


def _sum_optional(values: Iterable[int | None]) -> int | None:
    found = [int(item) for item in values if item is not None]
    if not found:
        return None
    return sum(found)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _flag(value: bool) -> str:
    return "yes" if value else "no"


def _optional_flag(value: bool | None) -> str:
    if value is None:
        return "—"
    return _flag(value)
