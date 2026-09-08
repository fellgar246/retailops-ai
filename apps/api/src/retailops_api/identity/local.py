"""Development identity provider.

Signs and validates short-lived tokens with a local symmetric key so the whole
application, its tests and the demo pipeline run with no external provider and
no cost. It is never a substitute for a hosted provider in a deployed
environment: the key lives in configuration and anyone holding it can mint a
token for any subject.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from retailops_api.identity.types import (
    DEFAULT_TOKEN_TTL_SECONDS,
    ExpiredTokenError,
    IdentityConfigError,
    InvalidTokenError,
    Principal,
    Role,
    parse_roles,
    truncate_display_name,
)

ALGORITHM = "HS256"
#: Shorter keys weaken HMAC-SHA256 below its design strength.
MIN_SECRET_LENGTH = 32
ISSUER = "retailops-local"
AUDIENCE = "retailops-api"


class LocalIdentityVerifier:
    """Validates tokens minted by :meth:`issue`."""

    def __init__(self, secret: str, *, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> None:
        if not secret.strip():
            raise IdentityConfigError("a local identity secret is required")
        if len(secret) < MIN_SECRET_LENGTH:
            raise IdentityConfigError(
                f"the local identity secret must be at least {MIN_SECRET_LENGTH} characters"
            )
        self._secret = secret
        self._ttl_seconds = ttl_seconds

    @property
    def provider_id(self) -> str:
        return "local"

    def issue(
        self,
        subject: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
        roles: frozenset[Role] | set[Role] | None = None,
        issued_at: datetime | None = None,
    ) -> str:
        """Mint a development token. Not available to deployed environments."""

        now = issued_at or datetime.now(UTC)
        granted = frozenset(roles) if roles else frozenset({Role.viewer})
        claims: dict[str, Any] = {
            "sub": subject,
            "name": display_name or subject,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._ttl_seconds)).timestamp()),
            "roles": sorted(role.value for role in granted),
        }
        if email:
            claims["email"] = email
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM)

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as error:
            raise ExpiredTokenError("token has expired") from error
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError("token is not valid") from error

        subject = str(claims.get("sub", ""))
        name = claims.get("name") or subject
        email = claims.get("email")
        return Principal(
            subject=subject,
            display_name=truncate_display_name(str(name)),
            email=str(email) if email else None,
            roles=parse_roles(claims.get("roles")),
        )
