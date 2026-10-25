(ns arrow.writer-test
  "The writer, checked against this repo's reader and the engine.

  **This suite cannot establish that the output is valid Arrow.** It shares a
  code base with the reader, so a wrong vtable or a misaligned buffer would
  round-trip through it cleanly. That claim is checked in CI by writing files
  with `arrow.emit-for-python` and handing them to pyarrow's
  `validate(full=True)`, which walks offsets and buffer bounds instead of
  trusting the metadata.

  What this suite IS for: that the writer preserves values and nulls, that its
  output is a legal `IColumnSource` with the chunking the caller asked for, and
  that a query result can be materialised and read back."
  (:require [arrow.source :as asrc]
            [arrow.write :as w]
            [clojure.test :refer [deftest is testing]]
            [columnar.plan :as plan]
            [columnar.source :as csrc]
            [columnar.vector :as cvec]))

(defn- read-back
  "Every value of `column`, across every batch of the file `bs`."
  [bs column]
  (let [s (asrc/open bs)]
    (vec (mapcat (fn [c]
                   (let [col (csrc/-read-column s c column)]
                     (map #(cvec/value-at col %) (range (cvec/count col)))))
                 (range (csrc/-chunk-count s))))))

(deftest values-and-nulls-survive-a-round-trip
  (let [cols [["price"  (cvec/column :int64 [10 20 30])]
              ["region" (cvec/column :utf8 ["east" "west" "east"])]
              ["note"   (cvec/column :utf8 [nil "clearance" nil])]
              ["flag"   (cvec/column :bool [true nil false])]
              ["ratio"  (cvec/column :double [1.5 nil -0.5])]
              ["small"  (cvec/column :float [1.5 -2.25 nil])]
              ["tiny"   (cvec/column :int8 [-1 2 127])]]
        bs (w/of-columns cols)]
    (is (= ["price" "region" "note" "flag" "ratio" "small" "tiny"]
           (csrc/-schema (asrc/open bs))))
    (doseq [[n col] cols]
      (testing n
        (is (= (mapv #(cvec/value-at col %) (range (cvec/count col)))
               (read-back bs n)))))))

(deftest a-null-is-distinct-from-a-value-in-every-layout
  ;; The failure this guards is a writer that puts a sentinel in the values
  ;; buffer instead of setting the mask: every aggregate over the column still
  ;; returns a number, and the number is wrong.
  (let [bs (w/of-columns [["n" (cvec/column :int64 [nil 0 nil])]
                          ["s" (cvec/column :utf8 [nil "" nil])]
                          ["b" (cvec/column :bool [nil false nil])]])]
    (testing "0, the empty string and false are values, not absences"
      (is (= [nil 0 nil] (read-back bs "n")))
      (is (= [nil "" nil] (read-back bs "s")))
      (is (= [nil false nil] (read-back bs "b"))))
    (let [s (asrc/open bs)]
      (is (= 2 (:nulls (csrc/-chunk-stats s 0 "n")))))))

(deftest a-column-with-no-nulls-writes-an-empty-validity-buffer
  ;; Present as a buffer entry, empty as a length. Dropping the entry would
  ;; shift every later buffer, which is silent until a column reads garbage.
  (let [bs (w/of-columns [["a" (cvec/column :int64 [1 2 3])]
                          ["b" (cvec/column :utf8 ["x" "y" "z"])]])
        s (asrc/open bs)]
    (is (= 0 (:nulls (csrc/-chunk-stats s 0 "a"))))
    (is (= [1 2 3] (read-back bs "a")))
    (is (= ["x" "y" "z"] (read-back bs "b"))
        "the second column's buffers are where the first column said they end")))

(deftest each-batch-becomes-one-prunable-chunk
  (let [fields [{:name "price" :type :int64 :nullable? true}]
        bs (w/file {:fields fields
                    :batches [[(cvec/column :int64 [1 2 3])]
                              [(cvec/column :int64 [4 5 6])]
                              [(cvec/column :int64 [7 8 9])]]})
        s (asrc/open bs)]
    (is (= 3 (csrc/-chunk-count s)))
    (is (= [3 3 3] (mapv #(csrc/-chunk-rows s %) (range 3))))
    (is (= [1 2 3 4 5 6 7 8 9] (read-back bs "price")))))

(deftest an-all-null-column-round-trips-and-still-prunes
  (let [bs (w/of-columns [["absent" (cvec/column :int64 [nil nil nil nil])]])
        s (asrc/open bs)
        st (csrc/-chunk-stats s 0 "absent")]
    (is (= [nil nil nil nil] (read-back bs "absent")))
    (is (= (:rows st) (:nulls st)))
    (is (= 1 (:chunks-skipped
              (plan/scan s {:columns ["absent"] :predicates [[:= "absent" 1]]}))))))

(deftest an-empty-batch-is-a-file-not-an-error
  (let [bs (w/of-columns [["n" (cvec/column :int64 [])]])
        s (asrc/open bs)]
    (is (= ["n"] (csrc/-schema s)))
    (is (= 0 (csrc/-chunk-rows s 0)))
    (is (= [] (read-back bs "n")))))

(deftest utf8-is-written-as-utf8
  (let [vs ["日本語" "" "aéb" nil]
        bs (w/of-columns [["s" (cvec/column :utf8 vs)]])]
    (is (= vs (read-back bs "s"))
        "multi-byte sequences are byte lengths in the offsets buffer, not
         character counts -- conflating them truncates every non-ASCII value")))

(deftest a-value-past-2-to-the-53-is-exact-or-refused
  (let [big 4611686018427387905]
    #?(:clj (is (= [big (- big) 0]
                   (read-back (w/of-columns [["big" (cvec/column :int64 [big (- big) 0])]])
                              "big")))
       :cljs (is (thrown? :default
                          (w/of-columns [["big" (cvec/column :int64 [big])]]))
                 "refused on the write side too, rather than written rounded"))))

(deftest writing-a-type-the-reader-refuses-is-refused-by-name
  (let [e (try (w/of-columns [["d" (cvec/column :decimal [1])]]) nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :arrow/unsupported-type (:type e)))
    (is (= :decimal (:logical e)))))

;; ── the capability this closes: a query result becomes a table ──────────────

(deftest a-scan-result-can-be-materialised-and-read-back
  ;; "Materialise this query into a table" -- the first bullet of the write
  ;; side. Read a file, scan it with a predicate, write the surviving rows as
  ;; a new Arrow object, and open that.
  (let [source (w/file {:fields [{:name "price" :type :int64}
                                 {:name "region" :type :utf8}]
                        :batches [[(cvec/column :int64 [10 110 210])
                                   (cvec/column :utf8 ["east" "west" "east"])]
                                  [(cvec/column :int64 [20 120 220])
                                   (cvec/column :utf8 ["west" "east" "west"])]]})
        {:keys [rows]} (plan/scan (asrc/open source)
                                  {:columns ["price" "region"]
                                   :predicates [[:= "region" "east"]]})
        materialised (w/of-columns
                      (w/columns-of-rows [["price" :int64] ["region" :utf8]] rows))]
    (is (= 3 (count rows)))
    (is (= [10 210 120] (read-back materialised "price")))
    (is (= ["east" "east" "east"] (read-back materialised "region")))
    (testing "and the materialised object is itself scannable"
      (is (= 3 (count (:rows (plan/scan (asrc/open materialised) {}))))))))

(deftest columns-of-rows-keeps-absent-values-null
  (let [rows [{"a" 1 "b" "x"} {"a" nil "b" nil} {"a" 3}]
        cols (w/columns-of-rows [["a" :int64] ["b" :utf8]] rows)
        bs (w/of-columns cols)]
    (is (= [1 nil 3] (read-back bs "a")))
    (is (= ["x" nil nil] (read-back bs "b")))))
