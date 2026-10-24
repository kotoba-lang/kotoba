(ns kotobase.lake.compact-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotobase.lake.compact :as compact]
            [kotobase.lake.table :as table]))

(def tbl (table/table-id "acme" "sales"))

(defn- member [cid rows partition stats]
  {:member (table/member-id tbl cid) :cid cid :rows rows
   :partition partition :statistics stats})

(def east-a (member "bafkA" 2 {"region" "east"} {"price" {:nulls 0 :min 10 :max 30}}))
(def east-b (member "bafkB" 2 {"region" "east"} {"price" {:nulls 1 :min 110 :max 130}}))
(def east-c (member "bafkC" 2 {"region" "east"} {"price" {:nulls 0 :min 210 :max 230}}))
(def west-a (member "bafkW" 2 {"region" "west"} {"price" {:nulls 0 :min 5 :max 7}}))

;; ── planning ────────────────────────────────────────────────────────────────

(deftest members-in-different-partitions-are-never-grouped
  ;; The partition value lives in the path, not the data. Merging across them
  ;; either loses the value or turns it into a column.
  (let [groups (compact/plan [east-a west-a east-b] {:min-members 2})]
    (is (= 1 (count groups)))
    (is (= {"region" "east"} (:partition (first groups))))
    (is (= ["bafkA" "bafkB"] (mapv :cid (:members (first groups)))))))

(deftest a-group-stops-at-the-target-so-compaction-does-not-make-one-huge-file
  (let [groups (compact/plan [east-a east-b east-c] {:target-rows 4 :min-members 2})]
    (is (= [["bafkA" "bafkB"]] (mapv #(mapv :cid (:members %)) groups))
        "the third would exceed the target, and a group of one is dropped")))

(deftest a-group-too-small-to-be-worth-rewriting-is-dropped
  (is (= [] (compact/plan [east-a west-a] {:min-members 2})))
  (testing "and min-members 1 would take them, which is why the default is 2"
    (is (= 2 (count (compact/plan [east-a west-a] {:min-members 1}))))))

(deftest a-plan-is-reproducible
  (is (= (compact/plan [east-a east-b east-c west-a] {})
         (compact/plan [east-a east-b east-c west-a] {}))))

;; ── merged statistics ───────────────────────────────────────────────────────

(deftest statistics-compose-across-a-group
  (is (= {"price" {:nulls 1 :min 10 :max 130}}
         (compact/merged-statistics [east-a east-b]))))

(deftest one-member-without-bounds-makes-the-merged-bound-unknowable
  ;; Inventing it from the members that DID report would be a claim about rows
  ;; nobody described.
  (let [unbounded (member "bafkU" 2 {"region" "east"} {"price" {:nulls 0}})
        m (compact/merged-statistics [east-a unbounded])]
    (is (= 0 (:nulls (get m "price"))))
    (is (not (contains? (get m "price") :min)))
    (is (not (contains? (get m "price") :max)))))

;; ── the guard ───────────────────────────────────────────────────────────────

(deftest a-rewrite-that-loses-a-row-is-refused
  ;; The failure this namespace exists to catch. A file missing a row opens,
  ;; parses and answers queries -- with less in it, and nothing downstream can
  ;; tell.
  (let [e (try (compact/verify-replacement!
                [east-a east-b]
                {:rows 3 :statistics {"price" {:nulls 1 :min 10 :max 130}}})
               nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :kotobase.lake/compaction-lost-rows (:type e)))
    (is (= 4 (:expected e)))
    (is (= 3 (:actual e)))))

(deftest a-rewrite-that-narrows-a-bound-is-refused
  ;; Narrower bounds mean values went missing even when the row count happens
  ;; to match -- a rewrite that replaced a value rather than dropping it.
  (let [e (try (compact/verify-replacement!
                [east-a east-b]
                {:rows 4 :statistics {"price" {:nulls 1 :min 20 :max 130}}})
               nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :kotobase.lake/compaction-narrowed-bounds (:type e)))
    (is (= "price" (:column e)))
    (is (= 10 (:was e)))
    (is (= 20 (:now e)))))

(deftest wider-bounds-are-allowed
  ;; `columnar.stats` rule 2: statistics are bounds and a writer may record
  ;; loose ones. Wider is safe -- it only costs pruning.
  (is (true? (compact/verify-replacement!
              [east-a east-b]
              {:rows 4 :statistics {"price" {:nulls 1 :min 0 :max 999}}}))))

(deftest a-replacement-that-reports-no-bounds-is-allowed
  ;; Absent bounds mean "no claim", which is slower and correct.
  (is (true? (compact/verify-replacement!
              [east-a east-b] {:rows 4 :statistics {"price" {:nulls 1}}}))))

;; ── the commit ──────────────────────────────────────────────────────────────

(def merged (member "bafkM" 4 {"region" "east"}
                    {"price" {:nulls 1 :min 10 :max 130}}))

(deftest the-commit-is-a-new-snapshot-naming-the-replacement
  (let [quads (compact/commit {:table tbl :id "s2" :parent "s1"
                               :members [east-a east-b west-a]
                               :replaced [east-a east-b]
                               :replacement merged})
        sid (table/snapshot-id tbl "s2")]
    (is (= [(:member merged) (:member west-a)]
           (table/snapshot-members quads sid))
        "the two replaced members are gone; the untouched one stays")
    (is (= #{{:s sid :p "snapshot/parent" :o (table/snapshot-id tbl "s1")}}
           (into #{} (filter #(= "snapshot/parent" (:p %))) quads))
        "lineage is preserved, so the pre-compaction table is still reachable")))

(deftest the-commit-refuses-a-rewrite-that-loses-rows
  ;; The guard is on the commit, not beside it -- so there is no path that
  ;; lands a lossy compaction by forgetting to call the checker.
  (is (= :kotobase.lake/compaction-lost-rows
         (:type (try (compact/commit {:table tbl :id "s2" :parent "s1"
                                      :members [east-a east-b]
                                      :replaced [east-a east-b]
                                      :replacement (assoc merged :rows 3)})
                     (catch #?(:clj Exception :cljs :default) e (ex-data e)))))))

(deftest replacing-members-that-are-not-in-the-snapshot-is-refused
  ;; Otherwise a compaction computed against a stale snapshot commits a
  ;; snapshot that quietly ADDS a file instead of replacing anything.
  (is (= :kotobase.lake/compaction-replaces-nothing
         (:type (try (compact/commit {:table tbl :id "s2" :parent "s1"
                                      :members [west-a]
                                      :replaced [east-a east-b]
                                      :replacement merged})
                     (catch #?(:clj Exception :cljs :default) e (ex-data e)))))))

(deftest the-previous-snapshot-still-answers-after-a-compaction
  ;; The property snapshots exist for, checked through compaction: the old
  ;; files are still named by the old snapshot.
  (let [manifest (into #{}
                       (concat
                        (table/snapshot {:table tbl :id "s1"
                                         :members [(:member east-a) (:member east-b)
                                                   (:member west-a)]})
                        (compact/commit {:table tbl :id "s2" :parent "s1"
                                         :members [east-a east-b west-a]
                                         :replaced [east-a east-b]
                                         :replacement merged})))]
    (is (= [(:member east-a) (:member east-b) (:member west-a)]
           (table/snapshot-members manifest (table/snapshot-id tbl "s1"))))
    (is (= [(:member merged) (:member west-a)]
           (table/snapshot-members manifest (table/snapshot-id tbl "s2"))))))
