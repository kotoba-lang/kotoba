# Exercise: Unauthorized Key Release

Date: 2026-07-01
Type: tabletop
Related issue: `security-monitoring-ir-drills`

## Scenario

A custodian grant is observed without a matching key-release receipt.

## Expected Signals

```edn
{:aiueos/event :security/key-release-missing-receipt
 :aiueos/severity :sev-1
 :aiueos/component "custody/provider"
 :aiueos/requester-did "did:example:requester"
 :aiueos/key-id "object-epoch-7"
 :aiueos/purpose "exercise"
 :aiueos/run-id "exercise-key-release-20260701"}
```

## Expected Response

1. Preserve signed grant, requester DID, nonce, purpose, and custodian id.
2. Search receipt log for matching release.
3. Rotate affected epoch keys for future writes.
4. Re-encrypt high-value content if plaintext exposure is plausible.
5. Emit warrant evidence if release is unreceipted.

## Result

The playbook is defined, but aiueos Phase-0 does not yet implement custody
release events directly. This exercise remains a readiness record and an input
to the custody/runtime integration.

## Follow-ups

- Define a shared event schema for custody release receipts.
- Add an integration test once custody events are connected to aiueos audit.

