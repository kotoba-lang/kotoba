# oak

OaK's portable ontology execution adapters are consumable as a pinned Git
dependency. `deps.edn` exposes `src/oak/semantic.cljk` together with the exact
Datalog, datom source, OWL 2 RL rules, and SPARQL engine revisions used by the
adapter; downstream runtimes do not need to reconstruct that classpath.

**OaK — the ontology as the kernel.** An agent does not act on the graph. It
hands `oak-call` a typed value naming what it wants, and a schema decides
whether that is a thing the world admits. Written in Kotoba, compiled by amu,
with the graph behind the `dataspace/transact` capability.

The name is a metaphor, so: this is not a library of ontology helpers, and it
is not [OAK, the Ontology Access Kit](https://github.com/INCATools/ontology-access-kit).
It is a **syscall table whose admission rule is an ontology**.

```
       agent                     kernel                        world
  ┌──────────────┐        ┌────────────────────┐        ┌──────────────┐
  │ a value of   │ ─────► │  S   entity types  │ ─────► │  dataspace   │
  │ [:variant    │        │      relations     │        │  assertions  │
  │  :oak/call]  │        │      domain/range  │        │              │
  │              │        │  ─────────────────  │        │              │
  │ never holds  │ ◄───── │  F   declare       │ ◄───── │  bindings    │
  │ the          │        │      relate        │        │              │
  │ capability   │        │      related       │        └──────────────┘
  └──────────────┘        │      census        │
                          └────────────────────┘
                            :ok value+evidence
                            :rejected code+detail
```

## Why this shape, on this stack

The OaK framing — the kernel is `K = (S, F)`, a schema plus the executable
reasoning functions permitted over it — lands on Kotoba almost without
translation, because Kotoba already refuses ambient authority. Three of the
paper's properties are not things this implementation adds; they are things
it cannot avoid:

| OaK wants | Kotoba already gives |
|---|---|
| the agent computes only through `F` | `F` is not exported. Admission is reached in exactly one place |
| the agent cannot reach the store directly | the graph is behind `:dataspace/transact`, and a guest that does not hold it cannot name a pattern |
| a refusal is a result, not a crash | no ambient `throw`; every refusal is `[:rejected code detail]` |

The `:capabilities` clause is checked both ways: a declared capability that is
never used is a compile error, and a policy that does not grant id 24 refuses
admission before a byte is emitted.

## Ontology-only app synthesis with executable semantics

The uncertain part of app construction is a choice among ontology identifiers,
never source text. A trained typed-decision model emits finite selections that
are sealed into a typed ontology transaction:

```clojure
[:oak.transaction/v1
 :goal/tender-intake
 "<ontology-digest>"
 [[:choice :action :action/declare-tender 9900] ...]]
```

The last value is confidence in basis points. Confidence floors are ontology
rows, not a model-global constant: structural roles currently require 0.80;
the measured OOD reasoner/effect roles require 0.60.  Every winner must still
be unique, at most 1.00, of the declared component kind, permitted by the goal,
and coherent under `:requires` / `:implements` / `:dispatch`.

```
trained OpenJev distributions (no generated text)
       │
       ▼
OWL 2 RL ── derives candidate role membership to a least fixpoint
       │
       ▼
SPARQL ── discovers the finite ontology candidate sets
       │
       ▼
compile-app-transaction ── validates version, ontology identity, role floor, permits, coherence
       │
       ▼
Execution IR ── State / Transaction / Capability / CausalLink / Effect + Execution
       │
       ▼
app manifest ── pins transaction, Execution IR, all component digests, ontology digest + DefCID
       │
       ▼
query-app ── exposes the selected reasoner/shape/query plans
       │
       ▼
run-app / OaK F ── capability-gated dataspace effect
```

`app-ontology-doc` is the source of truth. It describes the goal, a
reasoner profile, SHACL input constraint, SPARQL algebra, view, action, effect,
implementation binding, permissions, confidence floors, and dispatch
semantics. The eleven-row manifest carries the complete typed model transaction
and the compiler-derived Execution IR, pins both by digest, and also pins every
component digest, the ontology digest, and the actual DefCID of `do-declare`.
The IR names the selected state shape, transaction/event, attenuated capability,
causal link, effect opcode/target and implementation identity. `run-app`
re-derives the canonical IR from the current ontology and requires exact
document equality before interpreting its closed opcode; it never dispatches a
function name from model output.

The selected SHACL subset is executable, not documentary.  This experiment
interprets required single-value `:string` / `:keyword` properties and
`:shacl/in`; the tender status is constrained to `:open` or `:closed`.  Shape
validation happens before capability dispatch, and a rejected input is proven
to leave the dataspace unchanged. `query-app` also exports that same closed
shape plan. `oak.semantic/shape-plan->shacl` translates it fail-closed to the
canonical document ABI of the sibling `kotoba-lang/shacl` engine, and semantic
conformance compiles that sovereign `.kotoba` source to a second Wasm module
and executes both an accepting and a rejecting input through it. Unknown shape
constraints are rejected by the adapter rather than silently omitted.

`oak.semantic` is the mechanism adapter.  It evaluates the actual sibling
`org-w3-owl2` rules with the actual `datalog` least-fixpoint engine, materializes
the entailed RDF graph, and passes the ontology-selected algebra to the actual
sibling `sparql` engine.  Candidate discovery itself needs an OWL-derived
subclass membership; a ruleset that does not fire returns no candidate.

The model path uses the trained, published
`com-kotobalabs/open-jev-deberta-v3-large` artifact through
`typed_decisions.open_jev`.  The JSON result says `generated_text: false`,
contains the artifact/training provenance, and returns one calibrated
distribution for every closed option list.  The live conformance run pins the
artifact revision; recorded answers are not substituted for a forward pass.

### Semantic boundary

The executable reasoner runs over arbitrary input triples, on two paths:

| call | rules | engine | output |
|---|---|---|---|
| `(materialize :owl2-rl triples)` | `owl.rules/triple-rules`: subclass/subproperty/type closure, domain, range, transitive, symmetric, inverse | `datalog` least fixpoint | asserted + derived triples. **Unchanged** -- same set as before `entail` existed |
| `(entail :owl2-rl triples opts)` | the complete OWL 2 RL/RDF table, `owl.rules/owl2-rl-rules` (Profiles §4.3 Tables 4-9; eq-ref omitted, dt-* decided for xsd string/boolean/decimal/integer family/dateTime) | `owl.rl` semi-naive fixpoint | `{:graph :inferred :inconsistencies :consistent? :rules :diagnostics :counts}` |
| `(materialize :owl2-rl triples opts)` | as `entail` | `owl.rl` | `(:graph (entail ...))`; an inconsistent graph throws `:oak/owl-inconsistent` with the structured `:inconsistencies` unless `:allow-inconsistent? true` |

The complete path EMITS schema entailments as triples (`:schema? true`, the
default): the transitive `rdfs:subClassOf` / `rdfs:subPropertyOf` closures,
equivalences and propagated domains/ranges, so a consumer reads superclasses
from the graph. Its graph is a superset of the 2-arity one (measured on DoDAF
DM2 below), which is why it is a separate arity rather than a change to the
old one. Inconsistencies (every RL rule concluding `false`) come back as
`{:rule :cax-dw :table 7 :triples [...]}` -- never dropped. `supported-owl-rules`
and `supported-owl-vocabulary` (and `owl.rules/vocabulary-status`) list what
is implemented, so a caller can refuse an axiom whose rule is missing.

It is not full OWL 2 DL/SROIQ: existential introduction, disjunction,
unrestricted cardinality reasoning and tableau consistency are not silently
approximated. Asking for `:owl2-dl` returns `:oak/unsupported-owl-profile`.
This fail-closed boundary is part of the runtime contract, not a README caveat
masquerading as implementation.

Measured 2026-09-25 (`bench/dm2.cljk`, kbb SCI engine, a shared host at load
average ~100, so wall times are noisy): the DoDAF DM2 2.02 Mithril Form
(173 classes, 81 object properties, 712 axiom/declaration triples) plus a
deterministic synthetic instance graph --

| instance triples | 2-arity (datalog) | `entail` | `entail :schema? false` | 2-arity triples missing from `entail` |
|---|---|---|---|---|
| 3,000 | 41-60 s | 3.9-6.4 s | 1.4-2.1 s | 0 |
| 6,000 | 113 s | 12.3 s | 4.8 s | 0 |

```sh
kbb --backend sci --classpath <oak/src:org-w3-owl2/src:sparql/src:datalog+datom-source+text> \
  bench/dm2.cljk <dm2-form-file> [individuals] [edges]
```

SHACL remains a bounded executable subset (minimum/maximum count, canonical
document datatypes, `sh:in`, and node kind in the sibling engine; the current
OaK ontology uses count, datatype, and `sh:in`). It is now a live engine
connection, not a claim of complete SHACL Core. The kernel repeats its narrow
effect-admission checks so a host cannot bypass validation by omitting the
sibling preflight.

Measured on 2026-09-21 with Amu `wasm32-browser-kotoba-v1`: the module compiles
JVM-free; the base conformance suite admits the exact 0.80 action floor and
exact 0.60 effect floor while rejecting the values immediately below and a
confidence above 1.00. The semantic conformance path performed a real pinned
DeBERTa forward for all seven roles, compiled those choices in the Wasm module,
returned `:t-open` only after OWL-derived type membership and the selected
SPARQL two-pattern join, and compiled the sibling SHACL source to Wasm before
accepting `{:id "t-live" :status :open}` and rejecting the same shape with an
unknown status. The default fuel 512 remains insufficient; the base suite uses
16384 and the combined semantic instance uses 32768 after transaction and
Execution IR validation are included.

Run the two layers separately so missing model/engine inputs cannot look green:

```sh
kbb --backend sci bin/wasm-conformance.cljk
kbb --backend sci bin/semantic-conformance.cljk
```

The semantic runner requires `OAK_SEMANTIC_CLASSPATH`, `OPEN_JEV_PYTHON`,
`OPEN_JEV_SRC` (repository root or its `src` directory), `OPEN_JEV_MODEL`, and
`OPEN_JEV_REVISION`; absence exits 2. `SHACL_ROOT` may override the sibling
`../shacl` checkout. Missing source or a forward that emits no JSON also exits
2 instead of looking like a semantic pass.

## S

```clojure
(defn schema-doc [] :document
  [[:entity :agency]
   [:entity :tender]
   [:entity :supplier]
   [:relation :issued-by  :tender :agency]
   [:relation :awarded-to :tender :supplier]])
```

S is an ordinary document, so it has an identity: `document-sha256` of it, and
**every result carries that digest**. A result is therefore attributable to the
schema that admitted it, not merely to the kernel that returned it.

Editing `schema-doc` is how you retarget the kernel at another task. Nothing
below it names `:tender`.

## F

| call | admits when | returns |
|---|---|---|
| `:declare  {entity type}` | `type` is an `:entity` of S | count written |
| `:relate   {subject relation object}` | `relation` is in S, and the subject's and object's **types in the graph** match its domain and range | count written |
| `:related  {subject relation}` | `relation` is in S | the objects, as a document vector |
| `:census   {type}` | `type` is an `:entity` of S | how many entities carry it |

Refusals are named, not boolean: `:oak/unknown-entity-type`,
`:oak/unknown-relation`, `:oak/domain-violation`, `:oak/range-violation`,
`:oak/untyped-subject`, `:oak/untyped-object`, `:oak/graph-at-capacity`.

## Two doors, one admission

`oak-call` takes a call value. A browser host cannot hand it one:
`browser-host.mjs` admits a compound argument only if the host itself minted
it, and the constructors it exposes are `vectorI64`, `vectorF64`,
`stringIndex`, `disjointSetI64`, `document` and `bytes` — no record, no
variant. So the kernel also exports `call-declare`, `call-relate`,
`call-related` and `call-census`, which take scalars and assemble the call in
the guest.

That is a second **entry**, not a second kernel: each one builds the value and
hands it to `oak-call`, so S is consulted in exactly one place and nothing
below gains a way to reach the dataspace unadmitted. The conformance suite
asserts both halves — the export set, and that no `do-*` / `all-*` / `type-of`
is among it.

Note where the type of an entity lives. It is not an attribute of the call and
not a field of the schema — it is **an assertion in the graph**, put there by
an earlier admitted `:declare`. So checking a domain constraint is itself a
graph query, and an entity nothing has typed cannot be related to anything.

## Two ceilings, and only one of them is the kernel's

**The graph holds 32 typed entities and 32 facts**, because a query result is
one document and a document container holds `document-container-item-limit`
items. The kernel enforces this **on the write side**: it refuses a 33rd fact
with `:oak/graph-at-capacity` rather than accepting one it could never report.
It has to be the write side — the provider does not answer "too many", it traps
while encoding its reply, and a Kotoba guest has no `catch`.

**Reading is bounded again by the host's fuel, and that ceiling is not ours.**
Measured 2026-08-31 on the reference interpreter at its default fuel: a census
answers at 24 declared entities and traps `:fuel-exhausted` at 28 — so on that
host the fuel runs out before the document does. A browser wasm host budgets
fuel differently. The conformance suite therefore does not name a size: it
probes for the running host's own ceiling and asserts the invariant on both
sides of it — below, a read answers; above, what comes out is a Kotoba trap
naming `:fuel-exhausted`, never a wrong answer and never a host error object.

Do not copy either number into code. Measure the host you are on.

## Running it

```sh
kbb --backend sci bin/conformance.cljk        # from the repository root
```

No JVM: `kotoba.sema`, `kotoba.kir`, `provider.dataspace` and the reference
runtime are all `.cljc`, so analyze → lower → instantiate → invoke is Node
throughout. Missing sibling checkouts make the runner **exit 2** and say which
ones — a suite that could not run must not answer with what a suite that ran
and found nothing answers with.

To compile the kernel rather than interpret it:

```sh
amu check   src/oak/kernel.kotoba --jvm-free --policy src/oak/policy.edn
amu compile src/oak/kernel.kotoba --jvm-free --target wasm32-browser \
            --fuel 16384 --policy src/oak/policy.edn --output oak.wasm
```

Measured 2026-09-21, all JVM-free: the experiment is a **22,187-byte
`wasm32-browser-kotoba-v1` module**, which instantiates on
`amu/runtime/browser-host.mjs` and returns the same `document-sha256` for S as
the reference interpreter does.

```sh
kbb --backend sci test/browser-parity.cljk    # OAK_SOURCE / OAK_WASM / OAK_BROWSER_HOST
```

**The kernel's admission now runs on the compiled module too.**

```sh
kbb --backend sci bin/conformance.cljk         # the reference interpreter
kbb --backend sci bin/wasm-conformance.cljk    # the same checks, on the wasm module
```

The wasm runner requires `OAK_CLASSPATH` to contain `provider/src`, `text/src`,
and the exact osaho revision pinned by provider.  It refuses with exit 2 when
that classpath is absent; a nearby osaho checkout is not assumed to be the
pinned dependency.

The wasm run uses the same `provider.dataspace` the interpreter run does, with
a bridge either side of it — small, because the host's document form IS the
KIR document form; a keyword is the string `":is-a"` on one side and the
keyword `:is-a` on the other. Results can cross that way because the
host→guest direction goes through `admitHostResult`, which mints from plain
frozen arrays.

**One call, one instance.** A module's fuel is spent over the instance's life,
not per call, so a run that reuses an instance traps `unreachable` partway
through — measured here after four checks. The dataspace outlives the
instances because the provider is the host's, the same shape
`amu/runtime/dom-driver.mjs` uses for the same reason.

The suite discriminates on this backend as it does on the other: the domain
check made vacuous fails only the domain check, showing the call falling
through to the range check; query results discarded fails six.

`dataspace-v1` is qualified on `:reference`, `:wasm-aot`, `:native-aot` and
`:jit` — the only kit qualified across all four — which is why the graph plane
is this kit and not something built here. Check
`amu/resources/kotoba/lang/capability-kits/dataspace-v1.edn` for the current
values rather than trusting this sentence.

## What the suite actually discriminates

Green is cheap. These were measured by breaking the kernel one edit at a time
and confirming that what went red was what the check is named after:

| break | what failed |
|---|---|
| domain check made vacuous | *only* "a subject of the wrong type is refused as a domain violation" — and it showed the call falling through to the range check |
| capacity guard removed | the two capacity checks, reporting the provider's own `document-edn-read vector item limit exceeded` |
| evidence digest replaced with a constant | "every result carries the digest of the schema that admitted it" |
| query results discarded | six checks, starting with the ones that depend on a type being readable |
| the module compiled from a different S | the wasm/interpreter digest check, with both digests printed |

The first and last of those were run against **both** backends and failed the same checks on each. The capacity and evidence mutations were run against the interpreter only — the capacity one needs 34 instances on wasm, which is slow rather than hard.

## Boundaries with the nearest repositories

- **`kotoba-lang/ontology`** is a registry of *what kind of thing an ingested
  fact is* — object types and the connector that produced them. It answers a
  vocabulary question about data at rest. This repository answers an authority
  question about a call in flight. Neither is a layer of the other.
- **`kotoba-lang/kgraph`** and **`kotobase`** are the datom plane. This kernel
  does not touch them; the `dataspace-v1` provider may be backed by kgraph
  without the guest knowing.
- **`kotoba-lang/agent`** is one bounded execution. It is a caller here, not a
  component.

## Provenance

The framing is taken from *Toward Effective and Reliable LLM Agents via
Dynamic Ontology* (Zhang, Sun, Yang, Cui, Guo, Hu; arXiv:2608.22974), as it
was described to this repository's author — **the paper itself was not read**,
so treat the correspondence as a reading of the idea and not as a claim of
fidelity to its algorithms. What is here that the paper does not describe is
the capability boundary: OaK argues that the ontology should be the kernel,
and Kotoba is a language in which "kernel" can mean the thing that holds the
authority rather than a naming convention.

The paper also builds `S` and `F` from training data and refines them against
a judge. That loop is **not implemented here**. `S` is hand-written and fixed.
