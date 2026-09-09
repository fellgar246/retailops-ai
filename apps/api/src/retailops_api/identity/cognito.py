"""Hosted identity provider adapter.

Validates tokens issued by an external OpenID Connect provider against its
published signing keys. Signature, issuer, audience and expiry are all checked;
an unverified token is never accepted. Group claims are mapped onto the
application role model.

The key source is injected so the verifier can be exercised without network
access. The default source reads the provider's JWKS document over HTTPS and
caches it, refreshing at most once per interval when an unknown key id appears.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from retailops_api.identity.types import (
    ExpiredTokenError,
    IdentityConfigError,
    InvalidTokenError,
    Principal,
    parse_roles,
    truncate_display_name,
)

ALGORITHMS = ["RS256"]
GROUPS_CLAIM = "cognito:groups"
DEFAULT_REFRESH_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 5.0

#: Returns the provider's JWKS document.
KeySource = Callable[[], dict[str, Any]]


def https_key_source(jwks_uri: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> KeySource:
    if not jwks_uri.lower().startswith("https://"):
        raise IdentityConfigError("the signing key document must be served over HTTPS")

    def fetch() -> dict[str, Any]:
        request = urllib.request.Request(jwks_uri, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise InvalidTokenError("signing key document is malformed")
        return payload

    return fetch


class CognitoIdentityVerifier:
    """Validates hosted provider tokens against cached signing keys."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        key_source: KeySource,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
    ) -> None:
        if not issuer.strip():
            raise IdentityConfigError("an identity provider issuer is required")
        if not audience.strip():
            raise IdentityConfigError("an identity provider audience is required")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._key_source = key_source
        self._refresh_seconds = refresh_seconds
        self._keys: dict[str, Any] = {}
        self._fetched_at: datetime | None = None
        self._lock = threading.Lock()

    @property
    def provider_id(self) -> str:
        return "cognito"

    def verify(self, token: str) -> Principal:
        key_id = self._key_id(token)
        key = self._signing_key(key_id)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "iss"]},
            )
        except jwt.ExpiredSignatureError as error:
            raise ExpiredTokenError("token has expired") from error
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError("token is not valid") from error

        # An access token from the same pool carries a different use; only an
        # identity token describes the person.
        token_use = claims.get("token_use")
        if token_use is not None and token_use != "id":
            raise InvalidTokenError("token is not an identity token")

        subject = str(claims.get("sub", ""))
        # A pool that signs people in by email generates an opaque internal
        # username, so it ranks below the email as something a human reads.
        name = (
            claims.get("name") or claims.get("email") or claims.get("cognito:username") or subject
        )
        email = claims.get("email")
        return Principal(
            subject=subject,
            display_name=truncate_display_name(str(name)),
            email=str(email) if email else None,
            roles=parse_roles(claims.get(GROUPS_CLAIM)),
        )

    def _key_id(self, token: str) -> str:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise InvalidTokenError("token header is not readable") from error
        key_id = header.get("kid")
        if not key_id:
            raise InvalidTokenError("token does not name a signing key")
        if header.get("alg") not in ALGORITHMS:
            raise InvalidTokenError("token uses an unsupported signing algorithm")
        return str(key_id)

    def _signing_key(self, key_id: str) -> Any:
        key = self._cached_key(key_id)
        if key is not None:
            return key
        self._refresh()
        key = self._cached_key(key_id)
        if key is None:
            raise InvalidTokenError("token was signed by an unknown key")
        return key

    def _cached_key(self, key_id: str) -> Any:
        with self._lock:
            return self._keys.get(key_id)

    def _refresh(self) -> None:
        with self._lock:
            now = datetime.now(UTC)
            if self._fetched_at is not None:
                age = now - self._fetched_at
                if age < timedelta(seconds=self._refresh_seconds):
                    # Refusing to refetch bounds the load a stream of tokens
                    # naming unknown keys can put on the provider.
                    return
            document = self._key_source()
            keys: dict[str, Any] = {}
            for entry in document.get("keys", []):
                if not isinstance(entry, dict):
                    continue
                key_id = entry.get("kid")
                if not key_id:
                    continue
                keys[str(key_id)] = jwt.PyJWK(entry).key
            self._keys = keys
            self._fetched_at = now
