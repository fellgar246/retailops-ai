"""forecast evaluation

Creates forecast_runs and forecast_predictions so a walk-forward evaluation
can be stored: one run per model and origin, one prediction row per store,
category and forecast week. Predictions are owned by their run
(ON DELETE CASCADE). Entity identity uses store and category business codes.

See docs/adr/ADR-004-forecast-evaluation.md for the modelling decisions.

Revision ID: c7e4f19a2b08
Revises: 024162a4b5f3
Create Date: 2026-08-30 13:32:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c7e4f19a2b08"
down_revision: str | None = "024162a4b5f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_runs",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cutoff", sa.Date(), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("problem_id", sa.String(length=100), nullable=False),
        sa.Column("run_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("horizon >= 1", name=op.f("ck_forecast_runs_horizon_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_runs")),
    )
    op.create_index(op.f("ix_forecast_runs_cutoff"), "forecast_runs", ["cutoff"], unique=False)
    op.create_index(op.f("ix_forecast_runs_model_id"), "forecast_runs", ["model_id"], unique=False)
    op.create_table(
        "forecast_predictions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "forecast_run_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("store_code", sa.String(length=50), nullable=False),
        sa.Column("category_code", sa.String(length=50), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("predicted", sa.Float(), nullable=False),
        sa.Column("actual", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actual IS NULL OR actual >= 0",
            name=op.f("ck_forecast_predictions_actual_non_negative"),
        ),
        sa.CheckConstraint(
            "predicted >= 0", name=op.f("ck_forecast_predictions_predicted_non_negative")
        ),
        sa.CheckConstraint("step >= 1", name=op.f("ck_forecast_predictions_step_positive")),
        sa.ForeignKeyConstraint(
            ["forecast_run_id"],
            ["forecast_runs.id"],
            name=op.f("fk_forecast_predictions_forecast_run_id_forecast_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_predictions")),
        sa.UniqueConstraint(
            "forecast_run_id",
            "store_code",
            "category_code",
            "period_start",
            name=op.f("uq_forecast_predictions_run_entity_week"),
        ),
    )
    op.create_index(
        op.f("ix_forecast_predictions_forecast_run_id"),
        "forecast_predictions",
        ["forecast_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_forecast_predictions_period_start"),
        "forecast_predictions",
        ["period_start"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_forecast_predictions_period_start"), table_name="forecast_predictions")
    op.drop_index(
        op.f("ix_forecast_predictions_forecast_run_id"), table_name="forecast_predictions"
    )
    op.drop_table("forecast_predictions")
    op.drop_index(op.f("ix_forecast_runs_model_id"), table_name="forecast_runs")
    op.drop_index(op.f("ix_forecast_runs_cutoff"), table_name="forecast_runs")
    op.drop_table("forecast_runs")
