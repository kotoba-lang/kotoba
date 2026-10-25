(ns kotoba-actors.shiori
  "shiori 栞 — wellbecoming-detraction graph analysis (kotoba-datomic refactor).

  The seed (kotoba-actors.config/shiori-seed) is a wellbecoming-relief graph at
  AGGREGATE / cohort scale. NODE rows carry a `:organism/id` and an
  `:organism/kind` of one of #{:cohort :detractor :driver :mitigator}; these land
  in the db (the EAVT index) and are queryable with `d/q`.

  EDGE rows (縁) carry `:en/from` + `:en/to` + `:en/kind` (one of
  #{:drives :diminishes :relieves :routes-to}) and NO `*/id` key, so the engine
  SKIPS them when building the db. Edge-level analysis therefore MUST use
  `d/load-rows` + filter, NOT `d/q`.

  Every analysis fn below is a RED stub: the body is exactly
  `(throw (ex-info \"todo: <name>\" {}))`. Another agent implements them."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Real db built from the shiori seed via the engine. Not a stub."
  []
  (d/db-from-seed config/shiori-seed))

;; ── node counts (queryable via d/q on :organism/kind) ──────────────────────

(defn count-cohorts
  "Return the NUMBER (long) of cohort nodes — rows whose :organism/kind is
  :cohort. Identifying attribute: [?e :organism/kind :cohort]. Queryable with
  d/q against (db); does NOT need d/load-rows."
  [db]
  (count (d/q {:find '[?e]
               :where '[[?e :organism/kind :cohort]]}
              db)))

(defn count-detractors
  "Return the NUMBER (long) of detractor nodes — rows whose :organism/kind is
  :detractor. Identifying attribute: [?e :organism/kind :detractor]. Queryable
  with d/q against (db); does NOT need d/load-rows."
  [db]
  (count (d/q {:find '[?e]
               :where '[[?e :organism/kind :detractor]]}
              db)))

(defn count-drivers
  "Return the NUMBER (long) of driver nodes — rows whose :organism/kind is
  :driver. Identifying attribute: [?e :organism/kind :driver]. Queryable with
  d/q against (db); does NOT need d/load-rows."
  [db]
  (count (d/q {:find '[?e]
               :where '[[?e :organism/kind :driver]]}
              db)))

(defn count-mitigators
  "Return the NUMBER (long) of mitigator nodes — rows whose :organism/kind is
  :mitigator. Identifying attribute: [?e :organism/kind :mitigator]. Queryable
  with d/q against (db); does NOT need d/load-rows."
  [db]
  (count (d/q {:find '[?e]
               :where '[[?e :organism/kind :mitigator]]}
              db)))

;; ── edge count (NOT in db — needs d/load-rows + filter) ────────────────────

(defn count-edges
  "Return the NUMBER (long) of 縁 edge rows in the seed — rows with an :en/from
  key (equivalently :en/kind ∈ #{:drives :diminishes :relieves :routes-to}).
  These rows have NO `*/id` and are SKIPPED by the engine, so this MUST use
  (d/load-rows config/shiori-seed) + filter on :en/from — d/q will NOT see them."
  []
  (->> (d/load-rows config/shiori-seed)
       (filter :en/from)
       count))

;; ── closure / reachability over edges (needs d/load-rows + filter) ─────────

(defn dangling-edges
  "Return the SET of edge rows (maps) whose :en/from or :en/to does NOT name a
  real node id (a value present under some node's :organism/id). Identifying
  attribute: an edge's :en/from / :en/to vs the set of node :organism/id values.
  Edges are NOT in the db, so this MUST use (d/load-rows config/shiori-seed) +
  filter for the edges AND for the node ids; d/q cannot see edge rows. The
  closure invariant for the seed is that this set is EMPTY (every edge endpoint
  resolves to a real node)."
  []
  (let [rows (d/load-rows config/shiori-seed)
        node-ids (into #{} (keep :organism/id) rows)
        edges (filter :en/from rows)]
    (into #{} (filter #(or (not (node-ids (:en/from %)))
                           (not (node-ids (:en/to %))))
                      edges))))
