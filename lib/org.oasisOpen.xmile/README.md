# org-oasis-open-xmile

[![CI](https://github.com/kotoba-lang/org-oasis-open-xmile/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-oasis-open-xmile/actions/workflows/ci.yml)

**[OASIS XMILE 1.0](https://www.oasis-open.org/standard/xmile1-0/)
(the XML Interchange Language for System Dynamics) as EDN/Clojure data, in
portable `.cljc`.** A [kotoba-lang](https://github.com/kotoba-lang) `org-*`
library: the same pattern as `org-w3-webauthn`/`org-ietf-oauth2`/`org-ros` --
a small, zero-third-party-dependency, portable implementation of an open
standard, XML text or pure data in, pure data out. [System dynamics](https://en.wikipedia.org/wiki/System_dynamics)
(Jay Forrester's stock-and-flow modeling method) is the domain; XMILE 1.0
(approved as an OASIS Standard 2015-12-14) is the interchange format
Stella/iThink, insightmaker and others use for it. Spec references below
cite section numbers of the [OASIS Standard HTML](http://docs.oasis-open.org/xmile/xmile/v1.0/os/xmile-v1.0-os.html)
(also available as [PDF](http://docs.oasis-open.org/xmile/xmile/v1.0/os/xmile-v1.0-os.pdf)
and [XSD](http://docs.oasis-open.org/xmile/xmile/v1.0/os/schemas/xmile.xsd)).

A model is stocks (accumulators), flows (rates of change into/out of a
stock) and auxiliaries (algebraic converters), wired by equations in a
small infix micro-language (sec 3.3) -- e.g. a bathtub: `Inventory` (stock,
initial 100) filled by `Production` (flow, 10/step) and drained by
`Shipping` (flow, `Inventory / 4`). This library gives you that model as
plain EDN, a parser+evaluator for the equation language, structural
validation, and a fixed-step Euler/RK4 simulator -- no vendor tool, no XML
parser dependency (host injects a parsed XML tree; see `xmile.xml`).

## Maturity

| | |
|---|---|
| Role | capability (data model + equation language + validation + simulation) |
| Structural coverage | header, sim_specs, model_units, dimensions, model/variables (stock/flow/aux), gf -- namespaced UTF-8 XML text and element trees round-trip through `xmile.xml`; stock inflow/outflow priority is retained; module/group/views/macro and other unimplemented standard elements survive as raw extensions |
| Equation language | full sec 3.3 grammar/precedence; sec 3.5.1 math + sec 3.5.4 test-input built-ins evaluate; sec 3.5.3 `DELAY1`/`DELAY3`/`SMTH1`/`SMTH3`/`TREND` evaluate via model-level hidden-stock desugaring (`xmile.execute/desugar-delays`); sec 3.5.2 (stochastic) and the remaining sec 3.5.3 (`DELAY`/`DELAYN`/`SMTHN`/`FORCST`) parse but do not evaluate (v2, see Follow-ups) |
| Simulation | scalar stocks, `:euler`/`:rk4`, non-negative clamping, sec 3.5.3 hidden-stock built-ins; parameters (variable-free auxes) evaluated once per run, not once per sub-step; conveyor/queue transport and arrays are not yet simulated (v2) |
| Tests | round-trip/property coverage for every namespace; analytic (closed-form-vs-simulated) verification for the exponential-delay/smooth/Erlang-3/trend built-ins |
| Runtime deps | `kotoba-lang/dsl-core` (validation-problem convention) only |
| Kotoba | the equation language and every number in a simulation step ported to `kotoba/xmile_expr_core.kotoba`, held to `xmile.expr`/`xmile.execute` by three parity gates; the parser, the dependency ordering and the time loop are not ported; `.cljc` remains the authority and the load path |

## Namespaces

- `xmile.model` -- the EDN schema (sec 3.1 stock/flow/aux, sec 3.7.1
  sim_specs, sec 3.2.2 gf) plus a threading-friendly builder and the
  structural queries `xmile.validate`/`xmile.execute` need.
- `xmile.expr` -- the equation micro-language: `parse` (string -> EDN expr
  tree, sec 3.3 grammar/precedence) and `eval-expr` (pure evaluator, sec
  3.5 built-ins).
- `xmile.xml` -- converts between an *already-parsed* XML element tree
  (`{:tag :stock :attrs {...} :content [...]}`, compatible with
  `clojure.data.xml`/`cljs.xml`) and the `:xmile/*` EDN model. It also
  provides `parse-string`/`emit-string` for complete XML text; the JVM
  parser disables DTDs, external entities and XInclude. Emitted documents
  carry the required XMILE 1.0 version and namespace. It does not cover the
  diagram/display layer (`<views>`/`<style>`). Elements not yet interpreted
  by the runtime—including module/group/views/macro—are retained under
  `:xmile/extensions` or `:xmile/variable-extensions` and emitted again.
- `xmile.validate` -- structural checks (dangling references, illegal
  algebraic loops, malformed `sim_specs`/`gf`, unknown flow references)
  returning `kotoba.dsl.problem`-shaped problems. `:error` means the model
  is not valid XMILE; `:warn` means it's valid XMILE but exercises a
  feature `xmile.execute` v1 doesn't simulate yet. `validate-doc` additionally
  checks whole-document header/model/simulation-spec requirements and applies
  global `sim_specs` to models that do not override them.
- `xmile.execute` -- a pure fixed-step simulator (Euler or classical RK4)
  over the stock ODE system defined by the model's flow/aux network.
  `desugar-delays` implements sec 3.5.3 `DELAY1`/`DELAY3`/`SMTH1`/`SMTH3`/
  `TREND` by rewriting the model once up front, adding the hidden stock(s)
  each needs (exactly how Stella/Vensim implement them internally -- see
  its docstring for the construction and citations), so the rest of the
  Euler/RK4 machinery runs over the enlarged variable set unmodified.

## Contract

```clojure
(require '[xmile.model :as m]
         '[xmile.validate :as validate]
         '[xmile.execute :as execute])

(def bathtub
  (-> (m/model "bathtub" {:xmile/sim-specs (m/sim-specs 0.0 40.0 {:xmile/dt 1.0})})
      (m/add-variable (m/stock "Inventory" "100"
                                {:xmile/inflows #{"Production"} :xmile/outflows #{"Shipping"}}))
      (m/add-variable (m/flow "Production" "10"))
      (m/add-variable (m/flow "Shipping" "Inventory / 4"))))

(validate/valid? (validate/validate bathtub))   ;=> true

(def result (execute/run bathtub))
(get-in result [:xmile/series "Inventory"])     ;=> [100.0 92.5 86.375 ... converges to 40.0]
(:xmile/times result)                           ;=> [0.0 1.0 2.0 ... 40.0]
```

Reading or writing a real `.xmile` file:

```clojure
(require '[xmile.xml :as xml])

(def doc (xml/parse-string (slurp "model.xmile")))
(spit "round-trip.xmile" (xml/emit-string doc))
```

Hosts that already own XML parsing can continue to call `parse-doc` with an
element tree and `emit-doc` to receive one.

Sec 3.5.3 `DELAY1`/`DELAY3`/`SMTH1`/`SMTH3`/`TREND` work directly as a
variable's own equation -- no extra stock/flow wiring needed, `xmile.execute`
adds the hidden stock(s) internally:

```clojure
(def perceived
  (-> (m/model "perceived-rate" {:xmile/sim-specs (m/sim-specs 0.0 30.0 {:xmile/dt 0.1 :xmile/method :rk4})})
      (m/add-variable (m/aux "Perceived_Rate" "SMTH1(STEP(10, 2), 3)"))))

(get-in (execute/run perceived) [:xmile/series "Perceived_Rate"])
;=> [0.0 0.0 ... exponentially approaches 10.0 after t=2]
```

## Kotoba decision core

`src/xmile/expr.cljk` binds every one of XMILE's sec 3.5.1 math built-ins to a
host function -- `Math/exp` on the JVM, `js/Math.exp` on ClojureScript, sixteen
reader conditionals in all. That is the whole of XMILE's numeric semantics
resting on interop, and it is why the equation language could not be evaluated
anywhere but a JVM or a JavaScript engine.

`kotoba/xmile_expr_core.kotoba` carries the same semantics with no host math
library underneath it: the transcendentals are fixed polynomial kernels in the
Kotoba compiler's own f64 intrinsics, and the module sits in the `kotoba/pure`
profile -- no capabilities, no ambient authority. It is **the whole of
`xmile.expr/eval-expr`**, in two halves:

- **the operations** -- the sec 3.5.1 math built-ins, `^` and floored `MOD`,
  all six relational and three logical operators (XMILE has no boolean type;
  zero is false), and the sec 3.5.4 `STEP`/`RAMP`/`PULSE` test inputs.
- **the walk** -- the expression tree as a sealed recursive value
  (`:xmile/expr`) and the environment as a typed map, evaluated to
  `[:result :f64 :string]`. Errors are values here, not exceptions: that is one
  of the two constraints this language holds as permanent rather than
  provisional.
- **the simulation step** -- binding one non-stock variable's clamped value
  into the environment (sec 3.1.2), taking a stock's inflows minus its outflows
  (sec 3.1.1), and the Euler and RK4 state updates (sec 3.7.1).

The walk preserves the parts of `eval-expr` that are *semantics* rather than
implementation: `IF` evaluates one branch, `AND`/`OR` short-circuit, a refused
built-in (`DELAY1`, `RANDOM`) is refused before its arguments are evaluated, and
the environment is consulted before the reserved `PI`/`INF` table so a model
that binds `PI` gets its own value. Each of those is a separate test, and each
was shown to turn the gate red on its own.

What is still `.cljc`, and on purpose: the tokenizer and parser
(`xmile.expr/parse`), `xmile.xml`, `xmile.validate`, and -- inside
`xmile.execute` -- `topo-order`, `desugar-delays`, `constant-names`, the time
loop, and the iteration over variables and stocks. Deriving the evaluation
order is a graph colouring that also proves the model has no algebraic loop; it
is a different kind of claim from anything the port makes.

A model still cannot be simulated without a JVM or a JavaScript engine. What
moved is every number in a simulation step.

One measured ceiling, stated because it is the honest limit of the third
bullet: a value crossing this boundary is checked against fixed budgets
(`adt-node-limit` 64, `adt-depth-limit` 12, `typed-map-entry-limit` 31), and a
linked list costs two levels per link, so **a list of six names is refused**.
The port therefore takes one call per quantity rather than one per step, and a
stock with six or more inflows cannot have them summed in one call. The failure
is clean -- the boundary refuses, nothing computes a wrong number -- and there
is a test that pins the number so it cannot drift quietly.

One current-state note, because it is a constraint and not a design choice: the
environment holds `f64-to-bits` patterns in a `[:map :string :i64]` because
`[:map :string :f64]` is rejected today (*direct floating map keys or values are
outside the structured scalar ABI*). The conversion is exact in both directions
-- signed zero and NaN payloads survive, and there is a test that says so -- and
two functions know about it, so widening the ABI is a two-function change.

**`src/xmile/expr.cljk` is unchanged, and remains both the authority and the
thing consumers load.** The port proves the logic is expressible; it does not
replace it. Two gates compile the port and run it through the KIR interpreter in
the same JVM, asserting against the real `xmile.expr`:

- `test/xmile/kotoba_expr_core_parity_test.cljk` -- the operations, one at a time.
- `test/xmile/kotoba_eval_expr_parity_test.cljk` -- the walk. Every case there
  starts from an equation *string* and runs the real `xmile.expr/parse` over it,
  so the trees under test are the ones the parser actually produces.
- `test/xmile/kotoba_simulation_parity_test.cljk` -- the step. This one is
  `xmile.execute/run`'s own loop with every number in it coming from the port,
  asserted against `xmile.execute/run` over whole trajectories: five models,
  every recorded variable at every recorded time, and equality rather than a
  tolerance wherever no transcendental is involved -- RK4 included. A
  *mathematically identical* reassociation of the RK4 weighting turns exactly
  the two RK4 models red and leaves the Euler ones green, which is what makes
  the bit-exactness claim mean something.

Both keep the same two halves apart -- exactly where the two agree, and exactly
where they do not:

- **exact** -- `ABS` `SQRT` `INT` `MIN` `MAX` `MOD`, the relational and logical
  operators, `PI` `INF`, `STEP` `RAMP` `PULSE`. A one-ulp difference here would
  be a defect.
- **within 1e-12 relative** -- `EXP` `LN` `LOG10` `SIN` `COS` `TAN` `ARCSIN`
  `ARCCOS` `ARCTAN` and `^`. Bit equality is not available against a host math
  library and claiming it would be a lie; the worst error observed across the
  corpus is 1.276e-13 (`TAN` at 1000.25, where sin's and cos's wide-angle
  reduction errors compound through the quotient). Every run prints the table.
- **narrower on purpose** -- the port traps where the host returns a non-finite
  value (`LN(0)`, `EXP(1000)`, `ARCSIN(2)`), which is fail-closed and better,
  and *also* traps beyond `|angle| <= 8192*pi` where `Math/sin` reduces fine,
  which is a gap in the port and is pinned as one.

Qualified today on the `kotoba-wasm` and `kotoba-script` backends, which is
where the f64 transcendental intrinsics are emitted. The two native backends
emit f64 arithmetic but no `exp`/`log`/`sin`/`cos`/`atan2`; that is an
implementation gap in a backend, not a ceiling of the language, so nothing in
the port is shaped around avoiding it.

```bash
kbb -M:test -n xmile.kotoba-expr-core-parity-test
kbb -M:test -n xmile.kotoba-eval-expr-parity-test
kbb -M:test -n xmile.kotoba-simulation-parity-test
```

## Follow-ups (v2, out of scope for this landing)

- **Stochastic built-ins** (sec 3.5.2: `RANDOM`/`NORMAL`/`EXPRND`/
  `LOGNORMAL`/`POISSON`) -- `xmile.expr/parse` accepts calls to them (so a
  model round-trips and validates structurally); `eval-expr` throws, and
  `xmile.validate` flags them as a `:warn`. A real implementation needs a
  host-injected seeded-RNG port (a design decision -- which port shape,
  whether/how seeds are threaded through the model -- this landing doesn't
  make).
- **`DELAY`/`DELAYN`/`SMTHN`/`FORCST`** (the rest of sec 3.5.3 --
  `DELAY1`/`DELAY3`/`SMTH1`/`SMTH3`/`TREND` ARE implemented, see Maturity
  above and `xmile.execute/desugar-delays`) -- `DELAY`/`DELAYN`/`SMTHN` are
  the same hidden-stock-cascade construction but with an arbitrary
  order/delay-time-per-stage `N` (`DELAY1`/`DELAY3`/`SMTH1`/`SMTH3` are the
  fixed `N`=1/3 special cases this landing built); `FORCST` extrapolates a
  TREND-derived growth rate forward over a horizon. Same `:warn` treatment
  as the stochastic built-ins in the meantime.
- **Conveyor/queue stock transport** (sec 3.7.2/3.7.3) -- modeled as data
  in `xmile.model`/round-trips through `xmile.xml`, but `xmile.execute`
  throws rather than approximate their transit-time/discrete-slot
  mechanics silently. A conveyor's discrete-in-substance slug-queue
  transport is a genuinely different execution model from the scalar-ODE
  Euler/RK4 loop above (not just another hidden-stock ODE, unlike this
  landing's DELAY1/DELAY3/SMTH1/SMTH3/TREND), so it's left as a dedicated
  follow-up rather than approximated.
- **Arrays / dimensioned variables** (sec 4.5) -- `xmile.xml` models
  `<dimensions>` structurally; per-element/apply-to-all array equations
  are not evaluated by `xmile.execute`.
- **Units dimensional analysis** (sec 3.6) -- `xmile.xml` round-trips unit
  definitions and aliases as data; no unit-consistency checking of
  variable equations is performed.
- **Submodels/modules and macros** (sec 3.7.4) -- not modeled.
- **Diagram/display layer** (`<views>`, `<style>`) -- deliberately out of
  scope; sec 3.7.5 states a conformant simulator does not need it.
- Integration methods `rk2`/`rk45`/`gear` (sec 3.7.1 allows them) -- only
  `euler`/`rk4` are implemented.

## Test

```bash
kbb -M:test
kbb -M:conformance  # official OASIS XMILE 1.0 XSD
```

See [`MATURITY.md`](MATURITY.md) for denominator-based percentages. XSD
validity, structural preservation, semantic coverage and executable coverage
are tracked separately.

## License

MIT.
