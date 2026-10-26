# ADR-0066 — The rest of the offline floor

Date: 2026-08-18

## Status

Accepted and executable. ADR-0041 decision 5 listed four clauses; ADR-0060
turned the first into a QEMU gate and said the other three were unasserted.
They are asserted now.

## What was missing

> *boot to a verified kernel, verify its own enrolment, refuse admission of
> anything not already admitted, and keep appending to its local audit chain*

ADR-0060 proved the first: the image boots with no NIC and loses exactly the
network. The other three had never been stated as a machine's behaviour with
the uplink down — only as capabilities that exist.

## What is new, honestly

Every piece is individually covered: `aiueos.enroll-test`,
`aiueos.broker-test`, `aiueos.audit-test`. **What nothing asserted is the
conjunction under the one condition that matters** — that these still hold with
the network gone, and that its being gone is a refusal rather than a quiet
downgrade.

`aiueos.offline-floor-test` runs every fixture against a policy carrying
`:aiueos.policy/net-allow #{}` and no trust anchors. Those functions are pure
decisions and do not consult the network; the state is in the fixture anyway,
because **a floor is a claim about a machine in a state, and if the state is not
in the test the claim is about nothing.**

Four clauses:

1. **Enrolment decides from what the device holds.** A claim inside its window
   with a locally computed possession proof is granted; without the proof it is
   refused rather than assumed — `enroll/claim`'s own distinction between
   `:no-proof-of-possession` and false.
2. **Admission still refuses.** A trusted component is granted, and an
   AI-generated one declaring `:network` and `:secrets` is denied. That
   direction is the one that matters: **an offline machine must not become a
   permissive one.**
3. **Every decision is still audited**, grant and deny, and each entry still
   validates — the chain does not degrade because the network did.
4. **The uplink being down is a refusal, not a downgrade.**
   `:origin-not-allowed` for a block read, `:no-trust-anchors` for a peer —
   *two different refusals*, and `publisher/keep-running?` true, so the machine
   keeps running what it has rather than treating an unreachable publisher as a
   reason to stop.

## The fixtures were wrong three times, and measurement fixed them

The first version guessed three APIs and all three were wrong: `enroll/claim`
wants `:state :factory` not `:unclaimed`, `audit/audit-entry` takes four
positional arguments not a map, and the manifest that `broker/verify-one`
denies is the one declaring effects, not the one importing a capability.

They were fixed by reading the sources rather than by adjusting the assertions
until they passed. Worth recording because the second option is always
available and produces a green test that asserts something nobody chose.

## Executable evidence

`aiueos.offline-floor-test`: **5 tests, 12 assertions, 0 failures.**
Full suite **640 / 9428 / 12** (the twelve upstream-blocked).
`kbb -M:test-fleet`: **639 / 9356 / 0.** Lint unchanged.

**Both directions**: making an empty allowlist permissive — one character in
`aiueos.policy` — fails `the-uplink-being-down-is-a-refusal-not-a-downgrade`,
which is the assertion that an offline machine stays closed rather than opening
up.

## Remaining boundary

- **This is the decision layer.** ADR-0060's gate covers the boot; nothing
  covers a running guest that loses its uplink mid-flight, which is a different
  claim needing a different harness.
- The audit clause asserts that entries are produced and well-formed, not that
  they reach durable storage. `aiueos.sealed-audit` owns that and needs a KMS
  adapter, so it is not part of a floor that must hold on any machine.
- ADR-0041's floor is now fully asserted. **That is the first item in this
  series to go from a sentence to a set of tests end to end**, and it took
  fifteen iterations, which is worth knowing about the rate.
