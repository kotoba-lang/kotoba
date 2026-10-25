(ns columnar.evolve-test
  (:require [clojure.test :refer [deftest is testing]]
            [columnar.evolve :as ev]
            [columnar.plan :as plan]
            [columnar.source :as src]
            [columnar.stats :as stats]
            [columnar.vector :as vec]))

(defn- mem-source [chunks]
  (let [schema (clojure.core/vec (keys (first chunks)))]
    (reify src/IColumnSource
      (-schema [_] schema)
      (-chunk-count [_] (count chunks))
      (-chunk-rows [_ c] (vec/count (val (first (nth chunks c)))))
      (-chunk-stats [_ c col] (stats/from-column (get (nth chunks c) col)))
      (-read-column [_ c col] (get (nth chunks c) col)))))

;; ── unification ─────────────────────────────────────────────────────────────

(deftest the-same-logical-type-under-two-format-names-unifies
  ;; Parquet says :byte-array, Arrow says :utf8, both decode to strings. A
  ;; table spanning the two formats must not see a type conflict.
  (is (= :utf8 (ev/unify-type "s" :utf8 :byte-array)))
  (is (= :string (ev/class-of :byte-array)))
  (is (= :string (ev/class-of :utf8)))
  (is (= (ev/class-of :int32) (ev/class-of :int64))))

(deftest the-wider-concrete-type-wins
  ;; Only int64 can describe every value in a table that has both.
  (is (= :int64 (ev/unify-type "n" :int32 :int64)))
  (is (= :int64 (ev/unify-type "n" :int64 :int32)))
  (is (= :double (ev/unify-type "f" :float :double)))
  (is (= :large-utf8 (ev/unify-type "s" :utf8 :large-utf8))))

(deftest a-null-column-makes-no-claim-and-vetoes-nothing
  ;; A column entirely null in one file says nothing about its type, so it
  ;; must not stop the other files from agreeing.
  (is (= :int64 (ev/unify-type "n" :null :int64)))
  (is (= :int64 (ev/unify-type "n" :int64 :null)))
  (is (= :null (ev/unify-type "n" :null :null))))

(deftest incompatible-classes-are-refused-by-name
  (let [e (try (ev/unify-type "x" :int64 :double) nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :columnar/incompatible-types (:type e)))
    (is (= "x" (:column e)))
    (is (= [:int64 :double] (:types e)))
    (is (= [:int :float] (:classes e))))
  (testing "int and string too -- guessing would put wrong values into a query
            that looks like it worked"
    (is (thrown? #?(:clj Exception :cljs :default) (ev/unify-type "x" :int64 :utf8)))))

(deftest an-unknown-type-unifies-only-with-itself
  (is (= :decimal (ev/unify-type "d" :decimal :decimal)))
  (is (thrown? #?(:clj Exception :cljs :default) (ev/unify-type "d" :decimal :int64))))

(deftest unify-orders-columns-by-first-appearance
  ;; A map's seq order is unspecified and differs between runtimes; a table
  ;; schema that reordered between JVM and cljs would make every plan built
  ;; from it runtime-dependent.
  (let [{:keys [columns types]}
        (ev/unify [{"b" :int32 "a" :utf8} {"c" :double "a" :byte-array} {"b" :int64}])]
    (is (= ["b" "a" "c"] columns))
    (is (= {"b" :int64 "a" :utf8 "c" :double} types))))

;; ── reconciliation ──────────────────────────────────────────────────────────

(def ^:private old-file
  ;; Predates the `note` column entirely.
  (mem-source [{"price" (vec/column :int32 [10 20]) "region" (vec/column :byte-array ["e" "w"])}]))

(def ^:private new-file
  (mem-source [{"price" (vec/column :int64 [110 120])
                "region" (vec/column :utf8 ["w" "e"])
                "note" (vec/column :utf8 ["x" nil])}]))

(def ^:private table-schema
  (ev/unify [{"price" :int32 "region" :byte-array}
             {"price" :int64 "region" :utf8 "note" :utf8}]))

(deftest a-file-missing-a-column-presents-it-as-all-null
  (let [s (ev/reconcile old-file table-schema)]
    (is (= ["price" "region" "note"] (src/-schema s)))
    (let [col (src/-read-column s 0 "note")]
      (is (= 2 (vec/count col)))
      (is (= [nil nil] (mapv #(vec/value-at col %) (range 2))))
      (is (= :utf8 (:type col)) "declared as the table's type, not as nothing"))))

(deftest an-absent-column-prunes-because-it-is-all-null
  ;; The useful consequence: null_count == rows is a proof, and it is the one
  ;; thing `columnar.stats` can rule a chunk out on without bounds. A file
  ;; predating a column is skipped outright rather than read to discover that
  ;; nothing matches.
  (let [s (ev/reconcile old-file table-schema)
        st (src/-chunk-stats s 0 "note")]
    (is (= {:rows 2 :nulls 2} st))
    (is (not (contains? st :min)) "an absent column claims nothing about values")
    (let [{:keys [chunks-read chunks-skipped]}
          (plan/scan s {:columns ["note"] :predicates [[:= "note" "x"]]})]
      (is (= 0 chunks-read))
      (is (= 1 chunks-skipped)))))

(deftest columns-that-exist-keep-their-real-statistics
  ;; The other half: synthesising must not disturb the pruning that works.
  (let [s (ev/reconcile old-file table-schema)]
    (is (= {:rows 2 :nulls 0 :min 10 :max 20} (src/-chunk-stats s 0 "price")))
    (let [{:keys [chunks-read chunks-skipped]}
          (plan/scan s {:columns ["price"] :predicates [[:= "price" 999]]})]
      (is (= 0 chunks-read))
      (is (= 1 chunks-skipped) "real bounds still rule the chunk out"))))

(deftest values-pass-through-and-are-relabelled-to-the-unified-type
  ;; Widening within a class is a label change, not a conversion: both readers
  ;; already produce Clojure values.
  (let [s (ev/reconcile old-file table-schema)
        col (src/-read-column s 0 "price")]
    (is (= [10 20] (mapv #(vec/value-at col %) (range 2))))
    (is (= :int64 (:type col)) "the table's type, though the file said int32")))

(deftest a-column-the-schema-does-not-name-is-hidden
  ;; The schema is the allowlist. A table must not grow a column because one
  ;; member happens to carry it.
  (let [extra (mem-source [{"price" (vec/column :int64 [1]) "secret" (vec/column :utf8 ["s"])}])
        s (ev/reconcile extra {:columns ["price"] :types {"price" :int64}})]
    (is (= ["price"] (src/-schema s)))
    (is (thrown? #?(:clj Exception :cljs :default)
                 (plan/scan s {:columns ["secret"]})))))

(deftest both-files-read-as-one-table
  (let [rows (fn [f] (:rows (plan/scan (ev/reconcile f table-schema) {})))]
    (is (= [{:columnar.plan/row 0 "price" 10 "region" "e" "note" nil}
            {:columnar.plan/row 1 "price" 20 "region" "w" "note" nil}]
           (rows old-file)))
    (is (= [{:columnar.plan/row 0 "price" 110 "region" "w" "note" "x"}
            {:columnar.plan/row 1 "price" 120 "region" "e" "note" nil}]
           (rows new-file))
        "and the file that HAS the column is unaffected")))

(deftest a-schema-naming-a-column-with-no-type-is-refused
  (is (= :columnar/schema-incomplete
         (:type (try (ev/reconcile old-file {:columns ["price" "nope"] :types {"price" :int64}})
                     (catch #?(:clj Exception :cljs :default) e (ex-data e)))))))

(deftest schema-of-reads-a-source-that-has-no-manifest
  (is (= {"price" :int32 "region" :byte-array} (ev/schema-of old-file)))
  (testing "and an empty source has no schema to report"
    (is (= {} (ev/schema-of (mem-source []))))))
