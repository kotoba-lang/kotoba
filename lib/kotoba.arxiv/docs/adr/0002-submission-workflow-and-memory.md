# ADR-0002: Submission workflow state and Kotoba memory

- **Status**: Accepted
- **Date**: 2026-06-28

## Decision

The arXiv actor models submission as a replayable workflow:

1. validate the package locally
2. start or resume the arXiv draft
3. upload the source archive
4. stop for explicit human approval before final public submission
5. record any server-side blocker and replan

Approval gates are surfaced as structured alerts, not just prose. Runtime
clients should render `:alerts` entries with `:presentation :alert` prominently
before executing the gated operation.

Endorsement failures are not generic errors. They are durable holds with the
attempted category and arXiv server message preserved. The actor may retry with a
truthful category that the account is allowed to submit to, or it may request
endorsement. It must not choose an unrelated category solely to bypass policy.

Kotoba can serve as the actor's memory layer by storing event-shaped datoms:
category decisions, attempts, holds, human approvals, and actor checkpoints.
Secrets and browser session material remain outside Kotoba; Kotoba stores only
facts needed for accountability and resumption.

## Consequences

`submissions/kotoba/status.edn` is the local working state for this package.
`actors/arxiv/memory/kotoba-schema.edn` defines the durable shape that can later
be committed into a Kotoba graph when the runtime integration is available.
