# kotoba-sema

`kotoba-sema` owns Kotoba source semantic analysis: reading forms, resolving
names, checking types and effects, elaborating capabilities, and producing a
validated HIR envelope.

```text
source bytes
  -> forms
  -> semantic analysis
  -> checked kotoba-hir
```

The implementation namespaces remain `kotoba.compiler.frontend`,
`kotoba.compiler.schema`, and `kotoba.compiler.kotoba-reader` during the
repository-boundary migration. Keeping those names preserves existing JVM and
NBB consumers while ownership moves out of the compiler orchestrator. New code
should enter through `kotoba.sema`.

The language repository remains authoritative for the vendored guest grammar
and capability catalog. This repository owns loading and enforcing those
contracts during semantic analysis.

`(eval request)` is deliberately not host evaluation. The frontend elaborates
the one-argument form to the catalogued `:code/eval` typed ability (wire ID 30),
inferring the request as `:document` and the result from its typed context.
`load-string`, `read-string`, reader evaluation, and ambient name resolution
remain forbidden. The host must resolve a checked definition CID and admit its
complete effect row before execution.

## Type-directed arithmetic (2026-09-02)

The plain numeric operators `+ - * / < <= > >= =` have one spelling each and
resolve by operand type, the way Unison resolves `+` to `Nat.+` or `Float.+`:

| operand types | `+` | `-` | `*` | `/` | `<` `<=` `>` `>=` | `=` | unary `-` |
|---|---|---|---|---|---|---|---|
| all `:i64` | `+` (unchanged) | `-` | `*` | rejected (use `quot`) | `<` ... | `=` | `-` |
| all `:f64` | `f64-add` | `f64-sub` | `f64-mul` | `f64-div` | `f64-lt` ... `f64-ge` | `f64-eq` | `f64-neg` |
| all `:f32` | `f32-add` | `f32-sub` | `f32-mul` | `f32-div` | `f32-lt` ... `f32-ge` | `f32-eq` | `f32-neg` |

- The resolution is a rewrite in the same type-directed pass that elaborates
  `option-or`, so it runs after variadic and chained forms are desugared to
  binary calls (`(< a b c)` on f64 lowers to two `f64-lt`) and before
  validation; every backend still sees only the typed operations.
- A program with no float operands is byte-identical to what it was before
  the rule existed (`test/kotoba/compiler/type_directed_arithmetic_test.cljk`
  holds two integer programs beside their pre-change output).
- The explicit spellings (`f64-add`, `f32-lt`, ...) remain valid; typed and
  ABI boundaries may still name their operation exactly.
- `quot` and the bit operations are integer-only and are not overloaded.
- A decimal literal next to an `:f32` operand narrows exactly-or-refused,
  the same rule `(f32-add x 1.5)` already applies; `(+ x 0.1)` on f32 is
  refused, not rounded.
- An unannotated parameter used as `(+ p 1.5)` is refined to `:f64` by the
  same mechanism that refines a string parameter from `string-substring`.

**Invariant: there is no implicit numeric conversion.** An `:i64` next to an
`:f64`, or an `:f32` next to an `:f64`, is rejected with a message that names
both types and the explicit conversions the author must choose between:
`i64-to-f64-checked` / `i64-to-f64-rounded`, `f64-to-i64-checked` /
`f64-to-i64-truncating`, `i64-to-f32-checked` / `i64-to-f32-rounded`,
`f32-to-i64-checked` / `f32-to-i64-truncating`, `f32-to-f64-exact`,
`f64-to-f32-rounded`. Widening and narrowing each have two spellings because
overflow and rounding are decisions the source has to write down.

## Development

```sh
kbb -M:test
```

## Responsibility boundary

- Owns source reading and semantic admission.
- Owns source/schema diagnostics and source-to-HIR elaboration.
- Produces `kotoba-hir`; does not lower HIR to KIR.
- Does not orchestrate compilation or emit machine code.

Explicit `(:export [])` namespace libraries may have no functions or only
private/internal functions. They have no synthesized entry or export.
Unmarked empty source and invalid public export/entry declarations remain
refused. This source/HIR stage does not qualify backend compilation.

Source signatures may name `:js-value`, an opaque host value for the restricted
JS emitter. Parameters, results and private calls retain this type in HIR v3;
it cannot silently become an integer or participate in numeric operations.
The semantic analyzer has no target parameter: compiler orchestration must
refuse this type on targets without its host ABI before lowering or execution.
This admission does not grant property access, callbacks or host capabilities.
The source operations `js-nullish?`, `js-truthy?`, and `js-strict-equal?`
accept only explicit `:js-value` operands, check fixed arities, and return
`:bool`. They retain typed HIR and delegate native JS observations to the
qualified reference/runtime contracts; generic equality still refuses opaque
values. They do not introduce coercion or host authority.

The unary source heads `js-typeof` (`:js-value` to `:string`), `js-array?`
(`:js-value` to `:bool`) and `js-bool-value` (`:bool` to `:js-value`) check
exact arities and operand/result types and remain reserved operations in HIR.
Boolean injection is explicit; it does not admit arbitrary scalar coercion.
These operations compose with a matching-type conditional to preserve raw
falsy input and inject a boolean result for truthy input. Qualification of the
runtime and emitter remains separate from this source admission; all opaque
results still require a target supporting the JS host ABI.

Canonical set items and map keys containing `:js-value` are refused, including
nested descriptors. Map values may contain it. Record/variant IDs and field
labels are inert names, so a field named `:js-value` with type `:string` is
ordinary ordered data. JS identity preservation is an emitter/runtime property,
not evidence supplied by semantic analysis alone; retained host graphs have
embedder-owned resource and lifetime costs.

`(js-undefined)` is a reserved zero-arity source operation returning
`:js-value`. The retained HIR head has no operands. Extra arguments, scalar
result mismatches and declared function-name capture are refused. Arbitrary
opaque JS literals remain unavailable. Runtime/emitter pins and Mithril
module source admission qualify separately; this operator-authored extension
is not a new System One model evaluation.

The undefined source qualification now consumes merged Osaho
`3fc6cdb8cc1ae3991cbf555c45af545997bacaa2`, including the zero-arity runtime
operation and normalized dynamic array observation. The maintained source
checks remain 15 tests / 105 assertions; final compiler consumers qualify
separately. Restricted JS instance fuel is not a public library lifetime
compatibility guarantee.


## Typed guest closures with opaque JS values

A typed guest closure may accept and return `:js-value`, including bounded
aggregate descriptors containing that leaf. The dispatcher keeps its existing
internal i64 closure handle and typed argument/result ABI; opaque JS references
are neither cast to i64 nor traversed. The unknown-dispatcher's unreachable
result inhabitant uses the already admitted zero-argument `js-undefined`.

Captures retain the existing i64 pair-chain ABI. This change does not admit an
opaque host function as a guest closure, JS property access, or opaque captures.
Wrong arguments/results and callable/linear-resource restrictions still refuse.
JS target admission remains separate from frontend analysis; non-JS compilation
must reject opaque JS signatures as before.

Published Osaho main 9d033b3e07fe32195e2c3ec93aa6d4a0645a848e fixes a preceding
interpreter bug: recognizing a trampoline must not read a Proxy result's CLJS
protocol properties. The maintained bootstrap checks now include five independent
closure tests / 28 assertions; the selected combined suite passes 20 / 133 with
that exact runtime pin. Actual Script ESM independently passes 45 comparisons
for 15 opaque values with zero property reads. These are typed guest closure
checks, not a host callback bridge, browser-host/self-host result or full Harness
migration. System One's public status remains 503; this is operator-authored.

Additional Node closure controls were measured on exact baseline 88fb953 and
candidate: the same two historical rendering-digest expectations and one stored
record-closure refusal expectation fail on both. Their expected values were not
changed to hide the failures. The maintained selected tests and repository CI
are distinct qualification scopes.


### Typed opaque guest captures (bootstrap qualification)

A lifted guest function may capture an explicitly typed `:js-value` leaf.
Sema carries that capture's type into the helper, stores it through
`js-capture-new`, and projects it with `js-capture-value` in the matching
closure dispatcher. Integer capture words, function IDs and chain tails keep
the existing ABI. Capture refinement recognizes mixed chains, including a
captured typed guest function. Five captures, helper arity limits and the
existing constructor fuel/cells ledger remain enforced.

On 2026-10-08 the maintained Node/nbb source suite passed 28 tests / 167
assertions using published Osaho PR103 at
`d1c27ed446745f9db7d4b20c6531e108e6949a9c`, with forbidden JVM launchers shadowed.
Eight new tests / 34 assertions cover opaque identity, mixed slots, captured
guest functions, typed arguments, nested captures, five-capture bounds,
allocation budgets, bad results and refused raw host invocation. The former
opaque-capture refusal control was deliberately replaced by the still-refused
record-with-JS capture control; supporting opaque leaves is the new behavior.

Three unchanged all-integer capture programs produce byte-identical complete
HIR against published baseline621e89b. Actual source was also lowered and
emitted through published Script PR111 (`ed36af5f71be11c2e688098653df516e684b1150`):
six functions / 14 opaque values / 84 identity comparisons, zero property reads,
three budget checks and 2000 calls passed in pinned offline Node v24.21.0.
This was a direct candidate pipeline, not normal Amu dependency closure.

Opaque-containing record captures, raw host callbacks, persistent escaping
closure instances and host callable adaptation remain separate prerequisites.
Restricted guest authority/default budgets are unchanged. These are bootstrap
and offline Node results, not browser-host or native selfhost qualification.
Operator-authored; public System One remained HTTP503. Earlier historical Node
closure-control failures remain documented above and were not hidden by changing
their assertions.
