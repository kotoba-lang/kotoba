# kotoba-script

Restricted JavaScript backend for Kotoba. This package accepts only checked
`kotoba.kir/v3` or typed `kotoba.kir/v4` data produced by
`kotoba-lang/amu`; it does not parse
`.kotoba` source and does not own language semantics.

```text
.kotoba -> kotoba-lang/amu -> checked KIR -> kotoba-script -> .mjs
```

## Runtimes: JVM and nbb, same bytes

`src/kotoba/script.cljk` is portable. The emitter is string construction over
checked KIR, so it runs on the JVM and on nbb/Node and emits **the same
module byte for byte** on both. That is what lets `amu compile --target js`
run without a JDK (`--jvm-free`). Three seams differ per host and are marked
with reader conditionals in the source:

| seam | JVM | nbb/Node |
|---|---|---|
| integer literals | `integer?` | BigInt (the nbb frontend lowers i64 to BigInt) or a plain JS integer in hand-built KIR; JS `-0` is never an integer literal and reads as the f64 `-0.0` |
| f64 literal text | `Double.toString` | `java-double-string`, JDK 19+ shortest-digit layout rebuilt from `Number.prototype.toExponential` (incl. the `4.9E-324` spelling of `MIN_VALUE`) |
| output verification | Closure Compiler AST walk | `node --check` for syntax + a token scan outside string literals for the same forbidden globals / properties / import forms. Weaker than the AST walk; its failure data says `:verifier :token-scan` |

A hand-built KIR on nbb cannot say `2.0` (a whole-number double reads as
i64 there; `-0.0` is the one exception); the compiler route never needs to,
because it lowers f64 to `(f64-from-bits …)`. The golden fixtures therefore
carry whole-number doubles as `#kotoba.parity/f64-bits "<hex>"`, which the
parity test reads back into the exact double.

```bash
kbb -M:test        # JVM suite (66 tests, 229 assertions)
npm run test-nbb       # nbb parity: emit bytes == JVM golden for 61 KIR fixtures, Double.toString table, verifier refusals
kbb -M:golden      # regenerate test/fixtures/parity/ from the JVM emitter after an emitter change
```

The golden set is every public var of `kotoba.script-test` whose value is a
KIR map (61 fixtures, 3,588,034 bytes of emitted ESM at the last
generation), so a new emitter path gets parity coverage by lifting its test
fixture into a public `def`. A var with `^{:emit-opts {…}}` metadata is
emitted with those options on both hosts (`<name>.opts.edn`). Fixtures whose
emit is expected to throw stay `let`-bound inside their deftest.

Generated modules expose `kotobaArtifact` and `instantiateKotoba(grants)`.
They use no ambient browser/Node authority and execute capability effects only
through explicitly supplied grant functions.

Every emitted artifact declares
`floatingPointPolicy: 'ieee-754-f32-f64-v7'`. KIR v4 admits scalar `:f32` and
`:f64` parameters and results. Both profiles provide exact bit conversion,
explicit add/subtract/multiply/divide/negate/absolute operations, ordered
comparisons, and an unordered predicate. Binary32 values are created only by
explicit rounding, integer conversion, or bit construction; decimal literals
remain binary64. Finite values, infinities, and both zero signs preserve their
IEEE-754 bits; NaN payloads are intentionally unobservable and canonicalized
to quiet NaN `0x7fc00000` or `0x7ff8000000000000`. Division follows IEEE-754,
including infinities, NaN, and signed zero. There are no implicit integer/float
conversions, fused operations, remainder, or general transcendentals in
this profile.

`f32-sqrt`/`f64-sqrt` and `f32-min`/`f32-max`/`f64-min`/`f64-max`
propagate NaN. Minimum selects negative zero and maximum selects positive zero
when the operands are opposite zero signs. Binary32 results round after the
named operation.

Qualified `f64-sin-quarter-turn` and `f64-cos-quarter-turn` accept only finite
radians in `[-pi/4, pi/4]`, evaluate fixed degree-17/16 Horner polynomials
without FMA, and guarantee absolute error at most `4e-15`. Inputs outside the
sealed domain trap instead of invoking ambient host transcendental functions.

`f64-sin-bounded` and `f64-cos-bounded` extend that contract to finite
`[-8192*pi, 8192*pi]` using fixed split-`pi/2` range reduction, ties-away-from-
zero quadrant selection, and the same quarter-turn kernels. Their absolute
error bound is `5e-12`; larger or non-finite angles trap.

`f64-exp-near-zero` accepts finite `[-0.5,0.5]` and
`f64-log-near-one` accepts finite `[0.75,1.5]`. Fixed degree-18 Taylor and
degree-21 atanh-series Horner kernels provide a `4e-15` absolute-error bound;
out-of-domain inputs trap and no host `Math.exp`/`Math.log` call is emitted.
`f64-atan2-bounded` accepts two finite binary64 coordinates, uses a fixed
degree-39 odd kernel after octant reduction, and guarantees absolute error at
most `2e-15`. It preserves the IEEE signed-zero quadrant cases, rejects NaN
and infinity, and never calls host `Math.atan2`.
`f64-exp-bounded` extends exponential to `[-512*ln(2),512*ln(2)]` using fixed
split-`ln(2)` reduction and exact binary scaling. `f64-log-bounded` accepts
`[2^-512,2^512]`, extracts a sealed binary exponent/mantissa, and reuses the
near-one kernel. Their relative/absolute error bounds are `1e-13`; neither
operation calls host `Math.exp` or `Math.log`, and values outside the declared
domains trap.
JavaScript is the checked output representation, not the source of Kotoba
semantics.

Numeric conversion is never implicit. `i64-to-f64-checked` rejects integers
that binary64 cannot represent exactly, while `i64-to-f64-rounded` explicitly
requests IEEE round-to-nearest conversion. `f64-to-i64-checked` accepts only
finite integral values in signed-i64 range; `f64-to-i64-truncating` explicitly
requests truncation toward zero and still rejects NaN, infinities, and
out-of-range results. The corresponding `i64-to-f32-*` and `f32-to-i64-*`
operations use the same checked-versus-lossy naming. `f64-to-f32-rounded` and
`f32-to-f64-exact` make width changes explicit.

KIR v4 preserves `:i64`, `:f32`, `:f64`, `:string`, `:keyword`, `:bool`, `:option-i64`, and the
first bounded `:map` profile as distinct value types. String
literals must be well-formed UTF-16, are capped at 4,096 UTF-8 bytes each and
65,536 bytes per module, and every runtime string crossing a function or host
boundary is revalidated against the 65,536-byte cap. The backend supports `string-byte-length`, `string=?`, `string-concat`,
`string-replace-all`, `string-contains?`, `string-fold-case`,
`keyword-from-string`, and `keyword-name`; it does not hash strings
into integers or expose JavaScript property access as language semantics.
Keywords preserve canonical Unicode source text, are capped at 512 UTF-8
bytes, and are never hashed into integers. Maps contain at most 128 unique
keyword keys and signed-i64 values; their host ABI is a canonical frozen array
of `[keyword, bigint]` entries. `map-assoc` returns a new frozen value and does
not mutate its input. Nested or mixed-value maps remain fail-closed until a
later explicitly typed profile owns them.

Booleans cross the host boundary only as JavaScript `true` or `false`; numeric
truthiness is not accepted. The first option profile is deliberately
`option<i64>` rather than an unbounded generic container. Its canonical host
ABI is the frozen tagged array `[false]` for none or `[true, bigint]` for some.
JavaScript `null`, `undefined`, integer sentinels, malformed tags, and payloads
outside signed i64 fail closed. `option-value` evaluates its fallback only for
none. The first algebraic-result profile is likewise deliberately closed:
`result<i64,i64>` uses the frozen tagged array `[true, bigint]` for ok and
`[false, bigint]` for err. Both payload positions are signed i64,
malformed/missing payloads fail closed, and `result-value` / `result-error`
evaluate their fallback only for the opposite variant. This is a monomorphic
ABI foundation, not yet a claim of generic ADTs.

Parametric results use the canonical recursive type descriptor
`[:result ok-type err-type]` and the explicit KIR operations
`result-ok-of`, `result-err-of`, `result-ok?-of`, `result-value-of`, and
`result-error-of`. Descriptors may nest to depth 8 and contain at most 64 type
nodes; runtime payload validation carries the same depth and node budgets.
Every constructor and projection carries its descriptor, so generated code
never guesses a payload type from JavaScript shape.

`result-match-of` is the checked KIR form for exhaustive result matching. It
contains exactly one ok binder/body and one err binder/body; both binders are
typed from the descriptor, both branch result types must agree, and generated
code validates the result before evaluating exactly one branch.

User-defined finite variants use
`[:variant :qualified/type [[:case payload-type] ...]]`, with 1--32 unique
cases inside the shared depth-8/node-64 type budget. Canonical host values are
frozen `[descriptor, ":case", payload]` arrays. The full descriptor is part of
the value identity and is structurally revalidated, preventing a same-named
case from another schema or module from being substituted. `variant-match`
must list every declared case exactly once and in declaration order; there is
no wildcard that can silently absorb later schema expansion.

Generic options use `[:option payload-type]`. Canonical host values are
`[descriptor, false]` for none and `[descriptor, true, payload]` for some, so
even payload-free none values retain exact type identity. Constructors,
projection, and exhaustive none/some matching carry the descriptor explicitly;
null, undefined, malformed tags, cross-option substitution, and eager fallback
evaluation remain outside the language ABI.

Fixed heterogeneous vectors use `[:vector [item-type ...]]` with at most 32
positions inside the shared depth-8/node-64 descriptor budget. Their canonical
host value is `[descriptor, item ...]`: descriptor identity, exact length, and
every position's declared type are revalidated at each export boundary.
Construction must supply every position exactly once; projection and persistent
replacement use an admission-time in-range integer index, so their result or
replacement type is statically determined. Equality first validates both full
values against the same descriptor and then compares every canonical nested
value structurally; JavaScript object identity is never observed. Dynamic indexes, sparse values,
append/drop operations, and host mutation are not admitted by this profile.

Typed sets use `[:set item-type]` and at most 32 values inside the shared
depth/node budget. Their canonical host value is `[descriptor, items]`, where
items are recursively validated, uniquely sorted by a language-owned total
order, and frozen. Constructors reject duplicates instead of silently losing
input. Membership, idempotent insertion, removal, count, and equality operate
on canonical values; updates never mutate their input. The total order covers
every currently admitted scalar and structured value type, so neither
JavaScript insertion order nor object identity participates in set semantics.

Nominal bounded records use
`[:record :qualified/type [[:field field-type] ...]]`, with 1--32 unique
keyword fields in declaration order under the shared depth/node budget. Their
canonical host value is `[descriptor, field-value ...]`; the complete nominal
schema, exact arity, and every field value are revalidated at each boundary.
Construction supplies every field exactly once in declaration order. Field
projection and persistent replacement require an admission-time declared
keyword literal, making their types static and excluding dynamic property,
prototype, sparse-object, and unknown-field behavior. Equality is structural
only after exact descriptor validation.

The first sequential collection profile is `vector<i64>`, bounded to 128
items. Its host ABI is a frozen JavaScript array whose elements are revalidated
as signed i64 at every exported boundary. `vector-get` has a lazy explicit
fallback; `vector-assoc` only replaces an existing index; `vector-conj` fails
at capacity. Both updates return new frozen arrays and never mutate the input.

Run tests with `kbb -M:test`.

## JS backend design and fuel regression

See [the implementation review and staged design](docs/js-backend-design-ja.md)
for the KIR/MIR/AST boundary, runtime strategy, source maps and known parity gaps.
`test/nbb/fuel.cljk` verifies exact fuel admission and per-instance accounting.
`test/nbb/differential.cljk` executes the same scalar KIR through JS, Wasm and
the reference evaluator; its pinned peer classpath is documented in the review.
These focused checks do not qualify all language profiles or resolve the
known synthesized-loop fuel discrepancy.

The new acceptance path is JVM-independent: `npm run test-jvm-free`. It checks
the peer SHAs in `scripts/jvm-free-peers.json` (sibling checkouts by default;
override with `KOTOBA_TEST_PEERS_ROOT`), runs all 51 focused assertions, and
fails if a test attempts a JVM launcher. CI fetches those exact peers without
installing Java or Clojure. Existing JVM tests remain compatibility diagnostics;
regenerating JVM goldens is not a prerequisite for new backend work.

Explicit entryless empty export vectors instantiate with no public functions,
including private-only libraries. Missing/implicit empty exports, dangling or
duplicate exports and executable entries with empty exports remain refused.
The acceptance engine is the exact `.cljk`-aware nbb Git pin in package-lock;
the checked peer source paths are passed in a dependency-free config. This
prevents nbb dependency resolution from launching bb/tools.deps/Java during
the JVM-free route. These Node runs remain bootstrap evidence, not selfhost.

## Opaque JS interoperability leaf

Checked KIR may declare `:js-value` arguments and results on this JS target.
Exports and internal calls preserve raw values exactly, including undefined,
NaN, signed zero, functions, symbols, cycles and proxies. Boundary checks treat
these as opaque leaves: no property access, coercion or copying. This does not
bound retained host graphs or grant callback/property/ambient operations.
Canonical ordering and explicitly opaque ordered set items/map keys refuse.
Existing scalar typing and capabilities remain checked. The new prelude guards
are emitted only when the KIR names the opaque type; existing golden modules
retain their bytes.
The checked JS-only operations `js-nullish?`, `js-truthy?`, and
`js-strict-equal?` consume explicitly opaque operands and return `:bool`.
They emit strict null/undefined tests, JavaScript ToBoolean, and strict
identity equality. Each operand is evaluated once, without property reads
or conversion. Other operand types and incorrect arities are refused.
The unary operations `js-typeof` (`:js-value` to `:string`), `js-array?`
(`:js-value` to `:bool`) and `js-bool-value` (`:bool` to `:js-value`) retain
these exact types. They emit native typeof, Array.isArray and checked boolean
injection, respectively, and evaluate their operand once. Array branding
recognizes foreign-realm arrays and preserves revoked-Proxy TypeError.
A composed opaque conditional can preserve falsy raw values and return an
injected bool otherwise, as required by the CosmoKit isPlainObject expression.
Finite emitted-code tests cover 26 host values, three explicit capability
callbacks evaluated once in order, and untouched getter/Proxy traps. The
unchanged 66-module / 109-check parity fixture remains a bootstrap comparison;
this is not complete package or compiler-selfhost qualification.
This backend addition still requires explicit source-frontend admission.

The small descriptor helper was proposed by public System One Coding as an
iterative refactor. Its initial full replacement had one extra closing
parenthesis; one budgeted repair returned unchanged source and was refused.
An operator removed that parenthesis, after which the original immutable
52 assertions passed on both baseline and candidate in a pinned offline image.
This is not model-only success. The emitter's separate raw-JS test executes an
actual generated library with 24 host values, including a revoked proxy.
Source syntax, Amu dependency pins/target guards and Mithril frontend linking
remain separate prerequisites; these tests are Node/nbb bootstrap evidence.

Array branding normalizes the observed `Array.isArray` result with JavaScript
truthiness before exposing a typed bool. This preserves negation when a host
replaces that function and returns a non-bool falsy value. The lookup and call
remain dynamic, the operand is evaluated once, errors propagate unchanged, and
return objects are not inspected or coerced through user hooks.

The zero-arity `(js-undefined)` operation returns an opaque JS undefined via
`void 0`. It needs no host lookup, source evaluation or opaque literal. Its
result is `:js-value`, with invalid arity or result types refused. This prepares
CosmoKit noop; complete source frontend, module linking and public function
reflection/constructibility parity still require separate qualification.


### Opaque JS capture cells (bootstrap prerequisite)

The checked KIR operations `js-capture-new` and `js-capture-value` retain an
opaque JS payload in a private typed cell. Integer IDs and chain tails retain
the existing closure ABI; ordinary `pair-first` refuses a typed opaque slot.
Only modules using these operations receive the private identity helpers and a
4096-cell shared pair arena. Ordinary and opaque pair allocations both count
there and debit the existing constructor fuel/cells ledger. The five-capture
closure limit and default execution budgets remain unchanged. Modules without
capture operations keep their prior emitted bytes.

Qualification on 2026-10-08: all ten maintained Node test scripts, executed
with a closed authored classpath and the pinned bootstrap engine, passed 23 tests
/ 165 assertions plus 109 parity checks; all 66 unchanged goldens (4,223,966
bytes) match. Forbidden JVM launchers remained unused. The outer peer-verifying
wrapper was not executed in this local environment; its new capture script is
registered for maintained acceptance.

An actual candidate artifact executed in pinned offline Node v24.21.0: 14
opaque values / 28 identity comparisons with zero property reads, seven trap,
budget and capture-limit checks, and 2000 calls. New maintained tests also
exercise shared ordinary/opaque arena exhaustion and private method identity
following ambient WeakSet method replacement.

This is an interpreter/emitter prerequisite paired with published Osaho PR103
(`d1c27ed446745f9db7d4b20c6531e108e6949a9c`). Checked Sema capture lifting,
normal Amu publication, persistent escaping closure and host callback adaptation,
browser-host execution and native selfhost remain separate work. The default
restricted subset verifier was retained. Operator-authored; public System One
status remained HTTP503, so no model performance result is claimed.

### Empty nominal records

Empty record descriptors now follow the published Sema options-map floor. Nominal
IDs, field shape and resource bounds remain checked. Modules without an empty
record descriptor retain their previous emitted bytes. Local bootstrap acceptance
passed 26 tests / 172 assertions plus 109 parity checks and 66 unchanged goldens.
See [qualification](docs/qualification/empty-records/README.md) for the closed
classpath, disabled Actions and normal Amu consumer limitations.
