# kotoba-lang/activitystreams

ActivityStreams 2.0 constructors authored as sovereign, bounded `.kotoba`
source. Canonical documents are accepted and returned across reference,
restricted JavaScript, and typed Wasm. JVM Clojure is a compiler/test host only.

Collections contain at most 32 entries, strings retain the 64 KiB UTF-8 budget,
and malformed document shapes fail closed.

## Test

```bash
kbb -M:test
```
