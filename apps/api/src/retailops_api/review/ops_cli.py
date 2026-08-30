"""Operate the local human-review queue.

    make reviews
    make review-feedback

Or, from ``apps/api``:

    uv run retailops-review queue
    uv run retailops-review start 1 --reviewer alice
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.db.session import get_session_factory
from retailops_api.domain.models.review import ReviewCase
from retailops_api.review.cases import (
    ReviewFilters,
    ReviewPriority,
    ReviewStatus,
    ReviewSubjectType,
    ReviewWorkflowError,
)
from retailops_api.review.feedback import project_feedback, write_feedback
from retailops_api.review.metrics import collect_metrics
from retailops_api.review.paths import default_review_output
from retailops_api.review.persist import (
    case_view,
    create_review_case,
    load_exception,
    load_finding,
)
from retailops_api.review.queue import list_cases
from retailops_api.review.types import RiskLevel
from retailops_api.review.workflow import (
    approve_review,
    assign_review,
    cancel_review,
    correct_review,
    reject_review,
    start_review,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        handler: Callable[[argparse.Namespace], int] = args.handler
        return handler(args)
    except ReviewWorkflowError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-review",
        description="Create, list and decide human review cases.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Open a case for a finding or exception.")
    create.add_argument("--finding", type=int, help="document_findings.id")
    create.add_argument("--exception", type=int, help="reconciliation_exceptions.id")
    create.add_argument("--priority", choices=[item.value for item in ReviewPriority])
    create.set_defaults(handler=_cmd_create)

    queue = sub.add_parser("queue", help="List cases with filters and stable order.")
    queue.add_argument("--status", action="append", choices=[item.value for item in ReviewStatus])
    queue.add_argument(
        "--priority", action="append", choices=[item.value for item in ReviewPriority]
    )
    queue.add_argument(
        "--subject-type", action="append", choices=[item.value for item in ReviewSubjectType]
    )
    queue.add_argument("--risk", action="append", choices=[item.value for item in RiskLevel])
    queue.add_argument("--supplier-id", type=int)
    queue.add_argument("--limit", type=int, default=50)
    queue.add_argument("--offset", type=int, default=0)
    queue.set_defaults(handler=_cmd_queue)

    start = sub.add_parser("start", help="Move an open case into active review.")
    start.add_argument("case_id", type=int)
    start.add_argument("--reviewer", required=True)
    start.set_defaults(handler=_cmd_start)

    assign = sub.add_parser("assign", help="Set or change the reviewer on an active case.")
    assign.add_argument("case_id", type=int)
    assign.add_argument("--reviewer", required=True)
    assign.set_defaults(handler=_cmd_assign)

    approve = sub.add_parser("approve", help="Accept the recommendation.")
    approve.add_argument("case_id", type=int)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--comment")
    approve.set_defaults(handler=_cmd_approve)

    reject = sub.add_parser("reject", help="Reject the recommendation. A reason is required.")
    reject.add_argument("case_id", type=int)
    reject.add_argument("--reviewer", required=True)
    reject.add_argument("--reason", required=True)
    reject.add_argument("--comment")
    reject.set_defaults(handler=_cmd_reject)

    correct = sub.add_parser("correct", help="Close with structured human corrections.")
    correct.add_argument("case_id", type=int)
    correct.add_argument("--reviewer", required=True)
    correct.add_argument("--suggested-value")
    correct.add_argument("--summary")
    correct.add_argument("--comment")
    correct.set_defaults(handler=_cmd_correct)

    cancel = sub.add_parser("cancel", help="Cancel an open or active case.")
    cancel.add_argument("case_id", type=int)
    cancel.add_argument("--reviewer", required=True)
    cancel.add_argument("--comment")
    cancel.set_defaults(handler=_cmd_cancel)

    metrics = sub.add_parser("metrics", help="Print queue rates and open-case count.")
    metrics.set_defaults(handler=_cmd_metrics)

    feedback = sub.add_parser("feedback", help="Export decided cases as evaluation rows.")
    feedback.add_argument(
        "--output",
        type=Path,
        help="Directory for feedback.jsonl (default: <repo>/data/reviews).",
    )
    feedback.set_defaults(handler=_cmd_feedback)

    return parser.parse_args(argv)


def _cmd_create(args: argparse.Namespace) -> int:
    if (args.finding is None) == (args.exception is None):
        print("error: pass exactly one of --finding or --exception", file=sys.stderr)
        return 1
    priority = None if args.priority is None else ReviewPriority(args.priority)
    with get_session_factory()() as session:
        finding = None if args.finding is None else load_finding(session, args.finding)
        exception = None if args.exception is None else load_exception(session, args.exception)
        case = create_review_case(session, finding=finding, exception=exception, priority=priority)
        session.commit()
        print(_format_case(case_view(case).to_dict()))
    return 0


def _cmd_queue(args: argparse.Namespace) -> int:
    filters = ReviewFilters(
        statuses=tuple(ReviewStatus(item) for item in (args.status or ())),
        priorities=tuple(ReviewPriority(item) for item in (args.priority or ())),
        subject_types=tuple(ReviewSubjectType(item) for item in (args.subject_type or ())),
        supplier_id=args.supplier_id,
        risks=tuple(RiskLevel(item) for item in (args.risk or ())),
    )
    with get_session_factory()() as session:
        page = list_cases(session, filters, limit=args.limit, offset=args.offset)
    print(f"total={page.total}  limit={page.limit}  offset={page.offset}")
    for item in page.items:
        print(_format_case(item.to_dict()))
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    return _mutate(lambda session: start_review(session, args.case_id, reviewer=args.reviewer))


def _cmd_assign(args: argparse.Namespace) -> int:
    return _mutate(lambda session: assign_review(session, args.case_id, reviewer=args.reviewer))


def _cmd_approve(args: argparse.Namespace) -> int:
    return _mutate(
        lambda session: approve_review(
            session, args.case_id, reviewer=args.reviewer, comment=args.comment
        )
    )


def _cmd_reject(args: argparse.Namespace) -> int:
    return _mutate(
        lambda session: reject_review(
            session,
            args.case_id,
            reviewer=args.reviewer,
            reason=args.reason,
            comment=args.comment,
        )
    )


def _cmd_correct(args: argparse.Namespace) -> int:
    correction = {}
    if args.suggested_value is not None:
        correction["suggested_value"] = args.suggested_value
    if args.summary is not None:
        correction["summary"] = args.summary
    return _mutate(
        lambda session: correct_review(
            session,
            args.case_id,
            reviewer=args.reviewer,
            correction=correction,
            comment=args.comment,
        )
    )


def _cmd_cancel(args: argparse.Namespace) -> int:
    return _mutate(
        lambda session: cancel_review(
            session, args.case_id, reviewer=args.reviewer, comment=args.comment
        )
    )


def _cmd_metrics(_args: argparse.Namespace) -> int:
    with get_session_factory()() as session:
        metrics = collect_metrics(session)
    print(json.dumps(metrics.to_dict(), indent=2))
    return 0


def _cmd_feedback(args: argparse.Namespace) -> int:
    output = args.output or default_review_output()
    with get_session_factory()() as session:
        rows = project_feedback(session)
    path = write_feedback(rows, output)
    print(f"wrote {path}  rows={len(rows)}")
    return 0


def _mutate(action: Callable[[Session], ReviewCase]) -> int:
    with get_session_factory()() as session:
        case = action(session)
        session.commit()
        print(_format_case(case_view(case).to_dict()))
    return 0


def _format_case(row: dict[str, object]) -> str:
    return (
        f"id={row['id']}  status={row['status']}  priority={row['priority']}  "
        f"risk={row['risk']}  subject={row['subject_type']}  reviewer={row['reviewer']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
