(ns kotoba-actors.uchiwake
  "uchiwake 内訳 — world product bill-of-materials analysis, refactored onto the
  kotoba-datomic substrate (`kotoba-actors.datomic`). Reads uchiwake's live seed
  (PRODUCT keyed on GTIN -> PART -> raw MATERIAL via :bom.edge/parent|child) and
  answers the BOM-decomposition / material-reachability questions the Python
  actor does, but via datoms + datalog `q` rather than map-walking.

  Entities carry a `*/name` (materials :material/name, parts :part/name, products
  :product/name); the BOM is a DAG of :bom.edge entities (parent CONTAINS child)."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Load the uchiwake seed into a kotoba-datomic db."
  []
  (d/db-from-seed config/uchiwake-seed))

(defn product-count
  "Number of trade items (entities with a :product/name)."
  [db]
  (count (d/q '{:find [?e]
                 :where [[?e :product/name ?n]]}
                db)))

(defn part-count
  "Number of parts / sub-assemblies (entities with a :part/name)."
  [db]
  (count (d/q '{:find [?e]
                 :where [[?e :part/name ?n]]}
                db)))

(defn material-count
  "Number of raw/refined materials (entities with a :material/name)."
  [db]
  (count (d/q '{:find [?e]
                 :where [[?e :material/name ?n]]}
                db)))

(defn bom-edge-count
  "Number of BOM edges (entities with a :bom.edge/parent)."
  [db]
  (count (d/q '{:find [?e]
                 :where [[?e :bom.edge/parent ?p]]}
                db)))

(defn- bom-children-raw
  "Direct child ids of `id` via BOM edges."
  [db id]
  (into #{} (map first)
        (d/q {:find '[?c]
              :where [['?e :bom.edge/parent id]
                      ['?e :bom.edge/child '?c]]}
             db)))

(defn bom-children
  "Direct children of entity `id` in the BOM DAG: the set of :bom.edge/child
  values over edges whose :bom.edge/parent is `id`."
  [db id]
  (bom-children-raw db id))

(defn- material? [db id]
  (boolean
   (seq (d/q {:find '[?n]
              :where [[id :material/name '?n]]}
             db))))

(defn materials-reachable
  "Transitive closure of the BOM DAG from product/part `id`, restricted to
  MATERIAL entities (those have a :material/name). Returns a set of material ids.
  e.g. for KitKat (gtin.07613035044289): #{mat.cocoa mat.milk-powder
  mat.palm-oil mat.sugar}."
  [db id]
  (loop [frontier [id]
         visited  #{}
           materials #{}]
    (if (empty? frontier)
      materials
      (let [node    (peek frontier)
            frontier (pop frontier)]
        (if (visited node)
          (recur frontier visited materials)
          (let [visited' (conj visited node)]
            (if (material? db node)
              (recur frontier visited' (conj materials node))
              (recur (into frontier (remove visited' (bom-children-raw db node)))
                     visited'
                     materials))))))))

(defn dangling-bom-edges
  "BOM edges whose :bom.edge/parent or :bom.edge/child does NOT resolve to a
  known product/part/material entity (any entity carrying a */name). Returns a
  set of the offending edge ids (empty = the BOM graph is closed)."
  [db]
  (let [product-ids  (into #{} (map first)
                           (d/q '{:find [?e]
                                   :where [[?e :product/name ?n]]}
                                 db))
        part-ids     (into #{} (map first)
                           (d/q '{:find [?e]
                                   :where [[?e :part/name ?n]]}
                                 db))
        material-ids (into #{} (map first)
                           (d/q '{:find [?e]
                                   :where [[?e :material/name ?n]]}
                                 db))
        known        (into #{} (concat product-ids part-ids material-ids))
        edges        (d/q '{:find [?e ?p ?c]
                            :where [[?e :bom.edge/parent ?p]
                                    [?e :bom.edge/child ?c]]}
                          db)]
    (into #{} (for [[e p c] edges
                    :when (or (not (known p)) (not (known c)))]
                e))))
