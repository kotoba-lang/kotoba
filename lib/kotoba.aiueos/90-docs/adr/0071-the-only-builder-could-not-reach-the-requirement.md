# ADR-0071 — The only builder could not reach the requirement

Date: 2026-08-19

## Status

Accepted and executable. It fixes a defect this series introduced four ADRs
ago, and answers — narrowly — the host/guest question named twice and deferred
twice.

## The defect

ADR-0065 made `:sensitive-local` and `:regulated` require trust anchors, and
tested it by handing `profile-violations` a config with the profile in it.

**`aiueos.image` never writes a profile into `boot.edn`.** It writes
`:aiueos/system`, `:aiueos/policy`, `:aiueos/anchors` and
`:aiueos/shutdown-after-boot?`, and nothing else — so every image this
repository's only builder produces boots as `:research`, which is what an
omitted profile resolves to.

**The requirement could not fire on any image built here.** It existed, it was
tested, and no artifact could reach it. That is the shape this series has spent
twenty iterations naming in other people's code, introduced by me, four ADRs
ago, and found only because ADR-0069's remaining boundary sent me looking at
where a guest's profile comes from.

## Decision

**The image declares the profile it was built for.** `image/plan` takes
`:deployment-profile` and `boot-edn` writes it.

**Host and guest are comparable, in one direction.**
`deployment-profile/at-least-as-strict?` orders `:research` <
`:sensitive-local` < `:regulated`, and `vm/validate-boot-inputs!` refuses when
the launcher is weaker than the image it was told it is booting:

- guest `:regulated`, host `:research` → **refused.** The image expected its
  artifact to be checked and the launcher did not know.
- guest `:research`, host `:regulated` → allowed. Verifying more than the image
  asked for costs nothing.

`:high-assurance` is not ranked. It is a refusal, not a stricter production
profile, and ordering it would have implied it could be satisfied. Unknown
profiles compare `false` rather than being ordered by accident.

**The launcher is told, not shown.** It does not read the initramfs, so
`:image-profile` is supplied by whoever runs both steps. That is the same
limitation ADR-0069 named and it is not fixed here — what is fixed is that
there is now something true to supply.

## The test that would have passed anyway

The first version of this asserted `(:deployment-profile p)` on the **plan**.
Deleting the `boot-edn` write broke nothing: the plan carried the field and the
image did not.

**Asserting on the intermediate rather than the artifact is this series' defect
in its own new test.** It now reads the profile out of a packaged initramfs —
unpacked with `cpio` in `aiueos.anchors-chain-test` — and the same deletion
fails it.

## Executable evidence

Full suite **658 / 9,461 / 12**; `-M:test-fleet` **654 / 1,941 / 0**;
`-M:tcb-check` valid with three file digests and the content digest
re-recorded; lint unchanged.

**Both directions**: reversing the strictness comparison fails four assertions
in `a-launcher-may-be-stricter-than-the-image-but-not-weaker`; deleting the
`boot.edn` write fails `the-packaged-initramfs-contains-the-bytes-the-manifest-names`
— which it did not before the test was fixed.

## Remaining boundary

- **Nothing supplies either profile at a real call site.** No CLI in this
  repository builds a production image or launches one, so both rules are
  available and exercised only by tests. Named for the third time, unchanged.
- **The guest still cannot check the host.** A machine booting `:regulated`
  has no way to know whether its artifacts were verified before it started;
  `:aiueos.boot/verified?` lives on the host's plan and never crosses. That is
  the half of the host/guest question this ADR does not answer, and answering
  it means the launcher writing evidence into the image it boots.
