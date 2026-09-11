# ADR-014 — Delivery and Deployment

- **Status:** Accepted
- **Date:** 2026-09-10
- **Scope:** Continuous integration, image publication, schema application, deployment, rollback
- **Supersedes in part:** the "apply only from a reviewed plan, by hand" practice of [ADR-011](ADR-011-aws-foundation-and-remote-state.md)

## Context

Every image was built by hand and every apply was run from one machine
with long-lived credentials in a shell. The quality gate was thorough but
only ran when someone remembered, and nothing prevented work that failed
it from reaching the default branch.

## Decision

### The pipeline holds no long-lived credentials

Workflows assume a role through an OpenID Connect provider. An access key
in repository settings does not expire, is copied when a process is
imitated rather than a repository forked, and is rotated only by someone
remembering to.

### A public repository decides the shape of the pipeline

Anyone may open a pull request, and a workflow triggered by one runs code
the author controls. So the quality and scanning workflows receive no
credentials on any trigger, and deployment runs only from the default
branch of this repository.

That restriction lives in the role's trust policy, which matches the token
subject with `StringEquals`, not in a workflow choosing not to ask. A
wildcard over the repository or the branch would let any workflow in any
repository of the organisation assume a role that can deploy.

A pull request from a fork therefore cannot obtain even the read-only
planning role. The workflow says so, rather than failing in a way that
looks like a broken pipeline.

### The pipeline runs the gate developers run

Workflows call the existing targets. Re-expressing the same checks in
workflow syntax produces two gates that drift, and the moment they
disagree the remote one stops meaning anything.

### An image is named after its commit

The tag is the commit SHA and the registry refuses to move a tag, so
"what is running" has an exact answer that points at a diff. A rebuild of
a commit that is already published is recognised rather than retried into
a failure.

### The schema is applied by the deployment

One task, once, before any service moves, using the image being deployed —
so the migrations and the code that expects them are the same commit. A
migration inside a container's start-up would race every other task
starting at that moment and turn a failure into a crash loop instead of a
stopped rollout.

A failure stops the deployment with the previous version still serving
against the previous schema.

### Plan on a pull request, apply on the default branch

Infrastructure changes are read as a plan before they are real. The
planning role grants no write.

### Staging is sized to be affordable, and says what it costs

The production-shaped composition costs roughly fifty times the account
budget. Staging drops the NAT gateway, uses the smallest database that
runs the schema, and runs one task per service.

Removing the NAT gateway means Fargate has no route to the registry, so
staging places tasks in public subnets with public addresses. Inbound
remains only what the security group allows. It is a weaker posture than
private subnets, chosen knowingly for an environment holding synthetic
data whose purpose is to prove a deployment works. Production keeps its
NAT gateway.

### Scanning has a written policy

Lockfiles and images are scanned on every pull request and weekly.
Findings at high severity or worse fail the run and name the package and
version; lower severities are reported and do not block. A scanner that
fails on everything is muted within a week.

## Consequences

- A failing check blocks a merge, which is the point and is also friction.
- Deployment is disabled until an environment exists to deploy to, so
  merging this changes nothing until it is switched on deliberately.
- Rolling back across a migration that removed or narrowed something is
  not a redeploy; the way back is forward. Each such migration must say so
  when it is written.
- Tasks in staging are publicly addressed. Production must not copy it.
- The weekly scan will eventually fail on a dependency nobody changed.
  That is the scan working.
- Production deployment, TLS, a custom domain and an operations
  notification destination remain outstanding.
