# ADR 0048: The bounded `:map` value type is lowered onto the canonical typed map

- Status: Accepted
- Date: 2026-09-01

## Context

KIR carries two map vocabularies.

`typed-map-new` / `typed-map-get` / `typed-map-assoc` / `typed-map-count` /
`typed-map-contains` / `typed-map-dissoc` / `typed-map-entry-at` /
`typed-map-equal` are the CANONICAL parametric map. Each use names its own
`[:map K V]` descriptor, and this backend has emitted them since the typed
value ABI landed.

`map-new` / `map-get` / `map-assoc` are the BOUNDED map. It is what a bare
`{:k 1}` literal desugars to (`kotoba.compiler.frontend/desugar-map`), and it
names no descriptor, because the frontend fixes one: every key is checked as
`:keyword` and every value as `:i64`. The bounded map IS `[:map :keyword :i64]`
and no source can spell anything else into it.

This backend carried the first vocabulary and not the second. A bare map
literal therefore refused, and it refused in two DIFFERENT places with two
DIFFERENT messages:

| source | refusal |
|---|---|
| `(get {:value 9} :value)` | `kotoba.wasm.core`'s `emit*` fallthrough, `typed Wasm operation is not qualified` — `map-get` is neither an emitter case nor a function in the module |
| `(let [m {:value 9}] …)` | `kotoba.wasm.typed/infer-type`, `unsupported typed Wasm expression` — a `let` needs the STATIC type of its init, and `map-new` had no inference case |

Which message a program got depended on whether it bound the map to a local,
not on anything about maps. Closing either site alone left the other standing.

Nothing had noticed, because nothing had asked: every map fixture in the
compiler's dual-backend conformance pilot writes `typed-map-*` explicitly
(`resources/kotoba/lang-conformance/values/typed_map_kit.kotoba`), and this
repository's suite contained no `map-new` at all. The language authority
meanwhile recorded `:map-literal :implementation #{:compiler :kotoba-wasm
:kotoba-cljs}` — a set it describes in the same file as "an assertion, not
evidence".

## Decision

`kotoba.wasm.typed/lower-bounded-maps` rewrites the bounded vocabulary onto
the canonical one over the whole KIR module, before anything else in this
backend sees it:

```
(map-new k1 v1 …)     -> (typed-map-new [:map :keyword :i64] k1 v1 …)
(map-get m k default) -> (option-value-of [:option :i64]
                           (typed-map-get [:map :keyword :i64] m k)
                           default)
(map-assoc m k1 v1 …) -> nested (typed-map-assoc [:map :keyword :i64] … k v)
:map in a signature   -> [:map :keyword :i64]
```

`map-get` answers its default only for an absent key; `option-value-of` emits
its fallback inside the else branch of the tag test, so that laziness survives
the rewrite rather than being restored by hand.

It is applied in two places, because two are reachable independently:

- `kotoba.wasm.core/emit`, as the first binding, so signatures, the descriptor
  table, the literal table, `infer-type`, `emit*` and the custom section all
  read one vocabulary.
- `kotoba.wasm.typed/requires-host-runtime?`, which callers outside this
  repository (`kotoba.compiler.core`, `kotoba.compiler.nbb.wasm-cli`) ask about
  the RAW KIR to derive `:wasm-features`. An empty `(map-new)` carries no
  keyword literal and no descriptor of its own, so the raw answer would be
  "no host value" for a module that, once emitted, imports `kotoba:typed`.

The function is idempotent, so applying it twice is applying it once.

No new map representation is added to this backend. The gap was a descriptor
that was never written down, not a missing mechanism.

## The ceiling this inherits, and why it is refused by name

`kotoba.kir.value/map-entry-limit` admits 128 entries for the bounded map on
the KIR oracle. The typed value runtime rejects a 32nd entry
(`browser-host.mjs`, `typed map entry budget exceeded`, and the same 31 in its
value-shape check). The two numbers are real and they differ.

A bounded map LITERAL over 31 entries is therefore refused here, at compile
time, as `bounded map exceeds the typed map entry budget` with the count and
the limit in its ex-data — rather than emitted into a module that traps when
the entry is added. A computed `map-assoc` can still cross the ceiling at run
time; that one the runtime owns and this backend cannot see.

So the honest claim is: **wasm32 carries the bounded map up to 31 entries.**
32..128 entries are admitted by the frontend and by the KIR oracle and refused
by this backend, by name. That is a narrower gap than the one this ADR closes,
and it is not closed.

## Evidence boundary

### What was measured

Measured 2026-09-01 against amu `27d82d8` and this repository at `3eb9bfe`,
through the JDK-free `bin/amu` path.

Before, four programs, `compile --target wasm32`:

| program | exit | message |
|---|---|---|
| `(defn main [] (match 5 0 100 5 200 :else 300))` | 0 | — (`main()` = `200n`) |
| `(defn main [] (get {:value 9} :value))` | 70 | `typed Wasm operation is not qualified` (`:operation map-get`) |
| `(defn main [] (match {:value 9} {:value n} n :else 0))` | 70 | `unsupported typed Wasm expression` (`:operation map-new`) |
| `lang/conformance/control/match_desugar.kotoba` | 70 | `unsupported typed Wasm expression` (`:operation map-new`) |

The first row is the control: `match` with no map compiles and runs. The cause
is the bounded map, and the second and third rows are two distinct sites.

After, all four emit. Instantiated through amu's `runtime/browser-host.mjs`
and called by export name, `main()` answers `9`, `9` and `21` for rows two,
three and four — the same values `kotoba.kir/execute` answers for the same
modules. Row four is the language authority's conformance case
`:bounded-control-match-and-pure-desugar`, whose manifest expects 21.

Suites, JVM and nbb, this repository:

| | unmodified `3eb9bfe` | with this change |
|---|---|---|
| `kbb -M:test` | 121 tests / 527 assertions / 0 failures | 130 / 542 / 0 |
| `run-tests.cljk` (nbb) | 2 tests / 2 assertions / 0 failures | 11 / 17 / 0 |

Break/unbreak, run on nbb over the same nine new tests:

- Removing `map-get` from the rewrite set: `a-bounded-map-read-that-binds-no-local-emits`,
  `a-bounded-map-bound-to-a-local-emits`, `a-bounded-map-write-emits` and
  `a-bounded-map-literal-at-the-typed-map-ceiling-emits` error with
  `typed Wasm operation is not qualified` and `:operation map-get`;
  `the-bounded-map-becomes-the-canonical-typed-map` names the surviving
  `map-get`. The other four stay green.
- Removing `map-new` instead: `a-bounded-map-bound-to-a-local-emits` errors
  with `unsupported typed Wasm expression` and `:operation map-new` — the
  second historical message, from the second site — while the shapes that
  reach `emit*` first still error with the first one.

Restored: 11 tests / 17 assertions / 0 failures.

### What was NOT done, and why

`typed-map-count`, `typed-map-contains`, `typed-map-dissoc`,
`typed-map-entry-at` and `typed-map-equal` have no bounded counterpart in KIR,
so nothing was added for them. The bounded surface is exactly `get` and
`assoc` (`lang/surface-status.edn`, `:map-literal :operations`).

The 31/128 divergence above is recorded, not resolved. Raising it would mean
changing the typed value domain in `kotoba.kir.value` and in every host that
implements it, which is a decision about the value ABI and not about this
lowering.

Execution was measured through `browser-host.mjs` on Node, at
`wasm32-kotoba-v1`, for three modules. It is not a claim about
`wasm32-browser-kotoba-v1`, about `wasm32-wasi-kotoba-v1`, about the Component
path, or about a browser engine.
