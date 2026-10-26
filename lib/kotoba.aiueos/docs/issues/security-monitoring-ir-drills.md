# Security: exercise monitoring and incident-response playbooks

Architecture review finding: `F-004`
Severity: High
Owner: aiueos operations/runtime

## Problem

Monitoring signals and incident-response playbooks are designed, but they need
live or tabletop evidence. Capability confinement is only operationally useful if
denials, traps, signer failures, and audit failures are visible and acted on.

## Risk

Containment failures may not be detected or handled quickly.

## Required work

- Emit sample security events for grants, denials, traps, package verification,
  key events, and audit sink failures.
- Run tabletop exercises for compromised signer and unauthorized key release.
- Run alert simulation for host capability denial spike.
- Store postmortems and event samples in evidence index.

## Acceptance criteria

- Alert samples include run/component/package ids.
- Postmortem records exist for at least two exercises.
- Response gaps are tracked in risk register or closed with evidence.
- `kotoba-lang/security` risk `R-005` has exercise evidence.

## Local resolution evidence

- Added tabletop record for compromised signer.
- Added tabletop record for unauthorized key release.
- Added alert simulation record for host capability denial spike.
- Marked this local issue as `:implemented-local` in `.issues/issues.edn`.

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-004`
- `kotoba-lang/security/docs/continuous-monitoring.md`
- `kotoba-lang/security/docs/incident-response.md`
