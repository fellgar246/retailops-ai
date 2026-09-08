"""Hosted identity provider: signature, issuer, audience and group mapping."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from retailops_api.identity.cognito import CognitoIdentityVerifier, https_key_source
from retailops_api.identity.types import (
    ExpiredTokenError,
    IdentityConfigError,
    InvalidTokenError,
    Role,
)

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example"
AUDIENCE = "example-client-id"
KEY_ID = "key-1"


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwks(signing_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    public.update({"kid": KEY_ID, "use": "sig", "alg": "RS256"})
    return {"keys": [public]}


def _token(key: rsa.RSAPrivateKey, **overrides: Any) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": "cognito-subject-1",
        "name": "Ana Operator",
        "email": "ana@example.test",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "token_use": "id",
        "cognito:groups": ["reviewer"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KEY_ID})


@pytest.fixture
def verifier(jwks: dict[str, Any]) -> CognitoIdentityVerifier:
    return CognitoIdentityVerifier(issuer=ISSUER, audience=AUDIENCE, key_source=lambda: jwks)


def test_configuration_must_name_an_issuer_and_audience(jwks: dict[str, Any]) -> None:
    with pytest.raises(IdentityConfigError):
        CognitoIdentityVerifier(issuer="", audience=AUDIENCE, key_source=lambda: jwks)
    with pytest.raises(IdentityConfigError):
        CognitoIdentityVerifier(issuer=ISSUER, audience="", key_source=lambda: jwks)


def test_a_valid_token_maps_onto_a_principal(
    verifier: CognitoIdentityVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    principal = verifier.verify(_token(signing_key))

    assert principal.subject == "cognito-subject-1"
    assert principal.display_name == "Ana Operator"
    assert principal.email == "ana@example.test"
    assert principal.roles == frozenset({Role.reviewer})
    assert principal.audit_subject == "cognito-subject-1"


def test_groups_we_do_not_model_are_ignored(
    verifier: CognitoIdentityVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    token = _token(signing_key, **{"cognito:groups": ["viewer", "billing-admin"]})

    assert verifier.verify(token).roles == frozenset({Role.viewer})


def test_a_token_from_another_issuer_is_rejected(
    verifier: CognitoIdentityVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_token(signing_key, iss="https://example.test/other"))


def test_a_token_for_another_audience_is_rejected(
    verifier: CognitoIdentityVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_token(signing_key, aud="another-client"))


def test_an_access_token_is_not_accepted_as_an_identity(
    verifier: CognitoIdentityVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    with pytest.raises(InvalidTokenError):
        verifier.verify(_token(signing_key, token_use="access"))


def test_an_expired_token_is_rejected(
    verifier: CognitoIdentityVerifier, signing_key: rsa.RSAPrivateKey
) -> None:
    past = datetime.now(UTC) - timedelta(hours=2)
    token = _token(
        signing_key,
        iat=int(past.timestamp()),
        exp=int((past + timedelta(minutes=5)).timestamp()),
    )
    with pytest.raises(ExpiredTokenError):
        verifier.verify(token)


def test_a_token_signed_by_an_unknown_key_is_rejected(
    verifier: CognitoIdentityVerifier,
) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(InvalidTokenError):
        verifier.verify(_token(other))


def test_an_unsigned_token_is_rejected(verifier: CognitoIdentityVerifier) -> None:
    token = jwt.encode({"sub": "x", "iss": ISSUER, "aud": AUDIENCE}, key="", algorithm="none")
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


def test_keys_are_fetched_once_for_repeated_tokens(
    signing_key: rsa.RSAPrivateKey, jwks: dict[str, Any]
) -> None:
    calls = 0

    def source() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return jwks

    verifier = CognitoIdentityVerifier(issuer=ISSUER, audience=AUDIENCE, key_source=source)
    for _ in range(3):
        verifier.verify(_token(signing_key))

    assert calls == 1


def test_the_key_document_must_be_served_over_a_secure_transport() -> None:
    with pytest.raises(IdentityConfigError):
        https_key_source("http://cognito-idp.us-east-1.amazonaws.com/keys")
