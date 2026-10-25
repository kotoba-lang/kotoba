# ADR 0001: Turtle serialization is sovereign Kotoba

`src/turtle.kotoba` is the sole production language source. JVM Clojure is a
compiler/test host only and is not a production runtime.

The serializer preserves IRI, blank-node, literal, datatype, language, prefix,
triple, one-argument Turtle and two-argument Turtle behavior. Prefix maps are
canonical bounded documents and therefore render in deterministic keyword-key
order. Inputs admit at most 32 prefixes and 32 triples; all intermediate and
result strings retain the 64 KiB UTF-8 budget. Unknown or malformed terms fail
closed and the program declares no effects.

Conformance covers observable strings, typed ABI, declared effects, resource
bounds, and rejection behavior across reference execution, restricted
JavaScript, and instantiated typed Wasm.
