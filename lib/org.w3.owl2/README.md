# org-w3-owl2

[![CI](https://github.com/kotoba-lang/org-w3-owl2/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-w3-owl2/actions/workflows/ci.yml)

**[OWL 2 Web Ontology Language](https://www.w3.org/TR/owl2-syntax/) --
the W3C Recommendation (2nd edition, 2012-12-11) "Structural Specification
and Functional-Style Syntax" -- as EDN/Clojure data, in portable `.cljc`.**
A [kotoba-lang](https://github.com/kotoba-lang) `org-*` library: the same
pattern as `org-oasis-open-xmile`/`org-w3-did`/`org-w3-rdf` -- a small,
zero-third-party-dependency, portable implementation of an open standard,
pure data in, pure data out. OWL 2 models an ontology (classes, properties,
individuals, and the axioms relating them) as a STRUCTURED OBJECT MODEL,
not RDF triples -- that structural spec (sections 3-10 of the document
above) is the ground truth this library follows; it deliberately avoids the
separate, much messier [RDF-mapping document](https://www.w3.org/TR/owl2-mapping-to-rdf/)
(see [`kotoba-lang/org-w3-rdf`](https://github.com/kotoba-lang/org-w3-rdf)
if you need the plain-triple view of an ontology).

An ontology is a set of axioms about classes (`:owl/entity-type :class`,
sec 5.1), properties (object/data/annotation, sec 5.3-5.5), and named
individuals (sec 5.6.1) -- e.g. `SubClassOf(:Cat :Animal)` (sec 9.1.1),
`ClassAssertion(:Cat :Felix)` (sec 9.6.3), `TransitiveObjectProperty(:hasAncestor)`
(sec 9.2.13). This library gives you that model as plain EDN, a
bidirectional converter to/from a parsed EDN tree that mirrors the spec's
functional-style text 1:1 (`owl.functional`), structural validation
(`owl.validate`), and a small set of tractable, non-reasoner graph closures
(`owl.reason`) -- no vendor tool, no OWL API, no description-logic reasoner.

## `owl.rules` -- the same semantics, evaluated by a query engine

`owl.reason` closes over an ontology you are holding. `owl.rules` emits
RDFS / OWL 2 RL as **Datalog rules** -- plain EDN, `[[(head ?a ?b) body ...]
...]` -- so a fixpoint engine runs them against a stored graph and reads only
the predicates a rule names.

```clojure
(require '[owl.rules :as rules])

{:find  '[?class]
 :where '[(owl-type "Felix" ?class)]      ;; every class, however deep
 :rules (rules/hierarchy-rules)}
```

Two rulesets, and the difference is a full scan:

- **`hierarchy-rules`** names every predicate literally (`rdf:type`,
  `rdfs:subClassOf`, `rdfs:subPropertyOf`, `owl:equivalentClass`), so an
  engine that plans reads per predicate touches four ranges. Transitive
  subclass and subproperty, and `rdf:type` closed over the class hierarchy.
- **`triple-rules`** adds `rdfs:subPropertyOf` propagation, `rdfs:domain` /
  `rdfs:range` typing, `owl:TransitiveProperty`, `owl:SymmetricProperty` and
  `owl:inverseOf`. These derive triples whose PREDICATE is a variable, so the
  base case is `[?s ?p ?o]` and no index narrows it. That is what the
  entailments mean, not a shortfall to optimise later.

Vocabulary is explicit, never guessed: `keyword-vocabulary` (`:rdfs/subClassOf`)
or `iri-vocabulary` (the full W3C IRIs), or your own map. A missing term throws
rather than becoming a `nil` predicate, which would match nothing and read as
an ontology that simply had no such axioms.

Those two Datalog rulesets are the RDFS core only: no `owl:sameAs`, no
`someValuesFrom` / `unionOf` / cardinality, no inconsistency detection. The
complete OWL 2 RL ruleset is the next section.

## `owl.rl` -- the complete OWL 2 RL/RDF ruleset

`owl.rules/owl2-rl-rules` is the W3C rule table of
[OWL 2 Profiles §4.3](https://www.w3.org/TR/owl2-profiles/#Reasoning_in_OWL_2_RL_and_RDF_Graphs_using_Rules),
Tables 4-9, one row per rule id (78 rows), as data. `owl.rl/entail`
evaluates it to a least fixpoint (semi-naive) over any set of `{:s :p :o}`
triples -- `hierarchy-rules` / `triple-rules` are unchanged.

```clojure
(require '[owl.rl :as rl])

(rl/entail triples {})            ;; keyword vocabulary (:rdf/type ...)
(rl/entail triples {:vocabulary owl.rules/rl-iri-vocabulary})   ;; imported RDF
;; => {:graph #{...} :inferred #{...} :consistent? true
;;     :inconsistencies [{:rule :cax-dw :table 7 :triples [...]}] ...}
```

- **Schema entailments are emitted** (`:schema? true`, the default): the
  transitive `rdfs:subClassOf` / `rdfs:subPropertyOf` closures (scm-sco,
  scm-spo), equivalences (scm-eqc*, scm-eqp*), domain/range propagation
  (scm-dom*, scm-rng*) and the restriction subsumptions (scm-hv, scm-svf*,
  scm-avf*, scm-int, scm-uni) are triples in `:graph`, so a superclass is read
  off the graph rather than probed with an individual. `:schema? false` skips
  Table 9.
- **RDF lists** (`intersectionOf`, `unionOf`, `oneOf`, `propertyChainAxiom`,
  `hasKey`, `members`, `distinctMembers`) are read from `rdf:first` /
  `rdf:rest`; a malformed list is listed under `:diagnostics`, not skipped
  silently.
- **Inconsistencies are results.** Every rule that concludes `false` is
  evaluated over the closed graph and each match is returned with its rule id
  and premise triples; nothing is thrown by `entail`. `owl.rl/materialize`
  (closure only) throws `ex-info` carrying the same structured list instead.
- **Capability lists** a consumer can refuse against: `supported-rules`,
  `rule-status` (id -> `:implemented` / `:partial` / `:omitted` + reason),
  `supported-vocabulary` (IRIs), `vocabulary-status` (IRI -> `:supported`,
  `:inert`, `{:partial r}`, `{:unsupported r}`), `inconsistency-rules`,
  and `triple-rules-coverage` for the legacy Datalog rulesets.

Rule status (the reasons are in `rule-status`):

| | |
|---|---|
| implemented | all of Tables 4, 5, 6, 7, 9 except eq-ref |
| omitted | **eq-ref** -- reflexive `owl:sameAs` is never materialized (nor derived by any other rule); its only observable consequence, `x differentFrom x` or a member repeated in `AllDifferent`, is reported as eq-diff1/2 |
| partial | **dt-type1, dt-type2, dt-eq, dt-not-type** -- decided for `rdfs:Literal`, `xsd:string`, `boolean`, `decimal`, `integer` and its 12 derived types, `dateTime`, `dateTimeStamp`; the rest of the RL datatype map (double, float, owl:real, rdf:PlainLiteral, binary, anyURI, ...) is undecided. **dt-diff** -- not materialized (one triple per literal pair); an `owl:sameAs` between literals of different value is reported as `:dt-diff` instead |
| RL-admitted form only | `owl:maxCardinality` / `owl:maxQualifiedCardinality` with 0 or 1 (the only values RL has rules for) |

Literals are `{:literal lexical :datatype DT}` maps (DT a keyword like
`:xsd/integer` or its IRI; `:language` for tagged strings) or native
integers / decimals / booleans. A bare string is a term, never a literal.

Conformance: the W3C OWL 2 test cases for profile RL (vendored, see
`test-resources/w3c-owl2/`) -- 91 cases: 67 pass, 18 fail, 6 cannot run
(functional-syntax-only or imports). All 11 runnable inconsistency tests and
all 56 runnable consistency tests pass; 10 of 28 positive-entailment tests
pass, and each of the 18 failures is a conclusion outside what the RL/RDF
rules derive (owl:differentFrom, complement/union class assertions,
property characteristics, datatype subsumption, DIRECT-only annotation
entailment) -- pinned with its reason in `test/owl/w3c_rl_test.cljk`.

## Maturity

| | |
|---|---|
| Role | capability (structural data model + functional-syntax tree round-trip + validation + tractable inference) |
| Structural coverage | ontology (3.1, 3.4), all 6 entity kinds (5.1-5.6.1), literals (5.7), object/data property expressions (6.1-6.2), all class expressions (8.1-8.5), all class/object-property/data-property axioms (9.1-9.3), all assertions (9.6), Declaration (5.8), a minimal AnnotationAssertion (10.2.1) |
| Functional-syntax tree | 1:1 EDN mirror of the spec's operator names (`:SubClassOf`, `:ObjectSomeValuesFrom`, ...); round-trips every axiom kind and a full ontology -- does NOT parse the concrete `SubClassOf(:Cat :Animal)` text (v2, see Follow-ups) |
| Validation | structural only: dangling references, n-ary arity minimums, self-disjoint axioms, negative cardinalities, and two reasoner-free contradictions (ClassAssertion vs DisjointClasses, SameIndividual vs DifferentIndividuals) |
| Inference | `owl.reason`: SubClassOf / TransitiveObjectProperty / Symmetric / Inverse closures over a model. `owl.rules` Datalog: the RDFS core. `owl.rl`: the complete OWL 2 RL/RDF rule table (§4.3 Tables 4-9) with structured inconsistency reports -- **not** a description-logic reasoner (OWL 2 DL entailment outside RL is out) |
| Tests | round-trip/property coverage for every namespace; every RL rule with a positive fixture, a premise-drop control and a rule-drop control; the W3C RL conformance cases pinned per case |
| Runtime deps | `kotoba-lang/dsl-core` (validation-problem convention) and `kotoba-lang/coll` for `owl.validate`; `owl.rules` and `owl.rl` require nothing |

## Namespaces

- `owl.model` -- the EDN schema: entities (sec 5.1-5.6.1), literals
  (sec 5.7), object/data property expressions (sec 6.1-6.2), class
  expressions (sec 8.1-8.5), class axioms (sec 9.1), object/data property
  axioms (sec 9.2-9.3), assertions (sec 9.6), Declaration (sec 5.8), a
  minimal Annotation/AnnotationAssertion (sec 10), and the Ontology
  container (sec 3.1, 3.4) -- plus threading-friendly builders and the
  structural queries `owl.validate`/`owl.reason` need (`axioms-of-type`,
  `subclass-axioms`, `entities`, `referenced-entities`, `class-expr-nodes`).
- `owl.functional` -- bidirectional conversion between `owl.model` EDN and
  a parsed EDN tree that mirrors the OWL 2 Functional-Style Syntax 1:1,
  e.g. `SubClassOf( :Cat :Animal )` <-> `[:SubClassOf [:Class iri] [:Class iri]]`.
  Does NOT tokenize the real text grammar or resolve `Prefix(...)`
  declarations/prefixed names -- see Follow-ups (mirrors how `xmile.xml` in
  `org-oasis-open-xmile` converts between an *already-parsed* generic tree
  and its domain EDN without owning text parsing).
- `owl.validate` -- structural checks (dangling entity references given
  sec 5.8 Declarations, sec 9 n-ary axiom minimum-arity, a class/property
  listed twice in its own Disjoint* axiom, negative cardinalities, and two
  contradictions detectable by plain set intersection: an individual
  asserted into two mutually-`DisjointClasses` classes, and an individual
  pair asserted both `SameIndividual` and `DifferentIndividuals`) returning
  `kotoba.dsl.problem`-shaped problems. `:error` means structurally invalid
  OWL 2; `:warn` means valid but a v2 scope-out or an ambiguous case (an
  undeclared reference when the ontology has imports this library doesn't
  resolve).
- `owl.reason` -- **NOT a full description-logic reasoner** (SROIQ is a
  research-grade undertaking, explicitly out of scope -- see Follow-ups).
  Implements exactly three tractable, decidable-by-simple-graph-algorithm
  closures: (a) `SubClassOf` transitive closure over atomic classes (plain
  DAG/graph reachability, sec 9.1.1), (b) `TransitiveObjectProperty` closure
  over asserted `ObjectPropertyAssertion` facts (sec 9.2.13, per-property
  reachability), and (c) `SymmetricObjectProperty`/`InverseObjectProperties`
  fact materialization (sec 9.2.11, 9.2.4). `inferred-types` combines (a)
  with `ClassAssertion` (sec 9.6.3) to answer "is individual x (transitively)
  a member of class C".

## Contract

```clojure
(require '[owl.model :as m]
         '[owl.functional :as f]
         '[owl.validate :as validate]
         '[owl.reason :as reason])

;; Note: name locals Cat/Animal/Felix (not cat/animal/felix) -- lowercase
;; `cat` would shadow clojure.core/cat and print a compiler warning.
(def Cat (m/class "http://example.org/onto#Cat"))
(def Animal (m/class "http://example.org/onto#Animal"))
(def Felix (m/named-individual "http://example.org/onto#Felix"))

(def onto
  (-> (m/ontology "http://example.org/onto")
      (m/add-axiom (m/declaration Cat))
      (m/add-axiom (m/declaration Animal))
      (m/add-axiom (m/declaration Felix))
      (m/add-axiom (m/sub-class-of Cat Animal))
      (m/add-axiom (m/class-assertion Cat Felix))))

(validate/valid? (validate/validate onto))    ;=> true

(reason/inferred-types onto "http://example.org/onto#Felix")
;=> #{"http://example.org/onto#Cat" "http://example.org/onto#Animal"}

;; round-trip an axiom through the functional-syntax-mirroring EDN tree
(f/emit-axiom (m/sub-class-of Cat Animal))
;=> [:SubClassOf [:Class "http://example.org/onto#Cat"] [:Class "http://example.org/onto#Animal"]]

(= (m/sub-class-of Cat Animal) (f/parse-axiom (f/emit-axiom (m/sub-class-of Cat Animal))))
;=> true
```

## Follow-ups (v2, out of scope for this landing)

- **Full OWL 2 DL reasoning (SROIQ description logic)** -- genuinely
  research-grade, not a reasonable v1 scope. `owl.reason` implements only
  the three tractable graph closures described above; it does NOT do
  existential/cardinality/disjunction reasoning, tableau-based consistency
  checking, or classification. `owl.validate` only catches the specific,
  reasoner-free contradictions listed above -- a `valid?` ontology can still
  be DL-inconsistent in ways neither namespace can see.
- **RDF/XML and Turtle serialization** -- the
  [OWL 2 Mapping to RDF Graphs](https://www.w3.org/TR/owl2-mapping-to-rdf/)
  is a separate, much messier W3C document; conceptually deferred to
  [`kotoba-lang/org-w3-rdf`](https://github.com/kotoba-lang/org-w3-rdf) for
  the plain-triple view. Not implemented here.
- **The concrete Functional-Style Syntax TEXT grammar** -- `owl.functional`
  defines an EDN tree that mirrors the grammar's structure 1:1 and
  round-trips through it, but does not tokenize/parse the actual
  `SubClassOf(:Cat :Animal)` text, and does not resolve `Prefix(...)`
  directives or prefixed-name (`:Cat`) shorthand into full IRIs. A real
  text parser (and its Prefix-resolution pass) is real, separate scope.
- **OWL 2 profiles (EL/QL/RL) validation** -- not implemented; `owl.validate`
  checks structural well-formedness only, not profile membership.
- **SWRL rules** -- not modeled.
- **Datatype facets/restrictions beyond basic named datatypes** -- data
  ranges (sec 7) are, for v1, always just a named `Datatype` entity;
  `DataIntersectionOf`/`DataUnionOf`/`DataComplementOf`/`DataOneOf`
  (sec 7.1-7.4) and `DatatypeRestriction` facets (sec 7.5) are not modeled.
- **Anonymous individuals** (sec 5.6.2) -- not modeled; only
  `NamedIndividual` (sec 5.6.1) is supported.
- **`HasKey` (sec 9.5) and `DatatypeDefinition` (sec 9.4) axioms** -- not
  modeled.
- **Full annotation axioms** -- `owl.model` covers a minimal
  `Annotation`/`AnnotationAssertion` (sec 10.1, 10.2.1) only;
  `SubAnnotationPropertyOf`/`AnnotationPropertyDomain`/`AnnotationPropertyRange`
  (sec 10.2.2-10.2.4) are not modeled.
- **Metamodeling/punning consistency checking** (sec 5.9) -- punning itself
  (the same IRI legitimately typed as e.g. both `Class` and
  `NamedIndividual`) is respected by `owl.validate`'s declaration matching,
  but no further punning-specific semantic checks are performed.

## Test

```bash
kbb -M:test
```

## License

MIT.
