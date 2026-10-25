# Changelog

## 0.2.1 — 2026-08-03

**Bug fix.** A request larger than the device's `:max-transfer-bytes` passed
through `plan` whole. Merging refuses to *grow* a command past the maximum,
which is not the same as ensuring none exceeds it, and a single oversized
request arrives that way.

A 1 MiB read against a 128 KiB device produced one 1 MiB command — which the
device cannot execute, and which `benefit` correctly reported should have been
eight. **The plan was below its own stated floor**, which is incoherent and is
how the bug was found.

`split-oversized` now runs after merging and before ordering, chunking to
whole blocks so every piece stays aligned. `:stats :splits` reports how many
extra commands it cost.

30 tests, 97 assertions.


## 0.2.0 — 2026-08-03

`benefit` — what can planning buy on this request list, before planning it?

The last of the five T5 libraries to gain a bound computable ahead of the work,
after `layout/achievable-ratio`, `traversal/tiling-benefit` and
`paging/headroom`. Merging and ordering are only worth doing when there is
something to remove, and whether there is depends on the request list rather
than on the planner.

Both floors are exact rather than estimated. The byte floor is the measure of
the union of the aligned ranges — merging removes overlap, never alignment
overhead, so a list with no overlap is already at it. The travel floor is
`optimal-travel`, the shortest walk visiting every point on a line from a
starting position, which has a closed form.

`:captured` reports the fraction of the removable excess a plan actually took,
and is `nil` rather than 1.0 when there was no excess — claiming credit for a
request list that was already minimal would be the same dishonesty the other
libraries' bounds exist to prevent. Travel is `nil` on a zero-seek device
because the quantity does not apply, not because it is minimal.

**It immediately priced something that had only ever been prose.** C-SCAN is
ascending-only to avoid starving the far end. From a head above the span that
costs `(head - lo) + span` against an optimum of `(head - lo)` — exactly 2x
when the head sits on the top of the span, decaying toward 1 further away.
Trading up to 2x travel for bounded latency is defensible; doing it without
knowing the factor was not.

26 tests, 85 assertions.


## 0.1.0 — 2026-08-03

Initial implementation: align → merge → order → batch, as a pure function of
requests plus a device descriptor.

- Ordering is decided by the device's `:seek-cost`. C-SCAN on a seeking
  device; submission order preserved, untouched, on a zero-seek one.
- Merging follows the same split: sorted-then-merged where a seek costs
  something, submission-neighbours-only where it does not, so merging cannot
  reorder a device by the back door.
- Block alignment reported as amplification rather than hidden; sub-block
  writes reported as write amplification.
- `explain` states what the planner declined to do, not only what it did.

18 tests, 50 assertions.
