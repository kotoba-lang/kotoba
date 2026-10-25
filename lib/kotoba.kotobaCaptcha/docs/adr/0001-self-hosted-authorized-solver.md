# ADR-0001: Self-hosted authorized CAPTCHA task orchestrator

- Status: Accepted (2026-07-18)
- Supersedes: none
- Authority: portable task contract and authorization boundary

## Decision

Use a portable `.cljc` domain and explicit
`queued → processing → ready|failed|cancelled|expired` state machine. Expose
CapSolver-compatible `createTask`/`getTaskResult` response shapes behind an
adapter-neutral service API. Storage, HTTP, and workers are ports. Never retain
`clientKey` in task state.

Every task requires authorization evidence. Supported scopes are synthetic,
caller-owned first-party (with owner confirmation), and human-assisted. Generic
anti-bot challenge types are rejected. This service does not provide fingerprint
spoofing, proxy rotation, token injection, or circumvention of third-party access
controls.

## Evidence

Portable tests cover authorization rejection, supported scopes, transition
invariants, response compatibility, secret non-retention, and atomic memory-store
updates.
