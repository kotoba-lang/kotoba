# ADR-0048 — PID 1 boots knowing who it may talk to

Date: 2026-08-18

## Status

Accepted and executable for the hosted profile. It turns ADR-0047's carried
file into a loaded one. It does not verify the image that carries it, and the
bare-metal profile still ships no anchor set.

## Context

ADR-0047 staged a bootstrap anchor set into the initramfs, named its digest for
the release manifest, and left the file unread: `aiueos.pid1` did not consume
`boot.edn`'s `:aiueos/anchors`. The chain was complete as a sequence of
decisions and had a gap as a running system — a machine that boots carrying the
answer and never asks the question.

## Decision

**PID 1 loads and validates the document; it does not re-admit it.**

Re-checking a publisher signature over the file at PID-1 time would add nothing
when the image was verified, and could repair nothing when it was not — PID 1
is already executing that image's code. So the honest statement is the one the
boot state now carries: **`:aiueos.anchors/provenance :image`.** What the hosted
profile inherits is whatever verified the image, and today that is nothing.
The bare-metal profile has measured Secure Boot; this one does not. A later
parse cannot substitute for a boot path.

**Three outcomes, deliberately distinct**, because the difference between them
is the difference between a safe machine and a broken one:

| boot.edn | outcome |
|---|---|
| no `:aiueos/anchors` | boots with no pins, and records `:aiueos.anchors/present? false` |
| names a file that is missing, unreadable, or refused | **refuses to boot**, naming the file and the reason |
| names a valid document | boots with `:aiueos.cloud/trust-anchors` set |

The first and the second would otherwise look identical from the outside: both
are a machine with no pins, which reaches nothing. One of them is an image
working as designed and the other is an image that is broken, and *"reaches
nothing"* hides which. So absence is **recorded, not inferred** — the same rule
ADR-0042 applied to a response with no digest, one layer down.

Refusing the boot is the aggressive half and is deliberate. A machine that
boots with a broken pin file starts fine, passes every local check, and then
cannot talk to its storage or inference authority for a reason nothing on the
machine explains. Failing at the point where the file is named says which file
and why.

## Executable evidence

**14 tests, 32 assertions, 0 failures** in `aiueos.pid1-test` (5 new).

- an image carrying anchors boots with them, and **the pins it booted with are
  the ones `aiueos.cloud/admit-peer` then accepts and refuses against** — the
  boot config *is* the policy, so there is no second place for them to drift;
- an image carrying none boots and says so, and `admit-peer` answers
  `:no-trust-anchors` — reaching nothing, which is the safe half;
- a named file that is absent, that is not readable EDN, that has a malformed
  pin, or that is a future version, each refuses the boot with its own message.

**Both directions, shown.** Three mutations, each failing exactly what it
should: skipping the missing-file check fails only the absent-file test;
skipping the reader's verdict fails only the refused-document tests; dropping
the `:aiueos.anchors/present? false` record fails the round-trip and the
carries-none test — which is the "recorded, not inferred" property showing up
as two separate failures.

The existing `load-boot-config-round-trips` needed updating: the boot config
genuinely gained a field. It now asserts the new shape rather than being
loosened to ignore it.

Full suite **602 tests, 9271 assertions, 19 failures** — the same 19 test names
as the unmodified tree. `kbb -M:tcb-check` `{:valid? true :files 38 …}`
with `pid1.cljc` re-pinned. Lint unchanged.

## Remaining boundary

- **Nothing verifies the hosted image.** This is now the load-bearing gap of
  the whole chain: every link from the release manifest down is checked, and
  the thing the hosted machine actually boots is not.
- **The bare-metal image still carries no anchor set**, so this changes nothing
  for that profile.
- **No real pin exists to put in an image.** Unchanged, and still an
  operational act rather than a code change.
- **`load-anchors` runs before `deployment-profile/enforce!`**, so a profile
  that ought to require anchors cannot yet say so. Making "this profile must
  boot with pins" a profile rule is a small, obvious next step and is not done.

Next is the one that stops being avoidable: the hosted boot path has no
verification at all, and every property this series added rests on the image
being what it claims to be.
