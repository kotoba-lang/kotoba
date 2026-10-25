# kototama-component

Kototama's **Component engine host** — a replaceable native engine process
and the narrow JSON protocol used to execute an already admitted Component.

GitHub id `1312921812`. Previously `tender-component`; that URL still redirects.
The product is [`kototama`](https://github.com/kotoba-lang/kototama) (言霊).
`kototama` owns the contracts, admission envelope, provider boundary, and
aiueos grant translation. This repository owns the engine process. No WASI
directories, environment, arguments, or inherited stdio are exposed.
See root ADR-2608139980.

The bundled Rust micro-TCB uses Wasmtime with a minimal feature set. Other
engines may implement the same host protocol without entering `kototama` core.
The CI matrix executes compiler-produced typed v0.3 Components through three
engine paths:

- the Rust/Wasmtime micro-TCB, which instantiates Component Model binaries;
- pinned `jco` bindings under Node.js, as an independent Component adapter;
- the actual Cloudflare `workerd` binary. `jco` performs only the portable
  Component-to-ESM/Core-Wasm adaptation; workerd remains the engine.

The qualified world contains no ambient WASI. Authority is split into the
individually named `identity.sign`, `identity.verify`, `hash.sha256`,
`http.post`, `http.get-stream`, `object-store.get-stream`,
`object-store.put-block`, `object-store.compare-and-set-ref`, `log.read`,
`log.append`, and `clock.now` operations. Every call first acquires a
host-owned grant for exactly one operation. Wasmtime and jco/Node additionally
recheck the scoped ability, lease epoch/expiry, item/byte quota, and persistent
audit receipt at the provider boundary.

The workerd qualification places eight payload-carrying Components (the five
core operations plus three object-store operations) in one isolate whose
`globalOutbound` service is deny-all. It exposes only their named WIT
interfaces and checks the exact results
`4,0,1,3,1,32,202,4`. The Component type is checked before transpilation so a
v1 binary cannot pass under v0.3 metadata.

The separate `tender-resident-component-host` binary provides the resident
mode for murakumo canaries, keeping that authority surface out of the typed
v0.3 protocol host.
It binds loopback only, verifies the exact Component bytes before readiness,
and emits node-key-signed, fsync'd execution receipts. It does not add a WASI
linker. With no capability configuration it is provider-free; with a
SHA-pinned configuration it links only the typed HTTP, append-only storage,
and LLM imports admitted for the cloud-itonami effect chain, recording every
call in the receipt.

## The `.kotoba` cores here are not delegated, and will not be

ADR-2608120200 asks every repository holding `.kotoba` to state whether those
cores are running. The honest answer today is: **not at the moment.**

They are the qualification fixtures for the capability-gated host, compiled to
Component Model binaries and executed by the engines above — Chromium via
`jco`, and `workerd`. That happens in the `browser-component` and
`workerd-component` jobs of `.github/workflows/ci.yml`, and GitHub Actions is
disabled for this repository, as it is workspace-wide since ADR-2607300900
moved CI to the murakumo fleet. The last run was 2026-08-04, and the fleet has
no gate for this repository yet. So the fixtures are intact and correct, and
nothing is currently running them. Porting those qualification jobs to
`scripts/fleet-ci/gates.edn` is what would change that answer; until then the
`kbb -M:test` suite below is the only thing this repository executes.

Nothing executes the cores in-process, and that part is not a gap.

That is deliberate, and it is where the workspace's migration pattern stops.
ADR-2608112100 completes a Kotoba core by having the host run the shipped
artifact through `kotoba.kir/execute`, and several repositories now do exactly
that. It also states the limit: delegation is not tender — it is in-process
interpretation with no capability gate and no supervisor, fit for
`kotoba/pure` cores because they have nothing to gate. This repository is what
the other side of that sentence refers to.

**Size is not what stops it.** That ADR's measured boundary is the interpreter's
ADT node limit, which refuses a core holding a collection that grows with the
domain. Nothing here is close: the cores compile to 66–90 KIR nodes and every
one of them takes zero parameters, because a fixture carries its input as a
literal. What disqualifies them is authority, not shape.

Ten of the eleven cores carry an effect, one per admitted operation:

| core | declares | admitted under |
|---|---|---|
| `workerd-identity-sign-component.kotoba` | `:identity/sign` | `[:cap/call 1]` |
| `workerd-identity-verify-component.kotoba` | `:identity/verify` | `[:cap/call 2]` |
| `workerd-hash-component.kotoba` | `:hash/sha256` | `[:cap/call 3]` |
| `workerd-http-post-component.kotoba` | `:http/post` | `[:cap/call 4]` |
| `workerd-log-read-component.kotoba` | `:log/read` | `[:cap/call 5]` |
| `workerd-component.kotoba` | `:log/append` | `[:cap/call 6]` |
| `workerd-stream-component.kotoba` | `:http/get-stream` | `[:cap/call 13]` |
| `workerd-object-get-component.kotoba` | `:object/get-stream` | `[:cap/call 14]` |
| `workerd-object-put-component.kotoba` | `:object/put-block` | `[:cap/call 15]` |
| `workerd-object-cas-component.kotoba` | `:object/compare-and-set-ref` | `[:cap/call 16]` |

The eleventh, `browser-component.kotoba`, is `(defn main [] 42)`. It takes zero
parameters, so there is no decision in it to move, and its host asserts `42`
independently — which is what a conformance fixture is made of.

Measured 2026-08-12 against `kotoba-kir` `ccfc65b9`, the sha the pinned
compiler declares, by compiling each core under its own policy and executing
the resulting KIR directly. Two of the ten lower to KIR at all, and both then
perform their effect with nothing in the way:

```
workerd-component        (:log/append)     68 nodes
  kir/execute, no handler        => trap :capability-denied
  kir/execute, :typed-cap-call   => ran: capability 6 received "安全"

workerd-object-put-component (:object/put-block)  90 nodes
  kir/execute, :typed-cap-call   => ran: capability 15 received
                                    {:key "blocks/hash" :bytes "payload"}
```

The second line of each is the argument. `kotoba.kir/execute` takes `:cap-call`
and `:typed-cap-call` as plain caller-supplied functions. The policy is spent
at compile time — `:phase :admission` — and the shipped KIR carries no trace of
it, so nothing at the seam consults an allow-list, an ability descriptor, a
lease epoch, an audit sink, one-shot accounting, or a pinned host identity.
`tender.component/run-effectful!` enforces all of them. A KIR oracle here would
not be a lighter tender path; it would be a block written to the object store
with the gate taken off.

The other eight do not reach that seam even in principle. Their typed
request/response records and async task/stream resources are outside the KIR
vocabulary, and the compiler refuses at `:phase :wasm-typed-lowering` with
`typed Wasm operation is not qualified` — `bytes-response-byte-count`,
`http-response-status`, `bool-result`, `log-read-byte-count`, `object-cas-won`,
`bytes-task-byte-count`.

`tender.qualification-core-test` holds this shut. It fails if a core's declared
capabilities change without that table changing, and if a `.kir.edn` or a
`kotoba.kir` require appears while any core still carries an effect.

```sh
kbb -M:test
cargo test --locked --manifest-path native/component-host/Cargo.toml
```

## Execution contract entrypoints

Neutral descriptors are imported from `kotoba.core.execution` (core-contracts).
Component/WIT profiles and unchanged mixed v1 identity/lease codecs are imported
from `kotoba.abi.component` (abi). The old `kotoba.abi.contract` facade remains
readable for existing callers; new production imports select their owner.
The [integration contract](spec/execution-profile-integration.edn) records this
cutover. Existing v1 blocks/WIT/CIDs remain unchanged; v2 neutral identities
require a verified target binding and fresh CID/signature. This change does not
enable v2 runtime admission or claim Q9/native qualification.
