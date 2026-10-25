# ADR 0001: ActivityStreams construction is sovereign Kotoba

`src/activitystreams.kotoba` is the sole production language source. JVM
Clojure is a compiler/test host only and is not a production runtime.

The former open EDN values become bounded canonical documents. `ensure-vector`
uses the closed `document-kind` discriminator so null, an existing vector, and
a scalar remain distinct without host reflection. Constructors preserve the
ActivityStreams context, type names, optional activity fields, scalar-to-vector
normalization for `to` and `cc`, validation, and error documents.

Containers admit at most 32 entries and strings retain the 64 KiB UTF-8 budget.
Malformed maps, invalid scalar representations, forged host values, budget
overflow, and fuel exhaustion fail closed. The program declares no effects.
Conformance covers observable values, typed ABI, effect declarations, resource
bounds, and rejection across reference, restricted JavaScript, and instantiated
typed Wasm.
