# ADR-013 — Operator Intake and Asynchronous Processing

- **Status:** Accepted
- **Date:** 2026-09-09
- **Scope:** Starting work from the console, job records, queue adapters, the worker, shared storage
- **Supersedes in part:** the command-line-only intake of [ADR-006](ADR-006-supplier-document-intake.md) and [ADR-007](ADR-007-procurement-reconciliation.md)

## Context

Every capability the platform had was reachable only from a command line.
The API exposed the results afterwards, so an operator could read a
finding but could not produce one. Ingesting a supplier sheet meant shell
access to the machine running the application.

Exposing those pipelines as ordinary request handlers does not work.
Document analysis and semantic review take seconds to tens of seconds and
can be throttled and retried; a browser cannot hold a request open across
that and a load balancer will not let it.

## Decision

### Work that outlives a request is a job

Intake accepts the upload, records a job and answers immediately. The job
carries its kind, state, the verified subject that started it, what it
produced and why it failed. It is the only thing the console polls, and
the only place a failure is explained.

Reconciliation and forecast runs already persist their own results, so a
job points at what it produced rather than repeating it.

### The queue is an adapter, and the row is the record of truth

`JobQueue` has a database implementation and a hosted one, selected by
explicit configuration and never inferred from the AWS feature flags. The
database implementation needs no broker, which is what local development,
the demo and the test suite use.

A queue delivers work; it does not decide what happened. That is what
makes at-least-once delivery safe: a message naming a job that is already
terminal is discarded rather than run a second time.

### Claiming is a conditional update

A worker takes a job only if the row is still queued, so two workers never
hold the same one. A lease that expires returns the job to the queue,
because a worker that crashes would otherwise strand it in `running`
forever with nothing to notice.

Retries are bounded and a failure that retrying cannot fix — an unknown
supplier, an unsupported file — is not retried at all.

### The worker is a separate process

Not a thread inside the API. A request must never be delayed by another
operator's document, and the two scale independently. Concurrency comes
from running more workers, which keeps the loop simple enough to reason
about when something goes wrong.

### Submitting twice must not process twice

Every start carries an idempotency key, unique per kind and enforced by
the database rather than by a prior read. A default key derives from the
supplier and the checksum of the bytes, so the same file from the same
supplier is the same request. Without this a double-clicked button costs
two document analyses and produces two sets of findings for one sheet.

### The filename decides the media type

Not the declared content type, which the caller controls. Trusting it
would let an unsupported file past the boundary and fail deeper in, after
it had already been stored.

### Storage must be shared where instances are not

The API stores the bytes and the worker reads them back. Deployed, they do
not share a filesystem, so the application refuses to start with local
storage where more than one instance runs, rather than failing later when
the document turns out to be unreadable.

### Only infrastructure that something uses

The queue the worker consumes is created. An event bus, a routing rule and
a callback queue that nothing publishes to or reads from are opt-in: live
resources doing nothing still have to be understood by whoever comes next.

### Evaluating demand reads persisted history

An operator triggering an evaluation means the sales the platform already
holds, not a generated dataset, so the weekly panel is aggregated from the
database. The command line keeps its file-backed and synthetic paths.

## Consequences

- Running the platform locally now means running a worker as well as the
  API and the web application.
- The pipelines are untouched and the commands still call them, so an
  operator with shell access keeps a way in when the queue is unavailable.
- Rate limiting and the job table are per-deployment concerns that grow
  with the number of workers; more workers mean proportionally more
  provider calls.
- A document rejected by the rules is a successful job with findings, not
  a failed job. The work reached a verdict; the verdict was "no".
- Polling costs one request per job per second and a half. It is enough
  for a handful of operators and would not be for many.
- Step Functions execution of the human-review callback, TLS, the
  deployment itself and cloud CI/CD remain outstanding.
