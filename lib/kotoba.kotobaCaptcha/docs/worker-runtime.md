# Worker runtime and provider boundary

`kotoba-captcha` executes only synthetic fixtures, explicit human-assisted
verification, and image analysis for caller-owned first-party properties. It
does not implement third-party CAPTCHA bypass or anti-bot evasion.

## Runtime

`kotoba.captcha.worker-store/WorkerStore` is the durable queue boundary. The
included `task-store-adapter` adds atomic claim tokens and expiring leases to a
`TaskStore`; production deployments should implement the same protocol with a
transactional database. A stale worker cannot complete a task after its lease
expires or is reclaimed.

`kotoba.captcha.worker/run-once!` performs one bounded attempt. Retry count,
exponential delay, provider deadline and lease duration are configurable.
`run-bounded!` intentionally requires a maximum task count. Process hosts own
polling and shutdown, and should isolate untrusted or non-cooperative provider
code because the portable deadline detects overrun but cannot preempt it.

Cancellation is valid from queued or processing state and invalidates the
lease. Audit events recursively redact keys matching credentials, tokens,
authorization, cookies, and solutions. `AuditSink` exposes explicit retention
purging; production sinks should encrypt storage and enforce tenant-scoped
access.

## Providers

- `SyntheticProvider` handles deterministic CI fixtures without arbitrary code
  evaluation.
- `HumanProvider` waits for a separately authenticated human submission.
- `VisionProvider` is a first-party protocol boundary. It calls an injected
  `VisionBackend` only when `scope` is `first-party` and ownership is confirmed.

Provider results are one of `:ready`, `:retry`, `:waiting-human`, or `:failed`.
Solutions are stored on the task but never included in audit events.

## Production adapter requirements

Database implementations must atomically compare lease tokens, encrypt task
payloads and results, apply per-tenant quotas, and purge both task and audit
records. Human and vision transports must authenticate callers and must not
accept work outside the authorization recorded at task creation.
