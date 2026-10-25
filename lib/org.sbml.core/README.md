# org-sbml

[![CI](https://github.com/kotoba-lang/org-sbml/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-sbml/actions/workflows/ci.yml)

**[SBML Level 3 Version 2 Core](https://sbml.org/specifications/sbml-level-3/version-2/core/release-2/sbml-level-3-version-2-release-2-core.pdf)
(the Systems Biology Markup Language) as EDN/Clojure data, in portable
`.cljc`.** A [kotoba-lang](https://github.com/kotoba-lang) `org-*` library:
the same pattern as `org-oasis-open-xmile`/`org-w3-webauthn`/`org-ietf-oauth2` --
a small, zero-third-party-dependency, portable implementation of an open
standard, pure data in, pure data out. [Systems biology](https://en.wikipedia.org/wiki/Systems_biology)
reaction-network modeling (chemical kinetics, gene regulation, signaling
pathways) is the domain; SBML is the interchange format most simulators
(COPASI, libRoadRunner, Tellurium, CellDesigner, ...) use for it. Spec
references below cite section numbers of "The Systems Biology Markup
Language (SBML): Language Specification for Level 3 Version 2 Core,
Release 2" (Hucka et al., 2019, *Journal of Integrative Bioinformatics*
16(2):20190021; [PDF](https://sbml.org/specifications/sbml-level-3/version-2/core/release-2/sbml-level-3-version-2-release-2-core.pdf)).

A model is compartments (containers), species (the quantities that change),
parameters (constants or extra variables), and reactions (the processes
that convert species into other species at a rate given by a kinetic law) --
e.g. `A -> B` at rate `k * [A]`: compartment `cell`, species `A` (initial
amount 100) and `B` (initial amount 0), parameter `k` (0.1), reaction with
one reactant (`A`), one product (`B`), and a kineticLaw `<apply><times/>
<ci>k</ci><ci>A</ci></apply>`. Unlike OASIS XMILE's infix `<eqn>` STRING
(see the sibling `org-oasis-open-xmile`), SBML's equation language is
**Content MathML** -- the `<math>` payload is already an XML tree, not text
to tokenize; `sbml.mathml` is this library's equation micro-language,
playing the combined role `xmile.expr` + `xmile.xml` play together for
XMILE. This library gives you the model as plain EDN, a Content-MathML
expr-tree bridge + pure evaluator, structural validation, and a fixed-step
Euler/RK4 simulator -- no vendor tool, no XML parser dependency (host
injects a parsed XML tree; see `sbml.xml`/`sbml.mathml`).

## Maturity

| | |
|---|---|
| Role | capability (data model + Content MathML equation language + validation + simulation) |
| Structural coverage | compartments, species, parameters, reactions (reactants/products/modifiers, kineticLaw + local parameters), rules (assignment/rate/algebraic), unit definitions, events -- round-trips through `sbml.xml` |
| Equation language | sec 3.4.1's MathML subset: `plus`/`minus`/`times`/`divide`/`power`/`root` (n-ary/qualifier-aware), comparisons, `and`/`or`/`not`, `abs`/`exp`/`ln`/`log`/`floor`/`ceiling`/trig, `piecewise`, the `time` csymbol, and `max`/`min` all evaluate; `factorial`/`quotient`/`rem`/`xor`/`implies`/`sec`/`csc`/`cot`/hyperbolic trig/non-`time` csymbols (`delay`/`rateOf`/`avogadro`) parse but do not evaluate (v2, see Follow-ups) |
| Simulation | species amounts via reaction stoichiometry, AssignmentRule/RateRule-governed species/parameters, Euler/RK4; AlgebraicRule, Event, and dynamically-sized compartments are not yet simulated (v2) |
| Tests | round-trip/property/analytic-reference coverage for every namespace |
| Runtime deps | `kotoba-lang/dsl-core` (validation-problem convention) only |

## Namespaces

- `sbml.mathml` -- the Content MathML equation micro-language: converts
  between an *already-parsed* MathML element (`{:tag :apply :attrs {}
  :content [...]}`, exactly what `clojure.data.xml`/`cljs.xml` produce) and
  an EDN expr tree, plus `eval-expr` (pure evaluator, sec 3.4 semantics).
  Both directions of this bridge live in one namespace because Content
  MathML *is* XML -- there is no separate tokenizer/parser step the way
  XMILE's infix-string `<eqn>` needs one.
- `sbml.model` -- the EDN schema (sec 4.2 Model; sec 4.5 Compartment; sec
  4.6 Species; sec 4.7 Parameter; sec 4.11 Reaction/SpeciesReference/
  KineticLaw/LocalParameter; sec 4.9 Rules; sec 4.4 UnitDefinition/Unit)
  plus threading-friendly builders and the structural queries
  `sbml.validate`/`sbml.execute` need.
- `sbml.xml` -- converts between an *already-parsed* SBML XML element tree
  and the `:sbml/*` EDN model (the rest of the model besides `<math>`,
  which it delegates to `sbml.mathml`). Does not parse XML text and does
  not cover SBML Level 3 packages (spatial, multi, comp, qual, ...),
  `<listOfFunctionDefinitions>`/`<listOfInitialAssignments>`/
  `<listOfConstraints>`, or `<notes>`/`<annotation>`.
- `sbml.validate` -- structural checks (duplicate identifiers in the shared
  SId namespace sec 3.3.1, dangling references, a kineticLaw referencing a
  species outside its own reaction sec 4.11.5, conflicting species
  initial-value attributes sec 4.6.4, empty reactant/product lists sec
  4.11.1, unknown/duplicate rule variables sec 4.9.3) returning
  `kotoba.dsl.problem`-shaped problems. `:error` means the model is not
  valid SBML; `:warn` means it's valid SBML but exercises a feature
  `sbml.execute` v1 doesn't simulate yet.
- `sbml.execute` -- a pure fixed-step simulator (Euler or classical RK4)
  over the species-amount ODE system implied by a model's reactions
  (mass-action-style extent equations, sec 4.11.7) plus AssignmentRule/
  RateRule-governed variables.

## Contract

```clojure
(require '[sbml.model :as m]
         '[sbml.validate :as validate]
         '[sbml.execute :as execute])

;; A -> B, rate = k * [A]  (k = 0.1 /s, A0 = 100)
(def decay
  (-> (m/model "decay")
      (m/add-compartment (m/compartment "cell" {:sbml/size 1.0}))
      (m/add-species (m/species "A" "cell" {:sbml/initial-amount 100.0
                                             :sbml/has-only-substance-units? true}))
      (m/add-species (m/species "B" "cell" {:sbml/initial-amount 0.0
                                             :sbml/has-only-substance-units? true}))
      (m/add-parameter (m/parameter "k" {:sbml/value 0.1}))
      (m/add-reaction
       (-> (m/reaction "r1")
           (assoc :sbml/reactants [(m/species-ref "A")]
                  :sbml/products [(m/species-ref "B")]
                  :sbml/kinetic-law (m/kinetic-law [:apply :times [[:ci "k"] [:ci "A"]]]))))))

(validate/valid? (validate/validate decay))   ;=> true

(def result (execute/run decay {:start 0.0 :stop 10.0 :dt 0.01 :method :rk4}))
(last (get-in result [:sbml/series "A"]))     ;=> 36.787944117144576 (100 * e^-1, matches analytically)
(:sbml/times result)                          ;=> [0.0 0.01 0.02 ... 10.0]
```

Reading a real `.xml`/`.sbml` file: parse the XML text with your host's XML
parser into `{:tag :sbml :attrs {...} :content [...]}` (e.g.
`clojure.data.xml/parse` on the JVM), then `(sbml.xml/parse-doc that-tree)`.

## Follow-ups (v2, out of scope for this landing)

- **All SBML Level 3 packages** (spatial, multi, comp, qual, fbc, layout,
  render, ...) -- Level 3 Core only.
- **`FunctionDefinition`/`InitialAssignment`/`Constraint`** -- not modeled;
  `<lambda>` (used only inside FunctionDefinition math) is consequently
  entirely unparseable by `sbml.mathml`, and species/compartment/parameter
  initial values must come from their own attributes, not an
  InitialAssignment expression.
- **MathML `csymbol`s other than `time`** (`delay`, `rateOf`, `avogadro`,
  sec 3.4.6) -- `sbml.mathml/parse` round-trips them as `[:csymbol url
  args]`; `eval-expr` throws a clear error. `delay`/`rateOf` need genuine
  historical/differential state a fixed-step evaluator doesn't carry in
  v1; `avogadro` is a trivial constant we simply haven't wired up yet.
- **MathML operators outside the implemented subset**: `factorial`,
  `quotient`, `rem`, `xor`, `implies`, `sec`/`csc`/`cot` and the full
  hyperbolic/inverse-hyperbolic trig family, `<semantics>`/`<annotation>`/
  `<annotation-xml>` wrappers -- parse into `[:apply-unsupported name
  args]` (so a model round-trips/validates), `eval-expr` throws. Chained
  N-ary relational operators (MathML permits `<leq/>` with 3+ operands
  meaning `a<=b<=c`) are also not implemented -- comparisons here are
  strictly binary.
- **`AlgebraicRule`** (sec 4.9.2) -- modeled as data (round-trips,
  validates), but full DAE/simultaneous-equation solving is out of scope;
  `sbml.execute/run` throws rather than guess.
- **`Event`** (sec 4.12) -- modeled as data (Trigger/Priority/Delay/
  EventAssignment all round-trip through `sbml.xml`), but discontinuous
  event-driven state changes are not simulated; `sbml.execute/run` throws.
- **Dynamically-sized compartments** -- a Compartment targeted by an
  AssignmentRule/RateRule round-trips/validates (as a `:warn`), but
  `sbml.execute` always treats compartment size as fixed at `:sbml/size`
  for the whole run (species amount<->concentration conversion, sec
  4.6.4/4.6.5/4.6.8, uses that fixed size) -- `run` throws rather than
  silently ignore a rule on a compartment.
- **Variable stoichiometry** (a SpeciesReference targeted by a Rule/
  InitialAssignment, sec 4.11.3) -- `sbml.execute` always uses a
  SpeciesReference's static `:sbml/stoichiometry` (default 1.0 if absent).
- **Reaction identifiers as math values** (sec 4.11.8: a reaction's own id
  stands for its rate and may be referenced elsewhere) -- `sbml.validate`
  recognizes this as spec-valid (not a dangling reference) but flags it
  `:warn :sbml/reaction-id-as-value`; `sbml.execute`'s evaluation
  environment does not expose reaction rates under their id (only in the
  `:sbml/series` output, for reporting).
- **Units dimensional analysis** (sec 3.6/4.4) -- `sbml.xml` round-trips
  `UnitDefinition`/`Unit` as structural data (`u_new = (multiplier *
  10^scale * u_kind)^exponent`, sec 4.4.2); no unit-consistency checking of
  species/compartment/parameter/math units is performed.
- **`conversionFactor`** (sec 4.6.7/4.2.6) -- round-trips as data; not
  applied when computing a reaction's effect on a species' amount.
- **`fast` reactions** -- moot: SBML Level 3 Version 2 removed the `fast`
  attribute entirely (every reaction's speed is determined by its
  KineticLaw), so there is nothing to model here.

## Test

```bash
kbb -M:test
```

## License

MIT.
