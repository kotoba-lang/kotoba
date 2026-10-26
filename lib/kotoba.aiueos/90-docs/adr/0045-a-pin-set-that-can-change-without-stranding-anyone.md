# ADR-0045 — A pin set that can change without stranding anyone

Date: 2026-08-18

## Status

Accepted and executable as a decision layer. It closes the gap ADR-0044 opened.
No bootstrap set is built into any image yet, and no pin for a real endpoint is
recorded anywhere, so a fresh device still reaches nothing.

## Context

ADR-0044 made an https peer trustworthy only if its key is in the policy's pin
set, and recorded no pin for anything real. That left the machine strictly
worse off than before it landed: **a pinning client with no pin distribution is
a client that cannot connect.**

Distribution is the easy half. The hard half is change, and it has a shape
worth naming: **every mistake in a pin set is self-concealing.** A wrong
allowlist entry produces a refusal someone can read; a wrong pin set produces a
machine that cannot be told it has a wrong pin set, because the channel it
would be told over is the one the pin set governs.

## Decision

**An anchor set is a release, so it is admitted like one.** It is a signed,
sequenced document that changes what the machine trusts, facing the same four
attacks `aiueos.publisher` already answers — one stolen key, a key stolen
before it was known to be, rollback to a set whose key is now public, and
freeze. `aiueos.anchors` **composes** publisher rather than growing a second,
weaker copy, and publisher's reasons pass through unchanged.

Three rules are true of anchor sets and of nothing else:

- **A perfectly signed empty set is refused.** An empty pin set is not
  permissive, it is a brick. This is the one denial that protects the fleet
  from its own publisher.
- **Replacing every anchor at once is a one-way door.** An ordinary rotation
  must overlap: ship the new key alongside the old one, switch the server,
  retire the old one — three admitted sets, no step of which can strand a
  device. Going straight from `{a}` to `{b}` is refused as
  `:disjoint-without-break-glass`, and the verdict shows both sets, because the
  operator has to see the gap.
- **A compromise cannot overlap**, since dropping the stolen key is the entire
  point. That path is `:break-glass?`, requires **every** root key rather than
  the threshold, and reports `:one-way? true` so nobody does it by accident. It
  also drops the previous set *immediately* rather than through the overlap
  window — a window in which the stolen key still works is the thing being
  escaped.

**Trust on first use is not available.** A device with no anchors cannot be
handed one over a connection it has no way to judge, so the first set ships in
the image, covered by the release signature that already exists, and is marked
`:bootstrap?`. Anything else arriving at an anchorless device is
`:no-current-set`.

**A machine that cannot fetch keeps what it has.** `keep-using?` mirrors
`publisher/keep-running?`: freshness gates *admission of a new set*, never
continued use of the current one, because expiring the pin set when an anchor
server is unreachable would turn a network outage into a fleet outage.

## Executable evidence

**15 tests, 47 assertions, 0 failures** in `aiueos.anchors-test`.

- the full rotation dance runs: `{a}` → `{a,b}` → `{b}`, both steps admitted,
  the previous set usable inside the window and refused after it;
- `{a}` → `{b}` in one step is refused, "whatever it is called";
- break-glass below its own threshold is refused with the count it needed;
  break-glass at full threshold is admitted and says `:one-way? true`;
- an empty set is refused *while perfectly signed*;
- publisher's own reasons arrive unrelabelled for four separate attacks;
- **the set this produces is the set `aiueos.cloud/admit-peer` checks against**
  — the same retired key that `usable-anchors` stops returning is the key
  `admit-peer` then refuses. The two namespaces are joined by a test, not by a
  paragraph.

**Both directions, shown.** Three mutations, each failing exactly what it
should: dropping the overlap requirement fails the two rotation tests; keeping
the previous set through a break-glass fails only
`break-glass-drops-the-previous-set-at-once`; skipping the publisher call fails
all four pass-through assertions and nothing else.

Full suite **578 tests, 9212 assertions, 19 failures** — the same 19 test names
as the unmodified tree. `kbb -M:tcb-check` `{:valid? true :files 38 …}`;
`aiueos.anchors` is inventoried, because compromising it is compromising every
https connection the machine makes. Lint unchanged.

## Remaining boundary

- **No bootstrap set is in any image.** Marking a set `:bootstrap?` is
  admitted here; putting one in the release artifact is unimplemented. Until
  that exists, a fresh device has no anchors and therefore reaches nothing —
  the ADR-0044 gap is closed in design and still open in fact.
- **No pin is recorded for `kotobase.net` or `api.murakumo.cloud`.** This
  decides how a set changes, not what the first one contains.
- **Rotation is modelled, not exercised.** No fleet has run add → switch →
  retire against a real endpoint, and the seven-day overlap window has never
  been measured against how long convergence actually takes.
- **Nothing here fetches or verifies a signature**, and `:set-id` is a digest
  the caller computed — the same boundary `aiueos.ota` draws.

Next is the bootstrap set in the release image: the first pin has to arrive by
the one channel that is already trusted, which is the signed artifact the
machine boots.
