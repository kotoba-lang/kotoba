# ADR-0047 — Bytes in the image, and a chain with no gaps

Date: 2026-08-18

## Status

Accepted and executable for the hosted image. The **hosted** initramfs now
carries a bootstrap anchor set and names its digest; the **bare-metal** release
image still does not, and nothing reads the staged file at boot.

## Context

ADR-0046 built the judgement for a release-borne anchor set and left two things
unbuilt that it named: nothing decodes the artifact, and no image emits one. A
judgement with nothing to judge is a decision layer talking to itself.

## Decision

**The document is the canonical form this repository already has.**
`aiueos.key-lifecycle/document-bytes` is the one canonicaliser — its own
docstring says a second would be a signature-confusion hazard — so
`aiueos.anchors` supplies the *shape* and the JVM side supplies the bytes. Pins
are sorted, because a set has no order and a digest does. `:anchors/signature`
is reserved and unused: a release-borne set needs none, since the manifest binds
its digest and the manifest is signed.

**`read-document` is fail-closed, and one check earns its place beyond the
usual: a pin that is not 64 lowercase hex characters is refused rather than
carried.** A malformed pin can never equal a measured key, so a set containing
one arrives looking entirely valid and partly cannot work.

**`aiueos.image` stages it.** `plan` takes `:anchors`, computes the canonical
bytes *and their digest*, and reports `anchors-artifact` — `{:kind :anchors
:sha256 …}` — for the release manifest. `build-initramfs!` writes **those exact
bytes**; re-encoding the map at staging time is the whole hazard, so it does not
happen. `boot.edn` gains `:aiueos/anchors` so the guest can find the file.

## Executable evidence

**9 tests, 26 assertions** in `aiueos.anchors-chain-test`, with real files and a
real `cpio`/`gzip` package.

- the staged file, read back and canonicalised, measures to the digest the plan
  reported;
- **unpacked from a genuinely packaged initramfs**, it still measures to that
  digest, and `boot.edn` points at it;
- **the chain runs end to end**: release manifest names the digest → the device
  reads the staged file → measures it → `admit-from-release` admits it as the
  bootstrap set → `aiueos.cloud/admit-peer` then accepts `pin-a` and refuses
  `pin-c`. Every earlier test in this series checked one link; this one checks
  that the links are the same links.
- a file edited after signing is refused with `:anchors-digest-mismatch`;
- malformed, future-versioned and incomplete documents are refused, each with
  its own reason.

### A mutation found a test that could not fail

Three mutations were run. Two failed exactly what they should: accepting
malformed pins failed only the pin test, and re-encoding the document at staging
time failed only the packaged-image test.

**The third failed nothing.** Removing the sort from `document` left every
assertion green, because the ordering claim was written as
`(= [pin-a pin-b] (:anchors/anchors re-read))` and the two-element set happened
to iterate in that order anyway. The claim was true and the test was theatre.
It is now written as *two documents built from the same pins in opposite orders
have the same digest*, which fails when the sort is removed and passes when it
is there — verified in both directions.

Full suite **597 tests, 9258 assertions, 19 failures** — the same 19 test names
as the unmodified tree. `kbb -M:tcb-check` `{:valid? true :files 38 …}`
with `image.cljc` and `anchors.cljc` re-pinned. Lint unchanged.

## Remaining boundary

- **The bare-metal image carries nothing.** `os/aiueos/scripts/build-release-image.sh`
  emits no `:anchors` artifact, so a bare-metal device still has no anchors.
  Only the hosted initramfs path is closed.
- **Nothing reads the file at boot.** `aiueos.pid1` does not consume
  `boot.edn`'s `:aiueos/anchors`, so the set is carried and not yet loaded. The
  chain is complete as a sequence of decisions and still has a gap as a running
  system.
- **The document has no signature of its own.** Correct for the release-borne
  path; a set delivered any other way has no integrity of its own today.
- **There is still no real pin to put in it.** Deciding what the first set
  contains remains an operational act.

Next is the smallest of these and the one that turns carrying into using:
`aiueos.pid1` reads `:aiueos/anchors` at boot, admits it, and starts with a
policy that names keys — at which point the hosted profile is, end to end, a
machine that boots knowing who it may talk to.
