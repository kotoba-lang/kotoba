# Security: block safe releases without operational evidence packet

Architecture review finding: `F-007`
Severity: Medium
Owner: release/tooling implementation

## Problem

Operational evidence is currently designed but not tied to release blocking.
Safe releases should require evidence, not just advisory documentation.

## Risk

Security evidence can remain optional if release tooling does not fail when
SBOM, provenance, package verification, key status, or risk review is missing.

## Required work

- Add a `safe-release` evidence gate.
- Require conformance results, package verification, SBOM, provenance, key status
  snapshot, and critical/high risk review.
- Allow missing evidence only with an unexpired exception-register approval.

## Acceptance criteria

- Release tooling reads evidence index and exception register.
- Missing packet artifacts fail the release gate.
- Exception register entries require owner and expiry.
- `kotoba-lang/security` risk `R-006` has implementation evidence.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-007`
- `kotoba-lang/security/docs/operational-evidence.md`
- `kotoba-lang/security/docs/sbom-slsa.md`
