# Security: make FIPS/PQC crypto policy deployable and testable

Architecture review finding: `F-005`
Severity: High
Owner: crypto/runtime implementation

## Problem

Kotoba correctly does not claim FIPS validation or production PQC migration
today. The next step is making crypto policy enforceable through provider
metadata, inventory, and hybrid-envelope tests.

## Risk

Cryptographic claims can drift ahead of implementation. Long-retention private
data remains exposed to harvest-now-decrypt-later risk until hybrid wrapping and
epoch migration are implemented.

## Required work

- Add/check generated crypto inventory for implementation crypto uses.
- Add provider metadata to cryptographic envelopes and receipts.
- Add `:crypto-agile`, `:hybrid-required`, and `:fips-required` policy modes.
- Reject non-FIPS providers when `:fips-required` is configured.
- Add hybrid KEM wrapping test vectors for new object epochs.

## Acceptance criteria

- Crypto inventory is generated or checked in CI.
- Non-FIPS provider is rejected when `:fips-required` is set.
- Hybrid envelope test vectors exist for new object epochs.
- `kotoba-lang/security` risks `R-003` and `R-004` have implementation evidence.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-005`
- `kotoba-lang/security/docs/fips-validation.md`
- `kotoba-lang/security/docs/pqc-roadmap.md`
