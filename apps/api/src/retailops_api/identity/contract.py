"""Provider-neutral identity verification.

A verifier turns a bearer token into a :class:`Principal` or raises. The local
implementation signs its own development tokens; a hosted implementation
validates tokens issued by an external provider. Callers do not change.
"""

from __future__ import annotations

from typing import Protocol

from retailops_api.identity.types import Principal


class IdentityVerifier(Protocol):
    """Token verification. Implementations must not assume a cloud vendor."""

    @property
    def provider_id(self) -> str: ...

    def verify(self, token: str) -> Principal:
        """Return the authenticated principal or raise an identity error."""
        ...
