(ns columnar.engine-test
  (:require [clojure.test :refer [deftest is testing]]
            [columnar.aggregate :as agg]
            [columnar.plan :as plan]
            [columnar.source :as src]
            [columnar.stats :as stats]
            [columnar.vector :as vec]))

;; ── a source built from literal chunks ──────────────────────────────────────
;; `stats-override` exists so a test can hand the engine statistics that are
;; ABSENT or WIDER than the data — the two cases where a pruner that trusts
;; its inputs is wrong, and the ones a source built from real files cannot
;; produce on demand.

(defn- mem-source
  ([chunks] (mem-source chunks {}))
  ([chunks stats-override]
   (let [schema (vec (keys (first chunks)))]
     (reify src/IColumnSource
       (-schema [_] schema)
       (-chunk-count [_] (count chunks))
       (-chunk-rows [_ c] (vec/count (val (first (nth chunks c)))))
       (-chunk-stats [_ c col]
         (if (contains? stats-override [c col])
           (get stats-override [c col])
           (stats/from-column (get (nth chunks c) col))))
       (-read-column [_ c col] (get (nth chunks c) col))))))

(defn- col [vs] (vec/column :any vs))

;; three chunks, disjoint price ranges, so pruning is observable
(def chunks
  [{"price" (col [10 20 30]) "region" (col ["east" "east" "west"])}
   {"price" (col [110 120 130]) "region" (col ["west" "east" "east"])}
   {"price" (col [210 220 230]) "region" (col ["east" "west" "west"])}])

;; ── the property the library exists for ─────────────────────────────────────

(deftest a-filter-skips-chunks-it-can-rule-out
  (let [c (src/counting (mem-source chunks))
        {:keys [rows chunks-read chunks-skipped]}
        (plan/scan (:source c) {:columns ["price"] :predicates [[:= "price" 120]]})]
    (is (= [{:columnar.plan/row 4 "price" 120}] rows))
    (is (= 1 chunks-read) "only the chunk whose bounds contain 120")
    (is (= 2 chunks-skipped))
    (is (= #{1} (:chunks (src/read-counts c)))
        "an answer alone cannot distinguish this from reading all three and
         filtering, which is why reads are counted"))
  (testing "a range predicate prunes too"
    (let [c (src/counting (mem-source chunks))]
      (plan/scan (:source c) {:predicates [[:> "price" 200]]})
      (is (= #{2} (:chunks (src/read-counts c))))))
  (testing "an unselective predicate prunes nothing, and says so"
    (let [{:keys [chunks-read chunks-skipped]}
          (plan/scan (mem-source chunks) {:predicates [[:>= "price" 0]]})]
      (is (= 3 chunks-read))
      (is (= 0 chunks-skipped)))))

(deftest only-the-columns-the-query-mentions-are-read
  (let [c (src/counting (mem-source chunks))]
    (plan/scan (:source c) {:columns ["price"]})
    (is (= 3 (:columns (src/read-counts c)))
        "3 chunks x 1 column — reading `region` too is how a columnar scan
         quietly becomes a row scan"))
  (testing "a predicate column is read even when not projected"
    (let [c (src/counting (mem-source chunks))]
      (plan/scan (:source c) {:columns ["price"] :predicates [[:= "region" "east"]]})
      (is (= 6 (:columns (src/read-counts c))) "3 chunks x (price + region)"))))

;; ── the two rules that are dangerous to get backwards ───────────────────────

(deftest absent-statistics-never-permit-a-skip
  (let [c (src/counting (mem-source chunks {[0 "price"] nil [1 "price"] nil
                                            [2 "price"] nil}))
        {:keys [rows chunks-read chunks-skipped]}
        (plan/scan (:source c) {:columns ["price"] :predicates [[:= "price" 120]]})]
    (is (= 3 chunks-read) "no claim means no permission to skip")
    (is (= 0 chunks-skipped))
    (is (= [{:columnar.plan/row 4 "price" 120}] rows)
        "and the answer is still exactly right — slower, never wrong")))

(deftest pruning-is-necessary-not-sufficient
  (testing "bounds wider than the data must not widen the answer"
    (let [wide (mem-source chunks {[0 "price"] {:rows 3 :nulls 0 :min 0 :max 1000}})
          {:keys [rows]} (plan/scan wide {:columns ["price"]
                                          :predicates [[:= "price" 120]]})]
      (is (= [{:columnar.plan/row 4 "price" 120}] rows)
          "chunk 0 survives pruning on a bogus max and is then rejected row by
           row — pruning decides what to READ, never what MATCHES"))))

;; ── nulls ───────────────────────────────────────────────────────────────────

(deftest nulls-live-in-the-mask
  (let [c (vec/of :any [1 nil 3] [true false true])]
    (is (= 3 (vec/count c)))
    (is (= 1 (vec/null-count c)))
    (is (nil? (vec/value-at c 1)))
    (is (false? (vec/valid-at? c 1))))
  (testing "a present nil is expressible, which a sentinel could not do"
    (let [c (vec/of :any [nil] [true])]
      (is (true? (vec/valid-at? c 0)))
      (is (zero? (vec/null-count c)))))
  (testing "an all-null chunk is skipped for any value predicate"
    (is (true? (stats/skip-chunk? {:rows 3 :nulls 3} [:= "x" 1])))
    (is (true? (stats/skip-chunk? {:rows 3 :nulls 3} [:not-null "x"])))
    (is (false? (stats/skip-chunk? {:rows 3 :nulls 3} [:is-null "x"]))))
  (testing "a chunk with no nulls cannot answer :is-null"
    (is (true? (stats/skip-chunk? {:rows 3 :nulls 0 :min 1 :max 9} [:is-null "x"])))))

(deftest an-unknown-operator-never-permits-a-skip
  (is (false? (stats/skip-chunk? {:rows 3 :nulls 0 :min 1 :max 9} [:regex "x" "a.*"]))))

(deftest an-unknown-column-is-refused-rather-than-scanned
  (is (thrown? #?(:clj Exception :cljs :default)
               (plan/scan (mem-source chunks) {:columns ["nope"]})))
  (is (thrown? #?(:clj Exception :cljs :default)
               (plan/scan (mem-source chunks) {:predicates [[:= "nope" 1]]}))))

;; ── aggregates ──────────────────────────────────────────────────────────────

(deftest aggregates-answered-from-the-footer-read-nothing
  (doseq [[request expected]
          [[{:agg :count} 9]
           [{:agg :count-non-null :column "price"} 9]
           [{:agg :min :column "price"} 10]
           [{:agg :max :column "price"} 230]]]
    (let [c (src/counting (mem-source chunks))
          r (agg/aggregate (:source c) request)]
      (is (= expected (:value r)) (pr-str request))
      (is (= :statistics (:from r)))
      (is (= 0 (:read r)) "the answer was already in the metadata")
      (is (empty? (:chunks (src/read-counts c))) "and no chunk was touched"))))

(deftest statistics-are-disqualified-when-they-cannot-be-trusted
  (testing "a predicate disqualifies them"
    (let [r (agg/aggregate (mem-source chunks)
                           {:agg :max :column "price"
                            :predicates [[:= "region" "east"]]})]
      (is (= :scan (:from r)))
      (is (= 210 (:value r))
          "the east rows top out at 210; folding chunk bounds would answer
           230, which is a west row -- chunk bounds describe every row in the
           chunk and a filter selects some of them")))
  (testing "one chunk without bounds disqualifies the fold"
    (let [s (mem-source chunks {[1 "price"] nil})
          r (agg/aggregate s {:agg :max :column "price"})]
      (is (= :scan (:from r)))
      (is (= 230 (:value r))
          "folding only the chunks that reported bounds would answer about a
           subset of the file")))
  (testing "sum is never available from statistics"
    (let [r (agg/aggregate (mem-source chunks) {:agg :sum :column "price"})]
      (is (= :scan (:from r)))
      (is (= 1080 (:value r))))))

;; ── the shape kotobase.lake.tabular consumes ────────────────────────────────

(deftest select-produces-the-tabular-engine-shape
  (let [c (src/counting (mem-source chunks))
        {:keys [rows]} (plan/select (:source c)
                                    {:columns ["price"] :row nil
                                     :filters [["price" 120]]}
                                    ::row)]
    (is (= [{::row 4 "price" 120}] rows))
    (is (= #{1} (:chunks (src/read-counts c)))
        "an equality filter from a triple pattern prunes chunks — the whole
         point of the pattern reaching this far intact"))
  (testing "a bound row narrows the result"
    (let [{:keys [rows]} (plan/select (mem-source chunks)
                                      {:columns ["price"] :row 4 :filters []}
                                      ::row)]
      (is (= [{::row 4 "price" 120}] rows))))
  (testing "row numbers stay global across skipped chunks"
    (let [{:keys [rows]} (plan/select (mem-source chunks)
                                      {:columns ["price"] :row nil
                                       :filters [["price" 230]]}
                                      ::row)]
      (is (= [{::row 8 "price" 230}] rows)
          "chunk 2's third row is row 8 even though chunks 0 and 1 were never
           read — row numbering comes from metadata, not from counting reads")))
  (testing "range predicates prune the same way as equality"
    (let [c (src/counting (mem-source chunks))
          {:keys [rows]} (plan/select (:source c)
                                      {:columns ["price"] :row nil
                                       :filters []
                                       :predicates [[:>= "price" 100] [:< "price" 200]]}
                                      ::row)]
      (is (= [{::row 3 "price" 110} {::row 4 "price" 120} {::row 5 "price" 130}]
             rows))
      (is (= #{1} (:chunks (src/read-counts c)))
          "chunks whose min/max sit outside [100, 200) are not read"))))
