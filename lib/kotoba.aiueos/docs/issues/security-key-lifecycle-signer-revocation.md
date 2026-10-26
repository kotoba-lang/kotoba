# Security: enforce key lifecycle and signer revocation for manifests

Architecture review finding: `F-002`
Severity: Critical
Owner: aiueos authority contract / host adapter verification

## Problem

aiueos defines manifest authenticity contracts for host adapters, but signer
lifecycle status must be explicit in policy data. Expiry, revocation,
compromised status, and historical verification policy need a shared contract so
adapters cannot silently treat stale keys as active.

## Risk

A compromised or stale signer can remain trusted for new manifests until every
policy is manually edited.

## Required work

- Add key status shape for manifest signer verification.
- Require adapters to reject revoked, expired, or compromised keys for new
  artifacts.
- Reserve retired keys for historical verification.
- Record key status in audit/provenance events.

## Acceptance criteria

- Revoked and expired key states are representable and validatable in policy.
- Retired keys are distinguishable from active signers for historical-only
  adapter behavior.
- Compromised signer lookup produces incident-severity evidence.
- `kotoba-lang/security` risk `R-002` can move from `:open` to `:mitigated`.

## Local resolution evidence

- Added CLJC policy-level `:aiueos/signer-status` lifecycle states.
- Contract validates `active`, `retired`, `revoked`, `expired`, `compromised`,
  and `suspended`; missing status remains compatible with existing flat signer
  registries.
- Contract rejects `:aiueos/signer-status` entries that reference a signer absent
  from `:aiueos/signers`, preventing lifecycle typos from silently leaving a key
  active in host adapters.
- Added CLJC contract tests for signer lifecycle policy.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-002`
- `kotoba-lang/security/docs/key-lifecycle.md`
- `aiueos/SECURITY.md`
