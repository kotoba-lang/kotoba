# com-fabbers-stl

Rust-free, portable STL intake for the kotoba CAD/Kami pipeline.

`kotoba.fabbers.stl` parses ASCII STL into EDN facets, reports bounds and
surface area, and rejects malformed geometry explicitly. It does not execute
slicing or machine toolpaths; those stay policy-gated host operations.

```clojure
(require '[kotoba.fabbers.stl :as stl])
(stl/inspect "solid part ... endsolid part")
```

Binary STL is an explicit byte-buffer adapter boundary, never inferred from a
misleading `solid` header.

```sh
kbb -M:test
kbb -M:lint
```
