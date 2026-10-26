# Exercise: Compromised Signer

Date: 2026-07-01
Type: tabletop
Related issue: `security-monitoring-ir-drills`

## Scenario

Package or component signer `demo` is reported compromised after a signed
manifest has already been accepted by a policy.

## Expected Signals

```edn
{:aiueos/event :security/signer-status
 :aiueos/severity :sev-1
 :aiueos/signer "demo"
 :aiueos/status :compromised
 :aiueos/component "app/signed"
 :aiueos/package-cid nil
 :aiueos/run-id "exercise-compromised-signer-20260701"}
```

## Expected Response

1. Mark signer status as `:compromised`.
2. Reject new manifests signed by that signer.
3. Query affected manifests/components.
4. Preserve policy, manifest, audit entries, and release evidence.
5. Re-sign trusted artifacts with a new key or quarantine them.

## Result

The new `:aiueos/signer-status` policy field supports the required denial for
new artifacts. Production automation for affected-artifact discovery remains a
follow-up.

## Follow-ups

- Add release tooling that lists artifacts signed by a compromised signer.
- Export signer-status events into the central security evidence index.

