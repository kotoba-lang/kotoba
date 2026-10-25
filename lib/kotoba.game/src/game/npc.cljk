(ns game.npc
  "Restored from kami-game/src/npc.rs (kotoba-lang/kami-engine, deleted in PR #82),
  as part of the Rust→CLJC restoration (ADR-2607010930, com-junkawasaki/root).

  NPC AI: behavior tree + LLM dialogue stub + 'brainrot' behaviors (Skibidi,
  Grimace, Sigma, Ohio Boss, Fanum, Rizz). Mutating `&mut self` tick methods
  become pure functions returning `[state' update]`.

  The original imports `crate::common::SimpleRng`, which lives outside this
  cluster's assigned files (animation/physics/scene/npc). It's duck-typed
  here as a minimal deterministic LCG PRNG (`rng-new` / `rng-next-f32`) with
  the same `{seed) -> new-rng, next-f32 -> [0,1)}` shape; the exact numeric
  sequence isn't guaranteed to match the original `SimpleRng`, but callers
  only depend on statistical range properties (see the ported tests).")

;; ---------------------------------------------------------------------------
;; SimpleRng (duck-typed stand-in for crate::common::SimpleRng)
;; ---------------------------------------------------------------------------

(defn rng-new [seed] {:seed (bit-and seed 0xFFFFFFFF)})

(defn rng-next-f32
  "Returns [rng' value] where value is in [0,1)."
  [rng]
  (let [seed' (bit-and (+ (* (:seed rng) 1664525) 1013904223) 0xFFFFFFFF)]
    [{:seed seed'} (/ (double seed') 4294967296.0)]))

;; ---------------------------------------------------------------------------
;; vec3 helpers
;; ---------------------------------------------------------------------------

(def vec3-zero [0.0 0.0 0.0])

(defn v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v-scale [[x y z] s] [(* x s) (* y s) (* z s)])

(defn v-length [[x y z]]
  #?(:clj (Math/sqrt (double (+ (* x x) (* y y) (* z z))))
     :cljs (js/Math.sqrt (+ (* x x) (* y y) (* z z)))))

(defn v-distance [a b] (v-length (v- a b)))

(defn v-normalize-or-zero [v]
  (let [len (v-length v)]
    (if (< len 1.0e-8) vec3-zero (v-scale v (/ 1.0 len)))))

(defn- to-radians [deg] (* deg (/ #?(:clj Math/PI :cljs js/Math.PI) 180.0)))
(defn- sin [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- cos [x] #?(:clj (Math/cos (double x)) :cljs (js/Math.cos x)))
(def TAU (* 2.0 #?(:clj Math/PI :cljs js/Math.PI)))

;; ---------------------------------------------------------------------------
;; Behavior (NPC behavior-tree state)
;; ---------------------------------------------------------------------------

(defn behavior-idle [] {:type :idle})
(defn behavior-patrol [waypoint-index] {:type :patrol :waypoint-index waypoint-index})
(defn behavior-chase [target-entity] {:type :chase :target-entity target-entity})
(defn behavior-talk [partner-entity] {:type :talk :partner-entity partner-entity})

;; ---------------------------------------------------------------------------
;; Brainrot NPC behaviors
;; ---------------------------------------------------------------------------

(def skibidi-phases #{:rise :hold :drop :wait})

(def default-brainrot-update
  {:dx 0.0 :dy 0.0 :dz 0.0 :yaw 0.0 :pitch 0.0 :scale 0.0
   :teleport nil :spawn-puddle nil :spawn-damage-cubes false
   :steal-item false :charm-active false})

;; --- Skibidi: rises up, holds, drops, waits. Head yaw oscillation while up. ---

(defn skibidi-new [] {:phase :rise :timer 0.0})

(defn- skibidi-phase-duration [phase]
  (case phase :rise 1.0 :hold 0.5 :drop 0.5 :wait 2.0))

(defn- skibidi-next-phase [phase]
  (case phase :rise :hold :hold :drop :drop :wait :wait :rise))

(defn skibidi-tick
  "Returns [behavior' update]."
  [s dt]
  (let [timer' (+ (:timer s) dt)
        dur (skibidi-phase-duration (:phase s))
        [timer'' phase'] (if (>= timer' dur)
                            [(- timer' dur) (skibidi-next-phase (:phase s))]
                            [timer' (:phase s)])
        u (assoc default-brainrot-update :scale 1.0)
        u (case phase'
            :rise (assoc u :dy (* 2.0 dt) :yaw (* (sin (* timer'' 20.0)) 1.5))
            :hold (assoc u :yaw (* (sin (* timer'' 20.0)) 1.5))
            :drop (assoc u :dy (* -4.0 dt))
            :wait u)]
    [{:phase phase' :timer timer''} u]))

;; --- Grimace: slow pursuit + puddle spawning + wobble scale. ---

(defn grimace-new [] {:puddle-timer 0.0 :wobble-phase 0.0})

(defn grimace-tick
  "Returns [behavior' update]."
  [g dt my-pos target-pos]
  (let [speed 0.3
        dir (v-normalize-or-zero (v- target-pos my-pos))
        vel (v-scale dir (* speed dt))
        puddle-timer' (+ (:puddle-timer g) dt)
        [puddle-timer'' spawn] (if (>= puddle-timer' 5.0)
                                  [(- puddle-timer' 5.0) my-pos]
                                  [puddle-timer' nil])
        wobble-phase' (+ (:wobble-phase g) (* dt 2.0 TAU))
        scale (+ 1.0 (* 0.05 (sin wobble-phase')))]
    [{:puddle-timer puddle-timer'' :wobble-phase wobble-phase'}
     (assoc default-brainrot-update
            :dx (vel 0) :dy (vel 1) :dz (vel 2)
            :scale scale :spawn-puddle spawn)]))

;; --- Sigma: stands still. Nods when player within 5m. ---

(def sigma-states #{:idle :nodding})

(defn sigma-new [] {:state :idle :nod-timer 0.0})

(defn sigma-tick
  "Returns [behavior' update]."
  [s dt _my-pos nearest-player-dist]
  (let [u (assoc default-brainrot-update :scale 1.0)]
    (case (:state s)
      :idle
      (if (< nearest-player-dist 5.0)
        [{:state :nodding :nod-timer 0.0} u]
        [s u])

      :nodding
      (let [nod-timer' (+ (:nod-timer s) dt)
            nod-duration 0.5]
        (cond
          (< nod-timer' (* nod-duration 0.5))
          [{:state :nodding :nod-timer nod-timer'}
           (assoc u :pitch (* (- (to-radians 15.0)) 2.0 dt (/ 1.0 nod-duration)))]

          (< nod-timer' nod-duration)
          [{:state :nodding :nod-timer nod-timer'}
           (assoc u :pitch (* (to-radians 15.0) 2.0 dt (/ 1.0 nod-duration)))]

          :else
          [{:state :idle :nod-timer 0.0} u])))))

;; --- Ohio Boss: teleports every 3s, slow rotation, spawns damage cubes near player. ---

(defn ohio-boss-new [seed] {:teleport-timer 0.0 :rng (rng-new seed)})

(defn ohio-boss-tick
  "Returns [behavior' update]."
  [o dt my-pos nearest-player-dist]
  (let [teleport-timer' (+ (:teleport-timer o) dt)
        u (assoc default-brainrot-update :scale 1.0 :yaw (* 2.0 dt))]
    (if (>= teleport-timer' 3.0)
      (let [[rng1 a] (rng-next-f32 (:rng o))
            [rng2 r] (rng-next-f32 rng1)
            angle (* a TAU)
            radius (* r 20.0)
            tx (+ (my-pos 0) (* (cos angle) radius))
            tz (+ (my-pos 2) (* (sin angle) radius))
            u' (assoc u :teleport [tx (my-pos 1) tz]
                      :spawn-damage-cubes (< nearest-player-dist 10.0))]
        [{:teleport-timer (- teleport-timer' 3.0) :rng rng2} u'])
      [{:teleport-timer teleport-timer' :rng (:rng o)}
       (assoc u :spawn-damage-cubes (< nearest-player-dist 10.0))])))

;; --- Fanum: patrols food stalls, steals nearby player items with cooldown. ---

(defn fanum-new [waypoints] {:waypoint-index 0 :waypoints waypoints :steal-cooldown 0.0})

(defn fanum-tick
  "Returns [behavior' update]."
  [f dt my-pos nearby-item?]
  (let [steal-cooldown' (max 0.0 (- (:steal-cooldown f) dt))
        [steal? steal-cooldown''] (if (and nearby-item? (<= steal-cooldown' 0.0))
                                     [true 3.0]
                                     [false steal-cooldown'])
        u (assoc default-brainrot-update :scale 1.0 :steal-item steal?)
        waypoints (:waypoints f)]
    (if (empty? waypoints)
      [{:waypoint-index (:waypoint-index f) :waypoints waypoints :steal-cooldown steal-cooldown''} u]
      (let [target (nth waypoints (:waypoint-index f))
            dir (v- target my-pos)
            idx' (if (< (v-length dir) 0.5)
                   (mod (inc (:waypoint-index f)) (count waypoints))
                   (:waypoint-index f))
            vel (v-scale (v-normalize-or-zero dir) (* 1.0 dt))]
        [{:waypoint-index idx' :waypoints waypoints :steal-cooldown steal-cooldown''}
         (assoc u :dx (vel 0) :dy (vel 1) :dz (vel 2))]))))

;; --- Rizz: approach player, charm, walk away, repeat. ---

(def rizz-phases #{:approach :charm :walk-away})

(defn rizz-new [seed] {:phase :approach :timer 0.0 :walkaway-target vec3-zero :rng (rng-new seed)})

(defn rizz-tick
  "Returns [behavior' update]."
  [r dt my-pos nearest-player-pos]
  (let [u (assoc default-brainrot-update :scale 1.0)
        dist (v-distance my-pos nearest-player-pos)]
    (case (:phase r)
      :approach
      (if (<= dist 3.0)
        [(assoc r :phase :charm :timer 0.0) u]
        (let [dir (v-normalize-or-zero (v- nearest-player-pos my-pos))
              vel (v-scale dir (* 0.5 dt))]
          [r (assoc u :dx (vel 0) :dy (vel 1) :dz (vel 2))]))

      :charm
      (let [timer' (+ (:timer r) dt)
            u' (assoc u :pitch (- (to-radians 10.0)) :charm-active true)]
        (if (>= timer' 2.0)
          (let [[rng1 a] (rng-next-f32 (:rng r))
                [rng2 rr] (rng-next-f32 rng1)
                angle (* a TAU)
                rad (* rr 10.0)
                target [(+ (my-pos 0) (* (cos angle) rad)) (my-pos 1) (+ (my-pos 2) (* (sin angle) rad))]]
            [(assoc r :phase :walk-away :timer 0.0 :walkaway-target target :rng rng2) u'])
          [(assoc r :timer timer') u']))

      :walk-away
      (let [dir (v-normalize-or-zero (v- (:walkaway-target r) my-pos))
            vel (v-scale dir (* 0.5 dt))
            u' (assoc u :dx (vel 0) :dy (vel 1) :dz (vel 2))]
        (if (< (v-distance my-pos (:walkaway-target r)) 0.5)
          [(assoc r :phase :approach :timer 0.0) u']
          [r u'])))))

;; ---------------------------------------------------------------------------
;; Npc component + behavior tree tick
;; ---------------------------------------------------------------------------

(defn npc-new
  [name waypoints]
  {:name name
   :behavior (behavior-patrol 0)
   :waypoints waypoints
   :patrol-speed 2.0
   :detection-radius 8.0
   :talk-radius 3.0
   :dialogue-cooldown 10.0
   :cooldown-timer 0.0})

(defn npc-action-move [v] {:type :move :vec v})
(defn npc-action-talk [npc-name partner] {:type :talk :npc-name npc-name :partner partner})

(defn- nearest-player [my-pos players detection-radius]
  (->> players
       (map (fn [[id p]] [id (v-distance my-pos p)]))
       (filter (fn [[_ d]] (< d detection-radius)))
       (reduce (fn [best cur] (if (or (nil? best) (< (second cur) (second best))) cur best)) nil)))

(defn npc-tick
  "Tick the NPC behavior tree. Returns [npc' action]."
  [npc my-pos players dt]
  (let [cooldown-timer' (max 0.0 (- (:cooldown-timer npc) dt))
        npc (assoc npc :cooldown-timer cooldown-timer')
        nearest (nearest-player my-pos players (:detection-radius npc))]
    (cond
      ;; Close enough to talk
      (and nearest (< (second nearest) (:talk-radius npc)) (<= (:cooldown-timer npc) 0.0))
      (let [player-id (first nearest)]
        [(assoc npc :behavior (behavior-talk player-id) :cooldown-timer (:dialogue-cooldown npc))
         (npc-action-talk (:name npc) player-id)])

      ;; Player detected -> chase
      nearest
      (let [player-id (first nearest)
            target-pos (second (first (filter (fn [[id _]] (= id player-id)) players)))
            dir (v-normalize-or-zero (v- target-pos my-pos))]
        [(assoc npc :behavior (behavior-chase player-id))
         (npc-action-move (v-scale dir (:patrol-speed npc)))])

      ;; No player nearby -> patrol
      (= (:type (:behavior npc)) :patrol)
      (if (empty? (:waypoints npc))
        [npc (npc-action-move vec3-zero)]
        (let [wi (:waypoint-index (:behavior npc))
              target (nth (:waypoints npc) wi)
              dir (v- target my-pos)
              npc' (if (< (v-length dir) 0.5)
                     (assoc npc :behavior (behavior-patrol (mod (inc wi) (count (:waypoints npc)))))
                     npc)]
          [npc' (npc-action-move (v-scale (v-normalize-or-zero dir) (:patrol-speed npc)))]))

      ;; Default: return to patrol
      :else
      [(assoc npc :behavior (behavior-patrol 0)) (npc-action-move vec3-zero)])))

;; ---------------------------------------------------------------------------
;; LLM dialogue stub
;; ---------------------------------------------------------------------------

(defn generate-dialogue
  "LLM dialogue stub. In production -> murakumo.etzhayyim.com API."
  [npc-name _player-name]
  (case npc-name
    "Guard" "Halt! Who goes there? This island is protected by the KAMI World Council."
    "Merchant" "Welcome, traveler! I have rare gems and artifacts from distant islands."
    (str npc-name ": Greetings, adventurer!")))
