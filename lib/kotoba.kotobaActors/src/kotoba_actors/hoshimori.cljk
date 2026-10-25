(ns kotoba-actors.hoshimori
  "hoshimori 星守 — orbital-congestion-vs-stewardship analysis actor.

  Parallel Clojure / kotoba-datomic refactor: reads the orbital-orbit-graph
  seed and answers structural questions about it via the EAVT/datalog engine
  in `kotoba-actors.datomic`.

  SEED SHAPE (see config/hoshimori-seed):
    - NODE rows carry `:organism/id` (the entity id) and `:organism/kind`, one
      of #{:shell :operator :hazard :service}. These ARE in the db (queryable
      with d/q via :organism/kind).
    - EDGE (縁) rows carry `:en/from` + `:en/to` + `:en/kind` and NO id key, so
      `kotoba-actors.datomic/rows->datoms` SKIPS them — they are NOT in the db.
      Edge analysis MUST use `d/load-rows` + filter, never d/q.

  Every analysis fn here is an UNIMPLEMENTED stub (throws \"todo: ...\"). Another
  agent implements the bodies; a RED spec already pins the expected answers."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Real db built from the hoshimori seed via the engine. Node rows (those with
  `:organism/id`) become datoms; edge/縁 rows (no id) are skipped by the engine."
  []
  (d/db-from-seed config/hoshimori-seed))

;; ── node-type counts (queryable via d/q on :organism/kind) ──────────────────

(defn count-shells
  "Returns (long) the number of SHELL nodes — node rows whose `:organism/kind`
  is :shell. These have ids and ARE in the db: answer with d/q on :organism/kind."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :organism/kind :shell]]}
               (db))))

(defn count-operators
  "Returns (long) the number of OPERATOR nodes — node rows whose `:organism/kind`
  is :operator. In the db; answer with d/q on :organism/kind."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :organism/kind :operator]]}
               (db))))

(defn count-hazards
  "Returns (long) the number of HAZARD nodes — node rows whose `:organism/kind`
  is :hazard. In the db; answer with d/q on :organism/kind."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :organism/kind :hazard]]}
               (db))))

(defn count-services
  "Returns (long) the number of SERVICE nodes — node rows whose `:organism/kind`
  is :service. In the db; answer with d/q on :organism/kind."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :organism/kind :service]]}
               (db))))

;; ── edge count (NOT in db — must use d/load-rows + filter) ───────────────────

(defn count-edges
  "Returns (long) the total number of 縁 (edge) rows — rows carrying `:en/from`
  (and no `:organism/id`). These are SKIPPED by the engine, so this MUST use
  `d/load-rows` on config/hoshimori-seed + filter, NOT d/q."
  []
  (->> (d/load-rows config/hoshimori-seed)
       (filter #(and (contains? % :en/from)
                     (not (contains? % :organism/id))))
       count))

;; ── closure / reachability invariant (edges → nodes; uses d/load-rows) ──────

(defn dangling-edges
  "Returns a SET of the edge rows (the raw `:en/*` maps) whose `:en/from` or
  `:en/to` does NOT resolve to a node's `:organism/id`. The closure invariant is
  that this set is EMPTY. Because edge rows are not in the db, this MUST use
  `d/load-rows` on config/hoshimori-seed: collect node ids from rows with
  `:organism/id`, then keep edge rows whose from/to is not among them."
  []
  (let [rows (d/load-rows config/hoshimori-seed)
        node-ids (into #{} (keep :organism/id) rows)
        edge? #(and (contains? % :en/from)
                    (not (contains? % :organism/id)))]
    (into #{} (comp (filter edge?)
                    (remove #(and (node-ids (:en/from %))
                                  (node-ids (:en/to %)))))
          rows)))
