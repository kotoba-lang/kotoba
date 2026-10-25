(ns kotoba-actors.kadode
  "kadode 門出 — Clojure / kotoba-datomic refactor of the labour-exit (resignation)
  graph actor.

  The seed (kotoba-actors.config/kadode-seed) is a single top-level vector of
  rows of two shapes:

    - NODE rows: carry a `:lx/id` (entity id) + `:lx/kind` discriminator
      (one of :route :ground :document :risk :scenario). These ARE indexed into
      the db by kotoba-actors.datomic (db-from-seed), so `d/q` can see them.

    - EDGE (縁) rows: carry `:en/from` + `:en/to` + `:en/kind` and have NO id
      key. These are SKIPPED by the engine (not in db). Any analysis touching
      edges MUST read them via `d/load-rows` + filter, NOT `d/q`.

  Every analysis fn below is an UNIMPLEMENTED stub (throws ex-info \"todo: ...\").
  Another agent implements the bodies; this ns only fixes the contract."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

;; ── db (real, not a stub) ───────────────────────────────────────────────────

(defn db
  "Build and return the real EAVT db from the kadode seed. NODE rows only are
  indexed (edge/縁 rows have no id and are skipped by the engine)."
  []
  (d/db-from-seed config/kadode-seed))

;; ── node counts (one per :lx/kind; resolvable via d/q on :lx/kind) ───────────

(defn- count-kind [db kind]
  (count (d/q {:find '[?e]
               :where [['?e :lx/kind kind]]}
              db)))

(defn count-routes
  "Return the integer count of :route nodes. A route node is identified by
  [?e :lx/kind :route]; resolvable with d/q on the db (node rows are indexed)."
  [db]
  (count-kind db :route))

(defn count-grounds
  "Return the integer count of :ground nodes. A ground node is identified by
  [?e :lx/kind :ground]; resolvable with d/q on the db (node rows are indexed)."
  [db]
  (count-kind db :ground))

(defn count-documents
  "Return the integer count of :document nodes. A document node is identified by
  [?e :lx/kind :document]; resolvable with d/q on the db (node rows are indexed)."
  [db]
  (count-kind db :document))

(defn count-risks
  "Return the integer count of :risk nodes. A risk node is identified by
  [?e :lx/kind :risk]; resolvable with d/q on the db (node rows are indexed)."
  [db]
  (count-kind db :risk))

(defn count-scenarios
  "Return the integer count of :scenario nodes. A scenario node is identified by
  [?e :lx/kind :scenario]; resolvable with d/q on the db (node rows are indexed)."
  [db]
  (count-kind db :scenario))

;; ── edge count (縁 rows have no id; MUST use d/load-rows + filter) ────────────

(defn count-edges
  "Return the integer count of edge/縁 rows in the seed. An edge row is
  identified by the `:en/from` key (also has :en/to + :en/kind, no id). Edge
  rows are NOT in the db, so this MUST be computed from d/load-rows + filter,
  NOT d/q."
  [_db]
  (->> (d/load-rows config/kadode-seed)
       (filter :en/from)
       count))

;; ── closure invariant (dangling-edges -> set) ───────────────────────────────

(defn dangling-edges
  "Return the SET of edge endpoint ids (:en/from / :en/to values) that do NOT
  resolve to any known node id (:lx/id). The closure invariant for a
  well-formed graph is that this set is empty. Node ids come from the indexed db
  (or load-rows); edge endpoints MUST come from d/load-rows + filter on
  `:en/from`, since edge rows are not in the db."
  [db]
  (let [node-ids (into #{} (map first)
                       (d/q {:find '[?e]
                             :where [['?e :lx/kind '?kind]]}
                            db))
        endpoints (mapcat (fn [row]
                            [(:en/from row) (:en/to row)])
                          (filter :en/from (d/load-rows config/kadode-seed)))]
    (into #{} (remove node-ids) endpoints)))
