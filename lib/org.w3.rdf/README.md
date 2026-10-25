# kotoba-lang/rdf

EDN-first RDF dataset helpers, implementing the structural abstract syntax of
[RDF 1.1 Concepts and Abstract Syntax](https://www.w3.org/TR/rdf11-concepts/)
(W3C Recommendation, 25 February 2014).

RDF terms are plain maps:

- `{:rdf/type :iri :value "..."}` — Sec 3.2 IRIs
- `{:rdf/type :blank :id "..."}` — Sec 3.4 Blank Nodes
- `{:rdf/type :literal :value "..." :datatype ... :language ...}` — Sec 3.3 Literals

Triples and quads are maps with `:subject`, `:predicate`, `:object`, and
optional `:graph` (the Sec 4 named-graph name a quad belongs to).

## Literals (Sec 3.3)

A literal is a lexical form + a datatype IRI, plus a language tag **if and
only if** that datatype IRI is exactly `rdf:langString`
(`http://www.w3.org/1999/02/22-rdf-syntax-ns#langString`). `rdf.core/literal`
enforces this by defaulting the datatype so the *iff* always holds:

```clojure
(rdf/literal "hello")                   ;; datatype defaults to xsd:string
(rdf/literal "hello" {:language "en"})  ;; datatype defaults to rdf:langString
(rdf/literal "hello" {:datatype dt})    ;; used as given
```

**A note for anyone used to RDF 1.0**: RDF 1.0 had "plain literals" with no
datatype at all. RDF 1.1 removed that notion — every literal now has a
datatype IRI, and an undecorated literal is defined as syntactic sugar for
one typed `xsd:string` (Sec 3.3). Older RDF material that talks about "plain
literals" is describing what RDF 1.1 calls an `xsd:string`-typed literal.

## Structural validation (`rdf.validate`)

`rdf.validate` checks terms/triples/quads against the Sec 3.3 literal
constraint above, the Sec 3.1 subject/predicate/object role constraints
(rejecting "generalized RDF triples", Sec 7, e.g. a literal subject), and the
Sec 4 graph-name-must-be-an-IRI-or-blank-node constraint. It returns
[`kotoba.dsl.problem`](https://github.com/kotoba-lang/dsl-core)-shaped
problems, domain `:rdf`:

```clojure
(require '[rdf.validate :as v])
(v/problems [quad1 quad2 ...]) ;; => [{:rdf/severity :error|:warn :rdf/code ... :rdf/id ... :rdf/msg ...} ...]
(v/errors   [quad1 quad2 ...]) ;; => only the :error-severity problems
(v/valid?   [quad1 quad2 ...]) ;; => true iff no :error-level problems (warnings are advisory)
```

`rdf.core` also has an older, ad hoc `errors`/`validate-quad`/`validate`
(kept, unchanged, for backward compatibility — its problem maps predate this
repo's adoption of the shared `kotoba.dsl.problem` convention and it doesn't
check the Sec 3.3 literal constraint). Prefer `rdf.validate` for new code.

## RDF Datasets (`rdf.dataset`, Sec 4)

An RDF dataset is exactly one default graph plus zero or more named graphs,
each named by an IRI or a blank node, where a graph is itself a **set** of
triples (Sec 3: duplicate triples collapse, order isn't significant):

```clojure
(require '[rdf.dataset :as ds])
(def d (ds/dataset [(rdf/quad s p o1) (rdf/quad s p o2 g)]))
(ds/default-graph d) ;; #{...} -- quads with no :graph
(ds/named-graph d g) ;; #{...} -- quads with :graph = g
(ds/graph-names d)   ;; #{g}
(ds/all-triples d)   ;; set union across the default graph + every named graph
(ds/all-quads d)     ;; flat seq of quads, round-trips with `dataset`
(ds/subjects d)      ;; distinct subject terms anywhere in the dataset
(ds/predicates d)    ;; distinct predicate terms anywhere in the dataset
(ds/objects d)       ;; distinct object terms anywhere in the dataset
```

This is distinct from `rdf.core/dataset`, which predates this namespace and
is a flat, ungrouped, non-deduped bag of quads (`{:rdf/dataset [quad ...]}`);
it's kept as-is for backward compatibility.

## Follow-ups (out of scope here)

- **Model-theoretic semantics** — entailment, graph equivalence beyond
  term-equality, inconsistency. RDF 1.1 Concepts Sec 1.7 formally defers this
  to the separate *RDF 1.1 Semantics* document, so a purely structural
  library like this one shouldn't duplicate it. RDFS/OWL entailment-level
  checking belongs to `kotoba-lang/org-w3-owl2`, a sibling project.
- **Concrete syntax parsing** (RDF/XML, Turtle, N-Triples, JSON-LD, ...) —
  this repo only models the abstract syntax (terms/triples/datasets).
  `kotoba-lang/org-w3-turtle` already exists for serializing these same
  term/triple maps to Turtle — extend concrete-syntax coverage there, not
  here.
- **Full RFC 3987 IRI conformance** — `rdf.validate/iri-problems` only
  flags a missing/blank `:value` as an error and a missing scheme prefix as
  a `:warn` heuristic; it doesn't parse IRIs against the full RFC 3987
  grammar.

## Test

```bash
kbb -M:test
```
