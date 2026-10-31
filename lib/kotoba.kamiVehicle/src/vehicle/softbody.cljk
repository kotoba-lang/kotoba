(ns vehicle.softbody
  "Vehicle-agnostic soft-body mass-spring-damper on the vehicle node/beam/vec3
  primitives.

  `vehicle.vehicle/step` is vehicle-specific (tire / powertrain / Pacejka magic
  formula), so downstream soft-tissue consumers (e.g. kotoba-lang/biomech) had
  to re-implement a beam-only integrator in isolation. This namespace is that
  generic core, promoted into kami-vehicle itself: build a node/beam grid,
  anchor nodes, step under gravity with per-beam spring stiffness k [N/m] and
  viscous damping c [N·s/m]. Semi-implicit Euler with substeps for stability.

  Lifted from kotoba-lang/biomech `kotoba.biomech.softbody` (which was green
  there); biomech.softbody now consumes this namespace instead of duplicating
  it. Gravity is configurable; anchor nodes (mass 0) are fixed in place."
  (:require [vehicle.vec3 :as v3]
            [vehicle.node :as node]
            [vehicle.beam :as beam]))

(defn- grid-idx [cols r c] (+ (* r cols) c))

(defn make-grid
  "rows x cols grid of nodes at `spacing` [m], node mass `mass` [kg], beams
  of stiffness `spring` [N/m] and `damping` [N·s/m], connected horizontally
  and vertically. Returns a soft-body state map
  {:nodes [..] :beams [..] :gravity v3}."
  [rows cols spacing mass spring damping]
  (let [nodes (vec (for [r (range rows) c (range cols)]
                     (-> (node/new-node (grid-idx cols r c)
                                        (v3/v3 (* c spacing) (* r spacing) 0.0)
                                        mass :body)
                         node/refresh-inv-mass)))
        n-nodes (* rows cols)
        horz (for [r (range rows) c (range (dec cols))]
               (beam/new-beam (grid-idx cols r c)
                              (grid-idx cols r c) (grid-idx cols r (inc c))
                              spacing spring damping))
        vert (for [r (range (dec rows)) c (range cols)]
               (beam/new-beam (+ n-nodes (grid-idx cols r c))
                              (grid-idx cols r c) (grid-idx cols (inc r) c)
                              spacing spring damping))]
    {:nodes nodes :beams (vec (concat horz vert))
     :gravity (v3/v3 0.0 -9.81 0.0)}))

(defn fixed? "Is node anchored (mass 0)?" [nd] (node/fixed? nd))

(defn anchor-row
  "Fix (mass -> 0) all nodes in row `r` of a `cols`-wide grid state.
  Anchored nodes stay put while the rest of the body moves under gravity
  and beam forces."
  [state cols r]
  (let [to-fix (set (for [c (range cols)] (grid-idx cols r c)))]
    (update state :nodes
            (fn [ns] (mapv (fn [nd]
                             (if (to-fix (:id nd))
                               (node/refresh-inv-mass
                                (node/anchor (:id nd) (:position nd)))
                               nd))
                           ns)))))

(defn- beam-force-on-n1
  "Spring-damper force vector on n1 from beam b (n1<->n2). Stretch beyond
  rest-length pulls n1 toward n2; relative velocity along the beam is damped."
  [b n1 n2]
  (let [d (v3/sub (:position n2) (:position n1))
        len (v3/length d)]
    (if (< len 1e-9)
      (v3/v3 0.0 0.0 0.0)
      (let [dir (v3/scale d (/ 1.0 len))
            v-along (v3/dot (v3/sub (:velocity n2) (:velocity n1)) dir)
            f-mag (+ (* (- len (:rest-length b)) (:spring b))
                     (* v-along (:damping b)))]
        (v3/scale dir f-mag)))))

(defn- compute-forces
  "Per-node force vector = gravity (on non-fixed nodes) + summed beam forces."
  [{:keys [nodes beams gravity]}]
  (let [n (count nodes)
        f0 (vec (repeat n (v3/v3 0.0 0.0 0.0)))
        f-with-gravity
        (reduce (fn [f nd]
                  (if (node/fixed? nd)
                    f
                    (assoc f (:id nd) (v3/scale gravity (:mass nd)))))
                f0 nodes)]
    (reduce (fn [f b]
              (let [i1 (:n1 b) i2 (:n2 b)
                    f12 (beam-force-on-n1 b (nodes i1) (nodes i2))]
                (-> f
                    (assoc i1 (v3/add (f i1) f12))
                    (assoc i2 (v3/sub (f i2) f12)))))
            f-with-gravity beams)))

(defn step
  "Advance the soft-body by dt [s]. Semi-implicit Euler with `substeps`
  (default 8) for stability."
  ([state dt] (step state dt 8))
  ([state dt substeps]
   (let [n (max 1 (int substeps)) sdt (/ (double dt) n)]
     (loop [i 0 st state]
       (if (>= i n)
         st
         (let [forces (compute-forces st)
               new-nodes (mapv (fn [nd fi]
                                 (if (node/fixed? nd)
                                   nd
                                   (let [a (v3/scale fi (:inv-mass nd))
                                         v-new (v3/add (:velocity nd) (v3/scale a sdt))
                                         p-new (v3/add (:position nd) (v3/scale v-new sdt))]
                                     (-> nd (assoc :velocity v-new) (assoc :position p-new)))))
                               (:nodes st) forces)]
           (recur (inc i) (assoc st :nodes new-nodes))))))))

(defn simulate
  "Run `n` macro-steps of size dt from init; returns the final state."
  [init dt n]
  (loop [i 0 st init]
    (if (>= i n) st (recur (inc i) (step st dt)))))
