(ns kotoba.lang.force3d.core
  "Pure Clojure/cljc 3D force-directed graph layout simulation — analogous to
  d3-force-3d (the 3D extension of d3.js's force layout), reimplemented from
  scratch operating purely on EDN data. No DOM, no rendering, no JS interop;
  runs on JVM / SCI / ClojureScript / GraalVM / kotoba-WASM.

  ## Data shape

  A simulation state is `{:nodes [...] :links [...] :forces {...} :alpha n
  :alpha-min n :alpha-decay n :velocity-decay n}`.

  A node is a map with at least `{:id ... :x .. :y .. :z .. :vx .. :vy ..
  :vz ..}` — position (`:x :y :z`) and velocity (`:vx :vy :vz`). Any other
  keys (e.g. `:radius`, `:fixed?`) are preserved and available to forces.

  A link is a map `{:source id :target id :strength .. :distance ..}` where
  `id` matches a node's `:id`.

  ## Forces

  Each force is a plain function `(fn [sim] sim)` — it takes the whole
  simulation state and returns an updated simulation state (typically with
  `:nodes` velocities nudged). Forces are stored in `:forces` as a map from
  keyword name to force-fn, applied in map-iteration order each tick — order
  does not matter for correctness since forces only ever *accumulate*
  velocity, they don't read velocity from earlier forces in the same tick.

  Included forces: `charge`, `link`, `center`, `collision`. Barnes-Hut octree
  optimization for `charge` (O(n log n) instead of O(n^2)) is a plausible
  future improvement for large graphs; not implemented in v1 — brute force is
  fine for the graph sizes this is meant for (dozens to low thousands of
  nodes)."
  (:refer-clojure :exclude [distance]))

;; ---------------------------------------------------------------------------
;; portable math helpers (JVM Math vs. js/Math via reader conditionals)
;; ---------------------------------------------------------------------------

(defn- sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x) :default (Math/sqrt x)))
(defn- abs* [x] (if (neg? x) (- x) x))
(defn- sin* [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x) :default (Math/sin x)))

;; ---------------------------------------------------------------------------
;; small vector helpers (3D)
;; ---------------------------------------------------------------------------

(defn- sub3 [a b] [(- (a 0) (b 0)) (- (a 1) (b 1)) (- (a 2) (b 2))])

(defn- len3 [[x y z]] (sqrt (+ (* x x) (* y y) (* z z))))

(defn- node-pos [n] [(:x n 0.0) (:y n 0.0) (:z n 0.0)])

(defn distance
  "Euclidean distance between two nodes' positions."
  [a b]
  (len3 (sub3 (node-pos a) (node-pos b))))

(defn- jitter
  "A small deterministic nudge used to break ties when two nodes sit at the
  exact same point (distance 0 would otherwise produce a divide-by-zero /
  undefined direction for charge and collision forces). Not random — a
  pure function of the pair index, so simulations stay reproducible."
  [i]
  (abs* (- (mod (sin* (* i 12.9898)) 1.0) 0.5)))

;; ---------------------------------------------------------------------------
;; node indexing helpers
;; ---------------------------------------------------------------------------

(defn- index-nodes
  "id -> index into the :nodes vector, for O(1) lookup by link endpoints."
  [nodes]
  (into {} (map-indexed (fn [i n] [(:id n) i]) nodes)))

(defn- update-velocity
  "Add [dvx dvy dvz] to node's velocity."
  [node dvx dvy dvz]
  (-> node
      (update :vx (fnil + 0.0) dvx)
      (update :vy (fnil + 0.0) dvy)
      (update :vz (fnil + 0.0) dvz)))

;; ---------------------------------------------------------------------------
;; forces
;; ---------------------------------------------------------------------------

(defn charge
  "Pairwise repulsion (`strength` negative) / attraction (`strength`
  positive) between every pair of nodes, Coulomb-like: magnitude
  `strength / distance^2`, applied along the line between the two nodes.
  Brute-force O(n^2) — fine for v1; a Barnes-Hut octree is a possible future
  optimization for large n, intentionally not built now.

  Options: `:strength` (default `-30.0`, i.e. repulsive)."
  ([sim] (charge sim {}))
  ([sim {:keys [strength] :or {strength -30.0}}]
   (let [nodes (vec (:nodes sim))
         n (count nodes)
         idxs (vec (range n))
         deltas
         (reduce
          (fn [deltas i]
            (let [a (nth nodes i)
                  [dvx dvy dvz]
                  (reduce
                   (fn [[ax ay az] j]
                     (if (= i j)
                       [ax ay az]
                       (let [b (nth nodes j)
                             [dx dy dz] (sub3 (node-pos a) (node-pos b))
                             d0 (len3 [dx dy dz])
                             d (if (zero? d0) (+ 0.01 (jitter (+ i (* j 7)))) d0)
                             ;; `ux/uy/uz` point away from b (from b toward a).
                             ;; Negating strength here is what makes negative
                             ;; `:strength` (the default) *repulsive* — it
                             ;; pushes a further away from b — and positive
                             ;; `:strength` attractive (pulls a toward b).
                             mag (/ (- strength) (* d d))
                             ux (/ dx d) uy (/ dy d) uz (/ dz d)]
                         [(+ ax (* mag ux)) (+ ay (* mag uy)) (+ az (* mag uz))])))
                   [0.0 0.0 0.0] idxs)]
              (assoc deltas i [dvx dvy dvz])))
          {} idxs)]
     (assoc sim :nodes
            (mapv (fn [i node]
                    (let [[dvx dvy dvz] (get deltas i [0.0 0.0 0.0])]
                      (update-velocity node dvx dvy dvz)))
                  idxs nodes)))))

(defn link
  "Spring force pulling each linked pair of nodes toward `:distance` (default
  `30.0`) apart, scaled by `:strength` (default `1.0`, or a per-link
  `:strength`/`:distance` override taken from the link map itself if
  present). Applies half the correction to each endpoint (unless a node has
  `:fixed? true`, which never moves)."
  ([sim] (link sim {}))
  ([sim {:keys [strength distance] :or {strength 1.0 distance 30.0}}]
   (let [nodes (vec (:nodes sim))
         id->idx (index-nodes nodes)
         nodes (reduce
                (fn [nodes {:keys [source target] :as l}]
                  (let [si (id->idx source)
                        ti (id->idx target)]
                    (if (or (nil? si) (nil? ti) (= si ti))
                      nodes
                      (let [a (nth nodes si)
                            b (nth nodes ti)
                            target-d (double (:distance l distance))
                            k (double (:strength l strength))
                            [dx dy dz] (sub3 (node-pos b) (node-pos a))
                            d0 (len3 [dx dy dz])
                            d (if (zero? d0) 0.01 d0)
                            diff (* k (- d target-d) 0.5)
                            ux (/ dx d) uy (/ dy d) uz (/ dz d)
                            dvx (* diff ux) dvy (* diff uy) dvz (* diff uz)]
                        (cond-> nodes
                          (not (:fixed? a)) (assoc si (update-velocity a dvx dvy dvz))
                          (not (:fixed? b)) (assoc ti (update-velocity b (- dvx) (- dvy) (- dvz))))))))
                nodes
                (:links sim))]
     (assoc sim :nodes nodes))))

(defn center
  "Gravitates the whole node set toward `[cx cy cz]` (default the origin),
  preventing the graph from drifting away over time. `:strength` (default
  `0.1`) scales how strongly nodes are pulled back."
  ([sim] (center sim {}))
  ([sim {:keys [cx cy cz strength] :or {cx 0.0 cy 0.0 cz 0.0 strength 0.1}}]
   (assoc sim :nodes
          (mapv (fn [n]
                  (let [[x y z] (node-pos n)]
                    (if (:fixed? n)
                      n
                      (update-velocity n
                                       (* strength (- cx x))
                                       (* strength (- cy y))
                                       (* strength (- cz z))))))
                (:nodes sim)))))

(defn collision
  "Prevents node overlap: for every pair of nodes whose combined `:radius`
  (default `1.0` when absent) exceeds their distance apart, pushes them apart
  along the line between them so the gap equals the sum of their radii.
  `:strength` (default `1.0`) scales the correction."
  ([sim] (collision sim {}))
  ([sim {:keys [strength] :or {strength 1.0}}]
   (let [nodes (vec (:nodes sim))
         n (count nodes)]
     (assoc sim :nodes
            (loop [nodes nodes i 0]
              (if (>= i n)
                nodes
                (recur
                 (loop [nodes nodes j (inc i)]
                   (if (>= j n)
                     nodes
                     (let [a (nth nodes i)
                           b (nth nodes j)
                           ra (double (:radius a 1.0))
                           rb (double (:radius b 1.0))
                           min-d (+ ra rb)
                           [dx dy dz] (sub3 (node-pos b) (node-pos a))
                           d0 (len3 [dx dy dz])
                           d (if (zero? d0) 0.01 d0)]
                       (if (< d min-d)
                         (let [overlap (* strength (- min-d d) 0.5)
                               ux (/ dx d) uy (/ dy d) uz (/ dz d)
                               dvx (* overlap ux) dvy (* overlap uy) dvz (* overlap uz)
                               nodes (cond-> nodes
                                       (not (:fixed? a)) (assoc i (update-velocity (nth nodes i) (- dvx) (- dvy) (- dvz)))
                                       (not (:fixed? b)) (assoc j (update-velocity (nth nodes j) dvx dvy dvz)))]
                           (recur nodes (inc j)))
                         (recur nodes (inc j))))))
                 (inc i))))))))

;; ---------------------------------------------------------------------------
;; simulation construction + integrator
;; ---------------------------------------------------------------------------

(defn- ensure-node-defaults [n]
  (merge {:x 0.0 :y 0.0 :z 0.0 :vx 0.0 :vy 0.0 :vz 0.0} n))

(defn simulation
  "Construct a simulation state from `nodes` and `links` (analogous to
  `d3.forceSimulation`). Options:

  - `:forces` — map of keyword -> force-fn (each `(fn [sim] sim)`, or a
    `(fn [sim opts] sim)` pre-bound via partial); default `{:charge charge
    :link link :center center}` (no `:collision` by default — opt in per
    graph since it needs meaningful `:radius` values).
  - `:alpha` (default `1.0`) — cooling parameter, starts hot.
  - `:alpha-min` (default `0.001`) — `simulate` stops once alpha falls below
    this.
  - `:alpha-decay` (default `0.0228`, matches d3-force's default — chosen so
    alpha decays from 1 to alpha-min in ~300 ticks).
  - `:velocity-decay` (default `0.4`) — fraction of velocity kept each tick
    (friction); `(- 1 velocity-decay)` is lost each tick."
  ([nodes links] (simulation nodes links {}))
  ([nodes links {:keys [forces alpha alpha-min alpha-decay velocity-decay]
                 :or {forces {:charge charge :link link :center center}
                      alpha 1.0
                      alpha-min 0.001
                      alpha-decay 0.0228
                      velocity-decay 0.4}}]
   {:nodes (mapv ensure-node-defaults nodes)
    :links (vec links)
    :forces forces
    :alpha alpha
    :alpha-min alpha-min
    :alpha-decay alpha-decay
    :velocity-decay velocity-decay}))

(defn- apply-forces [sim]
  (reduce (fn [sim [_k f]] (f sim)) sim (:forces sim)))

(defn- integrate
  "Integrate velocity -> position for every non-fixed node, applying
  velocity decay (friction), scaled by the current alpha."
  [sim]
  (let [{:keys [velocity-decay alpha]} sim]
    (update sim :nodes
            (fn [nodes]
              (mapv (fn [n]
                      (if (:fixed? n)
                        n
                        (let [vx (* (:vx n 0.0) alpha)
                              vy (* (:vy n 0.0) alpha)
                              vz (* (:vz n 0.0) alpha)]
                          (-> n
                              (assoc :vx (* vx velocity-decay)
                                     :vy (* vy velocity-decay)
                                     :vz (* vz velocity-decay))
                              (update :x + vx)
                              (update :y + vy)
                              (update :z + vz)))))
                    nodes)))))

(defn tick
  "Apply every force once, integrate velocity -> position, and decay alpha.
  Returns the updated simulation state."
  [sim]
  (-> sim
      apply-forces
      integrate
      (update :alpha (fn [a] (max 0.0 (- a (* a (:alpha-decay sim))))))))

(defn simulate
  "Run `tick` repeatedly until alpha falls below `:alpha-min` or `max-ticks`
  is reached (default `1000`, a hard safety bound), whichever comes first.
  Returns the final simulation state (get `:nodes` for final positions)."
  ([sim] (simulate sim 1000))
  ([sim max-ticks]
   (loop [sim sim i 0]
     (if (or (>= i max-ticks) (< (:alpha sim) (:alpha-min sim)))
       sim
       (recur (tick sim) (inc i))))))

(defn node-by-id
  "Find a node in `sim`'s `:nodes` by `:id`, or nil."
  [sim id]
  (some #(when (= (:id %) id) %) (:nodes sim)))
