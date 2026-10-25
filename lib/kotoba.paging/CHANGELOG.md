# Changelog

## 0.3.1 — 2026-08-03

**Bug fix.** `optimal-misses` precomputed a `next-use` table and then never
read it, rescanning the tail of the trace for every resident key on every
eviction — O(n² × capacity). Invisible on the fifty-access fixtures in this
repo and hopeless past a few thousand.

It now maintains next-use per resident key, which is what the table was for.
The eviction scan is O(capacity) and a 20,000-access trace over 4096 pages
completes; the quadratic version would need ~10¹¹ steps for the same case.

No wall-clock assertion guards it — those are flaky in CI. Completing at all is
the guard.


## 0.3.0 — 2026-08-03

`compulsory-misses`, `optimal-misses` (Belady) and `headroom` — how much is
there to win, before choosing a policy?

Every policy question here is about closing a gap that nobody measures first,
so tuning either looks impressive against a bad baseline or hopeless against an
impossible one. Two bounds computable from the trace alone fix that:
compulsory (one miss per distinct page, unbeatable) and Belady's clairvoyant
OPT (unbeatable by any *online* policy). A policy near OPT has nothing left to
give; one far from it has headroom worth chasing. Which holds is a property of
the workload, not the policy.

**OPT bounds replacement, not prefetching, and the first version of `headroom`
ignored that.** Comparing a readahead-enabled cache against it produced LRU
taking 4 misses against an optimum of 12 — a real policy beating the
clairvoyant bound by 3x. The bound was fine; the comparison was not.
`headroom` now runs `demand-only` and reports `:bounds :replacement-only`, and
a test pins the nonsense so it cannot come back.

30 tests, 111 assertions.


## 0.1.0 — 2026-08-03

Initial implementation. `state + event -> {:state :effects}`; the host performs
the I/O.

- Policies `:lru`, `:clock` (victim replaced in its slot so the hand keeps its
  position) and `:slru` (probation → protected on second touch).
- Stride-detecting readahead: confirm before speculating, double while it pays,
  collapse to zero on a broken stride, never speculate on random access.
- Segments with independent budgets, so a streaming scan cannot evict metadata.
- Write intent carried in the in-flight record; full-page writes skip the read;
  eviction writes back before dropping; invalidate discards.
- Deterministic: logical sequence instead of a wall clock, sorted flush.

Two measured results are pinned by tests rather than asserted in prose:
`:slru` keeps a 3-page working set through a 40-page scan in an 8-page cache
and plain `:lru` keeps none; and the readahead window must be capped at half
the segment capacity, because uncapped it evicts its own results (measured
accuracy 2%).

24 tests, 72 assertions.
