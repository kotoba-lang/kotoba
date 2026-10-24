# org-omg-sysmlv2

[![CI](https://github.com/kotoba-lang/org-omg-sysmlv2/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-omg-sysmlv2/actions/workflows/ci.yml)

**A scoped subset of [OMG SysML v2](https://www.omg.org/sysml/sysmlv2/)
(Systems Modeling Language) as portable EDN/Clojure data, built via
threading-friendly Clojure builder functions and a strict textual-syntax
compatibility parser.** `sysml.text` parses and emits the normative notation
for the structural element kinds represented by this library. SysML v2's
complete `.sysml` grammar is much larger; syntax not yet interpreted
semantically is retained explicitly as `:opaque-syntax` token AST and emits
again rather than being silently discarded (see Follow-ups).

SysML v2 layers on top of **KerML** (Kernel Modeling Language), an
application-independent kernel with formal semantics. `sysml.kerml` models
KerML's `Type`/`Classifier`/`Feature`/`Specialization`/`Featuring`/
`Multiplicity`; `sysml.model` builds SysML's signature **Definition/Usage
duality** on top of it (a `Definition` is a reusable type, a `Usage` is an
occurrence of one in context -- e.g. a `Vehicle` PartDefinition nests an
`engine` PartUsage typed by an `Engine` PartDefinition, which nests a
`fuelIn` PortUsage typed by a `FuelPort` PortDefinition).

**Sources.** The formal specifications were adopted 2025-07-21 and
editorially updated 2026-03 for ISO submission:
[KerML 1.0](https://www.omg.org/spec/KerML/1.0/PDF) (OMG document
formal/26-03-01), [SysML 2.0 Language](https://www.omg.org/spec/SysML/2.0/Language/PDF)
(formal/26-03-02), and its companion
[Transformation spec](https://www.omg.org/spec/SysML/2.0/Transformation/PDF)
(formal/26-03-03) -- see the [OMG SysML v2 page](https://www.omg.org/sysml/sysmlv2/)
and [About-KerML](https://www.omg.org/spec/KerML/1.0/About-KerML)/
[About-SysML](https://www.omg.org/spec/SysML/2.0/About-SysML). Precise
structural shape (which attributes/references each class actually has) is
ground-truthed against the open-source
[SysML-v2-Pilot-Implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation)'s
Ecore metamodels -- `org.omg.sysml/model/kerml.ecore` and
`org.omg.sysml.model/src/main/resources/model/SysML.ecore` -- whose embedded
`eAnnotations` documentation reproduces spec-clause-level prose per class.
Source code docstrings in this library cite the specific ecore file and
approximate line number for each concept's structural shape.

## Maturity

| | |
|---|---|
| Role | data model (KerML kernel + SysML Definition/Usage elements + structural validation) |
| Concrete syntax | `sysml.text/parse-string` + `emit-string`: packages/import visibility; qualified and unrestricted names; represented Definitions and typed/untyped Usages; nesting; specialization/subsetting/redefinition; conjugated types; fixed/range/unbounded multiplicity; dotted references; connection/interface `connect … to …`; uninterpreted behavior/state/transition/expression/metadata syntax is retained as opaque token AST |
| KerML coverage | `Type`/`Classifier`/`Feature`/`Specialization`/`Featuring`/`Multiplicity`, plus `Conjugation` |
| SysML coverage | `Package`, `PartDefinition`/`Usage`, `AttributeDefinition`/`Usage`, `PortDefinition`/`Usage`, `ConnectionDefinition`/`Usage`, `InterfaceDefinition`/`Usage`, `ItemDefinition`/`Usage`, `ActionDefinition`/`Usage` (structural only), `RequirementDefinition`/`Usage` (subject/actor/required-constraint, satisfy/verify structural traceability) |
| Behavior/requirements semantics | structural only -- no execution, no constraint solving, no requirements-verification reasoning (see Follow-ups) |
| Tests | builder/query coverage for every namespace, incl. specialization-closure and validation error/warning classification |
| Runtime deps | `kotoba-lang/dsl-core` (validation-problem convention) only |

## Namespaces

- `sysml.kerml` -- the KerML 1.0 kernel EDN schema (`:kerml/*` keys):
  `Type`/`Classifier`/`Feature` element builders, `Specialization`/
  `Featuring`/`Conjugation` relationship builders, and queries including
  `all-supertypes` (a DFS/worklist closure over Specialization, mirroring
  KerML's own `Type::allSupertypes()` operation).
- `sysml.model` -- the SysML-level EDN schema (`:sysml/*` keys) built on
  top of `sysml.kerml` types: every Definition is a `kerml/classifier`,
  every Usage a `kerml/feature`, tagged with `:sysml/element-kind`.
  Threading-friendly builders for all covered Definition/Usage pairs plus
  `Package`, and structural queries (`definition-of`, `nested-usages`/
  `all-nested-usages`, `all-supertypes` re-exported for Definition-to-
  Definition generalization chains).
- `sysml.validate` -- structural checks returning `kotoba.dsl.problem`-
  shaped problems: wrong-kind locally resolved Definition references, illegal
  Specialization cycles (DFS white/gray/black), out-of-range Multiplicity
  bounds, dangling Connection/Interface ends, and `:warn`-level scope-out
  notices for Action elements and satisfy/verify relationships.
- `sysml.text` -- dependency-free parser/emitter for the explicit concrete-
  syntax subset listed in the maturity table. Comments and arbitrary
  whitespace are accepted. Source order is retained. Grammar outside the
  semantic subset becomes a validator-visible `:opaque-syntax` element and
  round-trips without being mistaken for an interpreted model element.

## Contract

```clojure
(require '[sysml.model :as sm]
         '[sysml.validate :as validate])

(def vehicle-model
  (-> (sm/model "vehicle-model")
      (sm/add-element (sm/port-definition "FuelPort"))
      (sm/add-element (sm/part-definition "Engine"))
      (sm/add-element (sm/port-usage "fuelIn" "FuelPort"))
      (sm/add-element (-> (sm/part-usage "engine" "Engine")
                           (sm/nest "fuelIn")))               ; engine owns a nested Port
      (sm/add-element (-> (sm/part-definition "Vehicle")
                           (sm/nest "engine")))))              ; Vehicle owns a nested Part

(validate/valid? (validate/validate vehicle-model))  ;=> true

(sm/definition-of vehicle-model "engine")   ;=> the Engine PartDefinition map
(sm/all-nested-usages vehicle-model "Vehicle")  ;=> #{"engine" "fuelIn"}
```

The corresponding textual boundary:

```clojure
(require '[sysml.text :as text])

(def vehicle-model
  (text/parse-string
   "package Vehicles {
      port def FuelPort;
      part def Engine { port fuelIn : FuelPort; }
      part def Vehicle { part engine : Engine; }
    }"
   "vehicle-model"))

(text/emit-string vehicle-model)
```

## Follow-ups (v2, out of scope for this landing)

- **Complete textual concrete syntax** -- the supported structural subset
  is parsed and emitted by `sysml.text`. Expressions, behaviors, states,
  transitions, flows, metadata annotations and feature values are now
  preserved as opaque token AST but are not yet mapped to semantic
  `sysml.model` element kinds; general multiplicity expressions and the
  remainder of the normative grammar are likewise not semantically
  interpreted. The authoritative grammar is the Pilot Implementation's
  `SysML.xtext`; each added production should land with a normative example
  fixture and round-trip test.
- **Action/behavior execution semantics** -- `ActionDefinition`/
  `ActionUsage` are modeled as data only (structurally, like any other
  Definition/Usage pair); no control-flow/execution engine.
- **Requirements verification/satisfaction reasoning** -- `satisfy`/
  `verify` relationships are modeled as named structural elements only
  (`sysml.model/satisfy-requirement-usage`/`verify-requirement-usage`); no
  requirements-traceability engine evaluates them. A real `VerificationCase`
  concept (KerML `RequirementVerificationMembership`) is not modeled.
- **Constraint solving** -- `RequirementDefinition`/`Usage`'s required
  constraints are plain expression strings (`:sysml/required-constraints`),
  and Analysis/Calculation/Constraint Definitions generally are not
  modeled as their own element kinds; no constraint solver.
- **Views/Viewpoints** and any **graphical/diagram notation** -- not
  modeled, matching this library's data-only scope.
- **Multiplicity bound expressions** -- KerML's real `Multiplicity` bounds
  are `Expression` trees (so a bound can itself be computed); this library
  simplifies bounds to plain integers.
- **Port conjugation semantics** -- `sysml.kerml/conjugate` records a
  `Conjugation` relationship structurally, but does not automatically
  flip Feature `direction` the way real KerML conjugation does.

## Test

```bash
kbb -M:test
kbb -M:conformance  # official OMG Simple Vehicle Model
```

See [`MATURITY.md`](MATURITY.md) for denominator-based percentages. The
official example currently has 100% syntax acceptance and token-AST
round-trip; semantic element coverage is reported separately and is not
called 100% while opaque elements remain.

## License

MIT.
