# Exercise: Host Capability Denial Spike

Date: 2026-07-01
Type: alert simulation
Related issue: `security-monitoring-ir-drills`

## Scenario

An untrusted component repeatedly calls a host capability that is not granted.

## Expected Signals

```edn
{:aiueos/event :security/capability-denial
 :aiueos/severity :sev-2
 :aiueos/component "app/notes"
 :aiueos/capability "fs/open"
 :aiueos/reason :unresolved-capability
 :aiueos/run-id "exercise-denial-spike-20260701"}
```

## Expected Response

1. Confirm component id, manifest, active policy, and surface.
2. Confirm denial reason is expected and no host adapter provided the capability.
3. If denial count exceeds threshold, quarantine component or disable the source
   package until reviewed.
4. Preserve run receipt and policy digest.

## Result

The expected denial class maps to aiueos `unresolved-capability`. Production
alert thresholds and metric export remain follow-ups.

## Follow-ups

- Add metrics export for denial counts by component/capability.
- Add threshold configuration for denial-spike alerts.

