(ns kotobase.lake.tabular-test
  (:require [clojure.test :refer [deftest is testing]]
            [datom.source :as source]
            [datom.source.conformance :as conf]
            [kotobase.lake.tabular :as tab]))

;; A fake engine that RECORDS every request. The recording is the point: an
;; answer-only test cannot tell a source that pushed the filter down from one
;; that read every row and filtered in memory, because both return the same
;; set. This is the same hazard kotobase-storage found in its sequential CAS
;; tests -- a correct answer produced by a mechanism that is not doing the work.
(defn- engine [columns rows]
  (let [log (atom [])]
    {:log log
     :engine
     (reify tab/ITabularEngine
       (-columns [_] columns)
       (-select [_ {:keys [columns row filters predicates] :as request}]
         (swap! log conj request)
         (cond->> rows
           (some? row) (filter #(= row (get % tab/row-attribute)))
           (seq filters) (filter (fn [r] (every? (fn [[c v]] (= v (get r c))) filters)))
           (seq predicates)
           (filter (fn [r]
                     (every? (fn [[op c v]]
                               (let [got (get r c)]
                                 (case op
                                   := (= got v)
                                   :< (and (some? got) (neg? (compare got v)))
                                   :<= (and (some? got) (not (pos? (compare got v))))
                                   :> (and (some? got) (pos? (compare got v)))
                                   :>= (and (some? got) (not (neg? (compare got v))))
                                   true)))
                             predicates)))
           (some? columns) (map #(select-keys % (conj (vec columns) tab/row-attribute))))))}))

;; ── long: the shape a table can fully express ───────────────────────────────

(defn- long-engine [quads]
  (:engine (engine ["s" "p" "o"]
                   (map-indexed (fn [i q] {tab/row-attribute i
                                           "s" (:s q) "p" (:p q) "o" (:o q)})
                                quads))))

(deftest long-source-conforms
  (let [failures (conf/check #(tab/long-source {:engine (long-engine %)}))]
    (is (empty? failures) (conf/report failures))))

(deftest long-source-pushes-every-bound-position
  (let [{:keys [log engine]} (engine ["s" "p" "o"]
                                     [{tab/row-attribute 0 "s" "a" "p" "k" "o" "b"}])
        src (tab/long-source {:engine engine})]
    (source/scan-set src ["a" "k" nil])
    (is (= [["s" "a"] ["p" "k"]] (:filters (last @log)))
        "a bound position must reach the engine as a filter, not be applied after")
    (source/scan-set src [nil nil nil])
    (is (= [] (:filters (last @log))) "and an unbound pattern pushes nothing")))

(deftest long-source-rechecks-a-loose-engine
  (testing "an engine that ignores filters must not widen the answer"
    (let [loose (reify tab/ITabularEngine
                  (-columns [_] ["s" "p" "o"])
                  (-select [_ _]
                    [{tab/row-attribute 0 "s" "a" "p" "k" "o" "b"}
                     {tab/row-attribute 1 "s" "z" "p" "k" "o" "b"}]))
          src (tab/long-source {:engine loose})]
      (is (= #{{:s "a" :p "k" :o "b"}} (source/scan-set src ["a" nil nil]))
          "a coarse row-group prune with no exact recheck would otherwise
           return a quad that contradicts the pattern"))))

(deftest long-source-refuses-a-relation-without-datom-columns
  (is (thrown? #?(:clj Exception :cljs :default)
               (tab/long-source {:engine (:engine (engine ["price" "qty"] []))}))))

;; ── wide: the shape real analytics files have ───────────────────────────────

(def wide-rows
  [{tab/row-attribute 0 "sku" "A1" "price" 100 "note" nil}
   {tab/row-attribute 1 "sku" "B2" "price" 250 "note" "clearance"}
   {tab/row-attribute 2 "sku" "C3" "price" 100 "note" nil}])

(defn- wide [] (engine ["sku" "price" "note"] wide-rows))

(deftest wide-source-answers-patterns
  (let [src (tab/wide-source {:engine (:engine (wide)) :subject-prefix "obj:x#row"})]
    (is (= #{{:s "obj:x#row0" :p "price" :o 100}
             {:s "obj:x#row2" :p "price" :o 100}}
           (source/scan-set src [nil "price" 100])))
    (is (= #{{:s "obj:x#row1" :p "sku" :o "B2"}
             {:s "obj:x#row1" :p "price" :o 250}
             {:s "obj:x#row1" :p "note" :o "clearance"}}
           (source/scan-set src ["obj:x#row1" nil nil])))
    (is (= 7 (count (source/scan-set src [nil nil nil])))
        "3 rows x 3 columns = 9, minus the two NULL notes")))

(deftest a-null-cell-is-an-absent-attribute
  (let [src (tab/wide-source {:engine (:engine (wide)) :subject-prefix "obj:x#row"})]
    (is (= #{{:s "obj:x#row1" :p "note" :o "clearance"}}
           (source/scan-set src [nil "note" nil]))
        "EAV cannot say `the value is nil`, and inventing a datom for every
         row without a note is how [nil \"note\" nil] starts lying")))

(deftest wide-source-pushes-projection-and-filter
  (let [{:keys [log engine]} (wide)
        src (tab/wide-source {:engine engine :subject-prefix "obj:x#row"})]
    (source/scan-set src [nil "price" nil])
    (is (= ["price"] (:columns (last @log)))
        "a bound predicate IS a column projection -- the whole reason this
         works on columnar files")
    (source/scan-set src [nil "price" 100])
    (is (= [["price" 100]] (:filters (last @log)))
        "and a bound object is the filter the engine prunes row groups with")
    (source/scan-set src ["obj:x#row1" nil nil])
    (is (= 1 (:row (last @log))) "a bound subject is a row selection")))

(deftest a-pattern-that-cannot-match-never-reaches-the-engine
  (let [{:keys [log engine]} (wide)
        src (tab/wide-source {:engine engine :subject-prefix "obj:x#row"})]
    (testing "an unknown predicate is not sent as an identifier"
      (is (= #{} (source/scan-set src [nil "'; DROP TABLE t; --" nil])))
      (is (= #{} (source/scan-set src [nil "unknown-column" nil])))
      (is (empty? @log)
          "column names are checked against -columns BEFORE anything leaves;
           a predicate is attacker-controlled in a multi-tenant deployment"))
    (testing "a foreign subject costs nothing"
      (is (= #{} (source/scan-set src ["someone-elses:thing" nil nil])))
      (is (= #{} (source/scan-set src ["obj:x#rowNaN" nil nil])))
      (is (empty? @log)
          "merged hands every pattern to every source, so a source that
           cannot recognise a foreign subject would answer it with a scan"))))

(deftest wide-cannot-hold-a-multi-valued-attribute
  (testing "long expresses the pair the conformance corpus depends on"
    (let [multi [{:s "alice" :p "likes" :o "tea"}
                 {:s "alice" :p "likes" :o "coffee"}]]
      (is (empty? (conf/check #(tab/long-source {:engine (long-engine %)}) multi))
          "long has a row per datom, so two values for one (s,p) is two rows")
      (is (= 1 (count (distinct (map :p multi))))
          "one column, two values: a wide row has nowhere to put the second --
           which is why the standard suite is run against long-source and
           wide-source gets its own corpus"))))

(deftest wide-source-pushes-a-value-range
  (let [{:keys [log engine]} (wide)
        src (tab/wide-source {:engine engine :subject-prefix "obj:x#row"})
        got (source/scan-range src "price" 100 250)]
    (is (= #{{:s "obj:x#row0" :p "price" :o 100}
             {:s "obj:x#row2" :p "price" :o 100}}
           got)
        "[100, 250) keeps 100 and drops 250")
    (is (= [[:>= "price" 100] [:< "price" 250]]
           (:predicates (last @log)))
        "the interval reaches the engine as predicates, not a full column scan")))
