(ns kotoba-actors.rasen
  "rasen 螺旋 — analysis layer over the public-genetics genome graph.

  STUB SANDBOX (RED): every analysis fn below is an unimplemented `todo` stub.
  Another agent implements the bodies later, against the contracts in the
  docstrings. The only non-stub here is `db`, which materialises the real seed
  via the engine.

  SEED SHAPE (discovered, see rasen_test for the pinned counts):
    - NODE rows carry `:genome/id` (the entity id) and are partitioned by
      `:genome/kind` ∈ {:gene :variant :phenotype :population :pathway}.
      These rows ARE in the db (queryable with d/q).
    - EDGE (縁) rows carry `:en/from` + `:en/to` + `:en/kind` and have NO
      `*/id` key, so `rows->datoms` SKIPS them — they are NOT in the db.
      Anything about edges MUST use `d/load-rows` + filter, NOT d/q."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Materialise the real rasen seed as an EAVT db (NODE rows only; edge/縁 rows
  lack `*/id` and are skipped by the engine). REAL — not a stub."
  []
  (d/db-from-seed config/rasen-seed))

;; ── node counts (one fn per :genome/kind) ─────────────────────────────────────
;; All node rows share the SAME id attribute `:genome/id`; the node TYPE is the
;; value of `:genome/kind`. So each count is a d/q over the db matching
;; [?e :genome/kind <kind>] (the rows are in the db).

(defn- count-by-kind [db kind]
  (count (d/q {:find  ['?e]
                :where [['?e :genome/kind kind]]}
               db)))

(defn gene-count
  "Number of :gene nodes. A gene node is a db entity with
  [?e :genome/kind :gene]. Implement via d/q over (db); the rows have `:genome/id`
  so they ARE in the db (do NOT use d/load-rows). Returns a non-negative integer."
  [db]
  (count-by-kind db :gene))

(defn variant-count
  "Number of :variant nodes. A variant node is a db entity with
  [?e :genome/kind :variant]. Implement via d/q over (db) (rows are in the db).
  Returns a non-negative integer."
  [db]
  (count-by-kind db :variant))

(defn phenotype-count
  "Number of :phenotype nodes. A phenotype node is a db entity with
  [?e :genome/kind :phenotype]. Implement via d/q over (db) (rows are in the db).
  Returns a non-negative integer."
  [db]
  (count-by-kind db :phenotype))

(defn population-count
  "Number of :population nodes. A population node is a db entity with
  [?e :genome/kind :population]. Implement via d/q over (db) (rows are in the db).
  Returns a non-negative integer."
  [db]
  (count-by-kind db :population))

(defn pathway-count
  "Number of :pathway nodes. A pathway node is a db entity with
  [?e :genome/kind :pathway]. Implement via d/q over (db) (rows are in the db).
  Returns a non-negative integer."
  [db]
  (count-by-kind db :pathway))

;; ── edge count (縁 rows, NOT in the db) ───────────────────────────────────────

(defn- edge-rows []
  (filter #(and (contains? % :en/from)
                (contains? % :en/to))
          (d/load-rows config/rasen-seed)))

(defn edge-count
  "Total number of 縁/edge rows. Edge rows are identified by having `:en/from`
  and `:en/to` and NO `*/id` key, so they are SKIPPED by the engine and are NOT
  in the db. MUST be computed via `(d/load-rows config/rasen-seed)` + filter on
  the presence of `:en/from`/`:en/to` (NOT d/q). Returns a non-negative integer."
  []
  (count (edge-rows)))

;; ── closure / referential-integrity invariant ────────────────────────────────

(defn dangling-edges
  "Referential-integrity closure check. Returns the SET of edge rows (縁 maps)
  whose `:en/from` OR `:en/to` is NOT the `:genome/id` of any node row.

  Edge rows have no `*/id`, so they are NOT in the db: load them via
  `(d/load-rows config/rasen-seed)` + filter for `:en/from`/`:en/to`. Node ids
  are the set of `:genome/id` values (obtainable via d/q [?e :genome/kind ?k] or
  from load-rows). A graph with full referential integrity returns #{} (empty)."
  []
  (let [rows (d/load-rows config/rasen-seed)
        node-ids (into #{} (comp (filter :genome/id) (map :genome/id)) rows)]
    (into #{} (filter (fn [edge]
                        (or (not (contains? node-ids (:en/from edge)))
                            (not (contains? node-ids (:en/to edge))))))
          (edge-rows))))
