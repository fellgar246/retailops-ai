"""Route protection: who may reach an endpoint, and who may decide."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.core.adapters import identity_verifier_for
from retailops_api.core.config import Settings
from retailops_api.identity.cognito import CognitoIdentityVerifier
from retailops_api.identity.local import LocalIdentityVerifier
from retailops_api.identity.types import IdentityConfigError
from retailops_api.main import create_app
from tests.conftest import TEST_IDENTITY_SECRET
from tests.review_support import finding_case

#: Every endpoint a browser reaches. Health checks are deliberately absent.
PROTECTED_PATHS = [
    "/ops/overview",
    "/search",
    "/forecasts",
    "/forecasts/1",
    "/documents",
    "/documents/1",
    "/reconciliations",
    "/reconciliations/1",
    "/exceptions",
    "/reviews",
    "/reviews/1",
    "/reviews/metrics",
    "/reviews/feedback",
    "/reviews/1/audit",
    "/audit",
]

DECISION_PATHS: list[tuple[str, dict[str, object]]] = [
    ("/reviews/1/start", {}),
    ("/reviews/1/assign", {}),
    ("/reviews/1/approve", {}),
    ("/reviews/1/reject", {"reason": "wrong"}),
    ("/reviews/1/correct", {"correction": {"summary": "x"}}),
    ("/reviews/1/cancel", {}),
]


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_every_endpoint_refuses_an_anonymous_caller(
    anonymous_client: TestClient, path: str
) -> None:
    response = anonymous_client.get(path)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", PROTECTED_PATHS)
def test_every_endpoint_refuses_an_unusable_token(app: object, session: Session, path: str) -> None:
    from tests.conftest import _bound_client

    for client in _bound_client(app, session, "clearly-not-a-token"):  # type: ignore[arg-type]
        assert client.get(path).status_code == 401


@pytest.mark.parametrize("path,body", DECISION_PATHS)
def test_a_viewer_may_not_decide(
    viewer_client: TestClient, path: str, body: dict[str, object]
) -> None:
    response = viewer_client.post(path, json=body)

    assert response.status_code == 403
    assert "reviewer" in response.json()["detail"]


def test_rejection_does_not_reveal_whether_a_case_exists(
    viewer_client: TestClient, session: Session
) -> None:
    """A viewer gets the same answer for a real case and an invented one."""

    case = finding_case(session, supplier_code="SUP-SEC-1")

    existing = viewer_client.post(f"/reviews/{case.id}/approve", json={})
    missing = viewer_client.post("/reviews/999999/approve", json={})

    assert existing.status_code == 403
    assert missing.status_code == 403
    assert existing.json() == missing.json()


def test_health_stays_open(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/health").status_code == 200


def test_a_reviewer_reaches_the_queue(api_client: TestClient) -> None:
    assert api_client.get("/reviews").status_code == 200


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


def test_the_local_provider_is_selected_and_validated() -> None:
    settings = Settings(auth_provider="local", auth_local_secret=TEST_IDENTITY_SECRET)

    assert isinstance(identity_verifier_for(settings), LocalIdentityVerifier)


def test_the_local_provider_requires_a_secret() -> None:
    with pytest.raises(IdentityConfigError, match="AUTH_LOCAL_SECRET"):
        identity_verifier_for(Settings(auth_provider="local", auth_local_secret=""))


def test_the_hosted_provider_is_selected_and_validated() -> None:
    settings = Settings(
        auth_provider="cognito",
        cognito_user_pool_id="us-east-1_example",
        cognito_client_id="client-1",
        cognito_region="us-east-1",
    )
    verifier = identity_verifier_for(settings, key_source=lambda: {"keys": []})

    assert isinstance(verifier, CognitoIdentityVerifier)


def test_the_hosted_provider_never_falls_back_to_the_local_one() -> None:
    """A misconfigured deployment must fail, not authenticate against a
    development key."""

    settings = Settings(
        auth_provider="cognito",
        auth_local_secret=TEST_IDENTITY_SECRET,
        cognito_user_pool_id="",
        cognito_client_id="client-1",
    )
    with pytest.raises(IdentityConfigError, match="COGNITO_USER_POOL_ID"):
        identity_verifier_for(settings)


def test_the_hosted_provider_requires_a_client_id() -> None:
    settings = Settings(
        auth_provider="cognito",
        cognito_user_pool_id="us-east-1_example",
        cognito_client_id="",
        cognito_region="us-east-1",
    )
    with pytest.raises(IdentityConfigError, match="COGNITO_CLIENT_ID"):
        identity_verifier_for(settings)


def test_aws_feature_flags_do_not_select_an_identity_provider() -> None:
    """Cloud storage or a hosted reviewer must not imply hosted identity."""

    settings = Settings(
        aws_enabled=True,
        aws_use_bedrock=True,
        auth_provider="local",
        auth_local_secret=TEST_IDENTITY_SECRET,
    )

    assert isinstance(identity_verifier_for(settings), LocalIdentityVerifier)


# --------------------------------------------------------------------------- #
# Surface and limits
# --------------------------------------------------------------------------- #


def test_a_deployed_instance_does_not_publish_its_schema() -> None:
    deployed = create_app(
        Settings(environment="prod", auth_provider="local", auth_local_secret=TEST_IDENTITY_SECRET)
    )
    client = TestClient(deployed)

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_a_developer_instance_publishes_its_schema(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_an_oversized_body_is_refused_before_it_is_read(
    anonymous_client: TestClient,
) -> None:
    """The ceiling applies at the boundary, ahead of authentication."""

    response = anonymous_client.post(
        "/reviews",
        content=b"{}",
        headers={"Content-Length": "99999999", "Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_decisions_are_rate_limited(session: Session, reviewer_token: str) -> None:
    from tests.conftest import _bound_client

    settings = Settings(
        environment="test",
        auth_provider="local",
        auth_local_secret=TEST_IDENTITY_SECRET,
        decision_rate_limit=2,
    )
    app = create_app(settings)
    case = finding_case(session, supplier_code="SUP-SEC-2")

    for client in _bound_client(app, session, reviewer_token):
        first = client.post(f"/reviews/{case.id}/start", json={})
        second = client.post(f"/reviews/{case.id}/start", json={})
        third = client.post(f"/reviews/{case.id}/start", json={})

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert third.headers["retry-after"]
