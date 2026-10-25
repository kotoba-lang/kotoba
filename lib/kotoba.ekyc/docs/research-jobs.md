# Durable research jobs — integration pending

`ekyc.identity-jobs` adds a private job coordinator over the same canonical
read/CAS state as identity and free quota. It does not provision a storage host,
KMS, queue, reviewer, screening feed, or production HTTP adapter.

The trusted host must validate the full request, compute its SHA-256 fingerprint,
resolve the authenticated Principal/application/session/scope, and pass an
unforgeable verified command to `enqueue!`. Do not expose host flags to clients.
The state and prompt must be encrypted in a private Kotobase graph. Port labels
are configuration checks, not independent proof of privacy or correct CAS.

Enqueue reserves free quota and the queued job in one CAS, with one active job
per Principal. A reused request ID with another input fingerprint or Principal
is refused. A durable outbox/queue dispatcher must discover queued records after
restart; `enqueue!` does not schedule work by itself. Before dispatch `run!`
rechecks current identity, scope, session and revocation and commits `running`.
Queue redelivery cannot send the model request again. The injected `infer!` must
enforce input/output policy, exact model, bounded response and a 2,100-second
abort deadline. The coordinator deadline alone does not abort external IO.

Unknown results, including a lost upstream response or an abandoned running job,
retain quota and block another concurrent job. `recover!` changes only expired
running records to unknown; it never infers again or refunds. An independently
authorized reconciliation workflow is still needed to resolve these records.
Unconfirmed CAS never permits dispatch. Failed result persistence must be
reconciled against the existing job, never handled by submitting a new ID.

`result!` checks ownership and current identity/scope plus the caller's current
authenticated session. It never returns the prompt. Completed records still need
a retention/deletion schedule. Finalization is conservative: stale or revoked
session evidence prevents result delivery and can cancel a result; production
observers need to keep evidence current for long-running inference.

Current quota policy is inherited from identity-policy (50 per Principal/day).
Cross-Principal person linking must be enforced by the production authority; this
module does not invent a person-level deduplication service.

Validation: kbb SCI compatibility tests exercise concurrent duplicate enqueue,
single dispatch, ambiguous outcome, cross-user reads, revocation, bad commit
receipt, restart recovery and a simulated 70-second completion. Test storage is
explicit in-memory state, not production persistence or native/Q9 evidence.
