# codebase

Content-addressed semantic definition identity, verified local persistence, and
hash-native authoring and evaluation for Kotoba code.

This repository owns canonical semantic blocks, namespace commits, closure
transfer, and pure build-cache keys. It does not parse source, compile or
execute components, serve network traffic, or grant runtime authority.

## What is addressed by hash

| Namespace | Owns |
| --- | --- |
| `semantic-code` | lowering a checked definition to canonical DAG-CBOR and its CIDv1 |
| `store` | immutable verified block persistence, namespace heads, CAS, merge |
| `ir` | reading blocks back: link decoding, reference traversal, CID substitution |
| `evaluator` | evaluating a definition by hydrating its dependencies BY CID |
| `authoring` | scratch source in, namespace commit out, with update propagation |
| `render` | projecting a stored definition back to readable source (`view`) |
| `names` | name / hash / abbreviation lookup, dependents, dependencies |
| `fetch` | bounded, verified hydration of a closure from an injected transport |
| `typed-code` | definition identity computed from the compiler's checked KIR |
| `typed-eval` | executing that KIR through the language oracle, hydrated by CID |
| `value-runtime` | bounded run-local Handle ↔ ValueCID resolution over canonical immutable values |

Two identity layers exist and they are not interchangeable. `semantic-code`
hashes an IR this repository normalizes for itself; `typed-code` hashes the
**checked KIR** the compiler produces and the backends consume, and binds the
typed interface (parameter types, result, declared effects) alongside the body.
Prefer `typed-code` for anything that will also be compiled: it is the layer
where what a definition IS and what gets executed are the same object, and its
language coverage is the compiler's rather than a hand-maintained subset.

**A third identity exists outside this repository, and it is the authority.**
`lang/code-identity.edn` (kotoba-lang/kotoba-lang) names
`kotoba.kir.definition-identity` (payload version 2, canonical DAG-CBOR, 10
frozen vectors, JVM/ClojureScript byte-identical) as the definition-CID
implementation, and `typed-code` does not call it: it hashes its own canonical
form, so the same definition gets a different CID from each (measured
2026-09-02, pinned by `test/kotoba/codebase/typed_code_identity_divergence_test.cljk`).
The recorded direction (`lang/code-identity.edn :identity-implementations`) is
that `typed-code` adopts `kotoba.kir.definition-identity` as its hashing core
under a versioned migration; that migration moves stored typed-code CIDs and
has not been done. Effect rows are the sharpest difference: `typed-code` seals
whatever it is handed as a string (a compiler wire row `[:cap/call 9]` becomes
the string `"[:cap/call 9]"`), while `kotoba-kir` refuses the wire row and seals
the named operation reached through `effect-row-from-hir`. Do not "fix" one
side to match the other quietly -- the divergence test exists so that it is done
on purpose.

Alpha-normalization in `typed-code` is verified rather than assumed. KIR has
five binding forms, and a sixth added later would silently leave a
source-chosen name inside a hash — so a binder that survives renaming fails the
compile closed instead.

Three properties hold by construction and are covered by tests:

- **A definition runs from its hash alone.** `evaluator/invoke` reads the block,
  hydrates every dependency by CID, and never consults a file, a namespace, or
  a name. Dropping every binding that points at a definition does not change how
  it runs; a missing dependency fails closed instead of falling back to a name.
- **An update propagates by rewriting, not recompiling.** `authoring` compiles a
  scratch buffer against the names a namespace currently selects, then rewrites
  each dependent's stored IR so its dependency CID points at the new definition.
  Dependent *source* is never required to still exist.
- **Received bytes are checked before they are believed.** `fetch` verifies that
  bytes hash to the CID that was requested *and* that they are the canonical
  encoding of what they decode to, so an untrusted provider can be wrong but not
  convincing.

Names are a lookup layer, not identity. A rename changes the namespace commit
and no definition CID; an ambiguous hash abbreviation is rejected rather than
resolved to whichever candidate sorts first.

Values use the same separation at runtime: `ValueCID` is a portable logical
address, `Handle` is a run-local bounded slot, and `Cap` remains authority.
`value-runtime` interns or hydrates canonical `kotoba.value.v1` blocks, rejects
forged handles, never reuses a released handle, and keeps runtime collection
separate from persistent CAS retention. It is the reference host kernel; Wasm
and native callback ABI adoption is tracked separately and must preserve this
contract rather than expose CIDs on the hot path.

`value-runtime-abi` fixes the shared backend boundary as five synchronous
operations over canonical bytes, CID text, and scalar handles. Wasm
typed-`externref` imports and native context callbacks are transports for this
ABI; they may not reinterpret the bytes or derive authority from a CID.

## Typed eval is admitted eval

`typed-eval/admit` is the public evaluation boundary. It accepts a definition
CID, rehydrates the checked KIR closure, checks the exact result descriptor and
the complete effect row against the caller's current allowance, binds finite
fuel and nested-eval depth, and returns a content-addressed admission capsule.
`typed-eval/invoke-admitted` rehashes that capsule before execution and binds the
result to a value CID.

This is deliberately not host `eval`, `load-string`, or mutable-name lookup.
A result hash is evidence after a computation; it cannot authorize effects
that happened before the result existed. Definition identity, admission
authority, and result evidence therefore remain three distinct hashes.

## Test

```sh
kbb -M:test
kbb -M:lint
```
