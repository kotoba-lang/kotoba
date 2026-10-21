# ADR 0002: Structured concurrency is a bounded scope state machine

- Status: accepted
- Date: 2026-08-30

Kotoba's portable async layer has no ambient threads, executor, or wall clock.
Structured concurrency is therefore represented as a canonical scope document
driven by the same host/durable loop that drives channels.

A scope admits at most 32 children while open. Closing stops admission and
joins until all children are terminal. The first reported child failure marks
the scope failed and cancels all running siblings; explicit scope cancellation
does the same. Completed, failed, and cancelled scopes contain no running
children. Unknown children, duplicate completion, late spawn, and bound excess
fail closed.

Cancellation here is a portable state transition, not proof that an external
OS task stopped. Capability providers must separately attest their cancellation
boundary.
