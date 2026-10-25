(ns game.physics
  "Restored from kami-game/src/physics.rs (kotoba-lang/kami-engine, deleted in PR #82),
  as part of the Rust→CLJC restoration (ADR-2607010930, com-junkawasaki/root).

  The original wraps the Rapier 3D physics engine and hecs ECS. This port is a
  zero-dependency, self-contained rigid-body simulation offering the same
  public surface (ground plane, dynamic/kinematic boxes, sensors, velocity
  control, jump impulses, stepping, raycast, sensor-intersection queries) via
  plain CLJC data + pure functions, since neither Rapier nor hecs are
  available as portable CLJC deps. `kami_core::actor::components::Position`
  is duck-typed here as a plain `{:position [x y z]}` map (see `sync-to-ecs`)
  rather than pulled in from another cluster.

  A `PhysicsWorld` is a plain map:
    {:bodies     {handle body}
     :colliders  {handle collider}
     :gravity    [x y z]
     :dt         seconds-per-step
     :next-body-handle    int
     :next-collider-handle int
     :sensor-pairs #{[collider-handle collider-handle] ...}}  ; populated by `step`

  `body`     = {:kind :dynamic|:kinematic :position [x y z] :linvel [x y z]
                :next-kinematic-translation nil-or-[x y z]}
  `collider` = {:half-extents [x y z] :position [x y z] :sensor? bool
                :body-handle nil-or-handle}")

;; ---------------------------------------------------------------------------
;; vec3 helpers
;; ---------------------------------------------------------------------------

(defn v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v-scale [[x y z] s] [(* x s) (* y s) (* z s)])

(defn v-length [[x y z]]
  #?(:clj (Math/sqrt (double (+ (* x x) (* y y) (* z z))))
     :cljs (js/Math.sqrt (+ (* x x) (* y y) (* z z)))))

(defn- fabs [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))

;; ---------------------------------------------------------------------------
;; TriggerZone / TriggerKind (data, ported 1:1)
;; ---------------------------------------------------------------------------

(def trigger-kinds #{:portal :item-pickup :damage-zone})

(defn trigger-zone [collider-handle kind data]
  {:collider-handle collider-handle :kind kind :data data})

;; ---------------------------------------------------------------------------
;; PhysicsWorld construction
;; ---------------------------------------------------------------------------

(def default-gravity [0.0 -9.81 0.0])
(def default-dt (/ 1.0 60.0))

(defn new-world
  ([] (new-world default-gravity default-dt))
  ([gravity dt]
   {:bodies {}
    :colliders {}
    :gravity gravity
    :dt dt
    :next-body-handle 0
    :next-collider-handle 0
    :sensor-pairs #{}}))

(defn- alloc-body [world body]
  (let [h (:next-body-handle world)]
    [(-> world
         (assoc-in [:bodies h] body)
         (update :next-body-handle inc))
     h]))

(defn- alloc-collider [world collider]
  (let [h (:next-collider-handle world)]
    [(-> world
         (assoc-in [:colliders h] collider)
         (update :next-collider-handle inc))
     h]))

;; ---------------------------------------------------------------------------
;; Builders
;; ---------------------------------------------------------------------------

(defn add-ground
  "Add a ground plane at y=0 (cuboid half-extents [100 0.1 100], top surface at y=0).
  Returns [world' collider-handle]."
  [world]
  (alloc-collider world {:half-extents [100.0 0.1 100.0]
                          :position [0.0 -0.1 0.0]
                          :sensor? false
                          :body-handle nil}))

(defn add-dynamic-box
  "Add a dynamic rigid body with a box collider. Returns [world' body-handle collider-handle]."
  [world pos half-extents]
  (let [[world1 bh] (alloc-body world {:kind :dynamic :position pos :linvel [0.0 0.0 0.0]
                                        :next-kinematic-translation nil})
        [world2 ch] (alloc-collider world1 {:half-extents half-extents :position pos
                                             :sensor? false :body-handle bh})]
    [world2 bh ch]))

(defn add-kinematic-box
  "Add a kinematic (server-controlled) body with a box collider. Returns [world' body-handle collider-handle]."
  [world pos half-extents]
  (let [[world1 bh] (alloc-body world {:kind :kinematic :position pos :linvel [0.0 0.0 0.0]
                                        :next-kinematic-translation nil})
        [world2 ch] (alloc-collider world1 {:half-extents half-extents :position pos
                                             :sensor? false :body-handle bh})]
    [world2 bh ch]))

(defn add-sensor
  "Add a sensor trigger zone (no physics response, intersection detection only).
  Returns [world' collider-handle]."
  [world pos half-extents]
  (alloc-collider world {:half-extents half-extents :position pos :sensor? true :body-handle nil}))

;; ---------------------------------------------------------------------------
;; Control
;; ---------------------------------------------------------------------------

(defn set-linvel
  "Set XZ velocity of a body, preserving its current Y velocity (matches
  rb.set_linvel(vector![vel.x, rb.linvel().y, vel.z], true))."
  [world handle [vx _ vz]]
  (if-let [body (get-in world [:bodies handle])]
    (assoc-in world [:bodies handle :linvel] [vx (get-in body [:linvel 1]) vz])
    world))

(defn jump
  "Apply a jump impulse if the body is near-resting vertically (|linvel.y| < 0.1)."
  [world handle impulse]
  (if-let [body (get-in world [:bodies handle])]
    (if (< (fabs (get-in body [:linvel 1])) 0.1)
      (update-in world [:bodies handle :linvel 1] + impulse)
      world)
    world))

(defn set-kinematic-pos
  "Queue a kinematic body's next position (applied on the following `step`)."
  [world handle pos]
  (if (contains? (:bodies world) handle)
    (assoc-in world [:bodies handle :next-kinematic-translation] pos)
    world))

;; ---------------------------------------------------------------------------
;; Simulation step
;; ---------------------------------------------------------------------------

(defn- aabb [pos half-extents] [(v- pos half-extents) (v+ pos half-extents)])

(defn- aabb-overlap? [[amin amax] [bmin bmax]]
  (and (<= (amin 0) (bmax 0)) (>= (amax 0) (bmin 0))
       (<= (amin 1) (bmax 1)) (>= (amax 1) (bmin 1))
       (<= (amin 2) (bmax 2)) (>= (amax 2) (bmin 2))))

(defn- integrate-body [body gravity dt colliders]
  (case (:kind body)
    :kinematic
    (if-let [next-pos (:next-kinematic-translation body)]
      (assoc body :position next-pos :next-kinematic-translation nil)
      body)

    :dynamic
    (let [linvel' (v+ (:linvel body) (v-scale gravity dt))
          pos' (v+ (:position body) (v-scale linvel' dt))]
      (assoc body :position pos' :linvel linvel'))

    body))

(defn- resolve-ground-collision
  "Simple ground-plane collision response: clamp dynamic boxes above the
  ground collider's top surface and zero downward velocity on landing."
  [body colliders own-collider]
  (if (and (= (:kind body) :dynamic) own-collider)
    (let [half-y (get-in own-collider [:half-extents 1])
          ground-colliders (filter (fn [[_ c]] (and (nil? (:body-handle c)) (not (:sensor? c))))
                                    colliders)]
      (reduce
       (fn [b [_ ground]]
         (let [ground-top (+ (get-in ground [:position 1]) (get-in ground [:half-extents 1]))
               body-bottom (- (get-in b [:position 1]) half-y)]
           (if (< body-bottom ground-top)
             (-> b
                 (assoc-in [:position 1] (+ ground-top half-y))
                 (assoc-in [:linvel 1] (max 0.0 (get-in b [:linvel 1]))))
             b)))
       body ground-colliders))
    body))

(defn step
  "Advance the simulation by `(:dt world)`. Integrates bodies (gravity for
  dynamic, queued translation for kinematic), resolves ground-plane
  collisions, syncs collider world positions to their parent bodies, and
  recomputes sensor/non-sensor overlap pairs."
  [world]
  (let [{:keys [bodies colliders gravity dt]} world
        bodies' (reduce-kv
                 (fn [acc handle body]
                   (let [own-collider (some (fn [[_ c]] (when (= (:body-handle c) handle) c))
                                             colliders)
                         integrated (integrate-body body gravity dt colliders)
                         resolved (resolve-ground-collision integrated colliders own-collider)]
                     (assoc acc handle resolved)))
                 {} bodies)
        colliders' (reduce-kv
                    (fn [acc handle c]
                      (if-let [bh (:body-handle c)]
                        (assoc acc handle (assoc c :position (get-in bodies' [bh :position])))
                        (assoc acc handle c)))
                    {} colliders)
        sensors (filter (fn [[_ c]] (:sensor? c)) colliders')
        non-sensors (filter (fn [[_ c]] (not (:sensor? c))) colliders')
        pairs (set (for [[sh sc] sensors
                         [oh oc] non-sensors
                         :when (aabb-overlap? (aabb (:position sc) (:half-extents sc))
                                               (aabb (:position oc) (:half-extents oc)))]
                     [sh oh]))]
    (assoc world :bodies bodies' :colliders colliders' :sensor-pairs pairs)))

;; ---------------------------------------------------------------------------
;; Sync / queries
;; ---------------------------------------------------------------------------

(defn sync-to-ecs
  "Write physics positions back into an ECS-like collection of entities.
  `entities` is a seq of `{:position [x y z] :physics-body body-handle ...}`
  maps (duck-typed stand-in for `kami_core::actor::components::Position` +
  hecs `World`, which are not part of this cluster). Returns the updated seq."
  [world entities]
  (mapv (fn [e]
          (if-let [bh (:physics-body e)]
            (if-let [body (get-in world [:bodies bh])]
              (assoc e :position (:position body))
              e)
            e))
        entities))

(defn get-position
  "Get the world position of a body, or nil if the handle is unknown."
  [world handle]
  (get-in world [:bodies handle :position]))

(defn sensor-intersections
  "All [sensor-collider-handle other-collider-handle] pairs currently overlapping."
  [world]
  (vec (:sensor-pairs world)))

;; ---------------------------------------------------------------------------
;; Raycast: ray vs. all collider AABBs (slab method). Returns [dist handle] or nil.
;; ---------------------------------------------------------------------------

(defn raycast [world origin dir max-dist]
  (let [[ox oy oz] origin
        [dx dy dz] dir
        hit-aabb (fn [[mn mx]]
                   (let [axis (fn [o d lo hi]
                                (if (zero? d)
                                  (if (or (< o lo) (> o hi)) [##Inf ##-Inf] [##-Inf ##Inf])
                                  (let [t1 (/ (- lo o) d) t2 (/ (- hi o) d)]
                                    (if (< t1 t2) [t1 t2] [t2 t1]))))
                         [txmin txmax] (axis ox dx (mn 0) (mx 0))
                         [tymin tymax] (axis oy dy (mn 1) (mx 1))
                         [tzmin tzmax] (axis oz dz (mn 2) (mx 2))
                         tmin (max 0.0 txmin tymin tzmin)
                         tmax (min max-dist txmax tymax tzmax)]
                     (when (<= tmin tmax) tmin)))]
    (->> (:colliders world)
         (keep (fn [[handle c]]
                 (when-let [t (hit-aabb (aabb (:position c) (:half-extents c)))]
                   [t handle])))
         (sort-by first)
         first)))
