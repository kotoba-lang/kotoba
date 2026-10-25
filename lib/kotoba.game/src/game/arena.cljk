(ns game.arena
  "Arena: physics-based action game prototype.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/arena.rs`.
  Floor + walls + ramps + dynamic cubes + player WASD + projectiles +
  NPC enemies + score.

  Cross-cluster note: the original Rust depends on `crate::physics::
  PhysicsWorld` and `crate::scene::{ComponentDef, EntityDef, IslandScene,
  MeshRef}` (physics.rs / scene.rs are not part of this cluster). This
  namespace has zero hard deps, so `IslandScene` / `EntityDef` /
  `ComponentDef` / `MeshRef` are duck-typed here as plain CLJC maps with
  the same field shape scene.rs uses; the final assembly pass may
  reconcile these against the real `game.scene` namespace once it lands.
  `Vec3` is a plain 3-vector `[x y z]`.")

;; -----------------------------------------------------------------------
;; Local Vec3 math.
;; -----------------------------------------------------------------------

(defn- v3-add [[x1 y1 z1] [x2 y2 z2]] [(+ x1 x2) (+ y1 y2) (+ z1 z2)])
(defn- v3-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn- v3-length [[x y z]] (Math/sqrt (+ (* x x) (* y y) (* z z))))
(defn- v3-normalize-or-zero [[x y z :as v]]
  (let [len (v3-length v)]
    (if (zero? len) [0.0 0.0 0.0] [(/ x len) (/ y len) (/ z len)])))

;; -----------------------------------------------------------------------
;; Duck-typed ComponentDef variants (mirroring scene.rs's shape).
;; -----------------------------------------------------------------------

(defn component-physics [dynamic?] {:type :physics :dynamic? dynamic?})
(defn component-player-spawn [] {:type :player-spawn})
(defn component-npc [name waypoints] {:type :npc :name name :waypoints waypoints})
(defn component-item [item-id item-name] {:type :item :item-id item-id :item-name item-name})
(defn component-portal [target-island] {:type :portal :target-island target-island})

(defn- entity
  "Build an EntityDef (duck-typed scene.rs shape) for a cube-mesh entity."
  [id pos scale color components]
  {:id id
   :position pos
   :rotation [0.0 0.0 0.0 1.0]
   :scale scale
   :mesh {:type :cube :color color}
   :components components
   :layer nil})

(defn arena-island
  "Create the Arena Island scene definition (duck-typed IslandScene map)."
  []
  {:context nil
   :ld-type nil
   :ld-id nil
   :name "Battle Arena"
   :genre nil
   :description nil
   :max-players nil
   :characters []
   :ambient-color [0.02 0.02 0.04]
   :sun-direction [-0.5 -3.0 -1.0]
   :sun-intensity 4.0
   :camera-mode nil
   :layers []
   :viewport nil
   :sun-color nil
   :point-lights []
   :atmosphere nil
   :postfx-preset nil
   :ibl-env-map nil
   :shadow nil
   :entities
   [;; Floor
    (entity "floor" [0.0 -0.5 0.0] [60.0 1.0 60.0] [0.3 0.3 0.35 1.0] [])
    ;; Walls (4 sides)
    (entity "wall-n" [0.0 2.0 -30.0] [60.0 4.0 1.0] [0.4 0.4 0.45 1.0] [])
    (entity "wall-s" [0.0 2.0 30.0] [60.0 4.0 1.0] [0.4 0.4 0.45 1.0] [])
    (entity "wall-e" [30.0 2.0 0.0] [1.0 4.0 60.0] [0.4 0.4 0.45 1.0] [])
    (entity "wall-w" [-30.0 2.0 0.0] [1.0 4.0 60.0] [0.4 0.4 0.45 1.0] [])
    ;; Ramps
    (entity "ramp-1" [10.0 1.0 10.0] [6.0 0.3 3.0] [0.5 0.4 0.3 1.0]
            [(component-physics false)])
    (entity "ramp-2" [-10.0 1.5 -8.0] [4.0 0.3 6.0] [0.5 0.4 0.3 1.0]
            [(component-physics false)])
    ;; Cover blocks (dynamic — can be pushed)
    (entity "cover-1" [5.0 0.5 -5.0] [2.0 1.0 2.0] [0.6 0.5 0.4 1.0]
            [(component-physics true)])
    (entity "cover-2" [-8.0 0.5 3.0] [1.5 1.5 1.5] [0.6 0.5 0.4 1.0]
            [(component-physics true)])
    (entity "cover-3" [0.0 0.5 12.0] [3.0 0.8 1.0] [0.6 0.5 0.4 1.0]
            [(component-physics true)])
    ;; Player spawns
    (entity "spawn-0" [-5.0 1.0 -5.0] [0.8 1.6 0.8] [0.2 0.7 1.0 1.0]
            [(component-player-spawn) (component-physics true)])
    (entity "spawn-1" [5.0 1.0 5.0] [0.8 1.6 0.8] [1.0 0.4 0.2 1.0]
            [(component-player-spawn) (component-physics true)])
    ;; NPC enemies
    (entity "enemy-1" [15.0 0.8 0.0] [1.0 1.6 1.0] [0.9 0.1 0.1 1.0]
            [(component-npc "Sentinel" [[15.0 0.8 -10.0] [15.0 0.8 10.0]])])
    (entity "enemy-2" [-15.0 0.8 5.0] [1.0 1.6 1.0] [0.9 0.1 0.1 1.0]
            [(component-npc "Hunter" [[-15.0 0.8 5.0] [-5.0 0.8 -10.0] [10.0 0.8 8.0]])])
    (entity "enemy-3" [0.0 0.8 -20.0] [1.2 2.0 1.2] [1.0 0.0 0.0 1.0]
            [(component-npc "Boss" [[0.0 0.8 -20.0] [0.0 0.8 -10.0]])])
    ;; Items: health + ammo + gems
    (entity "hp-1" [8.0 0.3 -12.0] [0.4 0.6 0.4] [1.0 0.2 0.3 1.0]
            [(component-item "potion-hp" "Health Potion")])
    (entity "hp-2" [-12.0 0.3 8.0] [0.4 0.6 0.4] [1.0 0.2 0.3 1.0]
            [(component-item "potion-hp" "Health Potion")])
    (entity "ammo-1" [0.0 0.3 0.0] [0.3 0.3 0.6] [0.8 0.8 0.2 1.0]
            [(component-item "ammo-box" "Ammo Box")])
    (entity "gem-1" [20.0 0.3 20.0] [0.5 0.5 0.5] [0.0 0.7 1.0 1.0]
            [(component-item "gem-blue" "Blue Gem")])
    (entity "gem-2" [-20.0 0.3 -20.0] [0.5 0.5 0.5] [1.0 0.5 0.0 1.0]
            [(component-item "gem-gold" "Gold Gem")])
    ;; Portal back to hub
    (entity "portal-hub" [0.0 1.5 -28.0] [3.0 3.0 0.5] [0.5 0.0 1.0 0.8]
            [(component-portal "hub")])
    ;; Pillars (decoration + cover)
    (entity "pillar-1" [12.0 1.5 -12.0] [1.0 3.0 1.0] [0.5 0.5 0.55 1.0] [])
    (entity "pillar-2" [-12.0 1.5 12.0] [1.0 3.0 1.0] [0.5 0.5 0.55 1.0] [])
    (entity "pillar-3" [20.0 1.5 0.0] [1.0 3.0 1.0] [0.5 0.5 0.55 1.0] [])
    (entity "pillar-4" [-20.0 1.5 0.0] [1.0 3.0 1.0] [0.5 0.5 0.55 1.0] [])]})

;; -----------------------------------------------------------------------
;; Projectile: {:position :velocity :damage :lifetime :owner-id}
;; -----------------------------------------------------------------------

(defn projectile-new
  [origin direction speed damage owner-id]
  {:position origin
   :velocity (v3-scale (v3-normalize-or-zero direction) speed)
   :damage damage
   :lifetime 3.0
   :owner-id owner-id})

(defn projectile-tick
  "Advance projectile by `dt`. Returns [alive? projectile']."
  [proj dt]
  (let [proj' (-> proj
                   (update :position v3-add (v3-scale (:velocity proj) dt))
                   (update :lifetime - dt))]
    [(> (:lifetime proj') 0.0) proj']))

;; -----------------------------------------------------------------------
;; ScoreBoard: {:scores [[client-id PlayerScore] ...]}
;; PlayerScore: {:kills :deaths :gems :damage-dealt}
;; -----------------------------------------------------------------------

(defn scoreboard-new [] {:scores []})

(def ^:private player-score-default {:kills 0 :deaths 0 :gems 0 :damage-dealt 0})

(defn- score-index [sb client-id]
  (some (fn [[i [id _]]] (when (= id client-id) i))
        (map-indexed vector (:scores sb))))

(defn- ensure-player
  "Ensure `client-id` has a score entry. Returns sb'."
  [sb client-id]
  (if (score-index sb client-id)
    sb
    (update sb :scores conj [client-id player-score-default])))

(defn- update-score [sb client-id f]
  (let [sb (ensure-player sb client-id)
        idx (score-index sb client-id)]
    (update-in sb [:scores idx 1] f)))

(defn add-kill [sb client-id] (update-score sb client-id #(update % :kills inc)))
(defn add-death [sb client-id] (update-score sb client-id #(update % :deaths inc)))
(defn add-gem [sb client-id] (update-score sb client-id #(update % :gems inc)))
(defn add-damage [sb client-id amount] (update-score sb client-id #(update % :damage-dealt + amount)))

(defn leaderboard
  "Get sorted leaderboard (by kills desc)."
  [sb]
  (vec (sort-by (comp - :kills second) (:scores sb))))
