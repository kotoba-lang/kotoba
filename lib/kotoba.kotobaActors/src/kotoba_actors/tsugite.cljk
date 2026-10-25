(ns kotoba-actors.tsugite
  "tsugite 継�手 — peoples-continuity graph analysis over the kotoba-datomic
  substrate. This is a RED sandbox: every analysis fn is a `todo:` stub that
  throws. Another agent implements the bodies later.

  Seed schema (see config/tsugite-seed):
    NODE rows carry `:organism/id` (the entity id) + `:organism/kind`, one of
    :people / :language / :pressure / :haven. These rows ARE in the db.

    EDGE (縁) rows have NO `:organism/id` — they use `:en/from` + `:en/to`
    + `:en/kind` + `:en/peril-load`. Per the engine contract, rows without a
    `*/id` key are SKIPPED by `db-from-seed`, so edges are NOT in the db and
    MUST be reached via `d/load-rows` + filter, NOT `d/q`."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Real db built from the tsugite seed (node rows only; edges are absent —
  see ns docstring). Returns whatever `d/db-from-seed` returns."
  []
  (d/db-from-seed config/tsugite-seed))

(defn- kind-count
  "Count nodes of the given :organism/kind using `d/q`."
  [kind]
  (count (d/q {:find  '[?e]
               :where [['?e :organism/kind kind]]}
              (db))))

(defn- edge-row?
  "A 縁 (edge) row has :en/from, :en/to and :en/kind, but no :organism/id."
  [row]
  (and (contains? row :en/from)
       (contains? row :en/to)
       (contains? row :en/kind)))

(defn people-count
  "Returns the number (long) of :people node entities — rows whose
  `:organism/kind` is :people. These rows have `:organism/id`, so this is
  answerable from the db via `d/q` (no `d/load-rows` needed)."
  []
  (kind-count :people))

(defn language-count
  "Returns the number (long) of :language node entities — rows whose
  `:organism/kind` is :language. Identified by `:organism/kind` :language;
  rows carry `:organism/id`, so answerable from the db via `d/q`."
  []
  (kind-count :language))

(defn pressure-count
  "Returns the number (long) of :pressure node entities — rows whose
  `:organism/kind` is :pressure. Identified by `:organism/kind` :pressure;
  rows carry `:organism/id`, so answerable from the db via `d/q`."
  []
  (kind-count :pressure))

(defn haven-count
  "Returns the number (long) of :haven node entities — rows whose
  `:organism/kind` is :haven. Identified by `:organism/kind` :haven;
  rows carry `:organism/id`, so answerable from the db via `d/q`."
  []
  (kind-count :haven))

(defn edge-count
  "Returns the total number (long) of 縁 (edge) rows — rows with NO
  `:organism/id`, identified by the presence of `:en/from`/`:en/to`/`:en/kind`.
  Edges are NOT in the db, so this MUST use `d/load-rows` + filter, NOT `d/q`."
  []
  (->> (d/load-rows config/tsugite-seed)
       (filter edge-row?)
       count))

(defn dangling-edges
  "Closure / referential-integrity check over the 縁 edges. Returns the SET of
  edge rows whose `:en/from` or `:en/to` does NOT resolve to an existing node
  `:organism/id`. An empty set means the graph is closed (every edge endpoint
  is a real node). Requires `d/load-rows` for edges (no `:organism/id`, so not
  in the db); node ids may come from `d/load-rows` or `d/q`."
  []
  (let [db        (db)
        node-ids  (into #{} (map first)
                        (d/q {:find  '[?e]
                              :where [['?e :organism/kind '?kind]]}
                             db))
        endpoints (juxt :en/from :en/to)
        dangling? (fn [edge]
                    (not-every? node-ids (endpoints edge)))]
    (->> (d/load-rows config/tsugite-seed)
         (filter edge-row?)
         (filter dangling?)
         set)))
