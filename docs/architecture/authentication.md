# Authentication and identity

How a request becomes an authorized action, and what the audit trail
records about who took it.

## Request path

```text
Browser
        ↓  same-origin call, session cookie
Web application route handler
        ↓  Authorization: Bearer <token>
API
        ↓
IdentityVerifier
        ↓
Principal (subject, display name, roles)
        ↓
Route authorization
        ↓
Review transition
        ↓
Audit event carrying the verified subject
```

The browser never holds a token. It is stored in an `httpOnly` cookie and
attached by a server-side route, which also hides where the API listens.

## The contract

```text
IdentityVerifier

Implementations:
- LocalIdentityVerifier      development tokens signed with a shared key
- CognitoIdentityVerifier    hosted tokens validated against published keys
```

The same shape as document storage and AI review: one contract in the
core, one local implementation, one cloud implementation, selected by
configuration. `Principal` contains no vendor concepts.

Selection is explicit. Each branch validates its own configuration and
raises on failure; none falls back to another provider.

## Roles

| Role | May read | May decide |
|---|---|---|
| `viewer` | yes | no |
| `reviewer` | yes | yes |

Roles arrive as provider groups and are mapped onto the model. Groups the
application does not model are ignored rather than rejected, so an
unrelated group cannot break sign-in.

## Authorization

Every endpoint requires an authenticated principal except the health
checks, which stay open for load-balancer probes. Protection is applied
to the whole router with an explicit allowlist, so a new endpoint is
protected by default rather than by remembering to opt in.

Review transitions additionally require the reviewer role. A viewer
receives an identical refusal whether or not the case exists, so the
response reveals nothing about the data.

## Verified identity

| Column | Holds |
|---|---|
| `review_cases.reviewer` / `reviewer_subject` | Display name / verified subject |
| `review_decisions.reviewer` / `reviewer_subject` | Display name / verified subject |
| `review_audit_events.actor` / `actor_subject` | Display name / verified subject |

The subject is immutable and is the only value trusted for identity. The
display name exists for humans and never drives a decision. Two people
sharing a name remain distinct.

A null subject means nothing vouched for the actor. Three cases produce
one:

- records written before authentication existed;
- events raised by the pipeline itself, which opens cases as `system`;
- an operator acting through the command line.

None of them are backfilled with a synthesised identifier, and the
interface reports the distinction rather than presenting them as
verified.

## Boundary limits

Request bodies are bounded before a handler runs. Review transitions are
rate limited per credential, counted within a process; several workers
therefore allow proportionally more traffic, which is enough to stop one
credential from hammering the endpoints.

Interactive API documentation is served only in development environments.

## What is not here

TLS termination, a custom domain and the deployment itself. Until they
exist the hosted flow is exercised against the development pool from a
developer machine.
