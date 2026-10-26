# Security: define deployment profiles for TCB and side-channel non-claims

Architecture review finding: `F-006`
Severity: Medium
Owner: aiueos/security architecture

## Problem

aiueos correctly documents that side channels are not addressed and that the TCB
is trusted, not verified. Deployment profiles should make those non-claims
visible to users and release notes.

## Risk

Users may infer that capability confinement also covers timing/cache/power
leakage, host runtime vulnerabilities, or formal verification. It does not.

## Required work

- Define deployment profiles: `research`, `sensitive-local`, `regulated`, and
  `high-assurance`.
- Name required controls and non-claims for each profile.
- Require release notes to name the deployment profile.
- Prevent high-assurance claims without explicit evidence.

## Acceptance criteria

- aiueos docs link deployment profiles.
- Release notes name profile and non-claims.
- `kotoba-lang/security` risk `R-008` has profile evidence.

## Local resolution evidence

- Added `docs/deployment-profiles.md` with `research`, `sensitive-local`,
  `regulated`, and `high-assurance` profiles.
- Linked the deployment profiles from `SECURITY.md` and `README.md`.
- Marked this local issue as `:implemented-local` in `.issues/issues.edn`.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-006`
- `aiueos/SECURITY.md`
