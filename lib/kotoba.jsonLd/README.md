# kotoba-lang/json-ld

EDN-first helpers for JSON-LD 1.1 documents.

This library keeps JSON-LD data as plain Clojure maps while providing stable
constructors for common JSON-LD objects: context, node, value, list, set, graph,
and compact IRI terms.

It is not a full JSON-LD processor. Expansion, compaction, framing, remote
context loading, and RDF dataset algorithms belong in a later processor layer.

## Test

```bash
kbb -M:test
```
