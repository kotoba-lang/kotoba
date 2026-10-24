# innen — 因縁

A **dependency record over human history**, as a reusable `.cljc` library:
entities (organizations, polities, municipalities), the contracts that bind
them, the events and incidents that follow, and — the part that is actually
hard — the **dependency edges between them**, each one traceable to a source a
human can check.

Prefix-less per `kotoba-lang/loop-ux-kaizen`'s
`resources/repository-rules.edn`: this repo is a **library** (it provides a
reusable contract and owns the domain scoring truth). It does not observe, does
not schedule, and does not write ledgers — that is
[`kotoba-lang/loop-innen`](https://github.com/kotoba-lang/loop-innen)'s job, the
same split as `dynamics` ⊣ `loop-system-dynamics`.

Zero third-party deps, portable `.cljc`, no host interop. Implements
ADR-2607258500 (`com-junkawasaki/root`).

## Why this exists

`ADR-2607203000` makes system-dynamics analysis of *any* entity a repo-wide
rule, and `kotoba-lang/loop-system-dynamics` implements it — but what that
record holds is **stocks and flows inside** each entity (nation defence budgets,
adherent counts, backlog sizes) plus loop archetypes. It has no way to say
*"this fab depends on that mine, under a concession granted by that polity in
1871, and here is the source."*

Meanwhile the workspace already holds thousands of real entities — 59
`cloud-itonami-municipality-*` repos, 161 `cloud-itonami-lei-*` legal entities,
5,200 companies of SEC financials in `cloud-murakumo-market-intel` — and, since
ADR-2607252000, a unified query plane that joins them on `:company/lei`. Also
no dependency edges. **The entities were recorded and the graph substrate
existed; the edges between them did not.** This is the missing layer.

## The contract

An edge always reads **`from` depends on `to`**. Every kind follows that
direction, causation included, so traversal never has to ask.

```clojure
{:innen.edge/from       :node/vereenigde-oostindische-compagnie
 :innen.edge/to         :node/staten-generaal-der-nederlanden
 :innen.edge/kind       :legal-authority   ; supply ownership control funding
                                           ; legal-authority obligation succession
                                           ; causation participation infrastructure information
 :innen.edge/necessity  :required          ; required | substitutable | incidental
 :innen.edge/confidence :documented        ; documented | attested | contested | estimate
 :innen.edge/valid      {:from "1602-03-20" :to "1799-12-31"}  ; when the RELATION held
 :innen.edge/as-of      "2026-07-25"                            ; when WE looked
 :innen.edge/source     "… citation with URL + retrieval date …"}
```

Four decisions carry most of the design:

**1. Unsourced is inadmissible, not discouraged.** `innen.schema/edge-problems`
returns `:error` (not `:warn`) for a missing `:innen.edge/source`, and
`innen.core/graph` *throws* rather than build a graph containing one. A
dependency claim about history is exactly the sort of statement a language model
produces from plausibility alone; the schema makes that version
unrepresentable. `graph*` is the escape hatch for ingest tooling that needs to
report what it rejected.

**2. `:causation` needs a basis.** A `:causation` edge must carry
`:innen.edge/causal-basis` naming what *in the source* asserts the causal link.
Co-occurrence is not causation, and the schema refuses to let a date proximity
become one.

**3. Partial and BCE dates are first-class.** `"1602"`, `"1602-03"`,
`"1602-03-20"` and `"-0221"` are all real answers with different precision.
`innen.time` resolves each to a closed `[lower, upper]` key interval instead of
inventing a day, so `(t/before? "1602" "1602-06")` is **false** — unknown order
is reported as not-comparable rather than guessed. The integer keys are monotone
across the BCE/CE boundary, which is what lets Datalog ask `[(< ?k 0)]`.

**4. Scores state their own basis.** `criticality` under-states fragility
wherever the record is thin, so every score carries `:innen/basis`. `HHI` says
`:edge-count-equal-weight` when no source gave real shares, and `:stated-share`
only when every edge of that kind carries one — there is no third case where
shares are guessed.

## Use

```clojure
(require '[innen.core :as c] '[innen.algo :as a] '[innen.tx :as tx])

(def g (c/graph {:nodes [...] :edges [...] :as-of "2026-07-25"}))

;; the graph as it stood in 1750, not today's graph hand-filtered
(c/as-of g "1750")

;; what fails if this node fails, and how the failure travels
(a/cascade g #{:node/some-strait})        ;=> {:innen/failed #{…} :innen/rounds [#{…} #{…}]}
(a/criticality g)                          ;=> ranked, most-critical first
(a/cycles g)                               ;=> mutual dependency clusters (Tarjan)
(a/concentration g :node/some-fab)         ;=> single-source risk per edge kind
(a/explain g :node/a :node/b)              ;=> shortest path WITH each hop's citation
(a/frontier g)                             ;=> what to ingest next, ranked by leverage
```

`cascade` semantics, which everything downstream inherits: a `:required`
dependency that fails, fails its dependent; `:substitutable` dependencies of the
same kind fail their dependent only when **all** of them have failed;
`:incidental` never propagates.

## Datomic / DataScript

One attribute table (`innen.tx/attributes`) generates the Datomic schema, the
DataScript schema, and both tx projections, so they cannot drift:

```clojure
(tx/datomic-schema)     ; [{:db/ident … :db/valueType … :db/cardinality …} …]
(tx/datascript-schema)  ; {attr {:db/valueType :db.type/ref} …}
(tx/->tx g {:dataset "innen-core"})       ; relational: endpoints as lookup refs
(tx/->flat-tx g {:dataset "innen-core"})  ; flat: for the unified query plane
```

`:innen.node/id` is `:db.unique/identity`, so `:innen.edge/from` / `:innen.edge/to`
are `:db.type/ref` lookup refs (`[:innen.node/id :node/x]`) and re-transacting a
corpus upserts instead of duplicating.

**`:company/lei` is deliberately not renamed into an `innen` namespace.** It is
the same attribute `market-intel` and `cloud-itonami-lei` already use, so an
innen node joins straight to SEC financials and legal-entity blueprints:

```clojure
[:find ?legal ?rev ?dep-label
 :where
 [?n "company/lei" ?lei] [?n "innen.node/label" ?legal]
 [?f "company/lei" ?lei] [?f "company/revenue-usd" ?rev]
 [?e "innen.edge/from-id" ?nid] [?n "innen.node/id" ?nid]
 [?e "innen.edge/to-id" ?tid] [?d "innen.node/id" ?tid] [?d "innen.node/label" ?dep-label]]
```

(bare-string attributes because the unified plane's DataScript build wants them
that way — see `com-junkawasaki/root` `manifest/edn-query.cljs`.)

## Test

```bash
kbb --backend sci --classpath "src:test" test/run_tests.cljk   # 35 tests, 136 assertions
```

Fixtures are **synthetic on purpose** (`:node/a`, "Test org A"). Real historical
claims belong in a sourced corpus (`kotoba-lang/loop-innen`), never in a test
fixture — a fact asserted only inside a passing test looks verified when all the
test proved is that the code accepted a string.

## Not here, on purpose

- **Ingest, scheduling, ledgers, reports** — `kotoba-lang/loop-innen`.
- **Stocks and flows** — `kotoba-lang/dynamics`. An innen edge says *A depends
  on B*; a dynamics stock says *how much of A there is*. Both are needed and
  neither subsumes the other.
- **Storage** — plain EDN in, plain data out. Persistence is Datomic /
  kotobase / DataScript via `innen.tx`, or `kotoba-lang/arrangement` for
  `[s p o]` triples.
- **Visualisation** — a `dot` / `graphml` export is a follow-up; both libraries
  already exist in `kotoba-lang` and this repo will consume them rather than
  emit DOT text of its own.

## License

MIT — matching the rest of the kotoba-lang library/loop family (`dynamics`,
`loop-system-dynamics`, `loop-ux-kaizen`, `arrangement`).
