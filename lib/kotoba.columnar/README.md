# columnar

**A vectorized analytic execution core in portable `.cljc`.** The engine half
of "query a raw file in place" — DuckDB's job, minus the format zoo and the
SQL frontend, on the runtimes this workspace actually ships to.

```clojure
(require '[columnar.plan :as plan] '[columnar.aggregate :as agg])

(plan/scan source {:columns ["price"] :predicates [[:= "price" 120]]})
;; => {:rows [{::plan/row 4 "price" 120}] :chunks-read 1 :chunks-skipped 2}

(agg/aggregate source {:agg :max :column "price"})
;; => {:value 230 :from :statistics :read 0}      ; no data was read at all
```

## The thesis: the engine's job is to not read data

A columnar engine is not fast because it reads columns quickly. It is fast
because it does not read them. Everything here is arranged around that:

- **`columnar.stats`** answers one question — *can this chunk be skipped
  without reading it* — and is the most heavily tested namespace here.
- **`columnar.source`** splits `-chunk-stats` (cheap) from `-read-column`
  (expensive) into different protocol methods, so planning without reading is
  structural rather than a convention.
- **`columnar.plan`** reads only the columns the query mentions, and only the
  chunks statistics could not rule out.
- **`columnar.aggregate`** answers `count`, `min` and `max` from the footer
  when it honestly can, touching zero chunks.

`scan` reports `:chunks-read` / `:chunks-skipped` and `aggregate` reports
`:read`. That is not telemetry: **a caller cannot otherwise tell a plan that
pruned from one that read everything and filtered**, because both produce the
same rows. `source/counting` exists so tests can assert on it.

## Two rules that are dangerous to get backwards

**Absent statistics never permit a skip.** A chunk whose writer recorded no
bounds — normal, and unavoidable for types with no ordering — must be read.
The tempting shape is `(when-let [{:keys [min max]} stats] …)` wrapped around
the *keep* branch instead of the *skip* branch, and the failure is silent:
rows vanish from answers and nothing errors.

**Pruning is necessary, not sufficient.** `min`/`max` are bounds, and a writer
may record wider ones than the data warrants. A chunk that survives pruning
still gets the predicate applied to it exactly. Pruning decides what to read;
it never decides what matches. There is a test that hands the planner a
deliberately bogus `max` and requires the answer to stay correct.

Both are tested by construction rather than asserted in prose.

## Nulls live in a mask, not in the values

A null stored *in* the data — as nil, NaN, `-1`, `""` — is a value every
operator has to special-case, differently per type, and it is eventually
somebody's legitimate value. `columnar.vector` keeps validity beside the
values, so nulls are handled once and no value is reserved. `(vec/of :any
[nil] [true])` says "present, and it is nil", which a sentinel cannot.

The mask is a boolean vector rather than a bitset — a naive encoding of a
correct design. The decision that matters is mask-beside-values; swapping in
a bitset is local to that namespace. Stated here rather than left to be found
in a memory profile.

## Statistics are disqualified more often than you'd like

`aggregate` will not fold chunk bounds when:

- **any predicate is present.** Bounds describe every row in the chunk and a
  filter selects some of them. `max(price)` says nothing about `max(price)
  where region = 'east'` — and the tempting shortcut, prune-then-fold, is
  wrong for exactly the surviving chunks, which hold both matching and
  non-matching rows.
- **one chunk lacks bounds.** Folding the chunks that *did* report them
  silently answers about a subset of the file.
- **the aggregate is `sum`.** min/max/rows/nulls cannot produce it. Listed so
  its absence is a decision rather than an oversight.

## Scope

This is the execution core and the pruning planner. It is **not**:

- a file format reader. `IColumnSource` is where those plug in; a Parquet
  implementation belongs in `org-apache-parquet` (origin plane — the spec is
  Apache's), not here.
- a SQL frontend. `plan/select` produces the shape
  `kotobase.lake.tabular/ITabularEngine` consumes, so a triple pattern's
  projection and filters arrive here intact.
- an aggregate *pushdown* into a format's own execution. `sum` folds rows this
  library materialized.

No runtime dependencies, deliberately: this is what formats plug into, so
anything depended on here lands in every adapter that follows — the same
reasoning `datom-source` and `datalog` apply to themselves.

## Test

```sh
kbb -M:test                                          # JVM
kbb --backend sci --classpath "src:test" test/run.cljk                 # cljs, interpreted
kbb -M:cljs -m cljs.main --target node -m columnar.cljs-runner
kbb -M:lint
```

All of them, as CI runs them. The two ClojureScript runs are not duplicates of
each other or of the JVM one — a sibling repo in this workspace shipped a
cljs-only defect past a green JVM suite this week.
