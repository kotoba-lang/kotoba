(ns graph.layout
  "Force-directed graph layout (Fruchterman-Reingold style) + the Merkle-DAG-style
  PCB layout. Pure computation — no GPU dependency; produces (x, y) positions for
  each node.

  Restored from `kami-engine/kami-graph/src/layout.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as zero-dependency
  portable `.cljc`, per ADR-2607010930 (the clj-wgsl migration).

  ## Shapes (plain maps, no records)

  - `LayoutNode` -> {:x :y :vx :vy :radius :group-index :fixed}
  - `LayoutEdge` -> {:from-idx :to-idx :edge-type}
  - `ForceLayout` -> {:nodes [LayoutNode...] :edges [LayoutEdge...]
                       :alpha :alpha-decay :alpha-min :charge :link-dist :damping}
  - `PcbLayout` -> {:nodes [LayoutNode...] :edges [LayoutEdge...] :buses [BusLine...]}
  - `BusLine` -> {:collection :y :subscriber-count}

  ## Simulation state

  Unlike the original Rust (`&mut self` mutation), [[tick]] is a pure function
  `layout -> [layout' running?]` — matching the immutable-state pattern used
  throughout this migration. [[run]] folds `tick` up to `max-ticks` times or until
  convergence (`alpha < alpha-min`).")

;; --- ForceLayout: construction -------------------------------------------

(defn- initial-position
  "Golden-angle spiral initial position for node index `i`."
  [i]
  (let [angle (* (double i) 2.399)
        r (* (Math/sqrt (double i)) 8.0)]
    [(* r (Math/cos angle)) (* r (Math/sin angle))]))

(defn force-layout
  "Build a `ForceLayout` from `GraphData`. With `positions` (a vector of `[x y]`
  pairs, one per node, index-aligned with `(:nodes graph-data)`), nodes whose
  supplied position is non-zero start at that fixed initial position (still
  free to move — only [[pcb-layout]] pins nodes); all other nodes fall back to
  a golden-angle spiral. Mirrors `ForceLayout::new` / `ForceLayout::with_positions`."
  ([graph-data] (force-layout graph-data nil))
  ([graph-data positions]
   (let [gnodes (:nodes graph-data)
         n (count gnodes)
         nodes (mapv (fn [i node]
                       (let [supplied (when (and positions (< i (count positions)))
                                        (nth positions i))
                             [x y] (if (and supplied
                                            (or (not= (nth supplied 0) 0.0)
                                                (not= (nth supplied 1) 0.0)))
                                     supplied
                                     (initial-position i))]
                         {:x x :y y :vx 0.0 :vy 0.0
                          :radius (:radius node)
                          :group-index (:group-index node)
                          :fixed false}))
                     (range n) gnodes)
         edges (mapv (fn [e] {:from-idx (:from-idx e) :to-idx (:to-idx e) :edge-type (:edge-type e)})
                     (:edges graph-data))
         charge (if (> n 500) -80.0 -200.0)
         link-dist (if (> n 500) 50.0 100.0)]
     {:nodes nodes
      :edges edges
      :alpha 1.0
      :alpha-decay 0.005
      :alpha-min 0.001
      :charge charge
      :link-dist link-dist
      :damping 0.85})))

;; --- ForceLayout: one simulation tick -------------------------------------

(defn- skip-threshold [n]
  (if (> n 1000) (* 500.0 500.0) ##Inf))

(defn- charge-forces
  "Pairwise Coulomb-style repulsion. Returns [dvx dvy], per-node velocity deltas."
  [nodes charge alpha]
  (let [n (count nodes)
        thresh (skip-threshold n)
        zeros (vec (repeat n 0.0))]
    (reduce
      (fn [[dvx dvy] [i j]]
        (let [ni (nodes i) nj (nodes j)
              dx (- (:x nj) (:x ni))
              dy (- (:y nj) (:y ni))
              d2 (max (+ (* dx dx) (* dy dy)) 1.0)]
          (if (> d2 thresh)
            [dvx dvy]
            (let [d (Math/sqrt d2)
                  f (/ (* charge alpha) d2)
                  fx (* (/ dx d) f)
                  fy (* (/ dy d) f)]
              [(-> dvx (update i - fx) (update j + fx))
               (-> dvy (update i - fy) (update j + fy))]))))
      [zeros zeros]
      (for [i (range n) j (range (inc i) n)] [i j]))))

(defn- link-forces
  "Spring forces pulling edge endpoints toward `link-dist` apart. Returns [dvx dvy]."
  [nodes edges link-dist alpha]
  (let [n (count nodes)
        zeros (vec (repeat n 0.0))]
    (reduce
      (fn [[dvx dvy] {:keys [from-idx to-idx]}]
        (if (= from-idx to-idx)
          [dvx dvy]
          (let [s (nodes from-idx) t (nodes to-idx)
                dx (- (:x t) (:x s))
                dy (- (:y t) (:y s))
                d (max (Math/sqrt (+ (* dx dx) (* dy dy))) 1.0)
                f (* (- d link-dist) 0.05 alpha)
                fx (* (/ dx d) f)
                fy (* (/ dy d) f)]
            [(-> dvx (update from-idx + fx) (update to-idx - fx))
             (-> dvy (update from-idx + fy) (update to-idx - fy))])))
      [zeros zeros]
      edges)))

(defn tick
  "Run one tick of the force simulation. Returns `[layout' running?]` where
  `running?` is false once converged (`alpha < alpha-min`) — mirrors
  `ForceLayout::tick`'s `&mut self -> bool`, but pure."
  [layout]
  (if (< (:alpha layout) (:alpha-min layout))
    [layout false]
    (let [{:keys [nodes edges alpha alpha-decay alpha-min charge link-dist damping]} layout
          n (count nodes)
          [cdvx cdvy] (charge-forces nodes charge alpha)
          [ldvx ldvy] (link-forces nodes edges link-dist alpha)
          new-nodes (mapv (fn [i node]
                             (let [gvx (* (- (:x node)) 0.005 alpha)
                                   gvy (* (- (:y node)) 0.005 alpha)
                                   tvx (+ (:vx node) (cdvx i) (ldvx i) gvx)
                                   tvy (+ (:vy node) (cdvy i) (ldvy i) gvy)]
                               (if (:fixed node)
                                 (assoc node :vx 0.0 :vy 0.0)
                                 (let [vx (* tvx damping)
                                       vy (* tvy damping)]
                                   (assoc node :vx vx :vy vy
                                          :x (+ (:x node) vx)
                                          :y (+ (:y node) vy))))))
                           (range n) nodes)
          new-alpha (max (- alpha alpha-decay) alpha-min)]
      [(assoc layout :nodes new-nodes :alpha new-alpha) true])))

(defn run
  "Run the simulation until convergence or `max-ticks`, whichever comes first.
  Mirrors `ForceLayout::run`."
  [layout max-ticks]
  (loop [layout layout ticks-left max-ticks]
    (if (<= ticks-left 0)
      layout
      (let [[layout' running?] (tick layout)]
        (if running?
          (recur layout' (dec ticks-left))
          layout')))))

(defn reheat
  "Reset alpha to 1.0, restarting the simulation from the current positions."
  [layout]
  (assoc layout :alpha 1.0))

(defn settled?
  "True once the simulation has converged (alpha <= alpha-min)."
  [layout]
  (<= (:alpha layout) (:alpha-min layout)))

;; --- Merkle DAG PCB layout -------------------------------------------------
;;
;; Layered layout following data flow direction (Merkle DAG):
;;
;;   Y=0    +---------------------- Layer 0: Writers (apps that write) --------+
;;          |  [app] [app] [app] ...   sorted by project, placed in columns    |
;;          +------------------------------------------------------------------+
;;                    | write                    | write
;;   Y=BUS  ======== collection bus lines (shared data, horizontal) ==========
;;                    | subscribe/read           | subscribe/read
;;   Y=READ +---------------------- Layer 2: Readers (apps that read) --------+
;;          |  [app] [app] [app] ...   sorted by project, placed in columns    |
;;          +------------------------------------------------------------------+
;;
;; Deterministic, O(n). Data flows top -> bottom (writer -> collection -> reader).
;;
;; NOTE on determinism: the original Rust built the bus-line ordering from a
;; `HashMap` (`target_counts`), whose iteration order is unspecified, so ties in
;; subscriber count broke arbitrarily even upstream. This port sorts bus targets
;; by `[(- count) node-idx]`, which is a strictly deterministic total order (a
;; strict improvement, not a behavior change for the non-tied case).

(def ^:private dag-cell-w 6.0)
(def ^:private dag-layer-gap 60.0)
(def ^:private dag-bus-gap 2.0)

(defn pcb-layout
  "Build a `PcbLayout` from `GraphData`: writer apps on top, reader apps on the
  bottom, shared \"collection\" nodes with >=3 subscribers rendered as horizontal
  bus lines in between. Mirrors `PcbLayout::new`."
  [graph-data]
  (let [gnodes (:nodes graph-data)
        n (count gnodes)
        base-nodes (mapv (fn [gnode]
                            {:x 0.0 :y 0.0 :vx 0.0 :vy 0.0
                             :radius (if (= (:node-type gnode) "collection") 0.0 (:radius gnode))
                             :group-index (:group-index gnode)
                             :fixed true})
                          gnodes)
        edges (mapv (fn [e] {:from-idx (:from-idx e) :to-idx (:to-idx e) :edge-type (:edge-type e)})
                     (:edges graph-data))

        is-writer (reduce (fn [acc {:keys [from-idx edge-type]}]
                             (if (#{"writes" "invoke"} edge-type)
                               (assoc acc from-idx true)
                               acc))
                           (vec (repeat n false)) edges)
        is-reader (reduce (fn [acc {:keys [from-idx edge-type]}]
                             (if (#{"reads" "subscribe"} edge-type)
                               (assoc acc from-idx true)
                               acc))
                           (vec (repeat n false)) edges)

        {:keys [writer-nodes reader-nodes]}
        (reduce (fn [acc [i gnode]]
                  (cond
                    (= (:node-type gnode) "collection") acc
                    (is-writer i) (update acc :writer-nodes conj i)
                    (is-reader i) (update acc :reader-nodes conj i)
                    :else (update acc :reader-nodes conj i)))
                {:writer-nodes [] :reader-nodes []}
                (map-indexed vector gnodes))

        by-group (fn [i] [(:group-index (nth gnodes i)) i])
        writer-nodes (sort-by by-group writer-nodes)
        reader-nodes (sort-by by-group reader-nodes)

        nodes-1 (reduce (fn [nodes [col ni]]
                           (-> nodes
                               (assoc-in [ni :x] (* (double col) dag-cell-w))
                               (assoc-in [ni :y] 0.0)))
                         base-nodes
                         (map-indexed vector writer-nodes))

        target-counts (reduce (fn [acc {:keys [to-idx]}] (update acc to-idx (fnil inc 0)))
                               {} edges)
        bus-targets (->> target-counts
                          (filter (fn [[_ c]] (>= c 3)))
                          (sort-by (fn [[idx c]] [(- c) idx])))
        bus-y-start dag-layer-gap

        {:keys [nodes-2 buses]}
        (reduce (fn [{:keys [nodes-2 buses]} [i [node-idx cnt]]]
                  (let [y (+ bus-y-start (* (double i) dag-bus-gap))]
                    {:nodes-2 (-> nodes-2
                                  (assoc-in [node-idx :x] 0.0)
                                  (assoc-in [node-idx :y] y)
                                  (assoc-in [node-idx :radius] 0.0))
                     :buses (conj buses {:collection (:id (nth gnodes node-idx))
                                          :y y
                                          :subscriber-count cnt})}))
                {:nodes-2 nodes-1 :buses []}
                (map-indexed vector bus-targets))

        reader-y-start (+ bus-y-start (* (+ (double (count buses)) 2.0) dag-bus-gap) dag-layer-gap)
        nodes-3 (reduce (fn [nodes [col ni]]
                           (-> nodes
                               (assoc-in [ni :x] (* (double col) dag-cell-w))
                               (assoc-in [ni :y] reader-y-start)))
                         nodes-2
                         (map-indexed vector reader-nodes))]
    {:nodes nodes-3 :edges edges :buses buses}))
