# kotoba-lang/turtle

Turtle serializer authored as sovereign `.kotoba` source. It preserves RDF
terms, prefix maps and both Turtle call arities over bounded canonical document
values. JVM Clojure is used only by the compiler/test harness.

Prefix and triple collections are bounded to 32 items, strings to 64 KiB UTF-8,
and malformed terms fail closed. Compatibility is verified by observable output
and rejection behavior across reference, restricted JavaScript and typed Wasm.

## Test

```bash
kbb -M:test
```
