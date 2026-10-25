(ns kotoba-actors.tanemaki
  "Clojure / kotoba-datomic refactor of the tanemaki 種蒔き actor: a fund-
  stewardship graph over a SYNTHETIC candidate-org seed (G6).

  ── SEED SHAPE (discovered from the seed; see docstrings for exact attrs) ──────
  NODE rows carry `:fs/id` (the entity id) + `:fs/kind` one of
    :instrument :screen :criterion :source :org :milestone.
  EDGE (縁) rows carry `:en/from` + `:en/to` + `:en/kind` and NO id key, so the
  engine's `rows->datoms` SKIPS them — they are NOT in `db`. Any analysis over
  edges MUST use `d/load-rows` + filter on `:en/from`, never `d/q`."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

;; ── substrate ────────────────────────────────────────────────────────────────

(defn db
  "Real (non-stub): build the EAVT db from the tanemaki seed. Contains ONLY the
  node rows (those with `:fs/id`); edge/縁 rows are skipped by the engine."
  []
  (d/db-from-seed config/tanemaki-seed))

;; ── node-type counts (one fn per `:fs/kind`) ─────────────────────────────────

(defn count-instruments
  "Return the count (long) of instrument nodes: entities with
  `:fs/kind :instrument`. Countable from `db` via d/q (no d/load-rows)."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :fs/kind :instrument]]}
               (db))))

(defn count-screens
  "Return the count (long) of hard-screen nodes: entities with
  `:fs/kind :screen` (each also carries a `:screen/code`). Countable from `db`
  via d/q (no d/load-rows)."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :fs/kind :screen]]}
               (db))))

(defn count-criteria
  "Return the count (long) of weighted-criterion nodes: entities with
  `:fs/kind :criterion` (each also carries a `:criterion/weight`). Countable
  from `db` via d/q (no d/load-rows)."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :fs/kind :criterion]]}
               (db))))

(defn count-sources
  "Return the count (long) of evidence-source nodes: entities with
  `:fs/kind :source`. Countable from `db` via d/q (no d/load-rows)."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :fs/kind :source]]}
               (db))))

(defn count-orgs
  "Return the count (long) of candidate-org nodes (all synthetic, G6): entities
  with `:fs/kind :org`. Countable from `db` via d/q (no d/load-rows)."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :fs/kind :org]]}
               (db))))

(defn count-milestones
  "Return the count (long) of post-grant milestone nodes: entities with
  `:fs/kind :milestone`. Countable from `db` via d/q (no d/load-rows)."
  []
  (count (d/q '{:find [?e]
                 :where [[?e :fs/kind :milestone]]}
               (db))))

;; ── edge (縁) count ──────────────────────────────────────────────────────────

(defn count-edges
  "Return the total count (long) of 縁 edge rows: rows with an `:en/from` key.
  Edge rows have NO id key so they are NOT in `db` — this fn MUST use
  `d/load-rows` on `config/tanemaki-seed` + filter on `:en/from`, NOT d/q."
  []
  (count (filter :en/from (d/load-rows config/tanemaki-seed))))

;; ── closure / dangling-edge invariant ────────────────────────────────────────

(defn dangling-edges
  "Return the SET of edge endpoint ids that do NOT resolve to a node `:fs/id`
  (the graph-closure violation set). Endpoints are the `:en/from`, `:en/to` and
  `:en/evidence` values of every edge row. Because edges are NOT in `db`, this
  fn MUST use `d/load-rows` + filter on `:en/from` to read edges, and may use
  `db`/d/q (or the loaded rows) for the node-id set. A well-formed seed yields
  an EMPTY set (the closure invariant)."
  []
  (let [rows (d/load-rows config/tanemaki-seed)
        node-ids (into #{} (map :fs/id) (filter :fs/id rows))
        edge-rows (filter :en/from rows)
        endpoints (into #{} (comp (mapcat (juxt :en/from :en/to :en/evidence))
                                  (remove nil?))
                        edge-rows)]
    (into #{} (remove node-ids) endpoints)))
