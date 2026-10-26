# ADR-0046 — The first pin comes in the thing the machine boots

Date: 2026-08-18

## Status

Accepted and executable as a decision layer. The judgement that admits a
release-borne anchor set is complete and tested. **No release image emits one**,
so a fresh device still has no anchors: this closes the design, not the fact.

## Context

ADR-0045 said the first anchor set ships in the image and left `:bootstrap?` as
a flag a caller could pass. That is not a delivery path, it is a placeholder.
The delivery question is genuinely constrained: a device with no anchors cannot
fetch one, because the connection that would deliver it is the connection the
anchors exist to judge. **The only channel a fresh device already trusts is the
signed artifact it boots.**

Putting the set there has a consequence worth stating before building it:
**every release becomes a potential trust change.** An update that swaps the pin
set is authorised by the publisher root, which is correct — and would still
strand the fleet if the new keys are wrong, which the root's signature says
nothing about.

## Decision

**The anchor set is a release artifact of kind `:anchors`**, covered by the
release signature and the artifact digest machinery `aiueos.ota` already has.
`from-release` turns it into a proposal; `admit-set` judges it.

- **The carried set names the release it was made for**, and that name is
  checked against the release in hand. Without it, a set extracted from one
  release could be applied alongside another's bytes — the hole `aiueos.ota`
  exists to close, in the one place where getting it wrong costs the device its
  ability to be corrected.
- **Its identity is the artifact digest the manifest already binds**, so there
  is no second identity to keep in step.
- **`:bootstrap?` is a fact about the device, not a claim in the document.** A
  set is the bootstrap because this device has nothing, never because the bytes
  said so.
- **The update channel gets no shortcut.** `admit-from-release` is a
  convenience that skips no rule: a release replacing every anchor is refused
  as `:disjoint-without-break-glass` exactly as a standalone set would be. A
  perfectly signed release that strands the fleet is still a stranded fleet.

### A key collision found while building this

ADR-0045's anchor state used `:installed-sequence`, which is also what
`aiueos.publisher` reads for **releases**. A caller keeping one state map for
both — the obvious thing to do, since the root keys and revocation bitmap
really are shared — would have had the higher of the two numbers silently block
the other stream, and **a rollback would have arrived looking like an upgrade**.
Anchor state now carries `:installed-anchor-sequence` and this namespace hands
publisher the right one. Two sequence spaces, two keys.

## Executable evidence

**25 tests, 67 assertions, 0 failures** in `aiueos.anchors-test` (was 15/47).

- a fresh device takes its first set from the release it boots, and the set's
  id is the artifact digest;
- a set naming another release is refused, with both ids in the verdict;
- bytes that are not the artifact the manifest named are refused;
- `:bootstrap?` is false on a device that already has anchors *whatever the
  release says*;
- a release replacing every anchor, and a release carrying an empty set, are
  both refused; a release may break glass with every root key;
- releases at sequence 100 do not block anchor sets at 7, and applying a set
  advances only the anchor sequence.

**Both directions, shown.** Three mutations: letting `admit-from-release`
bypass `admit-set` fails all three no-shortcut tests plus the bootstrap
assertions; merging the two sequence spaces fails both sequence tests *and* the
rollback pass-through, which is the collision itself showing up; dropping the
release-id check fails only the binding test.

Full suite **588 tests, 9232 assertions, 19 failures** — the same 19 test names
as the unmodified tree. `kbb -M:tcb-check` `{:valid? true :files 38 …}`.
Lint unchanged.

## Remaining boundary

- **No image carries an `:anchors` artifact.** `os/aiueos`'s image build does
  not emit one and `aiueos.image` does not stage one. Everything above is the
  judgement that *would* admit one; a fresh device still reaches nothing. This
  is the same shape as ADR-0045's remaining gap, moved one step closer and not
  yet closed.
- **Nothing decodes the artifact.** `:carried` is what a provider decoded; the
  encoding of an anchor-set document is unspecified.
- **No pin for a real endpoint exists to put in it.** Deciding what the first
  set contains is an operational act, not a code change.

Next is the build: emit an `:anchors` artifact from the release image build and
stage it in the initramfs, so the decision layer has bytes to judge. That is
also the point at which the chain becomes checkable end to end — release
signature over an artifact digest, over a document, over a key, over a
connection.
