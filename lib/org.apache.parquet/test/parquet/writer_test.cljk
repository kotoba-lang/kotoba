(ns parquet.writer-test
  "The writer, checked against this repo's reader and the engine.

  **This suite cannot establish that the output is valid Parquet**, and the
  history of this file is the proof. Two measured failures, both invisible
  from inside the repo:

  1. The first version round-tripped through `parquet.source` perfectly while
     pyarrow refused to open it at all — `ColumnChunk.file_offset` is
     `required` in the thrift IDL and our reader never looks at it.
  2. The second opened cleanly with **every statistic invisible** to pyarrow —
     without `column_orders` the spec forbids trusting `min_value`/`max_value`,
     so a file whose statistics only this repo could see would have failed at
     the one job the writer was given.

  So the correctness gate is `test/fixtures/verify_written.py`. What this
  suite is for: values, nulls, chunking, refusals, and the property the writer
  exists for — that a file written here **prunes**."
  (:require [clojure.test :refer [deftest is testing]]
            [columnar.aggregate :as agg]
            [columnar.plan :as plan]
            [columnar.source :as csrc]
            [columnar.vector :as cvec]
            [parquet.footer :as footer]
            [parquet.source :as psrc]
            [parquet.thrift :as th]
            [parquet.write :as w]))

(defn- read-back [bs column]
  (let [s (psrc/open bs)]
    (vec (mapcat (fn [c]
                   (let [col (csrc/-read-column s c column)]
                     (map #(cvec/value-at col %) (range (cvec/count col)))))
                 (range (csrc/-chunk-count s))))))

(def ^:private sample
  [["price"  (cvec/column :int64 [10 20 30 110 120 130 210 220 230])]
   ["region" (cvec/column :utf8 ["east" "east" "west" "west" "east" "east" "east" "west" "west"])]
   ["note"   (cvec/column :utf8 [nil "clearance" nil nil nil "sale" nil nil nil])]
   ["ratio"  (cvec/column :double [1.5 2.25 nil -0.5 0.0 3.75 nil 1.0 -2.5])]])

(defn- three-row-groups []
  (w/file {:fields (w/fields-of sample)
           :batches (mapv (fn [i]
                            (mapv (fn [[_ c]]
                                    (cvec/take-rows c [(* 3 i) (+ 1 (* 3 i)) (+ 2 (* 3 i))]))
                                  sample))
                          (range 3))}))

;; ── the reason this writer exists ───────────────────────────────────────────

(deftest a-file-we-wrote-prunes
  ;; Arrow records no statistics, so an object materialised as Arrow is read
  ;; whole by every later query. Parquet is the format that fixes that, and
  ;; this is the assertion that it did: the writer computed min/max as it went
  ;; and put them where `parquet.source` finds them without touching a page.
  (let [bs (three-row-groups)
        {:keys [rows chunks-read chunks-skipped]}
        (plan/scan (psrc/open bs) {:columns ["price"] :predicates [[:= "price" 120]]})]
    (is (= [{:columnar.plan/row 4 "price" 120}] rows))
    (is (= 1 chunks-read))
    (is (= 2 chunks-skipped)
        "two row groups ruled out by statistics this writer produced")))

(deftest statistics-land-in-the-footer-where-a-reader-finds-them
  (let [m (footer/parse (three-row-groups))]
    (is (= 9 (:num-rows m)))
    (is (= ["price" "region" "note" "ratio"] (:columns m)))
    (is (= [{:nulls 0 :min 10 :max 30}
            {:nulls 0 :min 110 :max 130}
            {:nulls 0 :min 210 :max 230}]
           (mapv #(:statistics (first (:columns %))) (:row-groups m))))
    (testing "and a nullable column reports its null counts per group"
      (is (= [2 2 3] (mapv #(:nulls (:statistics (nth (:columns %) 2))) (:row-groups m)))))))

(deftest an-aggregate-comes-out-of-the-footer-of-a-file-we-wrote
  (let [s (psrc/open (three-row-groups))]
    (is (= {:value 230 :from :statistics :read 0}
           (agg/aggregate s {:agg :max :column "price"})))
    (is (= {:value 9 :from :statistics :read 0} (agg/aggregate s {:agg :count})))))

;; ── values ──────────────────────────────────────────────────────────────────

(deftest values-and-nulls-survive-a-round-trip
  (let [bs (three-row-groups)]
    (is (= [10 20 30 110 120 130 210 220 230] (read-back bs "price")))
    (is (= ["east" "east" "west" "west" "east" "east" "east" "west" "west"]
           (read-back bs "region")))
    (is (= [nil "clearance" nil nil nil "sale" nil nil nil] (read-back bs "note")))
    (is (= [1.5 2.25 nil -0.5 0.0 3.75 nil 1.0 -2.5] (read-back bs "ratio")))))

(deftest a-null-is-distinct-from-a-value
  ;; Definition levels, not a sentinel: 0 and the empty string are values.
  (let [bs (w/of-columns [["n" (cvec/column :int64 [nil 0 nil])]
                          ["s" (cvec/column :utf8 [nil "" nil])]])]
    (is (= [nil 0 nil] (read-back bs "n")))
    (is (= [nil "" nil] (read-back bs "s")))
    (is (= 2 (:nulls (csrc/-chunk-stats (psrc/open bs) 0 "n"))))))

(deftest an-all-null-column-writes-no-bounds
  ;; min/max of nothing is absent, not a large number -- and absent bounds are
  ;; what stop `columnar.stats` pruning on a claim the file never made.
  (let [bs (w/of-columns [["v" (cvec/column :int64 [nil nil nil])]])
        st (csrc/-chunk-stats (psrc/open bs) 0 "v")]
    (is (= 3 (:nulls st)))
    (is (not (contains? st :min)))
    (is (= [nil nil nil] (read-back bs "v")))))

(deftest a-value-past-2-to-the-53-is-exact-or-refused
  (let [big 4611686018427387905]
    #?(:clj (is (= [big (- big)]
                   (read-back (w/of-columns [["b" (cvec/column :int64 [big (- big)])]]) "b")))
       :cljs (is (thrown? :default
                          (w/of-columns [["b" (cvec/column :int64 [big])]]))
                 "refused rather than written rounded"))))

(deftest utf8-is-written-as-utf8
  (let [vs ["日本語" "" "aéb" nil]]
    (is (= vs (read-back (w/of-columns [["s" (cvec/column :utf8 vs)]]) "s"))
        "byte lengths in the offsets, not character counts")))

(deftest an-empty-batch-is-a-file-not-an-error
  (let [bs (w/of-columns [["n" (cvec/column :int64 [])]])
        s (psrc/open bs)]
    (is (= ["n"] (csrc/-schema s)))
    (is (= 0 (csrc/-chunk-rows s 0)))))

;; ── refusals ────────────────────────────────────────────────────────────────

(deftest a-type-the-reader-cannot-read-back-is-refused-by-name
  (let [e (try (w/of-columns [["b" (cvec/column :boolean [true])]]) nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :parquet/unsupported-type (:type e)))
    (is (= :boolean (:logical e)))
    (is (= w/writable (:writable e))
        "the refusal names what IS writable, so a caller can act on it")))

(deftest a-null-in-a-required-column-is-refused
  (let [e (try (w/file {:fields [{:name "n" :physical :int64 :required? true}]
                        :batches [[(cvec/column :int64 [1 nil 3])]]})
               nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :parquet/null-in-required (:type e))
        "REQUIRED is a claim about the data, and writing a null under it
         produces a file whose levels and values disagree")))

(deftest arrow-column-types-map-onto-parquet-physical-types
  ;; A column read out of an Arrow file writes to Parquet without the caller
  ;; restating its type -- which is how a materialised result gains statistics.
  (is (= [{:name "s" :physical :byte-array :required? false}
          {:name "i" :physical :int64 :required? false}
          {:name "f" :physical :double :required? false}]
         (w/fields-of [["s" (cvec/column :utf8 ["x"])]
                       ["i" (cvec/column :int64 [1])]
                       ["f" (cvec/column :float [1.5])]]))))

;; ── the thrift encoder, against the decoder beside it ───────────────────────

(deftest the-compact-encoder-round-trips-through-the-decoder
  (let [m (th/parse-struct
           (th/encode-struct [[1 :i32 -7]
                              [2 :list (th/encode-list :i32 [0 3])]
                              [3 :i64 1099511627776]
                              [4 :binary (th/string-bytes "name")]
                              [6 :double 1.5]
                              [9 :struct (th/encode-struct [[1 :i32 5]])]
                              [20 :i64 42]])
           0)]
    (is (= -7 (get m 1)))
    (is (= [0 3] (get m 2)))
    (is (= 1099511627776 #?(:clj (long (get m 3)) :cljs (get m 3))))
    (is (= "name" (th/bytes->string (get m 4))))
    (is (= 1.5 (get m 6)))
    (is (= 5 (get (get m 9) 1)))
    (is (= 42 #?(:clj (long (get m 20)) :cljs (get m 20)))
        "a field id more than 15 past the previous one falls back to a zigzag
         varint instead of the delta nibble"))
  (testing "a list of 15 or more needs the extended element header"
    (is (= 20 (count (get (th/parse-struct
                           (th/encode-struct [[1 :list (th/encode-list :i64 (range 20))]]) 0)
                          1))))))

(deftest a-varint-is-written-unsigned
  ;; zigzag of a value at or above 2^62 sets the top bit. A writer that tests
  ;; `(< v 0x80)` on a signed long then sees a negative, decides it fits in one
  ;; byte, and emits one -- which decodes to something small and plausible.
  ;; Measured: this returned 1 for 2^62+1.
  #?(:clj (let [bs (th/write-varint (th/zigzag-encode 4611686018427387905))]
            (is (= 10 (count bs)))
            (is (every? #(<= 0 % 255) bs)))
     :cljs (is (thrown? :default (th/write-varint (th/zigzag-encode 4611686018427387905)))))
  (testing "and small negatives stay one byte"
    (is (= [1] (th/write-varint (th/zigzag-encode -1))))))

(deftest fields-must-be-emitted-in-ascending-id-order
  ;; The delta nibble is relative to the previous field, so out-of-order
  ;; emission produces a struct that decodes to DIFFERENT field ids without
  ;; failing. Refused at the encoder instead.
  (is (= :parquet/encoder-misuse
         (:type (try (th/encode-struct [[3 :i32 1] [1 :i32 2]])
                     (catch #?(:clj Exception :cljs :default) e (ex-data e)))))))

(deftest snappy-pages-round-trip-and-are-smaller
  (testing "the codec field and the body have to agree, and both have to change"
    (let [cols [["s" (cvec/column :utf8 (vec (repeat 300 "the quick brown fox")))]
                ["n" (cvec/column :int64 (vec (repeat 300 42)))]]
          plain (w/of-columns cols :uncompressed)
          snap (w/of-columns cols :snappy)]
      (is (< (count snap) (/ (count plain) 5))
          "repetitive columnar data is where snappy earns its place")
      (testing "and our own reader gets the same values back"
        (is (= (plan/scan (psrc/open plain) {:columns ["n"]})
               (plan/scan (psrc/open snap) {:columns ["n"]})))))))

(deftest an-unknown-codec-is-refused-rather-than-silently-uncompressed
  (is (thrown? #?(:clj Exception :cljs js/Error)
               (w/of-columns [["n" (cvec/column :int64 [1 2 3])]] :zstd))))
