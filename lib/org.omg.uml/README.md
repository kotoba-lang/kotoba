# org-omg-uml

[![CI](https://github.com/kotoba-lang/org-omg-uml/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-omg-uml/actions/workflows/ci.yml)

**[OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/) (Unified Modeling
Language) as EDN/Clojure data, in portable `.cljc` -- scoped to v1's single
most defensible cut: the *Classes package* only (Class/Property/Operation/
Interface/Association/Generalization/Package/Enumeration/DataType/
Dependency, i.e. the structural class-diagram metamodel), with every
Behavior package (Activities, Interactions, UseCases, and especially
StateMachines) deliberately out of scope.** Full UML 2.5.1 spans 14 diagram
types across Structure and Behavior; attempting all of it shallowly would
be worse than a solid, honest Classes-only v1 -- the same
`org-*`-library pattern as `org-oasis-open-xmile`/`org-w3-webauthn`/
`org-ietf-oauth2`: a small, zero-third-party-dependency, portable
implementation of an open standard, pure data in, pure data out.
StateMachine in particular is not a temporary omission: `kotoba-lang/statechart`
already covers Harel-statechart-style state machines (UML StateMachine's
closest cousin and, for most modelers, a superior notation for the same
concept), so UML's own StateMachine package would only duplicate it -- see
Follow-ups.

Spec references below cite clause numbers of the
[OMG formal UML 2.5.1 specification](https://www.omg.org/spec/UML/2.5.1/PDF)
(`formal/17-12-05`). The Classes package is not one contiguous chapter in
the real spec -- it is assembled from clauses spread across four chapters:
Common Structure (clause 7: NamedElement/VisibilityKind sec 7.8.9/7.8.24,
MultiplicityElement sec 7.8.8, Dependency sec 7.7/7.8.4), Classification
(clause 9: Property sec 9.5/9.9.17, Operation/Parameter sec 9.6/9.9.11/
9.9.13, Generalization sec 9.9.7, AggregationKind sec 9.9.1), Simple
Classifiers (clause 10: DataType/Enumeration/EnumerationLiteral sec 10.5.2-
10.5.4, Interface/InterfaceRealization sec 10.4/10.5.5/10.5.6, PrimitiveType
sec 10.5.7), Structured Classifiers (clause 11: Class sec 11.4/11.8.3,
Association/AssociationClass sec 11.5/11.8.1/11.8.2), and Packages (clause
12: Package sec 12.2/12.4.5). The standard PrimitiveTypes library (Integer/
Boolean/String/UnlimitedNatural/Real) is its own clause 21.

A model is a UML::Package (sec 12.2/12.4.5) -- e.g. two Classes, `Person`
and `Employee`, related by a Generalization (sec 9.9.7), plus an
Association (sec 11.5/11.8.1) from `Employee` to an `Employer` Class with
per-end multiplicity, aggregation, and navigability (sec 11.5.3.1 -- UML's
most subtle structural concept). This library gives you that model as
plain EDN, structural validation, and a pragmatic XMI (XML Metadata
Interchange) subset for round-tripping through the generic parsed-XML-
element shape a host XML parser produces -- no vendor tool, no XML parser
dependency, no execute/simulate layer (a class model is a static structural
description, not something you run).

## Maturity

| | |
|---|---|
| Role | data model (Classes package only) + XMI subset + structural validation |
| Structural coverage | Class, Property/attribute, Operation/Parameter, Interface, Association (incl. AssociationClass), Generalization, Package (real nesting), Enumeration/EnumerationLiteral, DataType/PrimitiveType, Dependency (incl. Usage/Abstraction) -- round-trips through `uml.xml` |
| Out of scope | every Behavior package (Activities/Interactions/UseCases/StateMachines) and most non-Classes Structure clauses (Components, Composite Structures, Profiles, PowerTypes/GeneralizationSet, Templates) -- see Follow-ups |
| Tests | round-trip/property coverage for every namespace |
| Runtime deps | `kotoba-lang/dsl-core` (validation-problem convention) only |

## Namespaces

- `uml.model` -- the EDN schema (`:uml/*` namespaced keys) for Package/
  Class/Interface/Property/Operation/Parameter/Association/
  AssociationClass/Generalization/Enumeration/DataType/PrimitiveType/
  Dependency, plus threading-friendly builders and the structural queries
  `uml.validate` needs: `attributes-of`, `operations-of`,
  `generalizations-of`, `all-supertypes` (transitive closure over
  Generalization), `associations-touching`. Package nesting is real
  (`:uml/packaged-element` can hold further `:package` elements, sec
  12.4.5.6), but v1 resolves type/general/memberEnd references by simple
  classifier NAME across the whole model, not a fully-qualified path (sec
  7.4.3 qualifiedName resolution is not modeled -- see Follow-ups).
- `uml.xml` -- converts between an *already-parsed* XMI element tree
  (`{:tag :packagedElement :attrs {:xmi:type "uml:Class" :name "..."}
  :content [...]}`, exactly what `clojure.data.xml`/`cljs.xml` already
  produce) and the `:uml/*` EDN model. Does not parse XML text. Models a
  PRAGMATIC SUBSET of real XMI, not full XMI 2.x conformance -- see
  Follow-ups for the concrete gaps (no `xmi:id`/`xmi:idref`, navigability
  stored as an explicit flag rather than derived from end-ownership, etc).
- `uml.validate` -- structural checks (dangling type/classifier references,
  a Generalization-graph cycle check -- the same white/gray/black DFS
  technique as `xmile.validate`'s algebraic-loop check, applied to the
  Generalization graph instead of a flow/aux equation graph -- duplicate
  member names, an Interface owning an attribute, too-few Association
  ends, AssociationClass's disjoint-names constraint) returning
  `kotoba.dsl.problem`-shaped problems. `:error` means the model is
  structurally invalid; `:warn` means it's legal per the metamodel but
  this validator opinionatedly flags it (see the Interface/attribute note
  below).

This library has no execute/simulate namespace (unlike
`org-oasis-open-xmile`'s `xmile.execute`) -- a UML class model is a static
structural description with no natural "run" semantics to force onto it.

## Contract

```clojure
(require '[uml.model :as m]
         '[uml.validate :as validate])

(def person
  (-> (m/class "Person")
      (m/add-attribute (m/property "name" "String"))))

(def employer (m/class "Employer"))

(def employee
  (-> (m/class "Employee")
      (m/add-generalization "Person")))            ; sec 9.9.7

(def works-at
  (m/association "WorksAt"                          ; sec 11.5/11.8.1
                 [(m/assoc-end "employee" "Employee" {:uml/upper :*})
                  (m/assoc-end "employer" "Employer" {:uml/navigable? false
                                                       :uml/aggregation :shared})]))

(def model
  (-> (m/package "demo")
      (m/add-element person)
      (m/add-element employer)
      (m/add-element employee)
      (m/add-element works-at)))

(validate/valid? (validate/validate model))          ;=> true

(m/all-supertypes model "Employee")                   ;=> #{"Person"}
(map :uml/name (m/associations-touching model "Employer")) ;=> ("WorksAt")
```

Reading a real `.xmi` file: parse the XML text with your host's XML parser
into `{:tag :uml:Model :attrs {...} :content [...]}` (e.g.
`clojure.data.xml/parse` on the JVM), then `(uml.xml/parse-doc that-tree)`.

## Follow-ups (v2, out of scope for this landing)

**Entire Behavior packages, deliberately out of scope for a structural
library** (all 13 non-Class diagram types):

- **State Machines** (clause 14) -- permanently deferred, not just
  "not yet done": `kotoba-lang/statechart` already implements
  Harel-statechart-style state machines, UML StateMachine's closest
  cousin, so adding UML's own StateMachine metamodel here would only
  duplicate that library.
- **Activities** (clause 15, incl. Activity Diagram) -- control/data-flow
  behavior modeling.
- **Interactions** (clause 17) and its four diagram notations -- Sequence
  Diagram, Communication Diagram, Interaction Overview Diagram, Timing
  Diagram.
- **Use Cases** (clause 18, Use Case Diagram).
- **Common Behavior** (clause 13) -- the shared behavior/signal/event
  infrastructure those packages build on.
- **Component Diagram** notation over Components (clause 11.6 -- the
  `:uml/kind` data for Components is not modeled at all, only Classes).
- **Composite Structure Diagram** (clause 11.2/11.3/11.7 -- Structured
  Classifiers, Encapsulated Classifiers, Ports, Connectors,
  Collaborations).
- **Deployment Diagram** (clause 19 -- Nodes, Artifacts, Deployments).
- **Object Diagram** (instance-level snapshots -- clause 9.8
  InstanceSpecification/Slot/InstanceValue are not modeled).
- **Package Diagram** notation and **Profile Diagram** (clause 12.3 --
  Profile/Stereotype/Extension/ProfileApplication/PackageMerge; `uml.model`
  supports plain Package nesting but not the profile-extension mechanism).

**Structural (Classes-adjacent) gaps within v1's own scope:**

- **GeneralizationSet / PowerTypes** (sec 9.7) -- disjoint/complete
  generalization-set semantics and PowerType are not modeled; only the
  bare Generalization general/specific edge (sec 9.9.7).
- **Templates** (clause 7.3, `TemplateableElement`/`TemplateParameter`) --
  template Classifiers/Operations/Packages and their bindings.
- **Qualified associations and n-ary (>2-end) Associations** -- `assoc-end`
  has no qualifier support (sec 9.9.17.6 `qualifier`), and the library does
  not special-case Associations with more than two ends beyond the bare
  `association-end-count-problems` `[2..*]` sanity check.
- **Operation overloading by signature** -- `uml.validate`'s
  `duplicate-member-problems` flags any two Operations sharing a name on
  one Classifier, even though real UML (sec 9.4.3) permits overloading
  distinguished by parameter-list signature; v1 does not compare
  signatures.
- **Redefinition/subsetting semantics** (`isConsistentWith`,
  `subsettedProperty`, `redefinedOperation`, etc.) -- structurally these
  fields simply are not represented; only the plain owning/typing/
  generalization/multiplicity/aggregation facts are.
- **Substitution** (sec 9.9.22) and **Reception/Signal** (sec 10.3, 10.5.8-9)
  are not modeled.
- **Qualified-name resolution across nested Packages** (sec 7.4.3) --
  `uml.model` resolves every classifier reference by simple name across
  the WHOLE flattened model (see `all-elements`), assuming global
  uniqueness; two same-named Classifiers in different nested Packages are
  not distinguished.

**XMI conformance gaps** (see `uml.xml` namespace docstring for the full
rationale on each):

- No `xmi:id`/`xmi:idref` cross-reference resolution -- references are
  plain classifier-name strings, so `uml.xml` output round-trips through
  itself but is not guaranteed to import into a real XMI-conformant tool
  (Papyrus/MagicDraw/Enterprise Architect) without an adapter.
  Correspondingly, there is no `xmi:XMI` envelope or `xmlns:*` namespace
  declaration handling.
  - Association end **navigability** is stored as an explicit boolean flag
  per end rather than derived from WHERE the end Property is owned (sec
  11.5.3.1's real navigableOwnedEnd-vs-class-owned distinction).
- **Multiplicity** is flattened to `lower`/`upper` attributes directly on
  the owning element rather than nested `lowerValue`/`upperValue`
  `uml:LiteralInteger`/`uml:LiteralUnlimitedNatural` child elements (sec
  7.8.8.6), which is what conformant tools typically emit.
- No **Diagram Interchange** (`uml:Diagram`/notation/geometry) layer --
  this library is data-only, matching `xmile.xml`'s choice to skip
  XMILE's `<views>`/`<style>` display layer for the same reason (a
  conformant consumer of the underlying model does not need it).

## Test

```bash
kbb -M:test
```

## License

MIT.
