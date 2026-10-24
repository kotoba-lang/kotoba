# ADR 0001: Use Kotoba bounded documents as the source and runtime contract

Status: accepted

## Context

The former `src/annotation/core.cljk` library returned unrestricted Clojure
maps and depended on host collection semantics. Renaming that file would not
make it portable or safe: its values were heterogeneous, extensible W3C
documents, while Kotoba's general `:map` intentionally stores only bounded
keyword-to-i64 entries.

## Decision

Replace the `.cljc` implementation with `src/annotation/core.kotoba` and use
Kotoba typed ABI v11 `:document` throughout. Documents are bounded canonical
tagged trees, and all construction, lookup, merge, validation, and update work
is performed by admitted pure primitives. The required JSON-LD `@context` key
uses bounded `keyword-from-string`; it is not renamed to a more convenient but
incorrect key.

The build-time compiler is pinned by immutable Git SHA. Produced restricted
JavaScript and Wasm modules have no JVM runtime dependency. Tests execute the
reference semantics and instantiate both generated targets, rather than
asserting source renaming alone.

## Consequences

Host maps, objects, getters, functions, cyclic graphs, non-finite floats,
oversized documents, and forged Wasm externrefs are rejected. Optional fields
are represented by omission. The library's input and output contract is now
`:document`, so callers must migrate at the boundary instead of relying on
ambient Clojure map operations.


## Amendment — 2026-08-13: authority and load path are different things

The migration that this ADR records deleted `src/annotation/core.cljk` and left only
`src/annotation/core.kotoba`. A `.kotoba` file is on no Clojure classpath, so from that
commit onward `annotation.core` could not be loaded by ANY runtime this workspace
ranks above the native path (`kotoba wasm` > `clojurewasm` > ClojureScript > nbb,
and the JVM below them). "Production `.clj`/`.cljc`/`.cljs` sources are forbidden"
was read as "delete the load path", and the two are not the same requirement.

`src/annotation/core.cljk` is restored beside the `.kotoba`, and:

* **the `.kotoba` remains the sole semantic authority.** Nothing about the migration
  is reverted. The restored file is a load path, not a second design.
* **a parity gate holds the two equal.** `test/annotation/parity_test.cljk` compiles the
  `.kotoba` here and runs it through the reference evaluator in the same JVM,
  asserting agreement value by value. Where agreement is impossible it says so in a
  named test rather than dropping the case from the comparison.
* **`kotoba-lang/compiler` moved from `:deps` to the `:test` alias.** A consumer that
  requires the `.cljc` must not drag a compiler in behind it. `kotoba-lang/css`,
  `/dsl-core`, `/async` and `/postfx` set the same boundary.
* **`production-source-authority` is narrowed, not deleted.** `src/` is exactly two
  files. A third file, or a second `.cljc`, is still a fork of the authority and
  still fails.

**Semantics: verbatim, with four divergences asserted — and this is the opposite call
from `dsl-core`/`async`, for a measured reason.** There the guest had FIXED something
(a self-contradicting predicate; an unvalidated constructor), so the restored `.cljc`
adopted the guest. Here the guest is NARROWER than the function it replaced:

1. `specific-resource` no longer renames `:style` to `styleClass`. `styleClass` is the
   Web Annotation property name; `:style` is not. Adopting the guest would mean
   shipping a library that emits a non-spec key.
2. `specific-resource` no longer always emits `:source`; it merges the caller's
   document wholesale.
3. `errors` traps on a non-map document where it used to return a diagnosable
   `:annotation/document-must-be-map` problem.
4. `annotation` keeps an explicitly `nil`-valued known key as a null, where the
   pre-migration function dropped it.

A fifth divergence is a bound, not a behaviour: the KIR document budget is 32 entries
per container, and `annotation` adds `@context` and `:type`, so the guest cannot build
a 33-entry annotation that this namespace builds without complaint. That is the
`async` shape — 32 keys is well inside what a real Web Annotation carries — so it is
recorded as a narrowing of the contract, not an edge case.

Each of the five is a named test. None is excluded from the comparison.

**Removal condition.** The `.cljc` comes out when consumers have a load path that does
not require it — for the native route, ADR-2607279200 W4 in `com-junkawasaki/root`.
Until then, removing it is not a step of the migration; it is an outage.

Recorded in `com-junkawasaki/root` as ADR-2608134800, which follows ADR-2608130900
(`dsl-core`, `async`) and ADR-2608133600 (`postfx`, `cartpole-math`).
