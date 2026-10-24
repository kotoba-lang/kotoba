# jiten (事典)

An encyclopedia whose claims are checkable by query rather than by convention.

`jiten` owns the **admissibility contract** for an encyclopedic entry: what an
entry is, what a claim is, and what makes a claim admissible. It is a portable
`.cljc` library with **zero third-party dependencies**. It stores nothing and
renders nothing — storage is [kotobase](https://github.com/kotoba-lang/kotobase),
and rendering belongs to whatever reads it.

It is the article layer for the same record
[`innen`](https://github.com/kotoba-lang/innen) covers with dependency edges, and
it reuses `innen`'s vocabulary and join keys deliberately so the two can be
queried together.

## The one idea

Wikipedia's unit is a page of prose to which citations are attached by
convention. The convention is enforced by other people, after the fact, unevenly.

Here the unit is an entry whose body is a vector of **statements**, and a
statement with no `:jiten.statement/source` is an `:error` — `jiten.core/corpus`
refuses to build. Unsourced prose is *unrepresentable*, not discouraged.

Everything else follows from that:

- **`sources`** inverts the record: given a citation that turns out to be
  retracted or wrong, it returns exactly which claims must be revisited. On a
  pile of pages this is a scraping project.
- **`diff`** compares by `:jiten.statement/id`, so a reviewer sees *this claim's
  citation changed* rather than a line diff of reflowed prose. That is the decay
  an encyclopedia actually suffers: nobody deletes the claim and its citation
  together.
- **There is no `:jiten.entry/abstract`.** A lead paragraph is where an
  encyclopedia most reliably accumulates unsourced claims, because it reads as
  summary rather than assertion. The lead is a section like any other.
- **There is no attribute for rating, ranking, scoring, or judging an entry's
  subject.** Following the workspace convention, the gate is the attribute not
  existing: Datomic refuses an unknown attribute and DataScript cannot resolve
  one, so this is *cannot be written*, not *written as false*.

## Shape

```clojure
{:jiten.entry/id      :entry/acme
 :jiten.entry/title   "Acme Test Corp"
 :jiten.entry/lang    "en"                  ; BCP-47, required
 :jiten.entry/form    :article              ; article | disambiguation | index | glossary
 :jiten.entry/topic-kind :organization      ; first ten values are innen.schema/node-kinds
 :jiten.entry/subject :node/acme            ; an :innen.node/id — the cross-record join key
 :company/lei         "SYNTHETICLEI0000000A" ; carried VERBATIM, see below

 :jiten.entry/notability
 {:jiten.notability/basis   :registry       ; independent-sources | registry | workspace
  :jiten.notability/sources ["GLEIF registry entry, retrieved 2026-07-29"]}

 :jiten.entry/body
 [{:jiten.section/id :lead :jiten.section/heading "Lead"
   :jiten.section/statements
   [{:jiten.statement/id         :s/acme-1
     :jiten.statement/text       "Acme Test Corp was incorporated in 1998."
     :jiten.statement/source     "GLEIF registry entry, retrieved 2026-07-29"
     :jiten.statement/confidence :documented   ; documented | attested | contested | estimate
     :jiten.statement/links      [:entry/widget]}]}]

 :jiten.entry/links [{:jiten.link/to :entry/widget :jiten.link/kind :see-also}]}
```

`:contested` requires `:jiten.statement/dissent` (what the disagreeing sources
hold) and `:estimate` requires `:jiten.statement/method` (how it was derived).
Those two values are the ones a writer reaches for when the evidence is weak, so
each has to say what the weakness is.

## Notability is data, not an argument

Wikipedia settles "does this deserve an entry" on a talk page, which means the
answer is not available to a query and not stable over time. Here the basis is
declared and each basis has a machine-checkable condition:

| basis | condition |
|---|---|
| `:independent-sources` | ≥2 sources, and not the same citation twice |
| `:registry` | the subject has a registry id (LEI, QID, patent no., repo path), so its existence is not in question |
| `:workspace` | an entity of this workspace; must name the record establishing it |

`:disambiguation` and `:index` entries are exempt — and, symmetrically, may not
carry statements at all. A navigational entry exists because a title is
ambiguous, which is a fact about the corpus rather than about the world.

## Red links are warnings, on purpose

A link to an entry that does not exist is a `:warn`, never an `:error`. It is how
an encyclopedia states what it is missing, and making it fatal would force
writers to either stub everything or stop cross-referencing.
`jiten.core/frontier` ranks those gaps by how many entries already point at them,
so the record proposes its own next work.

A link target that is not an entry-id keyword at all *is* an error — that is a
typo, not a gap.

## Usage

```clojure
(require '[jiten.core :as j] '[jiten.tx :as tx] '[jiten.revision :as rev])

(def corpus (j/corpus entries))     ; throws on any :error
(def corpus (j/corpus* entries))    ; keeps going; problems in (j/problems-of corpus)

(j/sources corpus)                  ;=> {citation [statement-ids]} — the retraction query
(j/entries-about corpus :node/acme) ;=> every language's entry for one subject
(j/coverage corpus innen-node-ids)  ;=> {:covered [] :uncovered [] :ratio}
(j/frontier corpus)                 ;=> missing targets, most-wanted first
(j/contested corpus)                ;=> claims whose sources disagree, with the dissent
(j/explain corpus :entry/acme)      ;=> every claim with its citation attached
(j/stats corpus)                    ;=> counts, no judgements

(rev/diff v1 v2)                    ;=> statement-granular {:added :removed :changed :moved}
(rev/unsourced-after? d)            ;=> did an edit strip sourcing from a surviving claim?

(tx/datomic-schema)                 ;=> transactable against Datomic / kotobase
(tx/->tx corpus {:dataset "jiten"}) ;=> relational, lookup refs
(tx/->flat-tx corpus {...})         ;=> ref-free, for the unified query plane
```

## Projection: three entity types, one ref

Entries, sections, and **statements** are each entities. A statement having its
own identity, source, and confidence is what turns "which claims cite this
source" into Datalog. Sections are entities rather than a heading denormalised
onto each statement so that a section a writer opened and left empty survives the
round trip — if it vanished, the record that a topic was *considered* would be
lost.

**Everything goes in one kotobase ref.** Per ADR-260726, `kotobase.core/open`
takes one `:ref-name`, and `q` / `pull` / `datoms` reach exactly that far.
Splitting statements into their own database for write throughput would make the
source query unanswerable — which is most of why the projection is shaped this
way.

`:company/lei` and `:innen.node/wikidata` are carried **verbatim**, not renamed
into a `jiten` namespace. They are here precisely so an entry joins to
`market-intel`, `cloud-itonami-lei`, and `innen` with no translation. `innen.tx`
makes the same choice for the same reason.

The flat projection carries `:jiten.link/resolved?` as an explicit boolean.
That is redundant in the relational form and *not* redundant in the flat one: the
flat plane has no refs, so without it every link reads as a red link on exactly
the plane most likely to ask. (Found by running the projection into
datascript.js, not by reading it.)

## Versions are kotobase's job

`jiten.revision` deliberately does not store history. Kotobase already answers
`:as-of` / `:since` / `:history true` against any ref (ADR-2607265000), so an
entry's past versions are a query. What is left here is the editorial part
kotobase cannot supply: **who** changed it (a DID), **why** (a non-blank reason —
an unexplained edit cannot be reviewed once its author has forgotten it), against
**which basis**, and **what** changed at statement granularity.

## Test

```bash
kbb --backend sci --classpath "src:test" test/run_tests.cljk   # 57 tests, 145 assertions
```

Fixtures are **synthetic on purpose** (`:entry/a`, `"Test org A"`, cited as
`"fixture"`). Real encyclopedic claims do not belong in a test fixture: a fact
asserted only inside a passing test looks verified when all the test proved is
that the code accepted a string. For a record whose entire premise is
traceability, seeding it with untraceable claims inside its own suite would be
the exact failure it exists to prevent. Sourced corpora live in a corpus repo.

## License

MIT
