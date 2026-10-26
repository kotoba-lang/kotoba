# ADR-0007 — Safe Kotoba on aiueos: kotoba:kais host surface

- Status: accepted and implemented
- Date: 2026-06-27

## Context

aiueos now accepts components whose `:aiueos/source` is safe Kotoba / CLJ and
compiles them through `kotoba-clj` before launch. That creates a second security
boundary in addition to the Wasm host ABI:

1. **Compile time:** safe-kotoba rejects ambient language authority and emits
   only host imports implied by the source.
2. **Broker time:** aiueos verifies the manifest and policy, then converts the
   conferred capabilities into a `kotoba_clj::Policy`.
3. **Runtime:** the wasmtime host import implementation checks the same concrete
   target before doing any work.

This ADR pins the `kotoba:kais` host surface that makes that chain executable.
It is deliberately narrower than a production KAS/KQE/LLM service: Phase-0 keeps
the provider in-process and deterministic unless the caller explicitly supplies
fixtures.

## Decision

Bind three `kotoba:kais` interfaces in `src/host.rs`, all behind the existing
per-component conferred capability set:

| interface | guest builtin | capability |
|---|---|---|
| `kotoba:kais/auth@0.1.0` | `(has-capability? resource ability)` | `kotoba.auth/self` |
| `kotoba:kais/kqe@0.1.0` | `(kqe-assert! g s p obj)` / `(kqe-retract! ...)` | `kotoba.graph-write/<graph>` |
| `kotoba:kais/kqe@0.1.0` | `(kqe-get-objects g s p)` / `(kqe-query filter)` | `kotoba.graph-read/<graph>` or `kotoba.graph-read/*` |
| `kotoba:kais/llm@0.1.0` | `(llm-infer model prompt)` | `kotoba.infer/<model>` or `kotoba.infer/*` |

The runtime gate is target-aware. A program that compiled with a broad grant
still cannot write graph `b` unless the conferred runtime set contains
`kotoba.graph-write/b` or `kotoba.graph-write/*`. The same rule applies to graph
reads and model inference.

### Source compatibility

`.kotoba` is the preferred extension for safe Kotoba source. The loader also
honors `.cljc` reader conditionals using the Kotoba reader target, so
`#?(:kotoba ... :clj ... :default ...)` selects the Kotoba branch when aiueos
compiles a source component.

### KQE store

KQE state is an in-process graph store threaded through the broker across
components in a boot round, exactly like the topic bus. `aiueos up --kqe-store
path.edn` loads the graph before boot and writes it back after a successful boot,
allowing state to persist across invocations.

The persisted EDN format is:

```edn
{:aiueos/kqe
 [{:graph "kg"
   :subject "alice"
   :predicate "kg/name"
   :object-hex "76616c7565"}]}
```

Objects are raw `list<u8>` bytes from the guest ABI, encoded as lowercase hex on
disk.

### KQE query filter

`(kqe-query filter)` supports two filter shapes:

```clojure
(kqe-query "")          ;; all readable quads
(kqe-query "kg/role")   ;; backward-compatible predicate filter
(kqe-query "{:graph \"kg\" :subject \"alice\" :predicate \"kg/role\"}")
(kqe-query "{:graph \"kg\" :datomic {:find [?name] :where [[?e :kg/role \"admin\"] [?e :kg/name ?name]]}}")
```

The EDN map form may contain any subset of `:graph`, `:subject`, and
`:predicate`, each a string. With the `kototama` feature it may also contain
`:datomic`, whose value is passed to `kotoba-datomic::q` after the readable KQE
snapshot is materialized as Datomic datoms. Unknown keys, namespaced keys,
non-keyword keys, and non-string lightweight filter values trap at runtime. When
`:graph` is present, the host re-checks `kotoba.graph-read/<graph>` before
scanning or materializing the Datomic snapshot. In all cases returned rows are
filtered again by readable graph, so a broad query cannot leak quads from graphs
the component cannot read.

### LLM fixtures

LLM inference is deterministic by default. aiueos does not read environment
variables, secrets, network credentials, or external model APIs from inside the
host import. Instead, callers may inject a fixture map:

```edn
{:aiueos/llm {"modelA" "fixture-answer"}}
```

`aiueos run ... --llm-fixture llm.edn` and `aiueos up ... --llm-fixture llm.edn`
wire the fixture into `kotoba:kais/llm.infer`. The component must still hold
`kotoba.infer/modelA`. A missing fixture response returns the guest ABI's error
variant, which safe Kotoba observes as an empty handle (`0`), not ambient IO.

## Consequences

- The same authority is checked three times: source policy, broker grant, and
  runtime host call target. This is intentional defense in depth.
- KQE and LLM calls are now executable in aiueos, not only compile-time imports.
- Fixture-backed LLM keeps tests and agent workflows deterministic while leaving
  real external provider and secret management as a separate production surface.
- KQE query now has a narrow Datomic bridge for real kotoba-datomic `:find` /
  `:where` queries while keeping graph/subject/predicate filters available for
  the small Phase-0 host surface.

## Remaining work

- A production LLM provider must have an explicit secret boundary and audit model.
- KQE needs a versioned query envelope if the Datomic bridge grows additional
  inputs, rules, pull support, or pagination.
- External KAS/KQE persistence and replication are out of scope for this ADR.
