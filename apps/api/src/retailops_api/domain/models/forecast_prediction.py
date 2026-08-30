from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import Base, CreatedAtMixin, IdMixin, IdType

if TYPE_CHECKING:
    from retailops_api.domain.models.forecast_run import ForecastRun


class ForecastPrediction(IdMixin, CreatedAtMixin, Base):
    """One predicted week for one store and category, belonging to a run.

    Entity identity uses business codes rather than catalog foreign keys so a
    run can be stored from a portable dataset without resolving surrogate ids.
    ``actual`` is filled when the week is already observed (a backtest) and
    left empty when the week has not happened yet.

    Predictions are owned by their run: deleting the run removes them.
    """

    __tablename__ = "forecast_predictions"
    __table_args__ = (
        UniqueConstraint(
            "forecast_run_id",
            "store_code",
            "category_code",
            "period_start",
            name="uq_forecast_predictions_run_entity_week",
        ),
        CheckConstraint("step >= 1", name="step_positive"),
        CheckConstraint("predicted >= 0", name="predicted_non_negative"),
        CheckConstraint("actual IS NULL OR actual >= 0", name="actual_non_negative"),
    )

    forecast_run_id: Mapped[int] = mapped_column(
        IdType,
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_code: Mapped[str] = mapped_column(String(50), nullable=False)
    category_code: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted: Mapped[float] = mapped_column(Float, nullable=False)
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)

    run: Mapped[ForecastRun] = relationship(back_populates="predictions")

    def __repr__(self) -> str:
        return (
            f"ForecastPrediction(run_id={self.forecast_run_id!r}, "
            f"store_code={self.store_code!r}, category_code={self.category_code!r}, "
            f"period_start={self.period_start!r})"
        )
