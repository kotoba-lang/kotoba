# kotoba-ontology

Object-type + provenance registry for `kotoba-lang` / `cloud-itonami-*`.

`cloud-itonami` (`gftdcojp/cloud-itonami`) already runs an
`activity → decision → effect → audit` log over facts ingested from many
external sources (m365, PLM/ERP, open-data portals via connectors like
`kotoba-lang/goyoukiki`). What it does not have is a shared vocabulary for
*what kind of thing* an ingested fact is — each source has invented its own
ad hoc keyword shape for the same real-world entity. This repository is that
shared vocabulary: a small, honestly-scoped analogue of the object-type
layer in a Palantir Foundry-style ontology, without claiming the rest of
Foundry (no pipeline builder, no cross-org connector marketplace, no
Gotham-style intel product — see "Non-goals" below).

## Contract

```clojure
(require '[kotoba.ontology :as ontology]
         '[kotoba.ontology.connector :as connector])

(ontology/get-type :tender)
;; => {:id :tender, :name "Procurement Tender / Opportunity",
;;     :attributes {:status :keyword}, :key [:status]}

(ontology/conforms? :tender {:status :open})
;; => true

(connector/get-connector :jp.kkj)
;; => {:id :jp.kkj, :object-type :tender, :repo "https://github.com/kotoba-lang/goyoukiki", ...}

(connector/tag :jp.kkj {:status :open})
;; => {:status :open, :ontology/type :tender, :ontology/source :jp.kkj}

(connector/tagged-conforms? :jp.kkj (connector/tag :jp.kkj {:status :open}))
;; => true
```

- `kotoba.ontology` — object types: `:id`, `:name`, `:attributes` (required
  keys a conforming fact must have), `:key` (the attributes that identify
  one instance). `conforms?` is a structural check only — it does not
  validate attribute value types.
- `kotoba.ontology.connector` — a registry of *which* external-data
  connector produces *which* object type, and `tag`, the pure step that
  stamps a connector's already-normalized output with `:ontology/type`,
  `:ontology/source`, and optionally `:ontology/fetched-at` /
  `:ontology/confidence`.

### How each function refuses

The three failure signals are deliberately different values, because a
caller has to act differently on each:

| | unknown / unregistered id | known id, fact does not satisfy it |
|---|---|---|
| `ontology/conforms?` | `nil` — unanswerable | `false` |
| `connector/tagged-conforms?` | `false` | `false` |
| `connector/tag` | throws | n/a — `tag` does not check conformance |

`conforms?` returns `nil` rather than `false` for an object type it does not
know, so a typo'd type id cannot be read as a fact that failed validation.
`tagged-conforms?` collapses both to `false` on purpose: it is the predicate
for checking an *untrusted* claim, and a caller should never have to catch an
exception to find out that a claim is unverifiable.

`tag` is the one that throws, because it *writes* provenance rather than
reading it. It refuses three ways, each carrying a `:reason` in `ex-data`
(`:unregistered-connector`, `:connector-without-object-type`,
`:provenance-overwrite`) so the caller can tell them apart without matching
on the message. The last two exist because both would otherwise produce a
well-formed fact that is quietly wrong: one naming a source while claiming
`:ontology/type nil`, and one that came from a different connector than the
provenance on it now says. Re-tagging with the *same* id stays idempotent.

Neither namespace fetches anything. Fetch/parse stays exactly where
`kotoba-lang/goyoukiki` already put it for `jp.kkj` and `jp.geps`: a
per-source JVM-only adapter that does the HTTP call and maps the raw
response into the domain's own pure-data model
(`goyoukiki.model/opportunity`). This repo only indexes that pattern and
gives its output a common provenance tag, so a blueprint that consumes
several connectors can tell them apart without inventing its own registry
each time.

## Seeded with what's already real

The registry is seeded with exactly one object type, `:tender`, and the two
connectors that already produce it —
[`kotoba-lang/goyoukiki`](https://github.com/kotoba-lang/goyoukiki)'s
`jp.kkj` (kkj.go.jp live tender search) and `jp.geps` (GEPS awarded-bid open
data), both real, both tested against captured responses (see
`90-docs/adr/2607070300-kotoba-lang-goyoukiki-jp-real-ingestion-connectors.md`
in the `com-junkawasaki/root` superproject). New object types get added when
a real connector needs one, not ahead of one — `:tender` generalizes
`goyoukiki.model/opportunity`'s coarse common denominator (`:status`); the
richer domain-specific shape (`:agency`, `:cofog`, `:unspsc`,
`:required-categories`, `:min-rank`, ...) stays in `goyoukiki.model` itself,
which this registry does not attempt to replace.

## Non-goals

- **Not a pipeline/ETL builder.** No scheduling, no DAG, no UI. A connector
  is still a hand-written adapter in its own repo; this only indexes it.
- **Not a connector marketplace.** The registry lists connectors that exist
  in this fleet, not a general third-party catalog.
- **Not Gotham.** No geospatial/intel analysis, no case-management product.
- **Not a replacement for a domain's own richer model.** `goyoukiki.model`,
  `cloud-itonami`'s `:itonami.activity/*`, and similar stay the source of
  truth for their own domain; this registry only gives their *inputs* a
  common, checkable shape and provenance tag across blueprints.

## Use from a blueprint

Declare the technology in `blueprint.edn` once it is wired into
[`kotoba-lang/technology`](https://github.com/kotoba-lang/technology)'s
registry:

```clojure
:itonami.blueprint/required-technologies [:ontology ...]
```

`kotoba-lang/industry` maps ISIC-coded businesses to required technology
IDs; wiring individual blueprints' `required-technologies` to `:ontology` is
left as fleet-wide follow-up, not part of this initial capability library.

## Test

```sh
kbb -M:test
kbb -M:lint
```

`test/kotoba/ontology/registry_test.cljk` asserts properties of the two
registries *as tables* — referential integrity between them, unique ids,
`:key` drawn from `:attributes` — rather than naming `:tender` and `:jp.kkj`
by hand. Those are the tests that have to grow when a row is added, and they
are what catches a row whose `:object-type` is misspelled: such a connector
still resolves and still tags, and `tagged-conforms?` then returns `false`
for every fact it ever produces, which from the call site is
indistinguishable from facts that genuinely do not conform.

The suite is itself checked by mutation, in the superproject's
`scripts/maturity-loop/mutations.edn` (`kbb --backend sci scripts/maturity-loop/run.cljk
--only ontology`): nine ways this library could silently regress, each
replayed to confirm it turns the suite red and names the invariant it broke.
