# Otehon chunk-plan reference, 2026-11-13

Input: `network-awai/network-awai-apex` at
`f913f784c18fac0810e233ddec95fc7ef112c005`,
`src/awai/fs/large_file.cljc`, SHA-256
`7c0a85ef7e46c8131d1de307161a7b914fc9c033a28a4d803c96d8bf152b8e7f`.
The file was copied locally and its source was not altered. Separate one-shot
oracle executions, before the Native implementation:

```
nbb v1.4.208
nbb -cp src -e '(require (quote [awai.fs.large-file :as lf])) (doseq [n [0 1 8 9 16 17]] (prn n (lf/chunk-plan n {:leaf-size 8})))'
clojure CLI 1.12.5.1654; Clojure 1.12.5
clojure -Sdeps '{:paths ["src"]}' -M -e '(require (quote [awai.fs.large-file :as lf])) (doseq [n [0 1 8 9 16 17]] (prn n (lf/chunk-plan n {:leaf-size 8})))'
```

Both outputs were byte-identical. Written as `size -> [index,offset,length]`:

```
0  -> []
1  -> [[0,0,1]]
8  -> [[0,0,8]]
9  -> [[0,0,8],[1,8,1]]
16 -> [[0,0,8],[1,8,8]]
17 -> [[0,0,8],[1,8,8],[2,16,1]]
```

These are observations of the reference implementation, not proof of Native
correctness. Native admission is deliberately narrower: only the existing
logical-file v1 fixed profile, at most 1024 leaves of at most 16MiB; larger
Otehon plans do not silently inherit Native qualification. The outputs are
logical extents, not encoded bytes, CIDs, Pack offsets or device I/O. Native
predicates and refusals run separately inside the pinned Amu-built artifact.
The initial nbb invocation from beneath the monorepo attempted dependency
resolution, so it was stopped before producing a result; the recorded run used
an isolated local `nbb.edn` with only `{:paths ["src"]}`. No downloaded package
is part of the oracle or Native execution.
