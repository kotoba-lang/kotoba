(ns parquet.snappy
  "Snappy for Parquet pages — a thin delegation to `com-google-snappy`.

  This namespace held its own decoder until 2026-08-30, when the codec got a
  repository of its own so the Parquet WRITER could compress with it and Avro
  could stop refusing the name for want of an implementation. Two copies of a
  format is how they drift, so this is now the Parquet-shaped call and nothing
  more: raw format, and the declared length checked against what the page
  header promised."
  (:require [snappy.core :as snappy])
  (:refer-clojure :exclude [bytes]))

(defn decompress
  "Raw snappy in `bs[start,end)` -> a vector of unsigned ints.

  `expected` is the uncompressed size the page header promised. Checked, not
  ignored: a disagreement means the stream and the metadata describe different
  things, and continuing hands the decoder a buffer whose contents look like
  data."
  ([bs] (snappy/decompress bs))
  ([bs start end expected] (snappy/decompress bs start end expected)))
