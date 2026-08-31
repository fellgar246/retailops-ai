"""Wide wall-clock limits for the local generate / ingest / train / match path."""

from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.demo.performance import measure_local_steps


def test_local_steps_stay_within_wide_limits(session: Session, tmp_path: Path) -> None:
    timings = measure_local_steps(session, tmp_path / "synthetic", work=tmp_path / "work")
    assert {step.name for step in timings} == {
        "generate",
        "ingest",
        "train",
        "reconcile",
        "review_queue",
    }
    slow = [
        f"{step.name} {step.seconds:.2f}s > {step.limit:.1f}s" for step in timings if not step.ok
    ]
    assert slow == []
