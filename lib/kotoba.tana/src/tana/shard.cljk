(ns tana.shard
  "One root does not scale, and the measurement says where it stops.

  A root carries every member's statistics and every chunk's byte range, so
  it is O(members × chunks × columns) bytes. That is the trade it makes:
  constant requests, linear bytes. Measured on this repo's bench, a member
  costs ~700 bytes of root, so a root beats reading footers on **requests**
  immediately and loses on **bytes** at about three objects.

  So above a few dozen members the root splits in two levels:

      top          one small object: per-manifest bounds
       └─ manifest per-member statistics and byte ranges
            └─ object   the actual columnar file

  A query reads the top, fetches only the manifests its bounds could not rule
  out, and then ranges only the chunks those manifests could not rule out.
  Requests go from `1 + chunks` to `1 + manifests + chunks`, and bytes stop
  being linear in the whole table.

  This is the shape Iceberg's manifest-list/manifest split has, arrived at
  from the same pressure. What is different is that every level here is
  content-addressed, so a reader pins one address and cannot observe a
  half-published table — there is no catalog service holding a mutable
  pointer to the current one.

  ## Absence propagates upward

  A manifest reports bounds for a column only when **every** chunk under it
  reported them. One unbounded chunk makes the manifest unbounded for that
  column, and an unbounded manifest is fetched rather than skipped. Deriving
  a bound from the chunks that did report — the tempting shape — invents a
  claim the data never made, and the failure is the silent one: rows vanish."
  (:require [tana.table :as table]))

(defn- column-bounds
  "`{col {:min .. :max ..}}` over every chunk of every member, or absent."
  [members columns]
  (into {}
        (keep (fn [col]
                (let [chunks (for [m members, c (:chunks m)] (get-in c [:columns col]))
                      present (remove nil? chunks)
                      stats (map :stats present)]
                  (when (and (seq stats)
                             (= (count chunks) (count present))
                             (every? #(and (contains? % :min) (contains? % :max)) stats))
                    [col {:min (reduce (fn [a b] (if (neg? (compare b a)) b a)) (map :min stats))
                          :max (reduce (fn [a b] (if (pos? (compare b a)) b a)) (map :max stats))
                          :rows (reduce + 0 (map :rows stats))}]))))
        columns))

(defn split
  "Split `root` into a top and `manifests`, `per` members each.

  -> `{:top {...} :manifests {address manifest}}`. `hash-fn` addresses each
  manifest; the top names them and nothing else, so it stays small."
  [hash-fn root per]
  (when-not (pos? per)
    (throw (ex-info "manifests need at least one member" {:type :tana/invalid-shard})))
  (let [groups (partition-all per (:members root))
        built (mapv (fn [ms]
                      (let [manifest (table/table (assoc root :members (vec ms)))
                            address (table/address hash-fn manifest)]
                        {:address address
                         :manifest manifest
                         :entry {:manifest address
                                 :members (count ms)
                                 :rows (reduce + 0 (map :rows ms))
                                 :bounds (column-bounds ms (:columns root))}}))
                    groups)]
    {:top {:table (:table root)
           :columns (:columns root)
           :bounds-authority (:bounds-authority root)
           :manifests (mapv :entry built)
           :rows (:rows root)}
     :manifests (into {} (map (juxt :address :manifest)) built)}))

(defn- skip-manifest?
  "Reuses the chunk rule by presenting manifest bounds in chunk-stats shape.

  Not a second pruning implementation — `tana.plan` hands these to
  `columnar.stats/skip?` exactly as it does a chunk's."
  [entry]
  (fn [col] (get-in entry [:bounds col])))

(defn stats-of [entry] (skip-manifest? entry))
