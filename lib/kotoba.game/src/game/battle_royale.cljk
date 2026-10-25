(ns game.battle-royale
  "Battle Royale: Fortnite-style 100-player last-one-standing with storm, loot,
  building.

  Restored from kami-game's `battle_royale.rs` (kotoba-lang/kami-engine, Rust
  workspace deleted in PR #82; recoverable at commit
  a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa) as zero-dependency portable CLJC
  per ADR-2607010930.

  Server-authoritative match simulation. Storm circle shrinks over phases.
  Players loot weapons/shields/materials, build structures, and fight to be #1.
  Structs become plain maps with keyword keys; `&mut self` methods become pure
  functions returning updated state; `Vec3` becomes a 3-vector `[x y z]` with
  local vec math (no external glam dependency).

  Cross-cluster note: the original Rust depended on `crate::inventory`
  (`ItemType`, `Rarity`), `crate::scene` (`IslandScene`/`EntityDef`/`MeshRef`/
  `ComponentDef`), and `crate::island_gen::brainrot_characters`, all owned by
  other restoration clusters. To avoid blocking on those, this namespace
  inlines minimal duck-typed local shapes for `Rarity` (a keyword set) and for
  scene/entity maps (plain EDN maps matching the shape those other clusters'
  `.cljc` ports are expected to produce), documented inline below.")

;; ── Local duck-typed shapes (cross-cluster boundary) ─────────────────────
;; `Rarity` is normally owned by the `inventory` cluster; inlined here as a
;; keyword set since only comparison/embedding is needed, not its behavior.
(def rarity-values
  #{:common :uncommon :rare :epic :legendary})

;; ── Vec3 helpers (glam::Vec3 replacement) ─────────────────────────────────

(defn v3 [x y z] [(double x) (double y) (double z)])
(def v3-zero [0.0 0.0 0.0])

(defn v3-add [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v3-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v3-scale [[x y z] s] [(* x s) (* y s) (* z s)])

(defn v3-lerp
  "Linear interpolation from `a` to `b` by `t`, matching glam's `Vec3::lerp`."
  [a b t]
  (v3-add a (v3-scale (v3-sub b a) t)))

(defn v3-distance
  [[ax ay az] [bx by bz]]
  (let [dx (- ax bx) dy (- ay by) dz (- az bz)]
    (Math/sqrt (+ (* dx dx) (* dy dy) (* dz dz)))))

;; Rust's original storm timing used f32 accumulation, which (unlike f64/JS
;; doubles) tends to round *up* across thousands of dt additions and so
;; reliably crosses `wait_seconds`/`shrink_seconds` thresholds. Double
;; precision accumulation instead rounds slightly under after many additions
;; (e.g. summing 7200x 1/60.0 == 119.99999999999447, not 120.0). A tiny
;; epsilon keeps phase transitions behaviorally identical across f32/f64/JS
;; number platforms without changing the observable timing by more than a
;; fraction of a tick.
(def ^:private TIMER-EPSILON 1e-6)

;; ── Constants ──────────────────────────────────────────────────────────

(def MAX-PLAYERS 100)
(def MATCH-TICK-RATE 60)
(def MAP-SIZE 2000.0) ; 2km x 2km
(def BUS-ALTITUDE 200.0)
(def BUS-SPEED 80.0)
(def GLIDE-SPEED 30.0)
(def DEPLOY-ALTITUDE 50.0)
(def DBNO-DURATION 30.0)
(def DBNO-BLEED-DPS 3.33)

;; ── Match Phases ───────────────────────────────────────────────────────

(def match-phase-values
  "Ordered match phases. Order matters only for readability here (not used
  for comparison, unlike Rust's plain enum equality)."
  [:warmup :battle-bus :early-game :mid-game :end-game :victory])

;; ── Storm Circle ───────────────────────────────────────────────────────

(defn default-storm-phases
  "Storm circle configuration per phase."
  []
  [{:phase-index 0 :wait-seconds 120.0 :shrink-seconds 90.0 :end-radius 700.0 :damage-per-second 1.0}
   {:phase-index 1 :wait-seconds 90.0 :shrink-seconds 75.0 :end-radius 450.0 :damage-per-second 2.0}
   {:phase-index 2 :wait-seconds 75.0 :shrink-seconds 60.0 :end-radius 280.0 :damage-per-second 5.0}
   {:phase-index 3 :wait-seconds 60.0 :shrink-seconds 45.0 :end-radius 150.0 :damage-per-second 8.0}
   {:phase-index 4 :wait-seconds 45.0 :shrink-seconds 30.0 :end-radius 70.0 :damage-per-second 10.0}
   {:phase-index 5 :wait-seconds 30.0 :shrink-seconds 20.0 :end-radius 25.0 :damage-per-second 15.0}
   {:phase-index 6 :wait-seconds 20.0 :shrink-seconds 15.0 :end-radius 5.0 :damage-per-second 20.0}
   {:phase-index 7 :wait-seconds 15.0 :shrink-seconds 10.0 :end-radius 0.0 :damage-per-second 25.0}])

(defn new-storm-circle
  [map-center]
  {:current-center map-center
   :current-radius (* MAP-SIZE 0.5)
   :target-center map-center
   :target-radius (* MAP-SIZE 0.5)
   :phase-index 0
   :phase-timer 0.0
   :shrinking false
   :damage-per-second 1.0
   :phases (default-storm-phases)})

(defn storm-tick
  "Advance storm by dt seconds. Returns [storm' phase-changed?]."
  [storm dt]
  (let [phases (:phases storm)
        pi (:phase-index storm)]
    (if (>= pi (count phases))
      [storm false]
      (let [cfg (nth phases pi)
            storm (update storm :phase-timer + dt)]
        (if-not (:shrinking storm)
          ;; Waiting phase
          (if (>= (+ (:phase-timer storm) TIMER-EPSILON) (:wait-seconds cfg))
            (let [offset-scale (* (:end-radius cfg) 0.3)
                  angle (* pi 1.618 (* 2.0 Math/PI)) ; TAU
                  cc (:current-center storm)
                  target-center (v3 (+ (nth cc 0) (* offset-scale (Math/cos angle)))
                                     0.0
                                     (+ (nth cc 2) (* offset-scale (Math/sin angle))))]
              [(assoc storm
                      :shrinking true
                      :phase-timer 0.0
                      :target-radius (:end-radius cfg)
                      :target-center target-center
                      :damage-per-second (:damage-per-second cfg))
               false])
            [storm false])
          ;; Shrinking phase
          (let [t (min 1.0 (/ (:phase-timer storm) (:shrink-seconds cfg)))
                start-radius (if (pos? pi)
                               (:end-radius (nth phases (dec pi)))
                               (* MAP-SIZE 0.5))
                current-radius (+ start-radius (* (- (:target-radius storm) start-radius) t))
                current-center (v3-lerp (:current-center storm) (:target-center storm) (* t dt 0.1))
                storm (assoc storm :current-radius current-radius :current-center current-center)]
            (if (>= (+ (:phase-timer storm) TIMER-EPSILON) (:shrink-seconds cfg))
              (let [next-pi (inc pi)
                    storm (assoc storm
                                 :current-radius (:target-radius storm)
                                 :current-center (:target-center storm)
                                 :phase-index next-pi
                                 :phase-timer 0.0
                                 :shrinking false)
                    storm (if (< next-pi (count phases))
                            (assoc storm :damage-per-second (:damage-per-second (nth phases next-pi)))
                            storm)]
                [storm true])
              [storm false])))))))

(defn storm-inside?
  "Check if a position is inside the safe zone."
  [storm pos]
  (let [[px _ pz] pos
        [cx _ cz] (:current-center storm)
        dx (- px cx) dz (- pz cz)]
    (<= (Math/sqrt (+ (* dx dx) (* dz dz))) (:current-radius storm))))

(defn storm-damage-at
  "Get storm damage at a position (0 if inside safe zone)."
  [storm pos]
  (if (storm-inside? storm pos) 0.0 (:damage-per-second storm)))

(defn storm-distance-to-edge
  "Distance from position to safe zone edge (negative = inside)."
  [storm pos]
  (let [[px _ pz] pos
        [cx _ cz] (:current-center storm)
        dx (- px cx) dz (- pz cz)]
    (- (Math/sqrt (+ (* dx dx) (* dz dz))) (:current-radius storm))))

;; ── Weapons ────────────────────────────────────────────────────────────

(def weapon-type-values
  #{:assault-rifle :shotgun :smg :sniper-rifle :pistol :rocket-launcher :grenade-launcher})

(defn weapon-pool
  "Static pool of weapon definitions."
  []
  [;; Assault Rifles
   {:weapon-type :assault-rifle :name "Assault Rifle" :rarity :common :damage 30
    :headshot-multiplier 1.5 :fire-rate 5.5 :magazine-size 30 :reload-time 2.3
    :spread 2.5 :damage-falloff 50.0 :range 200.0 :projectile-speed 500.0}
   {:weapon-type :assault-rifle :name "Assault Rifle" :rarity :uncommon :damage 31
    :headshot-multiplier 1.5 :fire-rate 5.5 :magazine-size 30 :reload-time 2.2
    :spread 2.3 :damage-falloff 55.0 :range 200.0 :projectile-speed 500.0}
   {:weapon-type :assault-rifle :name "Assault Rifle" :rarity :rare :damage 33
    :headshot-multiplier 1.5 :fire-rate 5.5 :magazine-size 30 :reload-time 2.1
    :spread 2.0 :damage-falloff 60.0 :range 200.0 :projectile-speed 500.0}
   {:weapon-type :assault-rifle :name "SCAR" :rarity :epic :damage 35
    :headshot-multiplier 1.5 :fire-rate 5.5 :magazine-size 30 :reload-time 2.0
    :spread 1.5 :damage-falloff 65.0 :range 200.0 :projectile-speed 500.0}
   {:weapon-type :assault-rifle :name "SCAR" :rarity :legendary :damage 36
    :headshot-multiplier 1.5 :fire-rate 5.5 :magazine-size 30 :reload-time 2.0
    :spread 1.2 :damage-falloff 70.0 :range 200.0 :projectile-speed 500.0}
   ;; Shotguns
   {:weapon-type :shotgun :name "Pump Shotgun" :rarity :common :damage 80
    :headshot-multiplier 2.0 :fire-rate 0.7 :magazine-size 5 :reload-time 4.5
    :spread 6.0 :damage-falloff 10.0 :range 30.0 :projectile-speed 400.0}
   {:weapon-type :shotgun :name "Pump Shotgun" :rarity :uncommon :damage 85
    :headshot-multiplier 2.0 :fire-rate 0.7 :magazine-size 5 :reload-time 4.3
    :spread 5.5 :damage-falloff 12.0 :range 30.0 :projectile-speed 400.0}
   {:weapon-type :shotgun :name "Pump Shotgun" :rarity :rare :damage 90
    :headshot-multiplier 2.0 :fire-rate 0.7 :magazine-size 5 :reload-time 4.0
    :spread 5.0 :damage-falloff 14.0 :range 30.0 :projectile-speed 400.0}
   {:weapon-type :shotgun :name "Spaz-12" :rarity :epic :damage 100
    :headshot-multiplier 2.0 :fire-rate 0.7 :magazine-size 5 :reload-time 3.8
    :spread 4.5 :damage-falloff 15.0 :range 30.0 :projectile-speed 400.0}
   {:weapon-type :shotgun :name "Spaz-12" :rarity :legendary :damage 110
    :headshot-multiplier 2.0 :fire-rate 0.7 :magazine-size 5 :reload-time 3.5
    :spread 4.0 :damage-falloff 16.0 :range 30.0 :projectile-speed 400.0}
   ;; SMGs
   {:weapon-type :smg :name "SMG" :rarity :common :damage 17
    :headshot-multiplier 1.5 :fire-rate 12.0 :magazine-size 30 :reload-time 2.0
    :spread 3.5 :damage-falloff 25.0 :range 100.0 :projectile-speed 450.0}
   {:weapon-type :smg :name "SMG" :rarity :uncommon :damage 18
    :headshot-multiplier 1.5 :fire-rate 12.0 :magazine-size 30 :reload-time 1.9
    :spread 3.2 :damage-falloff 28.0 :range 100.0 :projectile-speed 450.0}
   {:weapon-type :smg :name "Rapid Fire SMG" :rarity :rare :damage 15
    :headshot-multiplier 1.5 :fire-rate 15.0 :magazine-size 26 :reload-time 1.7
    :spread 4.0 :damage-falloff 22.0 :range 80.0 :projectile-speed 450.0}
   ;; Snipers
   {:weapon-type :sniper-rifle :name "Bolt-Action Sniper" :rarity :rare :damage 105
    :headshot-multiplier 2.5 :fire-rate 0.33 :magazine-size 1 :reload-time 3.0
    :spread 0.0 :damage-falloff 200.0 :range 500.0 :projectile-speed 800.0}
   {:weapon-type :sniper-rifle :name "Heavy Sniper" :rarity :epic :damage 132
    :headshot-multiplier 2.5 :fire-rate 0.25 :magazine-size 1 :reload-time 4.0
    :spread 0.0 :damage-falloff 250.0 :range 500.0 :projectile-speed 900.0}
   {:weapon-type :sniper-rifle :name "Heavy Sniper" :rarity :legendary :damage 150
    :headshot-multiplier 2.5 :fire-rate 0.25 :magazine-size 1 :reload-time 4.0
    :spread 0.0 :damage-falloff 250.0 :range 500.0 :projectile-speed 900.0}
   ;; Pistols
   {:weapon-type :pistol :name "Pistol" :rarity :common :damage 24
    :headshot-multiplier 1.5 :fire-rate 6.75 :magazine-size 16 :reload-time 1.3
    :spread 3.0 :damage-falloff 30.0 :range 100.0 :projectile-speed 400.0}
   {:weapon-type :pistol :name "Pistol" :rarity :uncommon :damage 25
    :headshot-multiplier 1.5 :fire-rate 6.75 :magazine-size 16 :reload-time 1.2
    :spread 2.8 :damage-falloff 35.0 :range 100.0 :projectile-speed 400.0}
   ;; Explosives
   {:weapon-type :rocket-launcher :name "Rocket Launcher" :rarity :epic :damage 110
    :headshot-multiplier 1.0 :fire-rate 0.75 :magazine-size 1 :reload-time 3.0
    :spread 0.0 :damage-falloff 0.0 :range 300.0 :projectile-speed 100.0}
   {:weapon-type :rocket-launcher :name "Rocket Launcher" :rarity :legendary :damage 121
    :headshot-multiplier 1.0 :fire-rate 0.75 :magazine-size 1 :reload-time 2.8
    :spread 0.0 :damage-falloff 0.0 :range 300.0 :projectile-speed 100.0}
   ;; Brainrot weapons
   {:weapon-type :rocket-launcher :name "Skibidi Launcher" :rarity :epic :damage 125
    :headshot-multiplier 1.0 :fire-rate 0.6 :magazine-size 1 :reload-time 3.5
    :spread 0.0 :damage-falloff 0.0 :range 250.0 :projectile-speed 90.0}
   {:weapon-type :assault-rifle :name "Ohio Anomaly Rifle" :rarity :legendary :damage 38
    :headshot-multiplier 2.0 :fire-rate 6.0 :magazine-size 25 :reload-time 1.8
    :spread 1.0 :damage-falloff 80.0 :range 250.0 :projectile-speed 550.0}
   {:weapon-type :sniper-rifle :name "Sigma Sniper" :rarity :legendary :damage 165
    :headshot-multiplier 3.0 :fire-rate 0.2 :magazine-size 1 :reload-time 4.5
    :spread 0.0 :damage-falloff 300.0 :range 600.0 :projectile-speed 1000.0}
   {:weapon-type :pistol :name "Rizz Pistol" :rarity :epic :damage 30
    :headshot-multiplier 1.5 :fire-rate 8.0 :magazine-size 12 :reload-time 1.0
    :spread 2.0 :damage-falloff 40.0 :range 120.0 :projectile-speed 450.0}
   {:weapon-type :shotgun :name "Fanum Shotgun" :rarity :legendary :damage 120
    :headshot-multiplier 2.0 :fire-rate 0.8 :magazine-size 6 :reload-time 3.0
    :spread 3.5 :damage-falloff 18.0 :range 35.0 :projectile-speed 420.0}])

;; ── Consumables ────────────────────────────────────────────────────────

(def consumable-type-values
  #{:small-shield :large-shield :mini-hp :medkit :chug :small-fry :flopper
    :shield-fish :grimace-shake :gyatt-energy :ohio-milk})

(defn consumable-pool
  []
  [{:consumable-type :small-shield :name "Mini Shield" :rarity :common :use-time 2.0
    :hp-restore 0 :shield-restore 25 :hp-cap 100 :shield-cap 50 :stack-size 6}
   {:consumable-type :large-shield :name "Shield Potion" :rarity :uncommon :use-time 5.0
    :hp-restore 0 :shield-restore 50 :hp-cap 100 :shield-cap 100 :stack-size 2}
   {:consumable-type :mini-hp :name "Bandage" :rarity :common :use-time 3.5
    :hp-restore 15 :shield-restore 0 :hp-cap 75 :shield-cap 100 :stack-size 15}
   {:consumable-type :medkit :name "Med Kit" :rarity :uncommon :use-time 10.0
    :hp-restore 100 :shield-restore 0 :hp-cap 100 :shield-cap 100 :stack-size 3}
   {:consumable-type :chug :name "Chug Jug" :rarity :legendary :use-time 15.0
    :hp-restore 100 :shield-restore 100 :hp-cap 100 :shield-cap 100 :stack-size 1}
   {:consumable-type :small-fry :name "Small Fry" :rarity :common :use-time 1.0
    :hp-restore 25 :shield-restore 0 :hp-cap 75 :shield-cap 100 :stack-size 6}
   {:consumable-type :flopper :name "Flopper" :rarity :uncommon :use-time 1.0
    :hp-restore 100 :shield-restore 0 :hp-cap 100 :shield-cap 100 :stack-size 4}
   {:consumable-type :shield-fish :name "Shield Fish" :rarity :rare :use-time 1.0
    :hp-restore 0 :shield-restore 50 :hp-cap 100 :shield-cap 100 :stack-size 3}
   ;; Brainrot consumables
   {:consumable-type :grimace-shake :name "Grimace Shake" :rarity :legendary :use-time 8.0
    :hp-restore 100 :shield-restore 100 :hp-cap 100 :shield-cap 100 :stack-size 1}
   {:consumable-type :gyatt-energy :name "Gyatt Energy" :rarity :rare :use-time 0.5
    :hp-restore 0 :shield-restore 75 :hp-cap 100 :shield-cap 100 :stack-size 3}
   {:consumable-type :ohio-milk :name "Ohio Milk" :rarity :uncommon :use-time 2.0
    :hp-restore 50 :shield-restore 0 :hp-cap 100 :shield-cap 100 :stack-size 5}])

;; ── Building ───────────────────────────────────────────────────────────

(def build-piece-values #{:wall :floor :ramp :roof})
(def material-type-values #{:wood :brick :metal})

(defn material-initial-hp [material]
  (case material :wood 90 :brick 100 :metal 110))

(defn material-max-hp [material]
  (case material :wood 150 :brick 300 :metal 500))

(defn material-build-time [material]
  (case material :wood 4.0 :brick 12.0 :metal 20.0))

(defn material-cost [_material] 10)

(defn new-build-structure
  [id piece material position rotation-y owner-id]
  {:id id
   :piece piece
   :material material
   :position position
   :rotation-y rotation-y
   :current-hp (material-initial-hp material)
   :max-hp (material-max-hp material)
   :building true
   :build-progress 0.0
   :owner-id owner-id})

(defn build-structure-tick-build
  "Advance build. Returns [structure' complete?]."
  [structure dt]
  (if-not (:building structure)
    [structure false]
    (let [material (:material structure)
          max-hp (:max-hp structure)
          init-hp (material-initial-hp material)
          progress-before (:build-progress structure)
          progress-after (+ progress-before (/ dt (material-build-time material)))]
      (if (>= progress-after 1.0)
        [(assoc structure :building false :build-progress 1.0 :current-hp max-hp) true]
        ;; Apply this tick's HP growth as an INCREMENTAL delta on top of the
        ;; structure's actual :current-hp, not an absolute value re-derived
        ;; from :build-progress alone -- the latter silently discards any
        ;; damage build-structure-take-damage already applied, healing the
        ;; structure back to "as if undamaged" on the very next tick.
        ;; :current-hp is kept as an un-truncated double while building (like
        ;; :build-progress itself) so per-tick fractional growth accumulates
        ;; correctly instead of being rounded away before it can add up.
        (let [formula-hp (fn [p] (+ init-hp (* (- max-hp init-hp) p)))
              hp-delta (- (formula-hp progress-after) (formula-hp progress-before))
              current-hp' (min max-hp (+ (:current-hp structure) hp-delta))]
          [(assoc structure :build-progress progress-after :current-hp current-hp') false])))))

(defn build-structure-take-damage
  "Apply damage. Returns [structure' destroyed?]."
  [structure damage]
  (let [new-hp (max 0 (- (:current-hp structure) damage))
        structure (assoc structure :current-hp new-hp)]
    [structure (zero? new-hp)]))

(defn build-structure-dimensions
  [structure]
  (case (:piece structure)
    :wall (v3 5.12 2.8 0.15)
    :floor (v3 5.12 0.15 5.12)
    :ramp (v3 5.12 2.8 5.12)
    :roof (v3 5.12 0.15 5.12)))

;; ── Placement (grid-snap + aim targeting + overlap) ─────────────────────
;; ADR-2607121800 Phase A2: the economy above (piece/material/HP/harvest) was
;; already real and tested; what was missing was the "aim at a spot and place
;; a grid-snapped piece" targeting layer every building game needs on top of
;; it. Pure functions, reusable by any kotoba-lang game, not tied to this
;; namespace's own (unrelated, IP-risky — see PR/commit notes) POI generator.

(def GRID-SIZE
  "Building-grid cell size (world units), matching build-structure-dimensions'
  :wall/:floor footprint (5.12 x 5.12) — pieces tile edge-to-edge with no gap."
  5.12)

(defn snap-to-grid
  "Round a world position to the nearest building-grid cell centre in the XZ
  plane. Y passes through unsnapped — vertical placement (which floor/level)
  is the caller's concern, not this grid's."
  [[x y z]]
  (v3 (* (Math/round (/ x GRID-SIZE)) GRID-SIZE)
      y
      (* (Math/round (/ z GRID-SIZE)) GRID-SIZE)))

(defn placement-candidate
  "The grid-snapped cell one piece-length ahead of `origin`, facing `forward`
  (a normalized [x y z], typically the player's aim/move direction) — the
  standard 'hold a piece up, it snaps to the nearest valid spot' targeting
  every building game uses."
  [origin forward]
  (snap-to-grid (v3-add origin (v3-scale forward GRID-SIZE))))

(defn structures-overlap?
  "Do two positions resolve to the same building-grid cell (XZ)? Both are
  re-snapped here so a caller can pass either an already-snapped or a raw
  position."
  [pos-a pos-b]
  (let [[ax _ az] (snap-to-grid pos-a)
        [bx _ bz] (snap-to-grid pos-b)]
    (and (< (Math/abs (- ax bx)) 0.5) (< (Math/abs (- az bz)) 0.5))))

(defn placement-blocked?
  "Is `candidate` already occupied by an existing structure of the SAME
  piece type? Different piece types are allowed to share a cell (a floor, a
  wall, and a roof legitimately stack on one tile in every building game this
  genre-clones) — only same-on-same (two walls on the same tile) is blocked."
  [structures piece candidate]
  (boolean (some (fn [s] (and (= (:piece s) piece) (structures-overlap? (:position s) candidate)))
                 structures)))

;; ── Player State ───────────────────────────────────────────────────────

(def player-status-values
  #{:in-lobby :on-bus :gliding :alive :dbno :eliminated :spectating :disconnected})

(defn new-br-player
  [client-id did display-name]
  {:client-id client-id
   :did did
   :display-name display-name
   :status :in-lobby
   :position v3-zero
   :rotation-y 0.0
   :hp 100
   :shield 0
   :max-hp 100
   :max-shield 100
   :wood 0
   :brick 0
   :metal 0
   ;; weapon-slots: vector of 5 slots, nil = empty (Rust `[Option<WeaponDef>; 5]`)
   :weapon-slots [nil nil nil nil nil]
   :active-slot 0
   :ammo-light 0
   :ammo-medium 0
   :ammo-heavy 0
   :ammo-shells 0
   :ammo-rockets 0
   :kills 0
   :assists 0
   :damage-dealt 0
   :placement 0
   :dbno-timer 0.0
   :eliminated-by nil
   :bus-jumped false
   :landed false})

(defn br-player-effective-hp [player]
  (+ (:hp player) (:shield player)))

(defn br-player-alive?
  [player]
  (contains? #{:alive :gliding :on-bus} (:status player)))

(defn br-player-take-damage
  "Apply damage (shield first). Returns [player' actual-damage-dealt]."
  [player damage attacker-id]
  (if-not (contains? #{:alive :dbno} (:status player))
    [player 0]
    (let [shield (:shield player)
          hp (:hp player)
          shield-absorbed (min damage shield)
          remaining (- damage shield-absorbed)
          hp-absorbed (min remaining hp)
          total (+ shield-absorbed hp-absorbed)
          player (assoc player :shield (- shield shield-absorbed) :hp (- hp hp-absorbed))
          player (if (zero? (:hp player))
                   (if (contains? #{:alive :dbno} (:status player))
                     (assoc player :status :eliminated :eliminated-by attacker-id)
                     player)
                   player)]
      [player total])))

(defn br-player-heal
  "Heal HP (capped)."
  [player amount cap]
  (update player :hp #(min (+ % amount) cap (:max-hp player))))

(defn br-player-add-shield
  "Add shield (capped)."
  [player amount cap]
  (update player :shield #(min (+ % amount) cap (:max-shield player))))

(defn br-player-harvest
  "Harvest materials from objects."
  [player material amount]
  (let [cap 999]
    (case material
      :wood (update player :wood #(min (+ % amount) cap))
      :brick (update player :brick #(min (+ % amount) cap))
      :metal (update player :metal #(min (+ % amount) cap)))))

(defn br-player-can-build?
  [player material]
  (let [cost (material-cost material)]
    (case material
      :wood (>= (:wood player) cost)
      :brick (>= (:brick player) cost)
      :metal (>= (:metal player) cost))))

(defn br-player-spend-material
  "Returns [player' spent?]."
  [player material]
  (let [cost (material-cost material)
        k material]
    (if (< (get player k) cost)
      [player false]
      [(update player k - cost) true])))

(defn br-player-pick-up-weapon
  "Returns [player' dropped-weapon-or-nil]."
  [player weapon]
  (let [slots (:weapon-slots player)
        empty-idx (first (keep-indexed (fn [i s] (when (nil? s) i)) slots))]
    (if empty-idx
      [(assoc-in player [:weapon-slots empty-idx] weapon) nil]
      (let [idx (:active-slot player)
            dropped (nth slots idx)]
        [(assoc-in player [:weapon-slots idx] weapon) dropped]))))

;; ── Kill Feed ──────────────────────────────────────────────────────────
;; KillFeedEntry is a plain map:
;; {:tick :eliminator-name :eliminator-id :victim-name :victim-id
;;  :weapon-name :headshot :distance}

;; ── Loot Spawn ─────────────────────────────────────────────────────────

(def loot-type-values #{:weapon :consumable :ammo :material})
;; LootSpawn: {:id :position :loot-type :item-data :rarity :picked-up}

;; ── Battle Bus ─────────────────────────────────────────────────────────

(defn new-battle-bus
  [map-seed]
  (let [angle (* (double (mod map-seed 360)) (/ Math/PI 180.0))
        half-map (* MAP-SIZE 0.5)
        start (v3 (* (- half-map) (Math/cos angle)) BUS-ALTITUDE (* (- half-map) (Math/sin angle)))
        end (v3 (* half-map (Math/cos angle)) BUS-ALTITUDE (* half-map (Math/sin angle)))]
    {:start start
     :end end
     :speed BUS-SPEED
     :progress 0.0
     :active true}))

(defn battle-bus-current-position
  [bus]
  (v3-lerp (:start bus) (:end bus) (:progress bus)))

(defn battle-bus-tick
  "Returns [bus' finished?]."
  [bus dt]
  (if-not (:active bus)
    [bus false]
    (let [total-dist (v3-distance (:start bus) (:end bus))
          progress (+ (:progress bus) (/ (* (:speed bus) dt) total-dist))]
      (if (>= progress 1.0)
        [(assoc bus :progress 1.0 :active false) true]
        [(assoc bus :progress progress) false]))))

;; ── Match State ────────────────────────────────────────────────────────

(defn new-br-match-state
  [match-id map-seed]
  {:match-id match-id
   :phase :warmup
   :tick 0
   :elapsed-seconds 0.0
   :storm (new-storm-circle v3-zero)
   :bus (new-battle-bus map-seed)
   :players []
   :structures []
   :loot-spawns []
   :kill-feed []
   :alive-count 0
   :next-structure-id 1
   :next-loot-id 1
   :winner-id nil
   :map-seed map-seed})

(defn- find-player-idx [players client-id]
  (first (keep-indexed (fn [i p] (when (= (:client-id p) client-id) i)) players)))

(defn br-match-add-player
  "Returns [match' added?]."
  [match client-id did name]
  (cond
    (>= (count (:players match)) MAX-PLAYERS) [match false]
    (not= (:phase match) :warmup) [match false]
    :else [(update match :players conj (new-br-player client-id did name)) true]))

(defn br-match-start
  "Start the match: transition from Warmup to BattleBus."
  [match]
  (let [bus-pos (battle-bus-current-position (:bus match))
        match (assoc match :phase :battle-bus :alive-count (count (:players match)))]
    (update match :players
            (fn [players] (mapv #(assoc % :status :on-bus :position bus-pos) players)))))

(defn- update-alive-count [match]
  (assoc match :alive-count
         (count (filter #(contains? #{:alive :gliding :dbno} (:status %)) (:players match)))))

(defn- tick-bus [match dt]
  (let [[bus finished?] (battle-bus-tick (:bus match) dt)
        bus-pos (battle-bus-current-position bus)
        match (assoc match :bus bus)
        match (update match :players
                      (fn [players]
                        (mapv (fn [p]
                                (if (and (= (:status p) :on-bus) (not (:bus-jumped p)))
                                  (assoc p :position bus-pos)
                                  p))
                              players)))]
    (if finished?
      (-> match
          (update :players (fn [players]
                              (mapv (fn [p]
                                      (if (= (:status p) :on-bus)
                                        (assoc p :status :gliding :bus-jumped true)
                                        p))
                                    players)))
          (assoc :phase :early-game))
      match)))

(defn- tick-storm [match dt]
  (let [[storm phase-changed?] (storm-tick (:storm match) dt)
        match (assoc match :storm storm)]
    (if phase-changed?
      (let [pi (:phase-index storm)]
        (assoc match :phase (cond
                               (<= 0 pi 2) :early-game
                               (<= 3 pi 5) :mid-game
                               :else :end-game)))
      match)))

(defn- assign-tick-eliminations
  "For each player who newly transitioned to :eliminated during this tick
  (was not :eliminated in old-players but is now in new-players), assign
  :placement with the same convention br-match-process-hit already uses for
  combat kills -- (inc alive), where alive is the count of :alive/:dbno
  players remaining once this tick's eliminations are applied -- so storm
  and DBNO deaths rank by TRUE elimination order across the whole match,
  not by player array index (assign-placements, run once at match end,
  cannot reconstruct elimination order after the fact -- it only sees
  final :status, never when each player actually died). Multiple
  simultaneous eliminations within one tick (e.g. two players both hit 0 HP
  from storm damage on the same tick) get distinct placements in a fixed,
  arbitrary-but-deterministic order; there is no finer within-tick
  ordering data to recover, same as a real battle-royale server resolving
  simultaneous deaths in receipt order."
  [old-players new-players]
  (let [alive-after (count (filter #(or (br-player-alive? %) (= (:status %) :dbno)) new-players))
        newly-elim-idxs (keep-indexed
                         (fn [i p]
                           (when (and (not= (:status (nth old-players i)) :eliminated)
                                      (= (:status p) :eliminated))
                             i))
                         new-players)]
    (first
     (reduce (fn [[players placement] i]
               [(assoc players i (assoc (nth players i) :placement placement)) (dec placement)])
             [new-players (+ alive-after (count newly-elim-idxs))]
             newly-elim-idxs))))

(defn- tick-storm-damage [match dt]
  (let [storm (:storm match)
        old-players (:players match)
        match (update match :players
                      (fn [players]
                        (->> players
                             (mapv (fn [p]
                                     (if-not (= (:status p) :alive)
                                       p
                                       (let [dmg-per-sec (storm-damage-at storm (:position p))]
                                         (if (pos? dmg-per-sec)
                                           (let [dmg (long (Math/ceil (* dmg-per-sec dt)))]
                                             (first (br-player-take-damage p dmg 0)))
                                           p)))))
                             (assign-tick-eliminations old-players))))]
    (update-alive-count match)))

(defn- tick-dbno [match dt]
  (let [bleed (long (Math/ceil (* DBNO-BLEED-DPS dt)))
        old-players (:players match)
        match (update match :players
                      (fn [players]
                        (->> players
                             (mapv (fn [p]
                                     (if (= (:status p) :dbno)
                                       (let [p (update p :dbno-timer + dt)
                                             p (update p :hp #(max 0 (- % bleed)))]
                                         (if (or (zero? (:hp p)) (>= (:dbno-timer p) DBNO-DURATION))
                                           (assoc p :status :eliminated)
                                           p))
                                       p)))
                             (assign-tick-eliminations old-players))))]
    (update-alive-count match)))

(defn- tick-structures [match dt]
  (let [structures (mapv #(first (build-structure-tick-build % dt)) (:structures match))
        structures (filterv #(pos? (:current-hp %)) structures)]
    (assoc match :structures structures)))

(defn- assign-placements
  "Assign placements to eliminated players (reverse order of elimination) and #1 to winner."
  [match]
  (let [total (count (:players match))
        [players _]
        (reduce (fn [[players placement] i]
                  (let [p (nth players i)]
                    (if (and (= (:status p) :eliminated) (zero? (:placement p)))
                      [(assoc players i (assoc p :placement placement)) (dec placement)]
                      [players placement])))
                [(:players match) total]
                (range (count (:players match))))
        match (assoc match :players players)]
    (if-let [winner (:winner-id match)]
      (let [idx (find-player-idx (:players match) winner)]
        (if idx
          (update-in match [:players idx] assoc :placement 1)
          match))
      match)))

(defn- check-victory [match]
  (if (and (<= (:alive-count match) 1) (not= (:phase match) :victory))
    (let [match (assoc match :phase :victory)
          alive-ids (->> (:players match)
                          (filter #(or (br-player-alive? %) (= (:status %) :dbno)))
                          (mapv :client-id))
          match (if (= (count alive-ids) 1) (assoc match :winner-id (first alive-ids)) match)]
      (assign-placements match))
    match))

(defn br-match-tick
  "Main server tick. dt = 1/60."
  [match dt]
  (let [match (-> match (update :tick inc) (update :elapsed-seconds + dt))]
    (case (:phase match)
      :warmup match
      :battle-bus (tick-bus match dt)
      (:early-game :mid-game :end-game)
      (-> match
          (tick-storm dt)
          (tick-storm-damage dt)
          (tick-dbno dt)
          (tick-structures dt)
          check-victory)
      :victory match)))

(defn br-match-player-jump
  "Player jumps from bus."
  [match client-id]
  (if-let [idx (find-player-idx (:players match) client-id)]
    (let [p (nth (:players match) idx)]
      (if (= (:status p) :on-bus)
        (update-in match [:players idx] assoc
                   :status :gliding :bus-jumped true
                   :position (battle-bus-current-position (:bus match)))
        match))
    match))

(defn br-match-player-land
  "Player lands (transition from gliding to alive)."
  [match client-id position]
  (if-let [idx (find-player-idx (:players match) client-id)]
    (let [p (nth (:players match) idx)]
      (if (= (:status p) :gliding)
        (update-in match [:players idx] assoc :status :alive :position position :landed true)
        match))
    match))

(defn br-match-player-build
  "Player builds a structure. Returns [match' structure-id-or-nil]."
  [match client-id piece material position rotation-y]
  (if-let [idx (find-player-idx (:players match) client-id)]
    (let [player (nth (:players match) idx)]
      (if (not= (:status player) :alive)
        [match nil]
        (let [[player' spent?] (br-player-spend-material player material)]
          (if-not spent?
            [match nil]
            (let [id (:next-structure-id match)
                  structure (new-build-structure id piece material position rotation-y client-id)
                  match (-> match
                            (assoc-in [:players idx] player')
                            (update :next-structure-id inc)
                            (update :structures conj structure))]
              [match id])))))
    [match nil]))

(defn br-match-player-build-aimed
  "Player builds at a grid-snapped position one piece-length ahead of `origin`
  facing `forward`, instead of `br-match-player-build`'s raw caller-supplied
  position/rotation (still available as-is for tests/tools wanting an exact
  spot). Returns [match' structure-id-or-nil] — nil on a blocked cell too,
  same as the underlying fn's nil-on-can't-afford-material."
  [match client-id piece material origin forward]
  (let [candidate (placement-candidate origin forward)]
    (if (placement-blocked? (:structures match) piece candidate)
      [match nil]
      (br-match-player-build match client-id piece material candidate 0.0))))

(defn br-match-process-hit
  "Process hit from attacker to victim."
  [match attacker-id victim-id damage weapon-name headshot? distance]
  (let [victim-idx (find-player-idx (:players match) victim-id)]
    (if-not victim-idx
      match
      (let [victim (nth (:players match) victim-idx)
            [victim' actual-dmg] (br-player-take-damage victim damage attacker-id)
            eliminated? (= (:status victim') :eliminated)
            match (assoc-in match [:players victim-idx] victim')
            attacker-idx (find-player-idx (:players match) attacker-id)
            match (if attacker-idx
                    (update-in match [:players attacker-idx]
                               (fn [attacker]
                                 (cond-> (update attacker :damage-dealt + actual-dmg)
                                   eliminated? (update :kills inc))))
                    match)]
        (if eliminated?
          (let [attacker-name (if-let [i (find-player-idx (:players match) attacker-id)]
                                 (:display-name (nth (:players match) i))
                                 "")
                victim-name (:display-name (nth (:players match) victim-idx))
                alive (count (filter #(or (br-player-alive? %) (= (:status %) :dbno)) (:players match)))
                match (update-in match [:players victim-idx] assoc :placement (inc alive))
                entry {:tick (:tick match)
                       :eliminator-name attacker-name
                       :eliminator-id attacker-id
                       :victim-name victim-name
                       :victim-id victim-id
                       :weapon-name weapon-name
                       :headshot headshot?
                       :distance distance}
                match (update match :kill-feed conj entry)
                match (if (> (count (:kill-feed match)) 50)
                        (update match :kill-feed (comp vec rest))
                        match)]
            (update-alive-count match))
          (update-alive-count match))))))

(defn br-match-damage-structure
  "Damage a structure. Returns [match' destroyed?]."
  [match structure-id damage]
  (let [idx (first (keep-indexed (fn [i s] (when (= (:id s) structure-id) i)) (:structures match)))]
    (if-not idx
      [match false]
      (let [[structure' destroyed?] (build-structure-take-damage (nth (:structures match) idx) damage)]
        [(assoc-in match [:structures idx] structure') destroyed?]))))

;; ── Map Generation: POIs ──────────────────────────────────────────────

(def poi-type-values #{:city :town :landmark :industrial :military})

(defn generate-br-pois
  [_seed]
  [{:name "Tilted Towers" :center (v3 -200.0 0.0 100.0) :radius 120.0 :poi-type :city :loot-density 1.0 :building-count 24}
   {:name "Pleasant Park" :center (v3 300.0 0.0 400.0) :radius 100.0 :poi-type :town :loot-density 0.7 :building-count 14}
   {:name "Retail Row" :center (v3 500.0 0.0 -200.0) :radius 90.0 :poi-type :town :loot-density 0.8 :building-count 16}
   {:name "Salty Springs" :center (v3 100.0 0.0 -100.0) :radius 70.0 :poi-type :town :loot-density 0.6 :building-count 8}
   {:name "Dusty Depot" :center (v3 0.0 0.0 0.0) :radius 80.0 :poi-type :industrial :loot-density 0.5 :building-count 6}
   {:name "Lonely Lodge" :center (v3 -600.0 0.0 -500.0) :radius 70.0 :poi-type :landmark :loot-density 0.4 :building-count 6}
   {:name "Junk Junction" :center (v3 -700.0 0.0 600.0) :radius 60.0 :poi-type :industrial :loot-density 0.5 :building-count 4}
   {:name "Haunted Hills" :center (v3 -800.0 0.0 300.0) :radius 65.0 :poi-type :landmark :loot-density 0.4 :building-count 8}
   {:name "Fatal Fields" :center (v3 -100.0 0.0 -500.0) :radius 90.0 :poi-type :town :loot-density 0.6 :building-count 10}
   {:name "Moisty Mire" :center (v3 600.0 0.0 -600.0) :radius 100.0 :poi-type :landmark :loot-density 0.3 :building-count 4}
   {:name "Snobby Shores" :center (v3 -800.0 0.0 -100.0) :radius 80.0 :poi-type :town :loot-density 0.7 :building-count 10}
   {:name "Greasy Grove" :center (v3 -400.0 0.0 -400.0) :radius 75.0 :poi-type :town :loot-density 0.7 :building-count 10}
   {:name "Flush Factory" :center (v3 -500.0 0.0 -700.0) :radius 65.0 :poi-type :industrial :loot-density 0.5 :building-count 4}
   {:name "Tomato Town" :center (v3 200.0 0.0 500.0) :radius 50.0 :poi-type :landmark :loot-density 0.4 :building-count 4}
   {:name "Wailing Woods" :center (v3 700.0 0.0 400.0) :radius 100.0 :poi-type :landmark :loot-density 0.3 :building-count 2}
   {:name "Risky Reels" :center (v3 400.0 0.0 600.0) :radius 60.0 :poi-type :landmark :loot-density 0.5 :building-count 4}
   {:name "Loot Lake" :center (v3 0.0 0.0 300.0) :radius 90.0 :poi-type :landmark :loot-density 0.6 :building-count 6}
   {:name "Shifty Shafts" :center (v3 -300.0 0.0 -200.0) :radius 55.0 :poi-type :industrial :loot-density 0.6 :building-count 4}
   {:name "Anarchy Acres" :center (v3 200.0 0.0 700.0) :radius 85.0 :poi-type :town :loot-density 0.5 :building-count 8}
   {:name "KAMI Citadel" :center (v3 0.0 20.0 0.0) :radius 50.0 :poi-type :military :loot-density 1.0 :building-count 4}
   ;; Brainrot POIs
   {:name "Skibidi Sewers" :center (v3 350.0 0.0 350.0) :radius 85.0 :poi-type :landmark :loot-density 0.8 :building-count 8}
   {:name "Sigma Summit" :center (v3 -450.0 30.0 500.0) :radius 70.0 :poi-type :landmark :loot-density 0.6 :building-count 6}
   {:name "Ohio Outpost" :center (v3 700.0 0.0 -400.0) :radius 75.0 :poi-type :military :loot-density 0.9 :building-count 10}
   {:name "Grimace Grotto" :center (v3 -300.0 -5.0 600.0) :radius 80.0 :poi-type :landmark :loot-density 0.5 :building-count 4}
   {:name "Rizz Resort" :center (v3 500.0 0.0 500.0) :radius 90.0 :poi-type :city :loot-density 0.9 :building-count 16}
   {:name "Fanum Food Court" :center (v3 -600.0 0.0 -300.0) :radius 65.0 :poi-type :town :loot-density 0.7 :building-count 8}])

(defn poi-color
  [poi-type]
  (case poi-type
    :city [0.55 0.55 0.6 1.0]
    :town [0.6 0.5 0.4 1.0]
    :landmark [0.5 0.55 0.5 1.0]
    :industrial [0.45 0.45 0.5 1.0]
    :military [0.35 0.4 0.35 1.0]))

;; ── Scene generation ───────────────────────────────────────────────────
;; NOTE: `IslandScene`/`EntityDef`/`MeshRef`/`ComponentDef` are owned by the
;; `scene` restoration cluster; this generates plain duck-typed maps in the
;; same shape (entity maps with :id/:position/:rotation/:scale/:mesh/
;; :components/:layer) rather than depending on that cluster's namespace, so
;; this cluster is not blocked on it landing first.

(defn- cube-mesh [color] {:type :cube :color color})
(defn- trigger-component [kind data] {:type :trigger :kind kind :data data})
(defn- physics-component [dynamic?] {:type :physics :dynamic dynamic?})
(defn- item-component [item-id item-name] {:type :item :item-id item-id :item-name item-name})
(def player-spawn-component {:type :player-spawn})

(defn- entity
  [id position rotation scale mesh components layer]
  {:id id :position position :rotation rotation :scale scale
   :mesh mesh :components components :layer layer})

(def ^:private identity-rotation [0.0 0.0 0.0 1.0])

(defn- lcg-next
  "64-bit wrapping multiply-add, matching Rust's `u64::wrapping_mul`/
  `wrapping_add` (used as a cheap deterministic scatter hash, not real RNG).
  Uses `unchecked-*` so JVM longs wrap silently on overflow instead of
  auto-promoting to BigInt (mirrors two's-complement u64 wraparound closely
  enough for this scatter-hash use, though the sign bit differs from an
  unsigned u64 — irrelevant here since only the low 16 bits are consumed via
  `bit-and`)."
  [x mul add]
  #?(:clj (unchecked-add (unchecked-multiply (long x) (long mul)) (long add))
     :cljs (+ (* x mul) add)))

(defn generate-br-map
  "Generate the BR island scene with POI buildings and loot spawns.
  Returns a plain map in IslandScene shape (see cross-cluster note above)."
  [seed]
  (let [pois (generate-br-pois seed)
        half (* MAP-SIZE 0.5)
        terrain (entity "terrain" [0.0 -0.5 0.0] identity-rotation [MAP-SIZE 1.0 MAP-SIZE]
                         (cube-mesh [0.25 0.45 0.2 1.0]) [] nil)
        walls (for [[id pos scale] [["wall-n" [0.0 50.0 (- half)] [MAP-SIZE 100.0 2.0]]
                                     ["wall-s" [0.0 50.0 half] [MAP-SIZE 100.0 2.0]]
                                     ["wall-e" [half 50.0 0.0] [2.0 100.0 MAP-SIZE]]
                                     ["wall-w" [(- half) 50.0 0.0] [2.0 100.0 MAP-SIZE]]]]
                 (entity id pos identity-rotation scale (cube-mesh [0.0 0.0 0.0 0.0])
                         [(trigger-component "kill-wall" "{}")] nil))
        ;; Buildings + chests per POI
        [buildings _]
        (reduce
         (fn [[acc building-idx] poi]
           (let [bc (:building-count poi)
                 [center-x _ center-z] (:center poi)]
             (reduce
              (fn [[acc idx] i]
                (let [angle (+ (* (/ (double i) bc) (* 2.0 Math/PI))
                                (* (double (mod (* seed (count (:name poi))) 360)) 0.01))
                      r (+ (* (:radius poi) 0.3) (* (:radius poi) 0.6 (mod (* i 1.618) 1.0)))
                      bx (+ center-x (* r (Math/cos angle)))
                      bz (+ center-z (* r (Math/sin angle)))
                      floors (case (:poi-type poi)
                               :city (+ 2 (mod idx 5))
                               :town (+ 1 (mod idx 3))
                               :military (+ 1 (mod idx 2))
                               (+ 1 (mod idx 2)))
                      h (* (double floors) 3.0)
                      w (+ 6.0 (* (double (mod idx 4)) 2.0))
                      bldg (entity (str "bldg-" idx) [bx (* h 0.5) bz] identity-rotation [w h w]
                                    (cube-mesh (poi-color (:poi-type poi)))
                                    [(physics-component false)
                                     (trigger-component "harvestable" "{\"material\":\"brick\",\"amount\":30}")]
                                    nil)
                      acc (conj acc bldg)
                      acc (if (zero? (mod idx 2))
                            (conj acc (entity (str "chest-" idx) [bx 0.5 bz] identity-rotation [0.8 0.6 0.6]
                                               (cube-mesh [0.85 0.75 0.1 1.0])
                                               [(item-component "chest" "Chest")]
                                               nil))
                            acc)]
                  [acc (inc idx)]))
              [acc building-idx]
              (range bc))))
         [[] 0]
         pois)
        ;; Trees
        tree-count 500
        trees (keep
               (fn [i]
                 (let [s (lcg-next i 2654435761 seed)
                       x (* (- (/ (double (bit-and s 0xFFFF)) 65535.0) 0.5) MAP-SIZE 0.9)
                       z (* (- (/ (double (bit-and (bit-shift-right s 16) 0xFFFF)) 65535.0) 0.5) MAP-SIZE 0.9)
                       near-poi? (some (fn [p]
                                          (let [[cx _ cz] (:center p)
                                                dx (- cx x) dz (- cz z)]
                                            (< (Math/sqrt (+ (* dx dx) (* dz dz))) (* (:radius p) 0.5))))
                                        pois)]
                   (when-not near-poi?
                     (entity (str "tree-" i) [x 3.0 z] identity-rotation [1.5 6.0 1.5]
                             (cube-mesh [0.2 0.5 0.15 1.0])
                             [(physics-component false)
                              (trigger-component "harvestable" "{\"material\":\"wood\",\"amount\":50}")]
                             nil))))
               (range tree-count))
        ;; Rocks
        rock-count 200
        rocks (map
               (fn [i]
                 (let [s (lcg-next i 1103515245 seed)
                       x (* (- (/ (double (bit-and s 0xFFFF)) 65535.0) 0.5) MAP-SIZE 0.9)
                       z (* (- (/ (double (bit-and (bit-shift-right s 16) 0xFFFF)) 65535.0) 0.5) MAP-SIZE 0.9)]
                   (entity (str "rock-" i) [x 1.0 z] identity-rotation [2.5 2.0 2.5]
                           (cube-mesh [0.5 0.5 0.5 1.0])
                           [(physics-component false)
                            (trigger-component "harvestable" "{\"material\":\"brick\",\"amount\":40}")]
                           nil)))
               (range rock-count))
        ;; Cars
        car-count 100
        cars (map
              (fn [i]
                (let [s (lcg-next i 6364136223846793005 seed)
                      x (* (- (/ (double (bit-and s 0xFFFF)) 65535.0) 0.5) MAP-SIZE 0.85)
                      z (* (- (/ (double (bit-and (bit-shift-right s 16) 0xFFFF)) 65535.0) 0.5) MAP-SIZE 0.85)]
                  (entity (str "car-" i) [x 0.7 z] identity-rotation [3.5 1.4 1.8]
                          (cube-mesh [0.6 0.25 0.25 1.0])
                          [(physics-component false)
                           (trigger-component "harvestable" "{\"material\":\"metal\",\"amount\":60}")]
                          nil)))
              (range car-count))
        spawn-island (entity "spawn-island" [(- MAP-SIZE) -0.5 (- MAP-SIZE)] identity-rotation [50.0 1.0 50.0]
                              (cube-mesh [0.4 0.4 0.6 1.0])
                              [player-spawn-component]
                              nil)
        entities (vec (concat [terrain] walls buildings trees rocks cars [spawn-island]))]
    {:context "https://etzhayyim.com/ns/kami/scene"
     :ld-type "BattleRoyaleScene"
     :ld-id (str "urn:kami:br:map:" seed)
     :name "KAMI Battle Royale — Brainrot Edition"
     :genre "battle-royale"
     :description "100-player battle royale with Brainrot POIs — Skibidi Sewers, Sigma Summit, Ohio Outpost"
     :max-players 100
     ;; Cross-cluster: original called `crate::island_gen::brainrot_characters()`
     ;; (owned by another cluster's `.cljc` port). Left as an empty vector here
     ;; with a documented TODO rather than blocking on that namespace landing.
     :characters [{:id "brainrot-placeholder"}] ; TODO: replace with game.island-gen/brainrot-characters when that cluster lands
     :ambient-color [0.02 0.025 0.04]
     :sun-direction [-0.5 -2.0 -1.0]
     :sun-intensity 4.5
     :entities entities
     :camera-mode nil
     :layers []
     :viewport nil
     :sun-color nil
     :point-lights []
     :atmosphere nil
     :postfx-preset nil
     :ibl-env-map nil
     :shadow nil}))
