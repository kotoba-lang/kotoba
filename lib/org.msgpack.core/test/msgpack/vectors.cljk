(ns msgpack.vectors
  "Known-answer vectors produced by the REAL `@msgpack/msgpack`.

  Provenance: `scripts/gen-mst-vectors.mjs` in `kotoba-lang/checkpointer`
  imports `@msgpack/msgpack`, encodes the values below, and writes the hex to
  `test/kotoba/lang/checkpointer/mst_vectors.edn` under `:msgpack_vectors`.
  Both halves are transcribed here — the values from the generator's source,
  the bytes from its output — so that this library stays a leaf. An oracle
  that lives in the repository it is meant to check is not an oracle.

  These are the only vectors here with independent provenance. Everything
  else in the suite is round-trip, which can only tell an encoder that agrees
  with its own decoder from one that agrees with MessagePack if at least one
  end is pinned by bytes someone else produced.

  Two entries carry a note about the host, not about the codec:

  `array_with_float` is `[1 2.5 3]` and not `[1.0 2.0 3.0]` on purpose.
  JavaScript has one numeric type, so `@msgpack/msgpack` writes `3.0` as a
  fixint while the JVM writes a float64. A vector containing a whole-valued
  double could therefore never agree with both."
  (:require [msgpack.bytes :as b]))

(def long-str (apply str (repeat 500 "x")))

(def vectors
  "Each entry is `{:name :value :encoded}`. `:encoded` is lowercase hex."
  [{:name "nil" :value nil :encoded "c0"}
   {:name "true" :value true :encoded "c3"}
   {:name "false" :value false :encoded "c2"}
   {:name "zero" :value 0 :encoded "00"}
   {:name "small_pos_fixint" :value 42 :encoded "2a"}
   {:name "small_neg_fixint" :value -5 :encoded "fb"}
   {:name "uint8" :value 200 :encoded "ccc8"}
   {:name "uint16" :value 60000 :encoded "cdea60"}
   {:name "uint32" :value 3000000000 :encoded "ceb2d05e00"}
   {:name "int8" :value -100 :encoded "d09c"}
   {:name "int16" :value -30000 :encoded "d18ad0"}
   {:name "int32" :value -2000000000 :encoded "d288ca6c00"}
   {:name "float64" :value 3.5 :encoded "cb400c000000000000"}
   {:name "str_short" :value "hi" :encoded "a26869"}
   {:name "str_long" :value long-str :encoded (str "da01f4" (apply str (repeat 500 "78")))}
   {:name "bin" :value {:msgpack/bin [1 2 3 255 0]} :encoded "c405010203ff00"}
   {:name "array" :value [1 "two" 3 nil true] :encoded "9501a374776f03c0c3"}
   {:name "array_with_float" :value [1 2.5 3] :encoded "9301cb400400000000000003"}
   ;; array-map, because MessagePack writes map entries in order and a
   ;; hash-map does not have one. The generator's JavaScript object preserved
   ;; insertion order, so byte equality requires the same order here.
   {:name "map"
    :value (array-map "a" 1 "b" "two" "c" [1 2])
    :encoded "83a16101a162a374776fa163920102"}
   {:name "nested"
    :value (array-map "op" "put"
                      "meta" (array-map "kind" "writes")
                      "payload" {:msgpack/bin [9 8 7]})
    :encoded "83a26f70a3707574a46d65746181a46b696e64a6777269746573a77061796c6f6164c403090807"}])

(defn bytes-of [{:keys [encoded]}] (b/unhex encoded))
