# kototama hosts

Product name: **kototama**. The Solo5 word *tender* names the attendant-host
role, not a product. Root authority: `com-junkawasaki/root` ADR-2608139980.

This repository owns Kototama's abstract VM contract, profile definitions,
admission envelope, budgets, and `kototama → aiueos` grant translation. It
plays the EVM-like role of defining a stable execution environment; this does
not imply Ethereum bytecode compatibility. Concrete hosts implement artifact
execution profiles and stay in sibling repos so Kototama core does not ship a
specific engine, loader, or provider. The Lisp/IPLD transition contract and
EVM/FVM/FEVM compatibility profiles are defined in
[`kototama-virtual-machine.md`](kototama-virtual-machine.md).

## Portable application default

For an ordinary portable Kotoba application, Amu emits the canonical
`kototama.vm/program` DAG-CBOR artifact and Kotoba VM executes a supported
Kototama profile. This compiler default is owned by Amu; this repository owns
the artifact semantics and versioned VM contract. The current Kotoba VM
implementation is a partial `core/v1` profile, so consumers must check its
profile declaration before selecting operations.

Native ELF, browser/Node Wasm and WASI Component remain explicit, independently
qualified host/target profiles. They do not replace or redefine the canonical
Kototama program format. JVM/Chicory remains compatibility and diagnostic
coverage. AiueOS is one possible host; consensus remains an optional deployment
layer outside the VM.

| Host | Repository | Artifact | Why it is not this tree |
|---|---|---|---|
| browser / Wasm | `kotoba-lang/wasm-webcomponent` | AOT `.wasm` | one host profile; not the default or VM definition (ADR-2607061630) |
| native ELF | `kotoba-lang/kototama-native` | sealed native / ELF | ns `kototama.native.executor`; formerly `tender-native` |
| Component engine | `kotoba-lang/kototama-component` | admitted Component | Rust/Wasmtime micro-TCB must not enter kototama core (ADR-2607266000 D4) |
| JVM / Chicory | `src/kototama/tender.cljk` | Core Wasm via Chicory | compatibility and diagnostic implementation |

There is no engine priority order. Each claim is bounded to the exact
Kototama version, target, host operating system, operation and effect surface
covered by conformance evidence. Passing on one engine or OS does not qualify
another combination.

Aliases `:native-host` and `:component-host` on this repo's `deps.edn`
point at the sibling hosts. They are extra-deps, not core.

Do not add `provider` here. Providers are the hands aiueos may lend;
kototama binds them after a grant.
