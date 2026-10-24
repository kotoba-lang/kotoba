# datom-source

**The seam every kotobase query path plugs into.** Zero dependencies, pure `.cljc`.

kotobase's query namespaces take a *materialized* db — four in-memory indices —
which fixes the cost of every query at **O(database)** rather than O(result).
Measured on `arrangement` (2026-08-01): 57ms / 50 block-reads at 2k facts,
678ms / 640 at 32k. Linear in the size of the database, however few rows come back.

There is more than one way out of that (cursor scans, compaction over
partitions, precomputed views, adjacency indexes) and no reason to pick one
before any has been measured. So this library owns only the **contract**:

```clojure
(defprotocol IPatternSource
  (-scan [this pattern]))   ; pattern = [s p o], nil = wildcard -> #{{:s :p :o}}
```

Implementations live wherever the storage they read lives. This library owns
the combinators — and the conformance suite that makes the pieces
interchangeable rather than merely similar.

## Combinators

| | |
|---|---|
| `of-quads` | the reference source. O(n) per scan, on purpose — it is what others are checked against |
| `merged` | k sources as one. A partitioned root is a merge of its partitions |
| `filtered` | post-filter (e.g. `visible?`), as a wrapper so it cannot be forgotten |
| `counting` | records scans and quads. Comparing designs needs a number that is not wall-clock |
| `view` | precomputed answers for named patterns — the read-time cost removed rather than reduced |
| `absorb` | fold newly-asserted quads into a view incrementally |
| `cached` | memoize scans by pattern — pairs with `kotoba-lang/block-cache` |
| `datom.source.adjacency` | brick 4: out/in maps. One hop is O(degree), not O(database) |
| `datom.source.plane` | query-class → serving plane. `admit` refuses hydrate-then-scan / GraphSync-as-query |

Combinators are themselves sources, so they nest.

`view` has two properties a caller must know, because neither announces
itself: a view **does not follow its source** (facts asserted after
construction are invisible until `absorb`ed — it goes quietly stale while
staying confident), and **coverage is exact** (`[nil "knows" nil]` being
covered says nothing about `["alice" "knows" nil]`). Pass
`{:fallback? false}` to make an uncovered pattern throw rather than silently
cost a full scan. Retractions are not supported: folding an assertion into a
set is monotonic, removing one is not.

`cached` and [`block-cache`](https://github.com/kotoba-lang/block-cache) solve
different halves and neither subsumes the other. `block-cache` dedupes the
BLOCK reads under a scan and its key is content-addressed, so it can never go
stale. `cached` dedupes the scans themselves — measured on a recursive Datalog
rule, the fixpoint issued 22 scans and every one was the *same* pattern — but a
pattern is **not** a version, so scope it to one query or to a snapshot you know
is immutable.

## Conformance

```clojure
(require '[datom.source.conformance :as conf])
(deftest my-source-conforms
  (is (empty? (conf/check my-make-source)) (conf/report (conf/check my-make-source))))
```

`check` returns data, not assertions — a conformance suite that forces your
repo to adopt this repo's test framework is a dependency, not a contract.

The corpus is small but adversarial: shared predicates, repeated values across
subjects, an entity that is only ever an object, absent terms. `check` is
verified to REJECT a source that ignores the object position, so passing it
means something.

## Run

```
kbb -M:test
```
