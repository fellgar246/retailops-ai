"""Identity primitives shared by every verifier implementation.

The authenticated principal is a domain value. It carries a stable subject
identifier used for audit, a display name used only for presentation, and the
roles that authorize an action. Nothing here depends on a vendor SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

#: Audit and persistence store the subject in a 128-character column.
MAX_SUBJECT_LENGTH = 128
MAX_DISPLAY_NAME_LENGTH = 128

#: Lifetime of a development token.
DEFAULT_TOKEN_TTL_SECONDS = 8 * 60 * 60


class Role(StrEnum):
    """What a principal is allowed to do.

    ``viewer`` may read. ``reviewer`` may read and decide review cases.
    """

    viewer = "viewer"
    reviewer = "reviewer"


class IdentityError(Exception):
    """Base class for identity failures."""


class IdentityConfigError(IdentityError):
    """Verifier configuration is missing or inconsistent."""


class InvalidTokenError(IdentityError):
    """The token is malformed, unsigned, wrongly scoped or not trusted."""


class ExpiredTokenError(InvalidTokenError):
    """The token was well formed but is no longer valid."""


@dataclass(frozen=True)
class Principal:
    """An authenticated caller.

    ``subject`` is immutable and is what audit records point at. ``display_name``
    exists for humans reading the interface and must never drive authorization.
    """

    subject: str
    display_name: str
    email: str | None
    roles: frozenset[Role]
    #: False for an operator acting through a local tool, where no identity
    #: provider vouched for the subject. Such actions stay auditable but are
    #: never recorded as verified.
    verified: bool = True

    def __post_init__(self) -> None:
        if not self.subject.strip():
            raise InvalidTokenError("token has no subject")
        if len(self.subject) > MAX_SUBJECT_LENGTH:
            raise InvalidTokenError(f"subject must be at most {MAX_SUBJECT_LENGTH} characters")
        if not self.display_name.strip():
            raise InvalidTokenError("principal has no display name")

    @property
    def audit_subject(self) -> str | None:
        """The identifier audit records may trust, or nothing."""
        return self.subject if self.verified else None

    def has_role(self, role: Role) -> bool:
        return role in self.roles

    @property
    def may_decide(self) -> bool:
        """Only a reviewer may close a review case."""
        return Role.reviewer in self.roles


def parse_roles(values: object) -> frozenset[Role]:
    """Map provider group names onto roles, ignoring groups we do not model."""

    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    roles: set[Role] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            roles.add(Role(value.strip().lower()))
        except ValueError:
            continue
    return frozenset(roles)


def truncate_display_name(value: str) -> str:
    text = value.strip()
    return text[:MAX_DISPLAY_NAME_LENGTH]
