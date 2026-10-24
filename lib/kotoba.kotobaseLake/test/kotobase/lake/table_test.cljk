(ns kotobase.lake.table-test
  (:require [clojure.test :refer [deftest is testing]]
            [datom.source :as source]
            [columnar.evolve]
            [kotobase.lake.table :as table]))

(def tbl (table/table-id "acme" "sales"))

;; Three files, hive-partitioned by region, disjoint price ranges. `west` has
;; no price statistics at all — the normal state for a writer that recorded
;; none, and the one that must never be pruned away.
(def manifest
  (into #{}
        (mapcat table/add-member)
        [{:table tbl :cid "bafkA" :rows 2 :partition {"region" "east"}
          :statistics {"price" {:nulls 0 :min 10 :max 30}}}
         {:table tbl :cid "bafkB" :rows 2 :partition {"region" "east"}
          :statistics {"price" {:nulls 0 :min 110 :max 130}}}
         {:table tbl :cid "bafkC" :rows 2 :partition {"region" "west"}
          :statistics {}}]))

(defn- rows-for [cid]
  (case cid
    "bafkA" [[10] [30]]
    "bafkB" [[110] [130]]
    "bafkC" [[210] [230]]))

(defn- opener [opened]
  (fn [{:keys [cid object]}]
    (swap! opened conj cid)
    (source/of-quads
     (for [[i [price]] (map-indexed vector (rows-for cid))]
       {:s (str object "#row" i) :p "price" :o price}))))

(defn- table-src [opened & [on-prune]]
  (table/table-source {:quads manifest :table tbl
                       :open-member (opener opened)
                       :on-prune on-prune}))

;; ── the point of the namespace ──────────────────────────────────────────────

(deftest a-partition-predicate-opens-nothing-it-can-rule-out
  (let [opened (atom #{}) pruned (atom nil)
        src (table-src opened #(reset! pruned %))]
    (source/scan-set src [nil "price" 120])
    (is (= #{"bafkB" "bafkC"} @opened)
        "bafkA ruled out by price statistics; bafkC has none and so must be
         opened — absent statistics never permit a skip, one level up exactly
         as inside a file")
    (is (= 1 (:skipped @pruned))))
  (testing "a predicate on the partition column prunes without opening anything"
    (let [opened (atom #{})
          src (table-src opened)]
      (is (= #{{:s "obj:bafkC#row0" :p "region" :o "west"}
               {:s "obj:bafkC#row1" :p "region" :o "west"}}
             (source/scan-set src [nil "region" "west"])))
      (is (empty? @opened)
          "no file contains its partition column, so the answer comes from the
           manifest and not one byte is read"))))

(deftest a-partition-column-is-answered-from-the-manifest
  (let [opened (atom #{})
        src (table-src opened)]
    (is (= 6 (count (source/scan-set src [nil "region" nil])))
        "3 files x 2 rows, all from row counts in the manifest")
    (is (empty? @opened))
    (testing "and it is the value from the path, which no file holds"
      (is (= #{"east" "west"} (into #{} (map :o) (source/scan-set src [nil "region" nil])))))))

(deftest data-and-partition-columns-come-back-together
  (let [opened (atom #{})
        all (source/scan-set (table-src opened) [nil nil nil])]
    (is (= 12 (count all)) "6 price datoms + 6 region datoms")
    (is (= #{"price" "region"} (into #{} (map :p) all)))
    (is (= #{"bafkA" "bafkB" "bafkC"} @opened)
        "an unbound pattern cannot prune, and says so by opening everything")))

;; ── pruning is the same operation as inside a file ──────────────────────────

(deftest file-pruning-follows-the-same-rules-as-row-group-pruning
  (let [ms (table/members manifest tbl)]
    (testing "statistics rule a file out"
      (is (true? (table/skip-member? (first (filter #(= "bafkA" (:cid %)) ms))
                                     [[:= "price" 120]]))))
    (testing "absent statistics never do"
      (is (false? (table/skip-member? (first (filter #(= "bafkC" (:cid %)) ms))
                                      [[:= "price" 120]]))
          "the file gets opened: slower, and never a missing row"))
    (testing "a partition value rules a file out for free"
      (is (true? (table/skip-member? (first (filter #(= "bafkC" (:cid %)) ms))
                                     [[:= "region" "east"]])))
      (is (false? (table/skip-member? (first (filter #(= "bafkA" (:cid %)) ms))
                                      [[:= "region" "east"]]))))
    (testing "a range over a partition value is not guessed at"
      (is (false? (table/skip-member? (first (filter #(= "bafkC" (:cid %)) ms))
                                      [[:> "region" "zzz"]]))
          "comparable in principle, deliberately not attempted — a wrong skip
           here loses a whole file"))))

;; ── the manifest is queryable, not a blob ───────────────────────────────────

(deftest the-manifest-is-datoms-on-the-same-plane
  (let [ms (table/members manifest tbl)]
    (is (= 3 (count ms)))
    (is (= #{"east" "west"} (into #{} (map #(get-in % [:partition "region"])) ms)))
    (is (= {:nulls 0 :min 10 :max 30}
           (get-in (first (filter #(= "bafkA" (:cid %)) ms)) [:statistics "price"])))
    (testing "and members come back in a deterministic order"
      (is (= ["bafkA" "bafkB" "bafkC"] (mapv :cid ms))
          "the manifest is a set; without sorting, the order files are opened
           in is whatever the collection iterates in today"))
    (testing "attribute per column, so a query plane can see into it"
      (is (contains? (into #{} (map :p) manifest) "member/min/price"))
      (is (contains? (into #{} (map :p) manifest) "member/partition/region")))))

(deftest a-member-is-opened-at-most-once
  (let [opened (atom [])
        src (table/table-source {:quads manifest :table tbl
                                 :open-member (fn [{:keys [cid object]}]
                                                (swap! opened conj cid)
                                                (source/of-quads
                                                 [{:s (str object "#row0") :p "price" :o 1}]))})]
    (source/scan-set src [nil "price" 1])
    (source/scan-set src [nil "price" 1])
    (is (= (distinct @opened) @opened) "memoised across scans")))

;; ── schema evolution: members that do not agree about their columns ─────────

(def evolving
  "Three files written at different times. `note` was added after the first,
  the second widened `price`, and the third is entirely null in `note` — which
  makes no claim about its type and must not veto the others."
  (into #{}
        (mapcat table/add-member)
        [{:table tbl :cid "bafkOld" :rows 2 :partition {"region" "east"}
          :schema {"price" :int32 "region-name" :byte-array}
          :statistics {"price" {:nulls 0 :min 10 :max 30}}}
         {:table tbl :cid "bafkNew" :rows 2 :partition {"region" "east"}
          :schema {"price" :int64 "region-name" :utf8 "note" :utf8}
          :statistics {"price" {:nulls 0 :min 110 :max 130}}}
         {:table tbl :cid "bafkNull" :rows 2 :partition {"region" "west"}
          :schema {"price" :int64 "region-name" :utf8 "note" :null}
          :statistics {}}]))

(deftest a-member-records-its-own-columns
  (let [by-cid (into {} (map (juxt :cid :schema)) (table/members evolving tbl))]
    (is (= {"bafkOld"  {"price" :int32 "region-name" :byte-array}
            "bafkNew"  {"price" :int64 "region-name" :utf8 "note" :utf8}
            "bafkNull" {"price" :int64 "region-name" :utf8 "note" :null}}
           by-cid))))

(deftest the-table-schema-is-unified-without-opening-a-file
  (let [{:keys [columns types]} (table/table-schema evolving tbl)]
    ;; First appearance across members, and `members` sorts by member id --
    ;; so the order follows the manifest, not the order files were written.
    ;; Deterministic is the property that matters; chronological is not
    ;; something the manifest records.
    (is (= ["note" "price" "region-name"] columns))
    (is (= {"price" :int64        ; widened: only int64 describes every value
            "region-name" :utf8   ; Parquet's :byte-array and Arrow's :utf8 are
                                  ; one class and equal width, so the first
                                  ; member wins the tie
            "note" :utf8}         ; the all-null member did not veto it
           types))
    (testing "and the tie is between ALIASES, so the class is what agrees"
      (is (= :string (columnar.evolve/class-of (get types "region-name")))))))

(deftest partition-columns-are-not-in-the-table-schema
  ;; They are not in the files. Putting `region` here would make
  ;; `columnar.evolve` synthesise it as all-null for every member, replacing a
  ;; value the manifest knows with nothing — and `table-source` already
  ;; answers it from the manifest.
  (is (not (contains? (:types (table/table-schema evolving tbl)) "region")))
  (is (contains? (:partition (first (table/members evolving tbl))) "region")))

(deftest a-member-with-no-recorded-schema-contributes-nothing
  ;; Unknown columns and no columns are different claims, and only the second
  ;; is safe to unify on. `manifest` above records no schemas at all.
  (is (= {:columns [] :types {}} (table/table-schema manifest tbl))))

(deftest incompatible-columns-across-members-are-refused-by-name
  (let [clash (into #{}
                    (mapcat table/add-member)
                    [{:table tbl :cid "bafkI" :rows 1 :schema {"x" :int64} :statistics {}}
                     {:table tbl :cid "bafkF" :rows 1 :schema {"x" :double} :statistics {}}])
        e (try (table/table-schema clash tbl) nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :columnar/incompatible-types (:type e)))
    (is (= "x" (:column e)))))

;; ── snapshots and time travel ───────────────────────────────────────────────

(def ^:private m-a (table/member-id tbl "bafkA"))
(def ^:private m-b (table/member-id tbl "bafkB"))
(def ^:private m-c (table/member-id tbl "bafkC"))

(def history
  "Three snapshots: one file, then two, then the third replacing the second —
  which is what a compaction or a correction looks like."
  (into manifest
        (concat
         (table/snapshot {:table tbl :id "s1" :at "2026-08-01T00:00:00Z"
                          :members [m-a]})
         (table/snapshot {:table tbl :id "s2" :at "2026-08-02T00:00:00Z"
                          :parent "s1" :members [m-a m-b]})
         (table/snapshot {:table tbl :id "s3" :at "2026-08-03T00:00:00Z"
                          :parent "s2" :members [m-a m-c]})
         (table/set-current tbl "s3"))))

(defn- sid [id] (table/snapshot-id tbl id))

(deftest a-snapshot-names-its-members-explicitly
  (is (= [m-a] (table/snapshot-members history (sid "s1"))))
  (is (= [m-a m-b] (table/snapshot-members history (sid "s2"))))
  (is (= [m-a m-c] (table/snapshot-members history (sid "s3")))))

(deftest the-current-pointer-is-the-only-mutable-thing
  (is (= (sid "s3") (table/current history tbl)))
  (testing "and a table that was never snapshotted has none"
    (is (nil? (table/current manifest tbl)))))

(deftest an-old-snapshot-keeps-answering-what-it-answered
  ;; The whole mechanism. s2 named bafkB; s3 does not. Querying s2 still sees
  ;; it, because writing s3 did not edit s2.
  (is (= ["bafkA"] (mapv :cid (table/members-at history tbl (sid "s1")))))
  (is (= ["bafkA" "bafkB"] (mapv :cid (table/members-at history tbl (sid "s2")))))
  (is (= ["bafkA" "bafkC"] (mapv :cid (table/members-at history tbl (sid "s3"))))))

(deftest a-nil-snapshot-is-the-table-as-it-stands
  ;; What a caller predating snapshots meant, and what an unsnapshotted table
  ;; is. NOT the same as an empty snapshot.
  (is (= ["bafkA" "bafkB" "bafkC"] (mapv :cid (table/members-at history tbl nil))))
  (testing "an empty snapshot is a table deliberately emptied, and stays expressible"
    (let [emptied (into history (table/snapshot {:table tbl :id "s4" :parent "s3"
                                                 :members []}))]
      (is (= [] (mapv :cid (table/members-at emptied tbl (sid "s4"))))))))

(deftest lineage-is-the-parent-pointer-not-the-timestamp
  (is (= [(sid "s3") (sid "s2") (sid "s1")] (table/ancestry history (sid "s3"))))
  (is (= [(sid "s1")] (table/ancestry history (sid "s1"))))
  (testing "a hand-built cycle stops instead of looping"
    (let [looped (into #{} (concat
                            (table/snapshot {:table tbl :id "x" :parent "y" :members []})
                            (table/snapshot {:table tbl :id "y" :parent "x" :members []})))]
      (is (= 2 (count (table/ancestry looped (sid "x"))))))))

(deftest a-query-runs-against-a-snapshot
  (let [opened (atom #{})
        src (table/table-source {:quads history :table tbl
                                 :snapshot (sid "s2")
                                 :open-member (opener opened)})]
    (is (= #{{:s "obj:bafkA#row0" :p "price" :o 10}
             {:s "obj:bafkA#row1" :p "price" :o 30}
             {:s "obj:bafkB#row0" :p "price" :o 110}
             {:s "obj:bafkB#row1" :p "price" :o 130}}
           (source/scan src [nil "price" nil])))
    (is (= #{"bafkA" "bafkB"} @opened) "bafkC belongs to s3 and was never opened")))

(deftest the-schema-is-per-snapshot
  ;; A column added later is not in the table as it was before it was added.
  (let [q (into evolving
                (concat (table/snapshot {:table tbl :id "e1"
                                         :members [(table/member-id tbl "bafkOld")]})
                        (table/snapshot {:table tbl :id "e2" :parent "e1"
                                         :members [(table/member-id tbl "bafkOld")
                                                   (table/member-id tbl "bafkNew")]})))]
    (is (= ["price" "region-name"]
           (:columns (table/table-schema q tbl (table/snapshot-id tbl "e1")))))
    (is (= {"price" :int32 "region-name" :byte-array}
           (:types (table/table-schema q tbl (table/snapshot-id tbl "e1")))))
    (testing "and the later snapshot has the added column, widened"
      (let [{:keys [columns types]} (table/table-schema q tbl (table/snapshot-id tbl "e2"))]
        (is (= #{"price" "region-name" "note"} (set columns)))
        (is (= :int64 (get types "price")))))))
