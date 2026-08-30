from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from retailops_api.db.base import Base, CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from retailops_api.domain.models.forecast_prediction import ForecastPrediction


class ForecastRun(IdMixin, CreatedAtMixin, Base):
    """One forecast produced by one model at one origin.

    A run is an evaluation fact: the same cutoff and model can be written again
    as a new run, but an existing run is not edited. That is why the row carries
    no ``updated_at`` and no ``active`` flag.

    ``cutoff`` is inclusive: the ISO week containing it is the last week of
    history the model was allowed to read. ``horizon`` is the number of weeks
    ahead that were requested. ``run_metadata`` holds model knobs, backtest
    grouping and any other notes that do not deserve their own column.
    """

    __tablename__ = "forecast_runs"
    __table_args__ = (CheckConstraint("horizon >= 1", name="horizon_positive"),)

    model_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cutoff: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    problem_id: Mapped[str] = mapped_column(String(100), nullable=False)
    run_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    predictions: Mapped[list[ForecastPrediction]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"ForecastRun(id={self.id!r}, model_id={self.model_id!r}, cutoff={self.cutoff!r})"
