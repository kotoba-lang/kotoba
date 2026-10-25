(ns kotoba-actors.asobi
  "asobi 遊び — participation/access analysis over the seed play graph, refactored
  onto the kotoba-datomic EAVT/datalog substrate.

  Graph shape (discovered from the seed):
    - NODES carry an :organism/id and an :organism/kind, one of
      :work :practice :venue :event :enclosure. These ARE in the db (they have
      an id), so they can be counted via `d/q` against [?e :organism/kind <k>].
    - EDGES (縁) are rows keyed :en/from + :en/to + :en/kind with NO id. Per the
      engine contract these are SKIPPED by `rows->datoms`, so they are NOT in the
      db. Any edge-facing analysis MUST use `d/load-rows` + filter, never `d/q`.

  Every analysis fn below is implemented against the kotoba-actors.datomic
  engine."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Build the real EAVT db from the asobi seed (nodes only; edges have no id and
  are absent from the db). Returns a kotoba-datomic db value."
  []
  (d/db-from-seed config/asobi-seed))

;; ── node counts (db-backed; identified by :organism/kind) ────────────────────

(defn- count-kind
  "Count distinct entities with :organism/kind equal to k using d/q."
  [db k]
  (count (d/q {:find '[?e]
                :where [['?e :organism/kind k]]}
               db)))

(defn count-works
  "Return (long) the number of :work nodes — entities with
  [?e :organism/kind :work]. db-backed: countable via d/q (works have an id)."
  [db]
  (count-kind db :work))

(defn count-practices
  "Return (long) the number of :practice nodes — entities with
  [?e :organism/kind :practice]. db-backed: countable via d/q."
  [db]
  (count-kind db :practice))

(defn count-venues
  "Return (long) the number of :venue nodes — entities with
  [?e :organism/kind :venue]. db-backed: countable via d/q."
  [db]
  (count-kind db :venue))

(defn count-events
  "Return (long) the number of :event nodes — entities with
  [?e :organism/kind :event]. db-backed: countable via d/q."
  [db]
  (count-kind db :event))

(defn count-enclosures
  "Return (long) the number of :enclosure nodes — entities with
  [?e :organism/kind :enclosure]. db-backed: countable via d/q."
  [db]
  (count-kind db :enclosure))

;; ── edge count (NOT db-backed; edges have no id) ─────────────────────────────

(defn count-edges
  "Return (long) the total number of 縁 edge rows — rows keyed :en/from + :en/to
  (and no :organism/id). These are SKIPPED by the db, so this MUST use
  d/load-rows + filter, NOT d/q."
  []
  (->> (d/load-rows config/asobi-seed)
       (filter #(and (contains? % :en/from) (contains? % :en/to)))
       count))

;; ── closure (NOT db-backed; edge endpoints vs node ids) ──────────────────────

(defn dangling-edges
  "Return the SET of edge rows whose :en/from or :en/to does NOT resolve to a
  known node :organism/id. Closure invariant: a well-formed seed has NONE, so
  this returns #{}. Edges are absent from the db, so this MUST use d/load-rows +
  filter (load all rows, derive the node-id set from rows with :organism/id, and
  keep edge rows with an unresolved endpoint), NOT d/q."
  []
  (let [rows (d/load-rows config/asobi-seed)
        node-ids (into #{} (keep :organism/id) rows)]
    (into #{} (filter #(or (not (node-ids (:en/from %)))
                           (not (node-ids (:en/to %)))))
          (filter #(and (contains? % :en/from) (contains? % :en/to)) rows))))
