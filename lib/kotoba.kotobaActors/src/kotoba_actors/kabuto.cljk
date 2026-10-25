(ns kotoba-actors.kabuto
  "kabuto 兜 — world public-company supply-chain analysis, refactored onto the
  kotoba-datomic substrate (`kotoba-actors.datomic`). Reads kabuto's live seed
  and answers the same supply-chain-resilience questions the Python actor does,
  but via datoms + datalog `q` rather than map-walking.

  RESILIENCE LENS (G2, inherited from the actor): findings surface where supply
  CONCENTRATES (single-source / one-jurisdiction) so it can be routed to
  redundancy + accountability. This is NEVER a target-list."
  (:require [kotoba-actors.config :as config]
            [kotoba-actors.datomic :as d]))

(defn db
  "Load the kabuto seed into a kotoba-datomic db."
  []
  (d/db-from-seed config/kabuto-seed))

(defn company-count
  "Number of distinct listed companies (entities with a :company/sector)."
  [db]
  (count (d/q '{:find [?e]
                :where [[?e :company/sector ?s]]}
              db)))

(defn supply-edge-count
  "Number of supplier->customer supply edges (entities with :supply.edge/from)."
  [db]
  (count (d/q '{:find [?e]
                :where [[?e :supply.edge/from ?from]]}
              db)))

(defn sector-count
  "Number of distinct :company/sector values present."
  [db]
  (count (d/q '{:find [?s]
                :where [[?e :company/sector ?s]]}
              db)))

(defn dangling-edges
  "Supply edges whose :supply.edge/from or :supply.edge/to does NOT resolve to a
  known company entity. Returns a set of the offending edge ids (empty = clean)."
  [db]
  (set (mapcat identity
               (d/q '{:find [?edge]
                      :where [[?edge :supply.edge/from ?from]
                              (not-join [?from]
                                        [?company :company/id ?from])]}
                    db)
               (d/q '{:find [?edge]
                      :where [[?edge :supply.edge/to ?to]
                              (not-join [?to]
                                        [?company :company/id ?to])]}
                    db))))

(defn commodity-hhi
  "Herfindahl-Hirschman concentration index over supply edges grouped by
  :supply.edge/commodity, by SUPPLIER (:supply.edge/from). Returns a map
  {commodity hhi} where each hhi is in [0.0, 1.0] (1.0 = single supplier)."
  [db]
  (let [edges (d/q '{:find [?commodity ?supplier]
                     :where [[?edge :supply.edge/commodity ?commodity]
                             [?edge :supply.edge/from ?supplier]]}
                   db)]
    (->> edges
         (group-by first)
         (map (fn [[commodity pairs]]
                (let [suppliers (map second pairs)
                      total (count suppliers)
                      shares (vals (frequencies suppliers))
                      hhi (double (reduce + (map #(/ (* % %) (* total total)) shares)))]
                  [commodity hhi])))
         (into {}))))

(defn single-source-commodities
  "Commodities supplied by exactly one supplier in the seed — the brittle points.
  Returns a set of commodity values."
  [db]
  (set (for [[commodity hhi] (commodity-hhi db)
             :when (== 1.0 hhi)]
         commodity)))
