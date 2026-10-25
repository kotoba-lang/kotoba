# kotoba-lang/paging

**T5 library — a page cache that does not belong to an operating system.**

Every layer in this workspace ends up wanting the same thing: keep the hot
pages, notice a sequential scan and get ahead of it, do not let one cold
streaming pass flush the metadata, write dirty pages back before dropping
them. The kernel does it for files, a database for blocks, a worker for
object-store reads. Written three times it is three sets of bugs — and the
interesting part is identical every time and **none of it needs to perform
I/O**.

So it is the policy, as a pure function:

```clojure
(p/step state {:event :access :key [:file 42] :op :read})
;=> {:state … :effects [{:effect :fetch :key [:file 42] :reason :demand}]}
```

The host performs `:fetch`, `:writeback` and `:drop`, and feeds results back as
`:fill`. Nothing here touches a device, a socket or a clock.

## Four load-bearing decisions

**There is no wall clock.** Recency is a logical sequence stepped by each
event, so the same event list gives the same evictions on any machine, forever.
A cache keyed on `System/currentTimeMillis` cannot be regression-tested.

**A fetch in flight is not a fetch to reissue.** A requested-but-unfilled page
sits in `:in-flight`; a second miss on it counts as a miss and emits nothing.
Duplicate fetches are the classic bug of a cache whose miss path is a function
call rather than an effect.

**Readahead is a detector, not a constant.** A stream must confirm a stable
stride before anything speculative happens; the window doubles while it keeps
paying off and **collapses to zero** the moment the stride breaks — reset, not
decrement, because a stream that alternates is not a stream.

```clojure
(fetches …[:f 0] [:f 1] [:f 2])       ;=> demand only — stride not confirmed yet
(fetches …[:f 3])                      ;=> [[:f 3] [:f 4] [:f 5]]  — now it is
(fetches …[:f 500])                    ;=> [[:f 500]]              — and gone again
```

Random access never speculates. Applied there, readahead is not a small waste —
it multiplies the I/O of the exact workload least able to afford it.

**Speculation does not earn promotion.** Under `:slru` a page reaches the
protected region only on a hit that *follows a demand it already served*. Scan
pages are touched once each, never leave probation, and are always the next
thing evicted.

## Two results the tests pin down

A three-page working set, then a 40-page sequential scan through an 8-page
cache:

| policy | working set surviving |
|---|---|
| `:slru` | **3 of 3** |
| `:lru` | **0 of 3** |

The `:lru` failure is asserted, not glossed. Claiming scan resistance nobody
implemented is worse than not having it.

**The readahead window is capped at half the segment capacity**, and that is a
correctness bound rather than a tuning knob. Uncapped, the window doubles to 32
in an 8-page segment and evicts its own results before the stream arrives —
measured readahead accuracy 2%. The prefetcher was doing nothing but competing
with the demand stream for frames.

Inserting readahead at the cold end of a plain LRU list was the obvious
alternative and is worse than it sounds: the next speculative fill evicts the
previous one, so readahead destroys itself. Scan resistance has to be a
promotion rule, not an insertion position.

## Policies

| policy | mechanism | note |
|---|---|---|
| `:lru` | exact recency, a list move per access | the textbook one; not scan-resistant |
| `:clock` | reference bits + sweeping hand | no per-access list surgery — why a kernel uses it. A replacement takes the victim's **slot**, so the hand keeps its position |
| `:slru` | probation → protected on second touch | scan-resistant; 80% protected by default |

## Segments

One cold streaming pass should not evict the small hot metadata everything
depends on — the same reason `kotobase-peer` splits its block cache by size
class. Give the scan its own budget:

```clojure
(p/cache mach {:page-bytes 4096
               :segments [{:id :meta :capacity-pages 64  :policy :slru}
                          {:id :data :capacity-pages 512 :policy :clock}]})
```

50 pages of streaming `:data` leave `:meta` byte-identical.

## Correctness details that are easy to get wrong

- **Write intent rides in the in-flight record.** A write that misses fetches
  first; if the pending `:op` were dropped there, the page would land clean and
  the update would be silently lost.
- **A full-page write does not read first.** Fetching would pull bytes about to
  be overwritten — the write-allocate hardware cannot avoid and software can.
- **Eviction emits `:writeback` before `:drop`.** The ordering is the only
  thing that says a dirty page dropped without a writeback is data loss.
- **`:invalidate` discards; it does not write back.** A caller who wanted the
  bytes kept wanted `:flush`.
- **A fill nobody asked for throws.** It is a host bug, not a state to absorb.
- **`:flush` is sorted**, so the same dirty set produces the same writeback
  order in every runtime.

## Stats

`:readahead-accuracy` (used / judged) is the one to watch: a high hit rate with
low readahead accuracy means the cache is working *despite* the prefetcher. It
is `nil` — not a flattering `1.0` — when nothing was speculated on.

## Test

```sh
kbb -M:test
```

Pure `.cljc`. Depends only on
[`kotoba-lang/machine`](https://github.com/kotoba-lang/machine). See
ADR-2608030200 in the superproject.
