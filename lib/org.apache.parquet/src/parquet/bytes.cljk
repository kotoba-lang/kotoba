(ns parquet.bytes
  "Parquet's range planning, over the shared byte seam.

  `IByteSource` and its generic helpers were defined here, back when Parquet
  was the only format that needed them. They are now `columnar.bytes` — beside
  `IColumnSource`, which is the other half of the same seam — because a second
  `:scan` format (`org-apache-arrow`) needs the identical protocol, and a copy
  in each means a caller holding a range-reader cannot hand it to both, and an
  instrument that counts bytes has to be written once per format. Two things
  that can substitute for each other are one thing (ADR-2607299700).

  What stays here is the part that is actually about Parquet: `footer-ranges`
  describes *Parquet's* footer, not ranges in general.

  The protocol and helpers are re-exported rather than deleted, so
  `(reify parquet.bytes/IByteSource ...)` and
  `(satisfies? parquet.bytes/IByteSource x)` keep working — these vars hold
  the same protocol, so a source reified through either name satisfies both.
  New code should require `columnar.bytes` directly."
  (:require [columnar.bytes :as cbytes])
  (:refer-clojure :exclude [bytes]))

;; Re-exports. The same vars under a second name, so identity holds across it.
(def IByteSource cbytes/IByteSource)
(def -size cbytes/-size)
(def -read-range cbytes/-read-range)
(def of-vector cbytes/of-vector)
(def prefetched cbytes/prefetched)
(def counting cbytes/counting)
(def read-counts cbytes/read-counts)
(def source cbytes/source)
(def of-fn cbytes/of-fn)

(def footer-suffix-bytes
  "The fixed tail every Parquet file ends with: a 4-byte footer length and
  `PAR1`."
  8)

(defn footer-ranges
  "The ranges a caller must fetch, in order, to parse the footer of a file of
  `size` bytes.

  The second depends on the first, so this returns a map rather than a list:
  an async caller fetches the tail, hands it back, and is told what to fetch
  next. Stating the dependency in the type is cheaper than discovering it as a
  wrong answer from a single speculative read."
  [size]
  {:tail [(- size footer-suffix-bytes) size]})
