# ADR-0049 — The launcher checks what it is about to execute

Date: 2026-08-18

## Status

Accepted and executable for the hosted profile. It closes ADR-0048's named gap
as far as a host-side check can, and **it is not measured boot** — the ceiling
is stated below rather than left to be discovered.

## Context

ADR-0048 ended by naming the load-bearing gap: every link from the release
manifest down was checked — the manifest binds the anchors artifact's digest,
the document's pins are validated, the peer's key is measured against them —
and **the thing the hosted machine actually boots was checked by nothing.**
`aiueos.vm/validate-boot-inputs!` asserted that the kernel and initramfs
*existed*. A chain whose first link is unattached is a chain lying about its
length.

## Decision

**`aiueos.boot-admission` decides whether the artifacts a launcher is about to
boot are the artifacts a signed release manifest names**, and
`aiueos.vm/validate-boot-inputs!` enforces it before QEMU starts. It composes
`aiueos.publisher` (authorship) and `aiueos.ota/verify-artifacts` (digests)
rather than growing a third copy of either.

- **Both kinds are required.** A manifest that names the initramfs while the
  launcher takes its kernel from anywhere has verified the smaller half of what
  executes.
- **Unmeasured and mismatched are separate refusals.** Both deny, so neither is
  a silent pass, but they are different operator problems: a launcher that did
  not hash something, versus bytes that are not the bytes.
- **Only the artifacts the launcher boots are verified.** A manifest names more
  than a launcher touches — the anchors artifact lives *inside* the initramfs,
  so the initramfs digest already covers it. Re-hashing it here would mean
  opening the image to check bytes the guest checks anyway, while presenting
  one measurement as two. (The first implementation did verify everything the
  manifest named, and refused every valid boot; the test caught it.)
- **Authenticity, not recency.** No `:installed-sequence` is passed, so the
  monotonic check does not run. Booting an older release is allowed on purpose:
  a device that cannot boot an earlier image cannot be recovered, and
  anti-rollback belongs in the update path, where there is a stored sequence and
  a machine that is already running.
- **A launch with no `:release` proceeds and records
  `:aiueos.boot/verified? false`.** Refusing outright would break every local
  workflow that boots what it just built, which is a way of not being used. The
  difference between *checked* and *not checked* is written into the plan
  rather than inferred from the absence of a complaint — the same rule ADR-0048
  applied to a boot config with no anchors.

## Executable evidence

**22 tests, 51 assertions, 0 failures** across `aiueos.boot-admission-test`
(8 new) and `aiueos.vm-test` (4 new, with real temp files).

- artifacts matching a signed manifest boot, and the verdict names the digests
  it accepted so a receipt can too;
- **an initramfs edited after signing never reaches QEMU** —
  `refusing to boot: artifact-digest-mismatch`;
- an unsigned release never reaches QEMU;
- a kernel the manifest does not name, and an artifact nobody hashed, each
  refuse with their own reason and say which kind;
- an older release still boots;
- publisher's reasons arrive unrelabelled for three separate attacks.

**Both directions, shown.** Three mutations, each failing exactly what it
should: dropping the named-kinds check fails only that test; letting
`verify-artifacts!` ignore the verdict fails both launcher-refusal tests;
dropping the `:aiueos.boot/verified? false` record fails only the
not-checked test.

Full suite **614 tests, 9297 assertions, 19 failures** — the same 19 test names
as the unmodified tree. `kbb -M:tcb-check` `{:valid? true :files 39 …}`;
`boot_admission.cljc` is inventoried, because it decides what the host is
allowed to execute. Lint unchanged.

## Remaining boundary

- **This is not measured boot, and cannot become it.** The check runs on the
  host, in the launcher, so it is worth exactly as much as the host is; a
  compromised host verifies whatever it likes. What it does close is
  substitution and corruption of the artifact between build and boot, which was
  entirely open. The bare-metal profile answers the rest with firmware; the
  hosted profile cannot, and this ADR does not claim it does.
- **Nothing requires verification yet.** No deployment profile turns
  `:aiueos.boot/verified? false` into a refusal. That rule — and the matching
  one for anchors from ADR-0048 — is the obvious next step and is not done.
- **Signature verification is still the provider's**: `:verified?` per key is
  supplied, not computed here.
- **The bare-metal profile does not use this path**; its release image is
  verified by `verify-release-signature.py` outside this namespace, and the two
  have never been reconciled into one statement of what "verified" means.

Next is the profile rule: `sensitive-local` and above should refuse to boot
unverified artifacts and refuse to run without anchors. Both facts are already
recorded in the plan and the boot config; nothing reads them as requirements.
