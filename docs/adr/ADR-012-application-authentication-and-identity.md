# ADR-012 — Application Authentication and Verified Identity

- **Status:** Accepted
- **Date:** 2026-09-07
- **Scope:** Authentication, role authorization, verified identity in the audit trail, edge request limits
- **Supersedes in part:** the explicit-local-reviewer clause of [ADR-009](ADR-009-human-review-audit-feedback.md)

## Context

The human-review backend was built with the reviewer's name supplied by
the caller. That was an accepted local-phase trade-off: the workflow, the
audit log and the feedback export could all be exercised without an
identity provider.

It does not survive contact with a deployed environment. Every endpoint
was reachable without a credential, and anyone could approve a supplier
invoice under another person's name, which makes the audit log unusable
as evidence. The interface stored a free-text reviewer name in browser
storage and defaulted it to a placeholder.

## Decision

### Identity is an adapter contract, like storage and review

`IdentityVerifier` turns a bearer token into a `Principal`. Two
implementations satisfy it: one signs and validates development tokens
with a local key, one validates tokens issued by a Cognito user pool
against its published signing keys. Business logic imports neither an
AWS SDK nor a provider concept.

Selection is an explicit setting. It is never inferred from the AWS
feature flags: cloud storage or a hosted reviewer must not imply hosted
identity. Each branch validates its own configuration and raises rather
than falling through to another provider, so a misconfigured deployment
fails loudly instead of quietly accepting a development key.

### Amazon Cognito is the hosted provider

It is managed entirely through Terraform, which keeps the identity
perimeter in the same flow as the rest of the infrastructure; its groups
map directly onto the role model; and it makes the load balancer's native
authentication action available when a runtime is deployed. Its free
monthly active users cover this platform's handful of operators
indefinitely.

Auth0 and Clerk offer a better developer experience but introduce a
non-AWS vendor. A self-hosted directory would need a container and a
database of its own. Hand-rolled password handling was rejected outright.

The pool uses authorization code with PKCE, no implicit grant, no client
secret in the browser, and administrator-created accounts only.

### The local provider keeps development free of the cloud

Authentication must never require AWS. The local verifier signs its own
tokens so the pipeline, the demo and the test suite run with no external
provider and no cost. It is not a deployment option.

### Two roles

`viewer` may read. `reviewer` may read and decide. Finer permissions are
not modelled because the domain does not yet distinguish them.

### Identity comes from the token, and audit records the subject

The reviewer field is gone from every request body. Review cases,
decisions and audit events store the immutable subject alongside the
display name; only the subject is trusted, and the display name never
drives authorization.

Records written before authentication existed keep a null subject. They
are not backfilled: a synthesised identifier would look genuine and
would misrepresent what actually happened. The interface reports whether
an actor was verified.

An operator acting through the command line has no provider behind them.
Those actions stay auditable under a display name and are recorded as
unverified rather than being blocked or disguised.

### The browser never holds a credential

The web application exchanges the authorization code server-side and
keeps the session in an `httpOnly` cookie. Page scripts call this
application's own origin; a server-side route attaches the credential and
forwards to the API.

This also removes the build-time API origin from the browser bundle, so
one image runs in every environment and the image no longer has to be
built after the load balancer exists.

### Limits sit at the boundary

Request bodies are bounded before a handler runs, and review transitions
are rate limited per credential. The existing upload ceiling stays where
it is; it applies after the payload has been accepted, which is too late
to be the only check.

### Deployed instances do not publish their schema

Interactive documentation describes every endpoint and shape. It is
served in development environments only.

## Consequences

- The API cannot be used without a credential, including by the
  operations interface. Health checks stay open so a load balancer can
  probe the service.
- The test suite no longer reads a developer's environment file. Adapter
  selection had been depending on it, which is why three tests failed on
  a clean clone.
- Two review records may share a display name and remain distinct,
  because identity is the subject.
- Cognito's hosted sign-in is dated and hard to restyle. That is accepted
  in exchange for keeping identity inside Terraform.
- Rate limiting counts inside one process. Several workers therefore
  allow proportionally more traffic; the intent is to stop one credential
  from hammering the decision endpoints, not to enforce a global quota.
- TLS, a custom domain and the deployment itself remain outstanding.
  Until they exist, the hosted flow is exercised against the `dev` pool
  from a developer machine.
