# kotoba-lang/n-quads

N-Quads serializer authored as sovereign `.kotoba` source. It accepts bounded
canonical document RDF terms, performs literal fail-closed escaping, and runs
through the reference, restricted JavaScript, and typed Wasm targets. JVM
Clojure is used only by the compiler/test harness.

Each call admits at most 32 quads and all strings remain within the compiler's
64 KiB UTF-8 value budget. Unknown or malformed terms are rejected.

## Test

```bash
kbb -M:test
```
