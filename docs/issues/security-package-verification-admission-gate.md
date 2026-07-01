# Security: enforce package verification as a safe execution admission gate

Architecture review finding: `F-001`
Severity: Critical
Owner: package/runtime implementation

## Problem

The package trust model is currently stronger as a contract than as an enforced
release/admission boundary. Safe Kotoba package references require repo RID,
signed manifest CID, source tree CID, transitive locks, declared capabilities,
and optional component CID, but safe execution must reject unsafe package inputs
end-to-end.

## Risk

If safe-build or release tooling accepts version-only, unsigned, missing-CID,
stale-signer, bad-repo-RID, local path, or over-capability dependencies,
untrusted code can run with falsely trusted provenance.

## Required work

- Reject version-only dependencies in safe execution paths.
- Reject unsigned or unverifiable package manifests.
- Reject missing repo RID, manifest CID, tree CID, and component CID where
  required.
- Reject dependency capability grants not declared by the package and allowed by
  caller policy.
- Emit a package-verification receipt for release evidence.

## Acceptance criteria

- Negative fixtures for version-only, missing CID, bad signature, bad repo RID,
  stale/revoked signer, and over-capability dependencies fail safe-build.
- A safe release cannot be marked complete without package verification evidence.
- `kotoba-lang/security` risk `R-001` can move from `:open` to `:mitigated`.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-001`
- `kotoba-lang/kotoba-lang/docs/adr/ADR-kotoba-package-cid-lock.md`
- `kotoba-lang/security/docs/evidence-gates.md`
