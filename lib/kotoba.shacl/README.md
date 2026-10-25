# kotoba-lang/shacl

A bounded SHACL-inspired validator authored as sovereign `.kotoba` source.
Canonical documents are accepted and returned across the reference evaluator,
restricted JavaScript, and typed Wasm. JVM Clojure is a compiler/test host only.

The portable contract covers nested keyword paths, scalar/vector normalization,
minimum and maximum counts, datatype checks, arbitrary canonical-document `:in`
membership, IRI/literal node kinds, ordered validation errors, and shape
constructors. Containers are limited to 32 entries, strings retain the 64 KiB
UTF-8 budget, and an error result that exceeds the document budget fails closed.

`node-shape` accepts one bounded vector of property shapes. This is the explicit
portable ABI replacement for the former unbounded variadic Clojure constructor.

## Test

```bash
kbb -M:test
```
