# ADR-0006: Cloud live verification is explicit, bounded, and self-cleaning

- Status: Accepted (2026-07-18)
- Extends: ADR-0003

## Context

ADR-0003 defined a portable injected Cloud v3 client but intentionally tested
only mock transports. Phase 6 needs executable evidence against the service
without making ordinary test, lint, or example commands billable.

## Decision

`browseruse.cloud.http` is the JVM `java.net.http` and Cheshire host for the
portable request contract. It does not log request headers or bodies.

`browseruse.cloud.live-probe` is dry-run by default. A network request requires
both `--execute` and `BROWSER_USE_API_KEY`. Execution creates exactly one Agent
Session with `keepAlive=false`, a unique idempotency key, a server-enforced
`maxCostUsd`, and bounded polling. The accepted probe permits USD 0–1 and 10–600
seconds; its conservative defaults are USD 0.05 and 120 seconds. When create
returns an ID, session-level stop runs in `finally`, including poll failures.
Results expose bounded session metadata and cost fields, not the credential or
signed live/recording URLs.

Live evidence is recorded only after an authorized operator supplies a key and
explicitly executes the runbook. CI remains credential-free and non-billable.

## Evidence

- `kbb -M:cloud -m browseruse.cloud.live-probe` prints a dry-run plan.
- `kbb -M:cloud:test -d test -d test-cloud`
  verifies HTTP/JSON encoding, no-key failure, budget validation, and cleanup
  after a simulated polling failure.
