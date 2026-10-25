# kotoba-lang/vc

Bounded W3C Verifiable Credential and Verifiable Presentation constructors and
validators authored as sovereign `.kotoba` source. Canonical documents execute
through the reference evaluator, restricted JavaScript, and typed Wasm. JVM
Clojure is a compiler/test host only.

The portable contract preserves default and custom JSON-LD contexts, distinct
credential/presentation types, all optional credential fields, presentations,
recognizers, ordered validation errors, and scalar/vector normalization.
Collections contain at most 32 entries and strings retain the 64 KiB UTF-8
budget; malformed host values fail closed.

Former variadic type constructors now accept one bounded vector of keyword
documents. Credential and presentation option maps use canonical document keys.

## Test

```bash
kbb -M:test
```
