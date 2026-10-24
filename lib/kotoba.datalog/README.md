# datalog

A storage-free Datalog query engine in portable `.cljc`: four covering
indexes, triple-pattern routing over them, and a semi-naive fixpoint
evaluator with recursive rules, negation, disjunction, and aggregates.

Extracted from [`kotoba-lang/arrangement`](https://github.com/kotoba-lang/arrangement),
whose `arrangement.core` interleaved this query half with a persistence half
(commit/restore against a prolly-tree, addressed by CID). Only the query half
is here. The coupling between the two ran in exactly one direction and
through exactly one line — see "The one cut", below.

Re-extracted from `arrangement` `c09ce59f5b384e5035d9efd4d24cbcb1bcdf30bd`
(2026-08-02), which is where the query layer's hash join, projection pruning
and `cardinality` work landed. The extraction was mechanical — a namespace
rename plus the one cut — precisely so that re-running it stayed cheaper
than merging by hand.

That base also carried a **limit pushdown**, which `arrangement` reverted
hours later (`a98588c`) after the real LDBC dataset showed it made the very
queries it targeted several times slower. This library follows that revert —
see "Known gaps".

**There is no longer anything to re-extract: this is the only copy.**
`arrangement` `096523f` deleted its query layer and now depends on this
library. Its `arrangement.query` and `arrangement.datalog` are compatibility
shims delegating to `datalog.query` / `datalog.core`, and its
`arrangement.core` re-exports `datalog.index` (adding back the `ipld/link?`
default for `ref?` — see "The one cut"), so its existing consumers did not
change. Removing those shims is a follow-up. The re-extraction above was
needed because the two copies drifted 20 commits apart in silence; that
cannot happen to a shim.

## The four indexes are named for their sort orders

`{:eavt :aevt :avet :vaet}`. They were `{:spo :pso :pos :ocp}` until
2026-08-20, with the EAVT vocabulary carried alongside in prose — every
docstring in this library had to translate between the two, and `ocp` → VAET
is the translation that stopped being obvious (VAET is
value-attribute-entity; `ocp` reads as object-something-predicate and says
nothing about the order). One structure, one name.

| index | key order | accessor |
| --- | --- | --- |
| `:eavt` | s → p → o | `entity-attrs` |
| `:aevt` | p → s → o | `by-predicate` |
| `:avet` | p → o → s | `by-predicate-value`, `by-predicate-range` |
| `:vaet` | o → p → s | `refs-to` (ref-valued objects only) |

**The `t` is a position this structure does not have.** A triple is
`{:s :p :o}`; there is no transaction component, so nothing is sorted by
one. The names are Datomic's four index names adopted whole, because that is
how a reader of a triple store reads this shape — the trailing `t` marks the
slot this library does not fill. The triple's own field names stay
`:s`/`:p`/`:o`.

### A pre-rename db raises instead of answering zero

The renamed key is simply absent from a db built by an older `datalog`, so
`(:eavt db)` is `nil`, so the scan is empty, so the query **answers zero rows
and reports success**. Every entry point in `datalog.query` therefore calls
`datalog.index/check-shape!` first — one `contains?` per query — and a
pre-rename db gets an `ex-info` naming both the keys it found and the keys it
wanted. `datalog.index/legacy-db?` is the predicate on its own.

This is what makes the rename safe to land before every consumer's west pin
has moved: the skew is loud.

## Namespaces

| ns | what it is | requires |
| --- | --- | --- |
| `datalog.index` | the four covering indexes `{:eavt :aevt :avet :vaet}` — named for their sort orders | nothing |
| `datalog.query` | single `[s p o]` triple pattern with `nil` wildcards, routed to whichever index has the bound positions leading; `cardinality` counts a pattern's matches without materialising them | `datalog.index` |
| `datalog.core` | the Datalog engine: multi-clause join, `:find`/`:in`/`:where`/`:rules`/`:order-by`/`:limit` | `datalog.query`, `datom.source` |

```clojure
(require '[datalog.index :as index]
         '[datalog.core :as dl])

(def db (-> (index/empty-db)
            (index/assert-quad {:s "alice" :p "role" :o "admin"} (constantly false))
            (index/assert-quad {:s "alice" :p "name" :o "Alice"} (constantly false))
            (index/assert-quad {:s "bob"   :p "role" :o "user"}  (constantly false))))

(dl/q db {:find '[?name]
          :where '[[?s "role" "admin"]
                   [?s "name" ?name]]}
      (constantly true))
;; => #{["Alice"]}
```

On ClojureScript, `q-async` accepts a
`datom.source/IAsyncPatternSource` and returns a Promise with the same query
semantics. Joins, safe negation, disjunction, recursive rules, aggregates,
range fusion, ordering, and limits await the source at scan boundaries; the
engine does not materialize an async source into an in-memory db. The
synchronous `q` remains unchanged.

Independent substituted pattern/range scans in one join step run with
adaptive width `min(distinct-patterns, 8)`. Larger binding groups start first
to reduce the tail, while `:where` clause order and query semantics remain
unchanged. The bound prevents unbounded provider fan-out; a remote block layer
should also coalesce concurrent reads for the same content identifier.

The third argument to `q` (and to `datalog.query/query`) is `visible?`, and
it is **required**. There is no permissive-default arity. A query is not a
bare read: a caller must state a visibility decision, even if that decision
is `(constantly true)`. This namespace has no opinion about purpose, scope,
or capability — it just refuses to invent one for you.

That requirement is load-bearing for negation. `(not [e a v])` is evaluated
through the same `visible?`-filtered scan as every positive clause, so a
redacted fact and an absent fact are indistinguishable to `not`. Negation is
deliberately *not* implemented as "run the positive query, then
set-difference against the unfiltered db" — that would let a query infer a
hidden fact's presence by testing its absence.

## The one cut

In `arrangement`, `assert-quad`/`retract-quad` had an arity-2 form that
defaulted `ref?` — the predicate deciding whether an object also gets a
reverse-reference (`:vaet`) entry — to `ipld.core/link?`. That default was the
**only** reason the quad index depended on IPLD; the index itself never did
anything with a Link beyond calling a predicate on it.

Here `ref?` is a required parameter. Rather than invent a new implicit
default (every candidate is a guess about the caller's data model, and a
wrong guess silently yields an empty or over-full reverse index), the caller
says. Wrap it if you want the old ergonomics:

```clojure
(defn assert-quad [db q] (index/assert-quad db q ipld/link?))
```

Pass `(constantly false)` if you do not use reverse lookup; `refs-to` then
always returns `{}`.

## Dependencies

Exactly one, and it has `:deps {}` of its own — so that is the entire
transitive runtime closure:

```clojure
io.github.kotoba-lang/datom-source {:git/sha "32fd54f091348dab3c78bee765bb7214a056488d"}
```

Pinned to the SHA `arrangement`'s `main` uses. `datom.source/IPatternSource`
is the seam that lets `dl/q` run against something other than a materialized
in-memory db (a cursor over persisted indexes, a merge of partitions) without
changing a line of join logic; `datalog.core/scan*` dispatches on it.

Deliberately absent: `io-ipld`, `io-multiformats`, `prolly-tree`,
`block-cache`. Nothing in this repo stores, hashes, or content-addresses
anything.

## What this is NOT

- **Not a database.** No persistence, no commits, no snapshots, no restore,
  no transactor, no durability of any kind. `empty-db` returns a map; you
  thread it through pure functions and hold it wherever you like. Persisting
  one is `arrangement`'s job.
- **No IPLD, no CID, no content addressing.** See "The one cut".
- **Not Datomic-compatible.** The `:find`/`:where` surface is Datomic-*shaped*
  — it borrows the syntax so the shape is familiar — but it is not that
  grammar, and queries are not portable between the two. No entity ids, no
  schema, no attribute cardinality/uniqueness, no `db/ident`, no history or
  `as-of`/`since`, no transaction metadata.
- **Not a query planner.** `:where` clauses join strictly left-to-right in
  the order written. Clause order is a performance decision the caller owns.
  `:clause-cardinality` is a *hint a caller's own planner supplies* — it
  selects an execution strategy, never a clause order and never a semantics.

## α-canonical form

`datalog.core/normalize` renames every logic variable to `?0`, `?1`, … in order
of first appearance and leaves everything else exactly as written, so

```clojure
(= (normalize a) (normalize b))
```

decides α-equivalence: two queries that differ only in what they call their
variables are one value. A caller that content-addresses queries addresses the
normal form rather than the text — **that caller is not this library**. There
is no CID here (see "What this is NOT"), and a canonical *value* is precisely
the seam that keeps it out; hand the result to whatever owns content addressing
in your stack.

Three things are deliberately not normalized away, because each is meaning
rather than notation:

| | why it stays |
| --- | --- |
| `:find` order | the projection — same columns in another order is another answer |
| `:where` order | decides which queries are **legal**: safe negation is checked statically against it, so sorting clauses would change the accepted language, not the plan |
| `:in` order | positional against `inputs` |

So this is α-equivalence and nothing more. Two clause orders computing the same
relation normalize differently. That is correct here rather than incomplete — a
canonical form claiming more would have to be wrong somewhere, and quietly.

`:rules` definitions are numbered in their own scope, since a rule's parameters
are bound by the invocation rather than by the enclosing query; rule names, `_`,
`$`, whitelisted function symbols and every literal pass through untouched.

`:clause-cardinality` is renamed through the same map, **keys included** — it is
keyed *by clause*, so renaming `:where` alone would leave every hint keyed to a
clause that no longer occurs. That failure has no error and no wrong answer; the
hints would simply stop matching and the query would get slower. Not reordering
`:where` is what keeps those keys findable at all.

A variable that appears only in `:order-by` or `:clause-cardinality`, with no
binding site in `:in`/`:find`/`:where`, raises. Inventing a name for it would
produce a canonical form for a query that cannot run.

### Canonical form — `canonicalize`

`normalize` removes variable names. `canonicalize` additionally removes the
three orders this engine does not read, and **throws** rather than returning an
approximation when it cannot. Two functions rather than one flag, because a
caller has to know which contract it got.

Each of the three was measured, not taken from a docstring — permuting it
leaves `q`'s answer identical:

| position | why order is not read |
| --- | --- |
| `(or b1 b2 …)` | branches are alternatives checked against the same outer bindings, then unioned |
| `(or-join [v] b1 b2 …)` | as above, plus the declared shared vars |
| `:rules` definitions | alternatives of one name, unioned to a least fixpoint |

The control matters as much as the cases: reordering `:where` changes whether
the query is **accepted**, and the suite asserts that it still throws. If that
control ever stops throwing, the distinction this rests on is gone.

`(and c1 c2)` inside a branch is a conjunction and is not permuted.

#### Why the minimum over an orbit, rather than sorting each position

Renaming numbers variables by first appearance, so it depends on branch order;
sorting branches depends on the names. Sort-then-rename and rename-then-sort
each leave pairs that do not converge. Minimising over the orbit has no such
dependency: every order is renamed, and the smallest result is the same value
whichever order was written.

The orbit is a product of factorials, so it is bounded (`orbit-limit`, 5040)
and exceeding it **refuses**. A minimum over a prefix of the orbit cannot be
told from a real one.

#### The comparator does not use `pr-str`

A set and a map have no defined iteration order, so ordering by printed text
makes the answer depend on the host. Measured 2026-08-21:

```clojure
#{:zebra :apple :mango :kiwi :cherry :banana}
;; JVM  #{:cherry :mango :apple :zebra :kiwi :banana}
;; nbb  #{:zebra :apple :mango :kiwi :cherry :banana}
```

Sets and maps are compared through their own sorted contents instead, which is
defined everywhere. `arrangement` records the same hazard on its key path,
where two byte arrays with identical contents blinded differently.

This is asserted by pinning **which** branch wins for a set-valued query, so
the JVM and nbb suites cannot both pass unless the ordering is by content.
Substituting `pr-str` back in is 0 failures on the JVM and 2 under nbb — one
defect, visible from one host.

## The relation model above this one

A clause here is a **triple**: `[s p o]`, arity 3, and the positions are
positional — they carry no labels. That is the whole relation model this
library implements, and it is deliberately the smallest one that indexes.

**It is not the relation model this workspace's own vocabulary describes.**
A reader who opens this library and concludes "the relation model here is a
triple" is reading the implementation correctly and the vocabulary wrongly.
Recorded in `com-junkawasaki/root` ADR
`adr-2608201500-incidence-is-the-vocabulary-the-query-engine-stops-at-triples`.

One layer up, an incidence relation `i` has a **boundary**:

```text
∂(i) = List Endpoint,   Endpoint = {incidence, role, sign, mult}
```

- formalized in Lean 4 in [`com-junkawasaki/inc`](https://github.com/com-junkawasaki/inc)
  (incidence structures, bisimulation, quotient descent — checked, not sketched);
- fixed as vocabulary in `etzhayyim/architecture-framework`
  (`resources/eaf/ontology.edn`: `:endpoint-required [:endpoint/incidence
  :endpoint/role :endpoint/sign :endpoint/multiplicity]`, `:signs [-1 0 1]`);
- and claimed by [`kotoba-lang/kotobase`](https://github.com/kotoba-lang/kotobase)
  for every IPLD block, with `[e a v]` named as **the base case** — a minimal
  incidence with three labelled endpoints, and a tree as the degenerate case
  with one anonymous role.

So the triple is not wrong; it is the **role-erased** projection of a richer
relation. What erasure costs:

| incidence | this library | recoverable later? |
| --- | --- | --- |
| `role` (a label per endpoint) | position 0/1/2 | no — positions cannot be re-labelled after the fact |
| `sign` ∈ `{-1, 0, 1}` | absent | no |
| `mult` (a role repeating) | absent | no |
| `:incidence/kind` | `p`, when used that way | partly |

None of that is a defect to fix here today. It is the altitude at which this
library sits, stated so a reader does not mistake the floor for the ceiling.

### Two signs that the model wants to be richer

**`ref?` is a type trying to be born.** "The one cut" above records that this
library *removed* the `ipld.core/link?` default and made `ref?` a required
parameter, because no default is safe to guess. A distinction every caller
must state, on every call, is a distinction that belongs in the value rather
than in a threaded predicate — `Link` is already a first-class IPLD Data Model
kind (`:link`, DAG-CBOR tag 42, code 8 in `kotoba-lang/lang/value-codec.edn`),
so the value could carry it.

**There are two clause kinds for one concept.** A triple clause `[?x :p ?y]`
and a rule invocation `(rule-name ?x ?y)` both mean "this relation holds of
these terms", and are handled by separate paths (`rule-invocation?` in
`datalog.core`). An n-ary relation with labelled endpoints would be one kind.

### What is deliberately *not* going to change

Two properties of this library look like candidates for generalization and
are not, because each buys something a richer model would have to buy back:

- **`:where` is an ordered sequence, not a set.** `∧` is commutative, so a
  canonically-sorted conjunction would content-address more cleanly. But safe
  negation is checked *statically* by requiring every logic variable inside a
  `(not …)` clause to be bound by an **earlier positive clause**. Reordering
  changes which queries are accepted. A symmetry that costs a decidable check
  is a loss, not an elegance.
- **`visible?` stays required, and stays threaded through negation and
  recursion.** A redacted fact and an absent fact must remain indistinguishable
  to `not`. Any future relation IR must carry this; a purely value-theoretic
  `Term/Atom/Rule` algebra does not carry it for free.

## Execution strategies

These change how much work a query does, never what it answers. Each is
asserted against the path it replaces, by a test suite that runs the same
query both ways and compares:

- **One scan per distinct substituted pattern**, not one per binding. A step
  carrying thousands of bindings that substitute down to a few hundred
  distinct patterns asks the source a few hundred times.
- **Hash join under a cardinality hint.** With `:clause-cardinality`
  `{clause estimated-rows}`, a clause whose whole relation is small relative
  to the number of keyed scans a step would issue for it is read *once* and
  hash-joined. Omit the hint and every step stays on the keyed path — the
  safe default, since a broad scan of a large relation is the mistake the
  budget exists to avoid. A wrong hint costs time, never correctness
  (`hash_join_test.cljc` asserts this with a deliberately absurd one).
- **Projection pruning.** Variables that no remaining clause and no `:find`
  element reads are dropped between steps, which merges bindings that
  differed only in a column nobody reads. Disabled entirely when `:find`
  contains an aggregate, because there multiplicity *is* the answer.
There is deliberately **no limit pushdown** — see "Known gaps".

## Known gaps

Stated because they are real, not because they are planned:

- **`:limit` is not pushed into the join.** It applies to the finished
  projection, so the join still does all of its work; `:limit` makes top-N
  *expressible*, not cheaper. An ordered drive was landed upstream and
  reverted (`arrangement` `a98588c`): driving from the ordering clause
  re-derives every remaining clause once per value group, including the ones
  that do not depend on the driver at all. On LDBC IC02 that meant re-deriving
  882 rows 7,355 times — 6.5M rows of pure repetition to avoid joining 7,355 —
  and the harness went from ~4-5 minutes of CPU to over 15. Every equivalence
  test still passed; what broke was cost, which a 40-person fixture has too
  few distinct values to expose. The correct shape is a join reordering
  (evaluate driver-independent clauses once, run only the dependent ones per
  group, semi-join the two) and is not written.

- **No `pull`.** Projection is positional `:find` vectors only. There is no
  pull expression, no pattern syntax, no nested entity maps.
- **No `not-join`.** Negation is single-triple `(not [e a v])`. A negated
  multi-clause conjunction with explicit variable scoping does not exist.
- **No stratified negation.** `(not (rule-name ...))` — negating a *rule
  invocation* rather than a triple pattern — throws a clear error rather
  than silently misbehaving. Combining recursion and negation soundly
  requires stratification (a rule may never negate itself, even
  transitively), and that analysis is not implemented.
- **No `:find` shorthands.** No scalar (`?x .`), collection (`[?x ...]`), or
  tuple (`[?x ?y]`) find specs; no `:with`.
- **Function/predicate clauses are a fixed whitelist,** not arbitrary code.
  See `query-fns` in `datalog.core`: comparisons, arithmetic, `str`,
  `count`, `ground`, and four non-regex string predicates. Regex is
  deliberately excluded — a caller-supplied pattern is a ReDoS vector, and a
  query is caller-supplied data in this threat model.
- **Aggregates are a fixed set:** `count`, `count-distinct`, `sum`, `avg`,
  `min`, `max`.
- **`[_ _ o]` — bound object only — is an honest O(database) scan.** There is
  no index for it: `:vaet` covers only objects an `assert-quad` caller marked
  as refs. Correct, but linear.
- **`retract-quad` must be given a `ref?` that agrees with the one used to
  assert the same quad,** or the `:vaet` entry is left behind. Nothing
  enforces this.
- **Values are opaque for indexing, except range.** s/p/o are map keys.
 `<`/`>` still exist as predicate clause functions over already-bound
 values. Adjacent `[?e attr ?v]` plus those comparisons are fused into
 `query-range` / `IRangeSource` so the interval is cut once rather than
 scanned then filtered. HMAC-blinded persisted keys still cannot prune
 by value — that path stays prefix + decrypt + filter.
- **The fixpoint has a defensive iteration cap** (10,000) that throws rather
  than hanging. Derivation is monotonic over a finite domain so a correct
  query converges long before it; the cap exists to fail loudly.

## Tests

Ported from `arrangement`'s suite — the deftests covering the index
accessors, query routing, Datalog, and each execution strategy (hash join,
order/limit, projection pruning, cardinality).
`arrangement`'s IPLD-Link and commit/restore tests were not ported; they
belong to the half that stayed.

```bash
kbb -M:test      # JVM: 79 tests, 127 assertions, 0 failures, 0 errors
kbb -M:lint      # clj-kondo: 0 errors, 0 warnings
npm install && npm run test:cljs
                     # ClojureScript (shadow-cljs :node-test):
                     # 79 tests, 127 assertions, 0 failures, 0 errors
```

Both jobs run in CI on every push and PR. The ClojureScript job is a real
ClojureScript compile-and-run, not a `.cljc` file merely *named* portable:
`gen-shadow-cljs-edn.cljk` resolves `kbb -Spath` into
`shadow-cljs.edn`'s `:source-paths`, so cljs compiles against the same
pinned dependency SHAs the JVM job uses, and portability is machine-verified
rather than asserted.

Two `:fn-arity` warnings are expected in the cljs build: the
`visible-is-required` tests deliberately call `query`/`q` with a missing
`visible?` to prove there is no permissive-default arity.

## License

MIT.
