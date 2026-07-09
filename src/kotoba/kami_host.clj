(ns kotoba.kami-host
  "A minimal, deterministic game-engine ECS host for the kami-* host
  imports (kotoba-core-contracts \"kami/engine\", capability id 233): the
  kami:engine vocabulary exposed through kotoba's single (module \"kotoba\")
  ABI, so a `.kotoba` guest can drive real game logic on Chicory the same
  way kotoba-lang/wasm-webcomponent's kami-engine-host.js drives kami-clj
  guests on the browser's native engine.

  Same guest-computes/host-executes split as the gpu-set-position surface
  (ADR-2607078000): this host owns ALL entity state (id -> tag/position/
  velocity), the fixed-step Euler integration, the tick counter, the input
  axes, and a SEEDED xorshift64 random stream (deterministic replay — same
  seed, same game — never the OS RNG; that's random-bytes' job). The guest
  owns only per-tick decisions: the driver calls `step!` then the guest's
  0-arg `main`, once per tick, exactly like the now-days
  requestAnimationFrame loop — no guest-side loop or extra wasm export.
  Batch ops (move-tagged-toward!/despawn-within!) stand in for per-entity
  iteration the language deliberately doesn't have.

  One state map (see `fresh-state`) lives for one game run, mirroring
  kgraph's per-run fresh store; every wasm-facing op is guarded through
  kotoba.wasm-exec/guarded-host-functions (fail-closed, receipted), so a
  policy without :kami/engine denies the very first call."
  (:require [kotoba.wasm-exec :as wasm-exec]))

(defn fresh-state
  "Fresh game state: tick counter, entity table (id -> {:tag :x :y :vx
  :vy}, a sorted map so id-order iteration — and therefore nearest-tagged
  tie-breaking — is deterministic), host-owned input axes, and the seeded
  xorshift64 rng word (SEED must be non-zero for xorshift; 0 is remapped
  to the splitmix64 golden-gamma constant rather than rejected)."
  ([] (fresh-state 7))
  ([seed]
   {:tick (atom 0)
    :next-id (atom 0)
    :entities (atom (sorted-map))
    :axes (atom {})
    :rng (atom (if (zero? (long seed)) (unchecked-long 0x9E3779B97F4A7C15) (long seed)))}))

;; ---------------------------------------------------------------------------
;; Core ECS ops — plain data in, plain data out (unit-testable without any
;; wasm instance); the wasm-facing `kami-effects` layer below only decodes
;; the wire ABI (string ptr/len, f32 bit patterns) and delegates here.

(defn spawn-entity!
  "Spawn a TAG-tagged entity at (0,0) with zero velocity; returns its id."
  ^long [state tag]
  (let [id (long (dec (swap! (:next-id state) inc)))]
    (swap! (:entities state) assoc id
           {:tag tag :x 0.0 :y 0.0 :vx 0.0 :vy 0.0})
    id))

(defn despawn-entity!
  "Remove entity ID; 0 when it existed, -1 when it didn't."
  ^long [state id]
  (let [id (long id)]
    (if (contains? @(:entities state) id)
      (do (swap! (:entities state) dissoc id) 0)
      -1)))

(defn set-position!
  "Place entity ID at (X,Y); 0, or -1 for an unknown id."
  ^long [state id x y]
  (let [id (long id)]
    (if (contains? @(:entities state) id)
      (do (swap! (:entities state) update id assoc :x (double x) :y (double y)) 0)
      -1)))

(defn set-velocity!
  "Point entity ID's velocity at (VX,VY) units/second; 0, or -1 for an
  unknown id. `step!` integrates pos += vel * dt each fixed step."
  ^long [state id vx vy]
  (let [id (long id)]
    (if (contains? @(:entities state) id)
      (do (swap! (:entities state) update id assoc :vx (double vx) :vy (double vy)) 0)
      -1)))

(defn get-x ^double [state id]
  (double (get-in @(:entities state) [(long id) :x] 0.0)))

(defn get-y ^double [state id]
  (double (get-in @(:entities state) [(long id) :y] 0.0)))

(defn count-tagged ^long [state tag]
  (count (filter #(= tag (:tag %)) (vals @(:entities state)))))

(defn- dist ^double [^double ax ^double ay ^double bx ^double by]
  (Math/hypot (- ax bx) (- ay by)))

(defn nearest-tagged
  "Nearest TAG-tagged entity id within MAX-DIST of (X,Y), or -1. Ties go
  to the lowest id (sorted-map iteration order)."
  [state tag x y max-dist]
  (let [x (double x) y (double y) max-dist (double max-dist)]
    (long (or (first
               (reduce (fn [[_ best-d :as best] [id e]]
                         (if (= tag (:tag e))
                           (let [d (dist x y (:x e) (:y e))]
                             (if (and (<= d max-dist) (or (nil? best-d) (< d best-d)))
                               [id d]
                               best))
                           best))
                       [nil nil]
                       @(:entities state)))
              -1))))

(defn move-tagged-toward!
  "Point every TAG-tagged entity's velocity at (X,Y) at SPEED units/second
  (an entity already at the target gets velocity zero instead of a NaN
  direction); returns how many entities were repointed."
  [state tag x y speed]
  (let [x (double x) y (double y) speed (double speed)]
    (long (count
           (for [[id e] @(:entities state)
                 :when (= tag (:tag e))]
             (let [d (dist x y (:x e) (:y e))]
               (if (< d 1e-9)
                 (set-velocity! state id 0.0 0.0)
                 (set-velocity! state id
                                (* speed (/ (- x (:x e)) d))
                                (* speed (/ (- y (:y e)) d)))))))
          )))

(defn despawn-within!
  "Despawn every TAG-tagged entity within RADIUS of (X,Y); returns how
  many were despawned."
  [state tag x y radius]
  (let [x (double x) y (double y) radius (double radius)
        hit (vec (for [[id e] @(:entities state)
                       :when (and (= tag (:tag e))
                                  (<= (dist x y (:x e) (:y e)) radius))]
                   id))]
    (doseq [id hit] (despawn-entity! state id))
    (count hit)))

(defn set-axis!
  "Set host-owned input axis NAME (e.g. \"MoveX\") to V in [-1.0, 1.0] —
  the test/page-side stand-in for a real input device."
  [state name v]
  (swap! (:axes state) assoc name (double v))
  nil)

(defn axis ^double [state name]
  (double (get @(:axes state) name 0.0)))

(defn tick-n ^long [state]
  (long @(:tick state)))

(defn- xorshift64 ^long [^long s]
  (let [s (bit-xor s (bit-shift-left s 13))
        s (bit-xor s (unsigned-bit-shift-right s 7))]
    (bit-xor s (bit-shift-left s 17))))

(defn rand-int!
  "Uniform long in [0, N) from the seeded xorshift64 stream (advances it)."
  ^long [state n]
  (Long/remainderUnsigned (swap! (:rng state) xorshift64) (long n)))

(def default-dt
  "Fixed integration step: 60 steps/second, the same fixed-step convention
  kami-engine-host.js / kami-script-runtime-rs use (16ms ticks)."
  (/ 1.0 60.0))

(defn step!
  "Advance one fixed step: integrate every entity (pos += vel * dt), then
  bump the tick counter. The driver calls this BEFORE each guest `main`
  call, so the guest always observes freshly-integrated positions and a
  tick counter starting at 1 — mirroring the now-days loop's \"host
  recomputes, then calls main again\" ordering."
  ([state] (step! state default-dt))
  ([state dt]
   (let [dt (double dt)]
     (swap! (:entities state)
            (fn [es]
              (reduce-kv (fn [m id e]
                           (assoc m id
                                  (assoc e
                                         :x (+ (:x e) (* (:vx e) dt))
                                         :y (+ (:y e) (* (:vy e) dt)))))
                         (sorted-map) es)))
     (swap! (:tick state) inc))
   nil))

;; ---------------------------------------------------------------------------
;; Wire ABI layer

(defn- read-str ^String [instance ptr len]
  (String. (.readBytes (.memory instance) (int ptr) (int len)) "UTF-8"))

(defn- f32-arg
  "Decode arg slot I (Chicory packs every param's raw bits into a long) as
  the f32 the guest actually passed."
  ^double [^longs args i]
  (double (Float/intBitsToFloat (unchecked-int (aget args i)))))

(defn- f32-ret
  "Encode V as the raw f32 bit pattern Chicory expects back in the long
  return slot for an :f32-result host import."
  ^long [^double v]
  (Integer/toUnsignedLong (Float/floatToRawIntBits (float v))))

(defn kami-effects
  "op -> (fn [instance args] -> long) for every kami-* host import, against
  STATE (see `fresh-state`) — same raw-effect shape as
  kotoba.wasm-exec/real-op-effects, consumed by `kami-host-functions`."
  [state]
  {'kami-tick-n
   (fn [_instance _args] (tick-n state))
   'kami-spawn
   (fn [instance ^longs args]
     (spawn-entity! state (read-str instance (aget args 0) (aget args 1))))
   'kami-despawn
   (fn [_instance ^longs args] (despawn-entity! state (aget args 0)))
   'kami-set-position!
   (fn [_instance ^longs args]
     (set-position! state (aget args 0) (f32-arg args 1) (f32-arg args 2)))
   'kami-set-velocity!
   (fn [_instance ^longs args]
     (set-velocity! state (aget args 0) (f32-arg args 1) (f32-arg args 2)))
   'kami-get-x
   (fn [_instance ^longs args] (f32-ret (get-x state (aget args 0))))
   'kami-get-y
   (fn [_instance ^longs args] (f32-ret (get-y state (aget args 0))))
   'kami-count-tagged
   (fn [instance ^longs args]
     (count-tagged state (read-str instance (aget args 0) (aget args 1))))
   'kami-nearest-tagged
   (fn [instance ^longs args]
     (nearest-tagged state (read-str instance (aget args 0) (aget args 1))
                     (f32-arg args 2) (f32-arg args 3) (f32-arg args 4)))
   'kami-move-tagged-toward!
   (fn [instance ^longs args]
     (move-tagged-toward! state (read-str instance (aget args 0) (aget args 1))
                          (f32-arg args 2) (f32-arg args 3) (f32-arg args 4)))
   'kami-despawn-within!
   (fn [instance ^longs args]
     (despawn-within! state (read-str instance (aget args 0) (aget args 1))
                      (f32-arg args 2) (f32-arg args 3) (f32-arg args 4)))
   'kami-axis
   (fn [instance ^longs args]
     (f32-ret (axis state (read-str instance (aget args 0) (aget args 1)))))
   'kami-rand
   (fn [_instance ^longs args] (rand-int! state (aget args 0)))})

(defn kami-host-functions
  "Guarded HostFunctions for the kami-* surface (see
  kotoba.wasm-exec/guarded-host-functions: fail-closed per-call capability
  check against POLICY, receipted via OPTS' :record! when supplied). A
  policy that doesn't grant :kami/engine denies the very first call."
  ([state policy] (kami-host-functions state policy nil))
  ([state policy opts]
   (wasm-exec/guarded-host-functions (kami-effects state) policy opts)))
