"""Development identity provider: minting, validating and rejecting tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from retailops_api.identity.local import LocalIdentityVerifier
from retailops_api.identity.types import (
    ExpiredTokenError,
    IdentityConfigError,
    InvalidTokenError,
    Role,
)
from tests.conftest import TEST_IDENTITY_SECRET


def test_a_short_secret_is_refused() -> None:
    with pytest.raises(IdentityConfigError):
        LocalIdentityVerifier("too-short")
    with pytest.raises(IdentityConfigError):
        LocalIdentityVerifier("   ")


def test_round_trip_preserves_identity_and_roles(verifier: LocalIdentityVerifier) -> None:
    token = verifier.issue(
        "u-1", display_name="Ana", email="ana@example.test", roles={Role.reviewer}
    )
    principal = verifier.verify(token)

    assert principal.subject == "u-1"
    assert principal.display_name == "Ana"
    assert principal.email == "ana@example.test"
    assert principal.roles == frozenset({Role.reviewer})
    assert principal.may_decide is True
    assert principal.audit_subject == "u-1"


def test_a_viewer_may_not_decide(verifier: LocalIdentityVerifier) -> None:
    principal = verifier.verify(verifier.issue("u-2", roles={Role.viewer}))

    assert principal.may_decide is False


def test_unknown_groups_are_ignored(verifier: LocalIdentityVerifier) -> None:
    token = verifier.issue("u-3", roles={Role.viewer})
    principal = verifier.verify(token)

    assert principal.roles == frozenset({Role.viewer})


def test_a_token_signed_with_another_key_is_rejected(
    verifier: LocalIdentityVerifier,
) -> None:
    other = LocalIdentityVerifier("a-completely-different-identity-secret")
    with pytest.raises(InvalidTokenError):
        verifier.verify(other.issue("u-4"))


def test_a_tampered_token_is_rejected(verifier: LocalIdentityVerifier) -> None:
    token = verifier.issue("u-5", roles={Role.viewer})
    header, payload, signature = token.split(".")
    with pytest.raises(InvalidTokenError):
        verifier.verify(f"{header}.{payload}x.{signature}")


def test_an_expired_token_is_rejected() -> None:
    verifier = LocalIdentityVerifier(TEST_IDENTITY_SECRET, ttl_seconds=60)
    issued = datetime.now(UTC) - timedelta(hours=2)
    with pytest.raises(ExpiredTokenError):
        verifier.verify(verifier.issue("u-6", issued_at=issued))


def test_garbage_is_rejected(verifier: LocalIdentityVerifier) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify("not-a-token")
