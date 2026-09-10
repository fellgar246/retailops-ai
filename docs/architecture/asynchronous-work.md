# Asynchronous work

How an operator starts something, and what happens between the click and
the result.

## Path

```text
Console
        ↓  POST with an idempotency key
API
        ↓  store the bytes, record a job, answer 202
JobQueue
        ↓
Worker
        ↓
The same pipeline the command line runs
        ↓
Findings, a reconciliation run, or a forecast run
        ↓
Job reaches a terminal state
        ↓
Console stops polling and links to the result
```

Nothing waits on a request. Document analysis and semantic review take far
longer than a request may stay open.

## The job

| Field | Holds |
|---|---|
| `kind` | Document intake, reconciliation or forecast |
| `state` | Queued, running, succeeded, failed, cancelled |
| `requested_by` / `requested_by_subject` | Display name and verified subject |
| `request` | What is needed to run it. Never the payload |
| `result` | What it produced, by reference |
| `failure_reason` | Why it failed, in words |
| `attempts` / `max_attempts` | How many tries, and how many are allowed |
| `available_at` / `leased_until` | When it may be claimed, and by when it must finish |

The row is the record of truth. A queue delivers work and does not decide
what happened.

## The contract

```text
JobQueue

Implementations:
- DatabaseJobQueue   the job table itself, claimed with a conditional update
- SqsJobQueue        a hosted queue, with the table still holding state
```

The same shape as document storage, AI review and identity: one contract
in the core, one local implementation, one cloud implementation, chosen by
configuration.

## Mutual exclusion and recovery

A worker claims a job by moving it from queued to running **only if it is
still queued**. A worker that loses the race updates no rows and looks
again, so the same job is never handed to two workers.

A claim carries a lease. A worker that crashes leaves one behind; it
expires, the job returns to the queue, and the attempt is counted. Without
this a job would sit in `running` forever and nothing would notice.

## Retries

A failure worth retrying returns the job to the queue with a delay, so a
struggling provider is not hammered. A failure that retrying cannot fix is
recorded and left alone. Exhausted attempts fail the job permanently, and
the console shows the reason rather than a generic error.

With the hosted queue, an exhausted message reaches the dead-letter queue
through the queue's own redrive policy.

## Idempotency

Every start carries a key, unique per kind and enforced by the database.
Submitting the same file from the same supplier returns the original job.
The default key is the checksum of the bytes with the supplier, so a
double-clicked button costs one analysis, not two.

## Storage

Intake stores the bytes before creating the job, and the queue carries an
identifier. A whole document in a message would be wrong twice: messages
are small, and the worker can read the store directly.

Deployed, the API and the worker do not share a filesystem. The
application refuses to start with local storage where more than one
instance runs.

## What the console does

Polls the job until it settles, then stops. Leaving the page stops it. A
rejected request stops it, rather than retrying forever against a session
that has gone. A viewer sees no controls at all, rather than controls that
refuse on use.
