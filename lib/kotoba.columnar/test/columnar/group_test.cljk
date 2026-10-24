(ns columnar.group-test
  (:require [clojure.test :refer [deftest is testing]]
            [columnar.group :as group]
            [columnar.source :as src]
            [columnar.stats :as stats]
            [columnar.vector :as vec]))

;; The same literal-chunk source `engine_test` uses: statistics come from the
;; data unless a test overrides them, which is how absent or over-wide bounds
;; get exercised.
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

(def chunks
  [{"price" (col [10 20 30]) "region" (col ["east" "east" "west"])}
   {"price" (col [110 120 130]) "region" (col ["west" "east" "east"])}
   {"price" (col [210 220 230]) "region" (col ["east" "west" "west"])}])

(deftest groups-fold-across-chunks
  (let [{:keys [rows chunks-read]}
        (group/group (mem-source chunks)
                     {:group-by ["region"]
                      :aggs [{:as "n" :agg :count}
                             {:as "total" :agg :sum :column "price"}
                             {:as "hi" :agg :max :column "price"}]})]
    (is (= 3 chunks-read) "grouping has no metadata shortcut: every chunk is read")
    ;; east: 10+20 (chunk 0) + 120+130 (chunk 1) + 210 (chunk 2) = 490
    ;; west: 30      (chunk 0) + 110      (chunk 1) + 220+230    = 590
    (is (= [{"region" "east" "n" 5 "total" 490 "hi" 210}
            {"region" "west" "n" 4 "total" 590 "hi" 230}]
           rows))))

(deftest output-order-is-first-appearance-not-hash-order
  ;; A hash map's seq order is unspecified and differs between runtimes for
  ;; the same keys, which would make a grouped result runtime-dependent.
  (let [r (fn [cs] (mapv #(get % "k")
                         (:rows (group/group (mem-source cs)
                                             {:group-by ["k"]
                                              :aggs [{:as "n" :agg :count}]}))))]
    (is (= ["b" "a" "c"] (r [{"k" (col ["b" "a" "b" "c" "a"])}])))
    (is (= ["c" "b" "a"] (r [{"k" (col ["c" "c" "b"])} {"k" (col ["a" "b"])}]))
        "first appearance is across chunks, in chunk order")))

(deftest a-null-key-is-a-group-and-not-a-dropped-row
  (let [{:keys [rows]}
        (group/group (mem-source [{"k" (col ["a" nil "a" nil])
                                   "v" (col [1 2 3 4])}])
                     {:group-by ["k"]
                      :aggs [{:as "n" :agg :count} {:as "s" :agg :sum :column "v"}]})]
    (is (= [{"k" "a" "n" 2 "s" 4}
            {"k" nil "n" 2 "s" 6}] rows)
        "dropping null-keyed rows loses data without saying so")))

(deftest count-counts-rows-and-count-non-null-counts-values
  ;; The whole reason both exist. A group of three rows where one had a value
  ;; is 3 and 1, and conflating them is a wrong answer that looks plausible.
  (let [{:keys [rows]}
        (group/group (mem-source [{"k" (col ["a" "a" "a"])
                                   "v" (col [nil 7 nil])}])
                     {:group-by ["k"]
                      :aggs [{:as "rows" :agg :count}
                             {:as "vals" :agg :count-non-null :column "v"}
                             {:as "s" :agg :sum :column "v"}]})]
    (is (= [{"k" "a" "rows" 3 "vals" 1 "s" 7}] rows))))

(deftest an-all-null-group-sums-to-zero-and-has-no-min
  ;; min/max of nothing is nil, not a large number -- and it must stay
  ;; distinguishable from a group whose minimum really is some value.
  (let [{:keys [rows]}
        (group/group (mem-source [{"k" (col ["a"]) "v" (col [nil])}])
                     {:group-by ["k"]
                      :aggs [{:as "s" :agg :sum :column "v"}
                             {:as "lo" :agg :min :column "v"}
                             {:as "hi" :agg :max :column "v"}]})]
    (is (= [{"k" "a" "s" 0 "lo" nil "hi" nil}] rows))))

(deftest predicates-still-prune-chunks-under-a-group-by
  (let [c (src/counting (mem-source chunks))
        {:keys [rows chunks-read chunks-skipped]}
        (group/group (:source c)
                     {:group-by ["region"]
                      :aggs [{:as "n" :agg :count}]
                      :predicates [[:> "price" 200]]})]
    (is (= 1 chunks-read))
    (is (= 2 chunks-skipped) "the saving grouping DOES get: pruned chunks")
    (is (= #{2} (:chunks (src/read-counts c))))
    (is (= [{"region" "east" "n" 1} {"region" "west" "n" 2}] rows))))

(deftest only-the-columns-the-query-mentions-are-read
  (let [c (src/counting (mem-source chunks))]
    (group/group (:source c) {:group-by ["region"] :aggs [{:as "n" :agg :count}]})
    (is (= 3 (:columns (src/read-counts c)))
        "one column per chunk -- price is never touched by a count over region")))

(deftest absent-statistics-still-forbid-pruning
  ;; Rule 1 of columnar.stats, under a group-by: a source making no claim must
  ;; cause every chunk to be read, or rows vanish from the groups silently.
  (let [{:keys [chunks-read chunks-skipped rows]}
        (group/group (mem-source chunks {[0 "price"] nil [1 "price"] nil [2 "price"] nil})
                     {:group-by ["region"]
                      :aggs [{:as "n" :agg :count}]
                      :predicates [[:> "price" 200]]})]
    (is (= 3 chunks-read))
    (is (= 0 chunks-skipped))
    (is (= [{"region" "east" "n" 1} {"region" "west" "n" 2}] rows)
        "and the answer is the same one pruning produced -- pruning decides
         what to read, never what matches")))

(deftest grouping-by-nothing-is-the-whole-source
  (let [{:keys [rows]}
        (group/group (mem-source chunks)
                     {:aggs [{:as "n" :agg :count}
                             {:as "s" :agg :sum :column "price"}
                             {:as "lo" :agg :min :column "price"}]})]
    (is (= [{"n" 9 "s" 1080 "lo" 10}] rows)))
  (testing "and an empty source has no group at all"
    (is (= [] (:rows (group/group (mem-source [{"price" (col [])}])
                                  {:aggs [{:as "n" :agg :count}]}))))))

(deftest grouping-by-more-than-one-column
  (let [{:keys [rows]}
        (group/group (mem-source [{"a" (col ["x" "x" "y" "x"])
                                   "b" (col [1 2 1 1])
                                   "v" (col [10 20 30 40])}])
                     {:group-by ["a" "b"] :aggs [{:as "s" :agg :sum :column "v"}]})]
    (is (= [{"a" "x" "b" 1 "s" 50}
            {"a" "x" "b" 2 "s" 20}
            {"a" "y" "b" 1 "s" 30}] rows))))

(deftest unknown-columns-and-aggregates-are-refused-by-name
  (let [s (mem-source chunks)]
    (is (= :columnar/unknown-column
           (:type (try (group/group s {:group-by ["nope"] :aggs []})
                       (catch #?(:clj Exception :cljs :default) e (ex-data e))))))
    (is (= :columnar/unknown-aggregate
           (:type (try (group/group s {:group-by ["region"]
                                       :aggs [{:as "x" :agg :median :column "price"}]})
                       (catch #?(:clj Exception :cljs :default) e (ex-data e))))))
    (testing "and an aggregate that needs a column but was given none"
      (is (= :columnar/aggregate-needs-column
             (:type (try (group/group s {:group-by ["region"]
                                         :aggs [{:as "x" :agg :sum}]})
                         (catch #?(:clj Exception :cljs :default) e (ex-data e)))))))))

;; ── the two paths agree ─────────────────────────────────────────────────────

(deftest folding-while-reading-agrees-with-folding-materialised-rows
  ;; `group` folds as it reads; `scan-and-group` materialises first. Different
  ;; computations, same answer -- which is what makes the streaming one safe to
  ;; prefer.
  (let [req {:group-by ["region"]
             :aggs [{:as "n" :agg :count}
                    {:as "s" :agg :sum :column "price"}
                    {:as "lo" :agg :min :column "price"}
                    {:as "hi" :agg :max :column "price"}]}]
    (is (= (:rows (group/group (mem-source chunks) req))
           (:rows (group/scan-and-group (mem-source chunks) req))))
    (testing "under a predicate too"
      (let [req (assoc req :predicates [[:not-null "price"] [:< "price" 200]])]
        (is (= (:rows (group/group (mem-source chunks) req))
               (:rows (group/scan-and-group (mem-source chunks) req))))))))
