"""Champion / challenger comparison and the promotion policy.

A candidate is never promoted on a single metric. Both gates must pass:

Accuracy gate
    Candidate WAPE must be strictly lower than every baseline and, when a
    champion exists, strictly lower than the champion.

Secondary gate
    Candidate MAE must be less than or equal to the champion MAE when a
    champion exists. When there is no champion, candidate MAE must be less
    than or equal to the lowest baseline MAE.

Bias is recorded for diagnosis and is not a promotion gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retailops_api.forecasting.backtest import attach_actuals
from retailops_api.forecasting.frame import ForecastFrame
from retailops_api.forecasting.metrics import ForecastMetrics, score_points
from retailops_api.forecasting.models import Forecaster, ForecastPoint, default_baselines


@dataclass(frozen=True)
class PromotionPolicy:
    """Named metrics and the rule that both must be considered."""

    primary: str = "wape"
    secondary: str = "mae"

    def to_dict(self) -> dict[str, str]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "rule": (
                "Promote only when WAPE is strictly below every baseline and the "
                "champion (if any), and MAE is at most the champion MAE or, with "
                "no champion, at most the best baseline MAE. A single-metric win "
                "is not enough."
            ),
        }


DEFAULT_PROMOTION_POLICY = PromotionPolicy()


@dataclass(frozen=True)
class ModelScore:
    model_id: str
    metrics: ForecastMetrics
    predictions: tuple[ForecastPoint, ...]


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    reasons: tuple[str, ...]
    policy: PromotionPolicy
    candidate: ModelScore
    comparisons: tuple[ModelScore, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "promote": self.promote,
            "reasons": list(self.reasons),
            "policy": self.policy.to_dict(),
            "candidate": {
                "model_id": self.candidate.model_id,
                "metrics": self.candidate.metrics.to_dict(),
            },
            "comparisons": [
                {"model_id": score.model_id, "metrics": score.metrics.to_dict()}
                for score in self.comparisons
            ],
        }


def score_origin(
    frame: ForecastFrame,
    model: Forecaster,
    *,
    cutoff: date,
    horizon: int,
) -> ModelScore:
    """Predict from ``cutoff`` and score against actuals that exist on the frame."""
    points = attach_actuals(model.predict(frame, cutoff=cutoff, horizon=horizon), frame)
    return ModelScore(model_id=model.model_id, metrics=score_points(points), predictions=points)


def evaluate_promotion(
    candidate: ModelScore,
    comparisons: tuple[ModelScore, ...],
    *,
    policy: PromotionPolicy = DEFAULT_PROMOTION_POLICY,
    champion_id: str | None = None,
) -> PromotionDecision:
    """Apply the two-gate policy. ``comparisons`` must include every baseline."""
    reasons: list[str] = []
    promote = True
    candidate_primary = getattr(candidate.metrics, policy.primary)
    candidate_secondary = getattr(candidate.metrics, policy.secondary)

    if not comparisons:
        promote = False
        reasons.append("no comparison models were scored")

    for score in comparisons:
        other_primary = getattr(score.metrics, policy.primary)
        if candidate_primary >= other_primary:
            promote = False
            reasons.append(
                f"{policy.primary} {candidate_primary:.6f} is not strictly below "
                f"{score.model_id} ({other_primary:.6f})"
            )

    champion = next((score for score in comparisons if score.model_id == champion_id), None)
    if champion is not None:
        champion_secondary = getattr(champion.metrics, policy.secondary)
        if candidate_secondary > champion_secondary:
            promote = False
            reasons.append(
                f"{policy.secondary} {candidate_secondary:.6f} is worse than "
                f"champion {champion.model_id} ({champion_secondary:.6f})"
            )
    elif comparisons:
        best_secondary = min(getattr(score.metrics, policy.secondary) for score in comparisons)
        if candidate_secondary > best_secondary:
            promote = False
            reasons.append(
                f"{policy.secondary} {candidate_secondary:.6f} is worse than the "
                f"best baseline ({best_secondary:.6f})"
            )

    if promote:
        reasons.append(
            f"both gates passed: {policy.primary} beat every comparison and "
            f"{policy.secondary} did not regress"
        )
    return PromotionDecision(
        promote=promote,
        reasons=tuple(reasons),
        policy=policy,
        candidate=candidate,
        comparisons=comparisons,
    )


def compare_against_baselines(
    frame: ForecastFrame,
    candidate: Forecaster,
    *,
    cutoff: date,
    horizon: int,
    seasonal_lag: int,
    window: int,
    champion: Forecaster | None = None,
    policy: PromotionPolicy = DEFAULT_PROMOTION_POLICY,
) -> PromotionDecision:
    """Score the candidate, the three baselines and an optional champion at one origin."""
    candidate_score = score_origin(frame, candidate, cutoff=cutoff, horizon=horizon)
    scores = [
        score_origin(frame, model, cutoff=cutoff, horizon=horizon)
        for model in default_baselines(seasonal_lag=seasonal_lag, window=window)
    ]
    champion_id = None
    if champion is not None:
        champion_score = score_origin(frame, champion, cutoff=cutoff, horizon=horizon)
        scores.append(champion_score)
        champion_id = champion_score.model_id
    return evaluate_promotion(
        candidate_score,
        tuple(scores),
        policy=policy,
        champion_id=champion_id,
    )
