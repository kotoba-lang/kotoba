# mesh

HTTP mesh-route runtime for compiled Kotoba guests.

This repository owns route compilation/admission at startup, HTTP serving, and
runtime dispatch. It consumes the language compiler/runtime and self-host
contract; it does not own language semantics, fleet placement, or security
policy.

## Is the Kotoba running? (ADR-2608120200)

**Yes, since 2026-08-12: the HTTP contract is decided by a shipped Kotoba
core.** `src/kotoba/mesh/route.kotoba` is compiled to
`resources/mesh/oracle/route.kir.edn`, and `kotoba.mesh.node` executes it
through `kotoba.mesh.kotoba-oracle` on every request — which url shapes this
node recognises, which route a path names, whether a guest that ran had
anything to answer with, what outcome that is, and what status it gets. There
is no `.cljc` twin of those rules to drift from, because there is no second
copy.

What stayed in the host, and why:

| stays in `node.clj` | because |
|---|---|
| the route table | a collection that grows with the deployment. ADR-2608112100 measured the boundary — the core is handed a *boolean* saying the route was bound, so it sees the same four scalars whether the node serves one route or ten thousand |
| Chicory dispatch, reading guest memory, writing the socket | effects, not decisions |
| `compile-route`'s check-before-emit | the rule IS an order between two effects a guest cannot call. Delegating it would move the shadow and leave the rule |
| the `/health` body | it names which runtime answered — a fact about this host, not something the contract derives |
| which host imports are bound, and the `:llm-client` behind `llm_infer` | an LLM client is outbound network authority plus a credential. It is host configuration a node is *given*, never something a guest can name — see below |

Two gates exist that a behavioural test cannot replace
(`test/kotoba/mesh/kotoba_oracle_test.cljk`):

- **drift** — the shipped artifact is the current source, compiled. The
  existing suite never reads the artifact, so without this a stale one is
  invisible.
- **delegation** — a substituted core with the same exports and deliberately
  different answers is registered, and the live server is required to *follow*
  it over real HTTP. A host that had kept its own `cond` passes every other
  test in this repository; this is the only one that separates them. Verified
  by mutation: reverting one delegated call to a host copy fails this and
  **nothing else**.

## `llm/infer` from a mesh guest

A guest running here can call `llm_infer` (kotoba-core-contracts capability id
225, ABI `(prompt-ptr prompt-len out-ptr out-cap) -> bytes-written | -1`).
`examples/mesh_llm_answer.kotoba` does, and `test/kotoba/mesh/llm_infer_test.cljk`
drives it over a real socket. Before this, `dispatch` bound only the kgraph-*
imports, so such a guest could not even be instantiated — Chicory links by
(module, field) and `.build` throws on an unsatisfied import.

The client is **injected, never ambient**:

```clojure
(mesh-node/start! {"llm-answer" (mesh-node/compile-route
                                  "examples/mesh_llm_answer.kotoba"
                                  "examples/mesh_llm_answer_policy.edn")}
                  8080
                  {:llm-client {:infer-fn (fn [prompt] ...)}})
```

Nothing in this repository reads an API key or names a provider endpoint. An
operator supplies the `:infer-fn` — murakumo's own OpenAI-compatible boundary
`https://api.murakumo.cloud/v1`, for instance — and this code never learns what
it is. `kotoba.wasm-exec/default-host-state` ships `:llm-client` as nil on
purpose, and a node started without one **still serves the import**: a granted
guest runs, gets `-1`, makes no network call, and `route.kotoba`'s `answer?`
turns that into the same 204 an assert-only guest gets. Binding the import
unconditionally is what keeps *no client* and *no grant* distinguishable — the
latter throws from the capability guard.

The call is guarded exactly as the kgraph ops are: one entry of
`kotoba.wasm-exec/real-op-effects` handed to
`kotoba.wasm-exec/guarded-host-functions`, so `guard-host-call` checks it per
call against the route's compiled policy, fail-closed and receipted. There is
no unguarded path, and only that one op is bound — not the filesystem, http or
keychain surface `real-host-functions` would have wired.

Two refusals, both asserted **on their reason** rather than on "something
failed":

| when | what refuses | reason |
|---|---|---|
| startup | `compile-route`'s check-before-emit | `:capability-not-granted` |
| dispatch | `guard-host-call` | `:kotoba.host/denied :empty-intersection`, `:kotoba.host/call llm-infer` |

Each negative was verified by mutation — the mutation, and the failure it
produced, are recorded in the commit that landed them.

### `examples/*.kotoba` are not decision cores

The four `.kotoba` files under `examples/` are guest **payloads**, not cores,
and this seam does not compile or ship them. Compiling operator-supplied
`.kotoba` routes at startup is what this repository is *for* — precompiling one
into a shipped artifact would defeat it. `mesh_drama_profile.kotoba` is a ported
mesh app; `mesh_llm_answer.kotoba` calls `llm_infer`;
`mesh_no_answer.kotoba` and `mesh_bad_route.kotoba` are fixtures for
the 204 and the startup-rejection branches. They stay where they are, compiled
fresh by `compile-route`.

## Test

```sh
kbb -M:test
kbb -M:lint
```

Regenerate the shipped decision core after editing `route.kotoba` (the compiler
lives in `:test`, so it never reaches a consumer):

```sh
kbb -M:test:gen
```
