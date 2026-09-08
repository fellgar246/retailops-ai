from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from retailops_api.core.adapters import identity_verifier_for
from retailops_api.core.config import Settings, get_settings
from retailops_api.core.ratelimit import FixedWindowLimiter, RateLimitError
from retailops_api.db.session import get_session_factory
from retailops_api.identity.contract import IdentityVerifier
from retailops_api.identity.types import IdentityConfigError, IdentityError, Principal

#: Sent with every rejection so a client knows which scheme to use.
AUTH_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_app_settings(request: Request) -> Settings:
    """Configuration this application was built with.

    Reading it from the application rather than the process keeps an injected
    configuration authoritative, which is what tests and the demo rely on.
    """

    return getattr(request.app.state, "settings", None) or get_settings()


def get_identity_verifier(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> IdentityVerifier:
    """Build the verifier once per application.

    Construction reads configuration and, for a hosted provider, prepares a key
    source; neither should happen per request.
    """

    verifier = getattr(request.app.state, "identity_verifier", None)
    if verifier is None:
        verifier = identity_verifier_for(settings)
        request.app.state.identity_verifier = verifier
    return verifier


def get_decision_limiter(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> FixedWindowLimiter:
    limiter = getattr(request.app.state, "decision_limiter", None)
    if limiter is None:
        limiter = FixedWindowLimiter(
            limit=settings.decision_rate_limit,
            window_seconds=settings.decision_rate_window_seconds,
        )
        request.app.state.decision_limiter = limiter
    return limiter


def bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="authentication required",
            headers=AUTH_CHALLENGE,
        )
    return token.strip()


def get_principal(
    token: Annotated[str, Depends(bearer_token)],
    verifier: Annotated[IdentityVerifier, Depends(get_identity_verifier)],
) -> Principal:
    """Resolve the caller, or reject the request.

    A configuration failure is the operator's problem, not the caller's, so it
    is reported as a server error rather than as a rejected credential.
    """

    try:
        return verifier.verify(token)
    except IdentityConfigError as error:
        raise HTTPException(status_code=500, detail="identity is not configured") from error
    except IdentityError as error:
        raise HTTPException(
            status_code=401,
            detail="authentication failed",
            headers=AUTH_CHALLENGE,
        ) from error


def require_reviewer_role(
    principal: Annotated[Principal, Depends(get_principal)],
) -> Principal:
    """Only a reviewer may act on a case."""

    if not principal.may_decide:
        raise HTTPException(status_code=403, detail="the reviewer role is required")
    return principal


def limit_decisions(
    principal: Annotated[Principal, Depends(require_reviewer_role)],
    limiter: Annotated[FixedWindowLimiter, Depends(get_decision_limiter)],
) -> Principal:
    """Bound how fast one credential can close review cases."""

    try:
        limiter.check(principal.subject)
    except RateLimitError as error:
        raise HTTPException(
            status_code=429,
            detail="too many decisions; retry shortly",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
ReviewerPrincipal = Annotated[Principal, Depends(require_reviewer_role)]
DecidingPrincipal = Annotated[Principal, Depends(limit_decisions)]

__all__ = [
    "AUTH_CHALLENGE",
    "CurrentPrincipal",
    "DecidingPrincipal",
    "ReviewerPrincipal",
    "bearer_token",
    "get_app_settings",
    "get_db",
    "get_decision_limiter",
    "get_identity_verifier",
    "get_principal",
    "limit_decisions",
    "require_reviewer_role",
]
