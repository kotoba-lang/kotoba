(ns game.island-gen
  "Batch Island generator: convert Godot game catalog to KAMI Islands.

  Restored from kami-game's `island_gen.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Each Godot game becomes a KAMI Island with a game-specific scene
  (genre-based template) plus a brainrot character roster / Pokémon-style
  evolution chain system for the 6 'brainrot' games.

  The original depends on two sibling modules owned by other clusters of
  this parallel restoration:
    - `crate::scene` (`CharacterAppearance`, `CharacterDef`, `ComponentDef`,
      `EntityDef`, `IslandScene`, `MeshRef`) — the KAMI scene-graph types.
    - `crate::brainrot_mesh` (`BrainrotCharacter`, `.max_stage()`) — the
      brainrot evolution mesh builder.
  To keep this namespace self-contained and avoid blocking on load order
  across repos, both are inlined here as minimal local duck-typed plain
  data shapes (documented below) rather than required from another
  namespace. If/when `game.scene` and `game.brainrot-mesh` land from their
  owning clusters, callers can convert between these shapes and the
  canonical ones (same keys, kebab-cased).

  Local `EntityDef` shape:
    {:id string :position [x y z] :rotation [x y z w] :scale [x y z]
     :mesh mesh-ref :components [component ...] :layer nil-or-val}

  Local `MeshRef` variants (tagged maps):
    {:type :cube :color [r g b a]}
    {:type :sphere :color [r g b a] :radius r}
    {:type :plane :color [r g b a] :width w :depth d :subdivisions n}
    {:type :cylinder :color [r g b a] :h h :r1 r1 :r2 r2}

  Local `ComponentDef` variants (tagged maps):
    {:type :player-spawn}
    {:type :physics :dynamic bool}
    {:type :item :item-id id :item-name name}
    {:type :npc :name name :waypoints [[x y z] ...]}
    {:type :trigger :kind kind :data data-string}
    {:type :portal :target-island id}

  Local `IslandScene` shape mirrors the Rust struct fields 1:1 (kebab-case
  keys): :context :ld-type :ld-id :name :genre :description :max-players
  :characters :entities :ambient-color :sun-direction :sun-intensity
  :camera-mode :layers :viewport :sun-color :point-lights :atmosphere
  :postfx-preset :ibl-env-map :shadow.

  Local `CharacterDef` / `CharacterAppearance` shapes mirror the Rust
  structs 1:1 (kebab-case keys).

  `BrainrotCharacter` is a plain keyword (:skibidi :sigma :ohio :grimace
  :rizz :fanum); `brainrot-max-stage` inlines `.max_stage()` (values taken
  from `kami-game/src/brainrot_mesh.rs`, same deleted PR).

  The original's JSON-LD stamping (`serde_json::to_string`) is replaced
  with plain data: `generate-all-islands`/`generate-brainrot-islands`
  return `[scene game]` pairs directly (no JSON round-trip — serde isn't
  part of this zero-dep port; the scene map itself is the portable EDN
  form)."
  )

;; ---------------------------------------------------------------------
;; GameDef / Genre
;; ---------------------------------------------------------------------

(def genres
  #{:io-multiplayer :puzzle :rpg :simulation :visual-novel :card :arcade
    :adult :brainrot :chase})

(defn game-def
  [slug title genre max-players description]
  {:slug slug :title title :genre genre :max-players max-players :description description})

;; ---------------------------------------------------------------------
;; The Godot game catalog
;; ---------------------------------------------------------------------

(defn godot-game-catalog
  "The Godot games from games.etzhayyim.com: 22 originals + 6 brainrot +
  1 chase = 29 entries. (The original Rust test comment said '28 = 22 +
  6 brainrot', stale after the later `ketsu-gorilla` chase-game addition
  — this port uses the actual catalog length, 29, see `island-gen-test`.)"
  []
  [(game-def "agar" "Agar Arena" :io-multiplayer 100 "Grow by absorbing smaller cells")
   (game-def "slither" "Slither World" :io-multiplayer 100 "Snake multiplayer arena")
   (game-def "diep" "Diep Tanks" :io-multiplayer 50 "Tank shooter arena")
   (game-def "mope" "Mope Wilderness" :io-multiplayer 80 "Animal evolution multiplayer")
   (game-def "splix" "Splix Territory" :io-multiplayer 50 "Territory capture game")
   (game-def "hole" "Hole Devourer" :io-multiplayer 30 "Devour everything in the city")
   (game-def "paper" "Paper Conquest" :io-multiplayer 50 "Claim territory on paper")
   (game-def "wings" "Wings Dogfight" :io-multiplayer 30 "Aerial combat multiplayer")
   (game-def "zombs" "Zombs Defense" :io-multiplayer 4 "Base defense against zombies")
   (game-def "snake" "Snake Classic" :arcade 1 "Classic snake game")
   (game-def "colorbynumber" "Color Zen" :puzzle 1 "Relaxing color puzzle")
   (game-def "match3desires" "Match 3" :puzzle 1 "Match-3 puzzle game")
   (game-def "infinitedive" "Infinite Dive" :arcade 1 "Endless falling arcade")
   (game-def "dungeonslave" "Dungeon Quest" :rpg 4 "Dungeon crawler RPG")
   (game-def "kyberfrontier" "Kyber Frontier" :rpg 8 "Cyberpunk RPG adventure")
   (game-def "idolproduction" "Idol Manager" :simulation 1 "Idol production simulation")
   (game-def "nightclubtycoon" "Club Tycoon" :simulation 1 "Nightclub management sim")
   (game-def "loveandglitch" "Love & Glitch" :visual-novel 1 "Visual novel romance")
   (game-def "strippoker" "Card Showdown" :card 4 "Multiplayer card game")
   (game-def "alchemistlust" "Alchemist Lab" :adult 1 "Alchemy simulation")
   (game-def "haremconquest" "Conquest" :adult 1 "Strategy conquest game")
   (game-def "succubusagency" "Agency" :adult 1 "Management simulation")
   ;; Brainrot collection
   (game-def "skibidi" "Skibidi Arena" :brainrot 50 "Giant toilet boss battle — dop dop yes yes")
   (game-def "sigma" "Sigma Grindset" :brainrot 30 "Lone wolf gym simulator — no distractions")
   (game-def "ohio" "Ohio Final Boss" :brainrot 20 "Only in Ohio — survive the anomalies")
   (game-def "grimace" "Grimace Shake" :brainrot 40 "Purple blob chaos — don't drink the shake")
   (game-def "rizz" "Rizz Academy" :brainrot 25 "Master the art of W rizz")
   (game-def "fanum" "Fanum Tax" :brainrot 30 "Protect your food — tax collectors everywhere")
   ;; Chase games
   (game-def "ketsu-gorilla" "Goriketsu Dash!!" :chase 10
             "Slap a sleeping gorilla's butt and RUN — goriririri gorigori ketsu dasshu!")])

;; ---------------------------------------------------------------------
;; Scene helpers
;; ---------------------------------------------------------------------

(defn- cube-mesh [color] {:type :cube :color color})
(defn- sphere-mesh [color radius] {:type :sphere :color color :radius radius})
(defn- plane-mesh [color width depth subdivisions] {:type :plane :color color :width width :depth depth :subdivisions subdivisions})
(defn- cylinder-mesh [color h r1 r2] {:type :cylinder :color color :h h :r1 r1 :r2 r2})

(defn- entity
  "Cube entity with default rotation [0 0 0 1], no layer."
  [id pos scale color components]
  {:id id :position pos :rotation [0.0 0.0 0.0 1.0] :scale scale
   :mesh (cube-mesh color) :components components :layer nil})

(defn- entity-full
  "Entity with an explicit (non-cube) mesh."
  [id pos scale mesh components]
  {:id id :position pos :rotation [0.0 0.0 0.0 1.0] :scale scale
   :mesh mesh :components components :layer nil})

(def ^:private TAU (* 2.0 #?(:clj Math/PI :cljs js/Math.PI)))
(defn- fsin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn- fcos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))

;; ---------------------------------------------------------------------
;; game-to-island
;; ---------------------------------------------------------------------

(defn game-to-island
  "Generate a KAMI IslandScene (local shape, see namespace docstring) from
  a game definition."
  [game]
  (let [genre (:genre game)
        max-players (:max-players game)
        ground-color (case genre
                       :io-multiplayer [0.15 0.25 0.35 1.0]
                       :puzzle [0.2 0.3 0.25 1.0]
                       :rpg [0.25 0.2 0.15 1.0]
                       :simulation [0.3 0.3 0.3 1.0]
                       :arcade [0.1 0.1 0.2 1.0]
                       :brainrot [0.15 0.05 0.2 1.0]
                       :chase [0.08 0.35 0.05 1.0]
                       [0.2 0.2 0.25 1.0])
        arena-size (cond (> max-players 30) 80.0
                          (> max-players 4) 50.0
                          :else 30.0)
        entities (transient [])]
    (conj! entities (entity "ground" [0.0 -0.5 0.0] [arena-size 1.0 arena-size] ground-color []))

    (when (> max-players 1)
      (let [h (/ arena-size 2.0)
            wall-color [0.4 0.4 0.45 1.0]]
        (conj! entities (entity "wall-n" [0.0 2.0 (- h)] [arena-size 4.0 1.0] wall-color []))
        (conj! entities (entity "wall-s" [0.0 2.0 h] [arena-size 4.0 1.0] wall-color []))
        (conj! entities (entity "wall-e" [h 2.0 0.0] [1.0 4.0 arena-size] wall-color []))
        (conj! entities (entity "wall-w" [(- h) 2.0 0.0] [1.0 4.0 arena-size] wall-color []))))

    (let [spawn-count (min max-players 4)
          spawn-colors [[0.2 0.6 1.0 1.0] [1.0 0.4 0.2 1.0] [0.2 0.9 0.3 1.0] [0.9 0.9 0.1 1.0]]]
      (dotimes [i spawn-count]
        (let [angle (* (/ (double i) spawn-count) TAU)
              r (* arena-size 0.3)]
          (conj! entities
                 (entity (str "spawn-" i)
                         [(* r (fcos angle)) 1.0 (* r (fsin angle))]
                         [0.8 1.6 0.8]
                         (nth spawn-colors (mod i 4))
                         [{:type :player-spawn} {:type :physics :dynamic true}])))))

    ;; Genre-specific decorations
    (case genre
      :io-multiplayer
      (dotimes [i 20]
        (let [angle (* (/ (double i) 20.0) TAU)
              r (+ (* arena-size 0.2) (mod (* i 1.7) (* arena-size 0.3)))]
          (conj! entities
                 (entity (str "orb-" i) [(* r (fcos angle)) 0.3 (* r (fsin angle))] [0.3 0.3 0.3]
                         [0.0 0.8 0.6 1.0]
                         [{:type :item :item-id "orb" :item-name "Energy Orb"}]))))

      :rpg
      (do
        (conj! entities (entity "castle" [0.0 3.0 (* arena-size -0.3)] [8.0 6.0 8.0] [0.4 0.35 0.3 1.0] []))
        (conj! entities (entity "tower-l" [(* arena-size -0.2) 4.0 (* arena-size -0.3)] [3.0 8.0 3.0] [0.45 0.4 0.35 1.0] []))
        (conj! entities (entity "tower-r" [(* arena-size 0.2) 4.0 (* arena-size -0.3)] [3.0 8.0 3.0] [0.45 0.4 0.35 1.0] []))
        (conj! entities (entity "chest-1" [5.0 0.3 5.0] [0.6 0.4 0.4] [0.8 0.7 0.2 1.0]
                                [{:type :item :item-id "gem-gold" :item-name "Gold Gem"}])))

      :puzzle
      (let [grid-size 8
            cell-size (/ arena-size (+ grid-size 2.0))
            palette [[0.99 0.42 0.42 1.0] [0.31 0.80 0.77 1.0] [0.27 0.72 0.82 1.0]
                     [0.59 0.81 0.71 1.0] [1.0 0.92 0.65 1.0] [0.87 0.63 0.87 1.0]]]
        (conj! entities
               (entity "easel-frame"
                       [0.0 (+ (/ (* grid-size cell-size) 2.0) 1.0) (* arena-size -0.35)]
                       [(* (+ grid-size 1.0) cell-size) (* (+ grid-size 1.0) cell-size) 0.5]
                       [0.55 0.35 0.2 1.0]
                       [{:type :physics :dynamic false}]))
        (doseq [i (range grid-size) j (range grid-size)]
          (let [x (* (+ (- (double j) (/ grid-size 2.0)) 0.5) cell-size)
                y (+ (* (+ (- grid-size 1 i) 0.5) cell-size) 1.0)
                z (+ (* arena-size -0.35) 0.3)
                idx (+ (* i grid-size) j)
                color-num (inc (mod idx (count palette)))
                color (if (zero? (mod (+ i j) 3))
                        (nth palette (mod color-num (count palette)))
                        [0.92 0.90 0.85 1.0])]
            (conj! entities
                   (entity (str "cell-" idx) [x y z] [(* cell-size 0.92) (* cell-size 0.92) 0.15] color
                           [{:type :trigger :kind "paint"
                             :data (str "{\"cell_index\":" idx ",\"color_number\":" color-num "}")}]))))
        (doseq [[i pal-color] (map-indexed vector palette)]
          (let [angle (* (/ (double i) (count palette)) TAU)
                r (* arena-size 0.15)]
            (conj! entities
                   (entity (str "paint-" i) [(* r (fcos angle)) 0.35 (* r (fsin angle))] [0.6 0.8 0.6]
                           pal-color
                           [{:type :item :item-id (str "paint-" i) :item-name (str "Paint #" (inc i))}]))))
        (conj! entities (entity "palette-stand" [(* arena-size 0.25) 0.5 0.0] [3.0 1.0 2.0] [0.55 0.35 0.2 1.0] [])))

      :brainrot
      (do
        ;; Giant Toilet (Skibidi HQ) — center
        (conj! entities (entity "skibidi-bowl" [0.0 1.5 0.0] [4.0 3.0 4.0] [0.95 0.95 0.95 1.0] [{:type :physics :dynamic false}]))
        (conj! entities (entity "skibidi-tank" [0.0 4.0 -2.5] [3.5 3.0 1.5] [0.9 0.9 0.92 1.0] []))
        (conj! entities (entity "skibidi-lid" [0.0 3.5 0.5] [3.8 0.3 3.0] [0.92 0.92 0.95 1.0] []))
        (conj! entities (entity "skibidi-head" [0.0 5.5 0.0] [2.0 2.0 2.0] [0.85 0.7 0.6 1.0]
                                [{:type :npc :name "Skibidi Commander" :waypoints [[0.0 5.5 0.0] [0.0 6.5 0.0]]}]))
        ;; Sigma Gym — northeast
        (conj! entities (entity "sigma-gym-base" [(* arena-size 0.3) 0.5 (* arena-size -0.3)] [10.0 1.0 10.0] [0.25 0.25 0.3 1.0] []))
        (conj! entities (entity "sigma-throne" [(* arena-size 0.3) 2.0 (* arena-size -0.3)] [2.0 3.0 2.0] [0.1 0.1 0.15 1.0] []))
        (dotimes [i 4]
          (let [x (+ (* arena-size 0.3) (* (- i 1.5) 2.0))]
            (conj! entities
                   (entity-full (str "sigma-dumbbell-" i) [x 0.5 (+ (* arena-size -0.3) 3.0)] [0.6 0.6 0.6]
                                 (sphere-mesh [0.3 0.3 0.35 1.0] 0.3)
                                 [{:type :item :item-id (str "dumbbell-" i) :item-name "Sigma Weight"}]))))
        ;; Ohio Obelisk — northwest
        (conj! entities (entity "ohio-obelisk" [(* arena-size -0.35) 6.0 (* arena-size -0.25)] [1.5 12.0 1.5] [0.8 0.0 0.0 1.0] []))
        (dotimes [i 6]
          (let [angle (* (/ (double i) 6.0) TAU)
                r 5.0]
            (conj! entities
                   (entity (str "ohio-cube-" i)
                           [(+ (* arena-size -0.35) (* r (fcos angle)))
                            (+ 3.0 (* i 0.8))
                            (+ (* arena-size -0.25) (* r (fsin angle)))]
                           [1.2 1.2 1.2] [0.9 0.1 0.1 0.9]
                           [{:type :trigger :kind "damage" :data "{\"damage\":10}"}]))))
        ;; Grimace Swamp — southwest
        (conj! entities
               (entity-full "grimace-body" [(* arena-size -0.3) 3.0 (* arena-size 0.3)] [5.0 5.0 5.0]
                             (sphere-mesh [0.5 0.0 0.8 0.85] 2.5)
                             [{:type :npc :name "Grimace" :waypoints [[(* arena-size -0.3) 3.0 (* arena-size 0.3)]]}]))
        (conj! entities
               (entity-full "grimace-head" [(* arena-size -0.3) 7.0 (* arena-size 0.3)] [3.0 3.0 3.0]
                             (sphere-mesh [0.55 0.05 0.85 0.9] 1.5)
                             []))
        (dotimes [i 8]
          (let [angle (* (/ (double i) 8.0) TAU)
                r 8.0]
            (conj! entities
                   (entity-full (str "grimace-puddle-" i)
                                 [(+ (* arena-size -0.3) (* r (fcos angle))) 0.05 (+ (* arena-size 0.3) (* r (fsin angle)))]
                                 [2.0 0.1 2.0]
                                 (plane-mesh [0.4 0.0 0.6 0.7] 2.0 2.0 1)
                                 [{:type :trigger :kind "damage" :data "{\"damage\":5,\"effect\":\"slow\"}"}]))))
        ;; Rizz Academy — southeast
        (conj! entities (entity "rizz-podium" [(* arena-size 0.3) 1.0 (* arena-size 0.3)] [3.0 2.0 3.0] [0.9 0.15 0.5 1.0] []))
        (conj! entities (entity "rizz-stage" [(* arena-size 0.3) 0.3 (* arena-size 0.3)] [8.0 0.5 8.0] [0.8 0.1 0.4 1.0] []))
        ;; Fanum Market — east
        (conj! entities (entity "fanum-stall" [(* arena-size 0.4) 1.5 0.0] [6.0 3.0 4.0] [0.9 0.6 0.2 1.0] []))
        (dotimes [i 5]
          (conj! entities
                 (entity (str "fanum-food-" i) [(+ (* arena-size 0.4) (* (- i 2.0) 1.5)) 0.5 2.0] [0.8 0.8 0.8]
                         [0.95 0.75 0.3 1.0]
                         [{:type :item :item-id (str "food-" i) :item-name "Fanum Snack"}])))
        ;; Gyatt orbs
        (dotimes [i 12]
          (let [angle (* (/ (double i) 12.0) TAU)
                r (+ (* arena-size 0.15) (mod (* i 2.3) (* arena-size 0.2)))]
            (conj! entities
                   (entity-full (str "gyatt-orb-" i) [(* r (fcos angle)) 0.5 (* r (fsin angle))] [0.5 0.5 0.5]
                                 (sphere-mesh [1.0 0.2 0.6 1.0] 0.25)
                                 [{:type :item :item-id "gyatt-orb" :item-name "Gyatt Energy"}])))))

      :chase
      (do
        (conj! entities (entity "gorilla-spot" [0.0 0.1 0.0] [5.0 0.2 5.0] [0.15 0.08 0.03 1.0] [{:type :physics :dynamic false}]))
        (conj! entities (entity-full "gorilla-boss" [0.0 0.0 0.0] [1.0 1.0 1.0]
                                      (sphere-mesh [0.25 0.15 0.08 1.0] 1.8)
                                      [{:type :npc :name "Goriketsu" :waypoints [[0.0 0.0 0.0]]}]))
        (conj! entities (entity-full "gorilla-butt" [0.0 1.0 -1.0] [2.2 2.2 2.2]
                                      (sphere-mesh [0.95 0.15 0.1 1.0] 1.1)
                                      []))
        (dotimes [i 8]
          (let [angle (* (/ (double i) 8.0) TAU)
                r (+ (* arena-size 0.2) (mod (* i 3.7) (* arena-size 0.15)))]
            (conj! entities
                   (entity-full (str "palm-" i) [(* r (fcos angle)) 0.0 (* r (fsin angle))] [1.0 1.0 1.0]
                                 (cylinder-mesh [0.45 0.3 0.15 1.0] (+ 6.0 (* i 0.5)) 0.5 0.3)
                                 [{:type :physics :dynamic false}]))))
        (dotimes [i 20]
          (let [angle (+ (* (/ (double i) 20.0) TAU) 0.3)
                r (+ 10.0 (mod (* i 2.1) 30.0))]
            (conj! entities
                   (entity-full (str "banana-" i) [(* r (fcos angle)) 0.5 (* r (fsin angle))] [0.5 0.5 0.5]
                                 (sphere-mesh [1.0 0.85 0.0 1.0] 0.3)
                                 [{:type :item :item-id (str "banana-" i) :item-name "Banana"}]))))
        (conj! entities (entity "river" [0.0 -0.3 (* arena-size 0.3)] [8.0 0.1 20.0] [0.1 0.3 0.6 0.7]
                                [{:type :trigger :kind "slow" :data "Kawa da!"}]))
        (conj! entities (entity "vine-bridge" [0.0 0.5 (* arena-size 0.3)] [2.0 0.3 6.0] [0.3 0.2 0.08 1.0]
                                [{:type :physics :dynamic false}]))
        (conj! entities (entity-full "baby-gorilla-den" [15.0 0.0 10.0] [4.0 2.5 4.0]
                                      (sphere-mesh [0.2 0.15 0.08 0.8] 2.5)
                                      [{:type :trigger :kind "story" :data "Ko-gorira ga maigo de naiteiru..."}]))
        (conj! entities (entity "burnt-zone" [(* arena-size 0.35) 0.0 (* arena-size 0.25)] [15.0 0.1 15.0] [0.15 0.1 0.05 1.0] [])))

      ;; default: generic pillars
      (dotimes [i 4]
        (let [angle (* (/ (double i) 4.0) TAU)
              r (* arena-size 0.25)]
          (conj! entities
                 (entity (str "pillar-" i) [(* r (fcos angle)) 1.5 (* r (fsin angle))] [1.0 3.0 1.0] [0.5 0.5 0.55 1.0] [])))))

    ;; NPC (guard/merchant for RPG, announcer for arcade)
    (conj! entities
           (entity "npc-1" [(* arena-size 0.3) 0.8 0.0] [1.0 1.6 1.0] [0.9 0.7 0.1 1.0]
                   [{:type :npc
                     :name (case genre
                             :rpg "Blacksmith"
                             :simulation "Advisor"
                             :brainrot "Rizz Master"
                             :chase "Ko-Gorira"
                             "Announcer")
                     :waypoints [[(* arena-size 0.3) 0.8 -5.0] [(* arena-size 0.3) 0.8 5.0]]}]))

    ;; Portal back to hub
    (conj! entities
           (entity "portal-hub" [0.0 1.5 (* arena-size 0.45)] [3.0 3.0 0.5] [0.5 0.0 1.0 0.8]
                   [{:type :portal :target-island "hub"}]))

    ;; Items (HP potion + gems)
    (conj! entities
           (entity "potion-1" [-3.0 0.3 -3.0] [0.4 0.6 0.4] [1.0 0.2 0.3 1.0]
                   [{:type :item :item-id "potion-hp" :item-name "Health Potion"}]))
    (conj! entities
           (entity "gem-1" [3.0 0.3 3.0] [0.5 0.5 0.5] [0.0 0.5 1.0 1.0]
                   [{:type :item :item-id "gem-blue" :item-name "Blue Gem"}]))

    {:context nil :ld-type nil :ld-id nil
     :name (:title game)
     :genre (name genre)
     :description (:description game)
     :max-players max-players
     :characters []
     :entities (persistent! entities)
     :ambient-color [0.03 0.03 0.05]
     :sun-direction [-1.0 -2.0 -1.0]
     :sun-intensity 3.0
     :camera-mode nil
     :layers []
     :viewport nil
     :sun-color nil
     :point-lights []
     :atmosphere nil
     :postfx-preset nil
     :ibl-env-map nil
     :shadow nil}))

;; ---------------------------------------------------------------------
;; Batch generation
;; ---------------------------------------------------------------------

(declare brainrot-characters)

(defn generate-all-islands
  "Generate `[scene game]` pairs for all games, with JSON-LD metadata
  stamped on the scene."
  []
  (mapv (fn [game]
          (let [scene (-> (game-to-island game)
                           (assoc :context "https://etzhayyim.com/ns/kami/scene"
                                  :ld-type "IslandScene"
                                  :ld-id (str "urn:kami:island:" (:slug game))))]
            [scene game]))
        (godot-game-catalog)))

(defn generate-brainrot-islands
  "Generate `[scene game]` pairs for brainrot-only games, with characters attached."
  []
  (let [brainrot-chars (brainrot-characters)]
    (mapv (fn [game]
            (let [scene (-> (game-to-island game)
                             (assoc :context "https://etzhayyim.com/ns/kami/scene"
                                    :ld-type "IslandScene"
                                    :ld-id (str "urn:kami:island:" (:slug game))))
                  chars (filterv (fn [c]
                                   (or (some #(= % (:slug game)) (:spawn-points c))
                                       (some #(= % "all") (:spawn-points c))))
                                 brainrot-chars)]
              [(assoc scene :characters chars) game]))
          (filterv #(= :brainrot (:genre %)) (godot-game-catalog)))))

;; =============================================================================
;; Brainrot Evolution — Pokémon-style multi-stage definitions
;; =============================================================================

(def brainrot-max-stage
  "`.max_stage()` from kami-game's `brainrot_mesh.rs` (same deleted PR, not
  otherwise ported here — see namespace docstring)."
  {:skibidi 3 :sigma 4 :ohio 2 :grimace 3 :rizz 2 :fanum 3})

(defn evo-stage
  [stage name social domain scale body accessory]
  {:stage stage :form-name name :social-gate social :domain-gate domain
   :scale scale :body-override body :accessory-override accessory})

(defn brainrot-evolution
  [character-id character-enum stages]
  {:character-id character-id :character-enum character-enum :stages stages})

(defn brainrot-evolution-chains
  "All brainrot evolution chains."
  []
  [(brainrot-evolution
    "char-skibidi-commander" :skibidi
    [(evo-stage 0 "Mini Toilet" "" "" 0.6 nil nil)
     (evo-stage 1 "Skibidi Soldier" "kyu4" "boss_kills>=50" 1.0 "stocky" "sunglasses")
     (evo-stage 2 "Skibidi Tank" "kyu1" "a2a_raids>=10" 1.8 "stocky" "sunglasses")
     (evo-stage 3 "Skibidi Titan" "dan3" "all_brainrot_a2a" 3.0 "stocky" "mask")])
   (brainrot-evolution
    "char-sigma-male" :sigma
    [(evo-stage 0 "Scrawny Kid" "" "" 0.7 "slim" nil)
     (evo-stage 1 "Gym Bro" "kyu5" "streak>=7" 1.0 "athletic" "sunglasses")
     (evo-stage 2 "Sigma Male" "kyu3" "streak>=30,pr>=10" 1.1 "athletic" "sunglasses")
     (evo-stage 3 "Gigachad" "kyu1" "agents_trained>=5" 1.3 "stocky" "sunglasses")
     (evo-stage 4 "Sigma Ascended" "dan5" "streak>=100,all_follow" 1.5 "tall" nil)])
   (brainrot-evolution
    "char-ohio-boss" :ohio
    [(evo-stage 0 "Ohio Anomaly" "" "" 1.0 "tall" "mask")
     (evo-stage 1 "Ohio Nightmare" "kyu3" "anomaly_types>=12" 2.0 "tall" "mask")
     (evo-stage 2 "Ohio Eldritch" "dan2" "survival_rate<20,all_export" 4.0 "tall" "mask")])
   (brainrot-evolution
    "char-grimace" :grimace
    [(evo-stage 0 "Purple Puddle" "" "" 0.5 "stocky" nil)
     (evo-stage 1 "Grimace Blob" "kyu4" "recipes>=5" 1.0 "stocky" nil)
     (evo-stage 2 "Grimace Tide" "kyu1" "poison_supply>=10" 1.8 "stocky" nil)
     (evo-stage 3 "Grimace Singularity" "dan4" "all_agent_chaos_event" 2.5 "stocky" nil)])
   (brainrot-evolution
    "char-rizz-master" :rizz
    [(evo-stage 0 "Awkward Kid" "" "" 0.8 "slim" nil)
     (evo-stage 1 "Rizz Master" "kyu3" "like_rate>=30" 1.0 "slim" "earring")
     (evo-stage 2 "Rizz Sensei" "dan1" "agents_promoted>=5" 1.1 "slim" "earring")])
   (brainrot-evolution
    "char-fanum" :fanum
    [(evo-stage 0 "Street Kid" "" "" 0.8 "average" "hat")
     (evo-stage 1 "Tax Collector" "kyu4" "food_types>=10" 1.0 "average" "hat")
     (evo-stage 2 "Tax Baron" "kyu1" "all_supply_chain" 1.1 "stocky" "hat")
     (evo-stage 3 "Fanum Mogul" "dan3" "economy_volume_threshold,redistribute>=100" 1.4 "stocky" "hat")])])

;; ---------------------------------------------------------------------
;; Brainrot character roster
;; ---------------------------------------------------------------------

(defn character-appearance
  [{:keys [face skin-hue skin-lightness eye eye-color-hue eye-size nose mouth mouth-size
           hair hair-color-hue hair-color-lightness body height accessory1 accessory2]}]
  {:face face :skin-hue skin-hue :skin-lightness skin-lightness :eye eye
   :eye-color-hue eye-color-hue :eye-size eye-size :nose nose :mouth mouth
   :mouth-size mouth-size :hair hair :hair-color-hue hair-color-hue
   :hair-color-lightness hair-color-lightness :body body :height height
   :accessory1 accessory1 :accessory2 accessory2})

(defn character-def
  [{:keys [ld-type id name role appearance spawn-points]}]
  {:ld-type ld-type :id id :name name :role role :appearance appearance :spawn-points spawn-points})

(defn brainrot-characters
  "Brainrot character roster."
  []
  [(character-def
    {:ld-type "KamiCharacter" :id "char-skibidi-commander" :name "Skibidi Commander" :role "boss"
     :appearance (character-appearance
                  {:face "square" :skin-hue 0.08 :skin-lightness 0.65 :eye "wide" :eye-color-hue 0.1
                   :eye-size 1.4 :nose "large" :mouth "grin" :mouth-size 1.5 :hair "buzz"
                   :hair-color-hue 0.08 :hair-color-lightness 0.2 :body "stocky" :height 1.15
                   :accessory1 "sunglasses" :accessory2 "none"})
     :spawn-points ["skibidi" "all"]})
   (character-def
    {:ld-type "KamiCharacter" :id "char-sigma-male" :name "Sigma Grindset" :role "npc"
     :appearance (character-appearance
                  {:face "diamond" :skin-hue 0.06 :skin-lightness 0.55 :eye "narrow" :eye-color-hue 0.6
                   :eye-size 0.8 :nose "pointed" :mouth "neutral" :mouth-size 0.7 :hair "spiky"
                   :hair-color-hue 0.0 :hair-color-lightness 0.1 :body "athletic" :height 1.1
                   :accessory1 "sunglasses" :accessory2 "none"})
     :spawn-points ["sigma" "all"]})
   (character-def
    {:ld-type "KamiCharacter" :id "char-ohio-boss" :name "Ohio Final Boss" :role "boss"
     :appearance (character-appearance
                  {:face "long" :skin-hue 0.0 :skin-lightness 0.3 :eye "cat" :eye-color-hue 0.0
                   :eye-size 1.3 :nose "flat" :mouth "wide" :mouth-size 1.4 :hair "mohawk"
                   :hair-color-hue 0.0 :hair-color-lightness 0.0 :body "tall" :height 1.2
                   :accessory1 "mask" :accessory2 "none"})
     :spawn-points ["ohio"]})
   (character-def
    {:ld-type "KamiCharacter" :id "char-grimace" :name "Grimace" :role "boss"
     :appearance (character-appearance
                  {:face "round" :skin-hue 0.75 :skin-lightness 0.4 :eye "round" :eye-color-hue 0.75
                   :eye-size 1.2 :nose "button" :mouth "smile" :mouth-size 1.3 :hair "bald"
                   :hair-color-hue 0.75 :hair-color-lightness 0.3 :body "stocky" :height 1.15
                   :accessory1 "none" :accessory2 "none"})
     :spawn-points ["grimace"]})
   (character-def
    {:ld-type "KamiCharacter" :id "char-rizz-master" :name "Rizz Master" :role "npc"
     :appearance (character-appearance
                  {:face "heart" :skin-hue 0.07 :skin-lightness 0.6 :eye "almond" :eye-color-hue 0.35
                   :eye-size 1.1 :nose "small" :mouth "smile" :mouth-size 1.2 :hair "wavy"
                   :hair-color-hue 0.08 :hair-color-lightness 0.3 :body "slim" :height 1.05
                   :accessory1 "earring" :accessory2 "none"})
     :spawn-points ["rizz" "all"]})
   (character-def
    {:ld-type "KamiCharacter" :id "char-fanum" :name "Fanum Tax Collector" :role "npc"
     :appearance (character-appearance
                  {:face "oval" :skin-hue 0.07 :skin-lightness 0.45 :eye "droopy" :eye-color-hue 0.08
                   :eye-size 1.0 :nose "medium" :mouth "pout" :mouth-size 1.1 :hair "afro"
                   :hair-color-hue 0.0 :hair-color-lightness 0.15 :body "average" :height 1.0
                   :accessory1 "hat" :accessory2 "none"})
     :spawn-points ["fanum" "all"]})
   ;; YORO mascot — green blob with chef hat, big blue eyes, toothy grin
   (character-def
    {:ld-type "KamiCharacter" :id "char-yoro-mascot" :name "YORO" :role "mascot"
     :appearance (character-appearance
                  {:face "round" :skin-hue 0.33 :skin-lightness 0.55 :eye "round" :eye-color-hue 0.58
                   :eye-size 1.4 :nose "button" :mouth "grin" :mouth-size 1.5 :hair "bald"
                   :hair-color-hue 0.0 :hair-color-lightness 0.9 :body "stocky" :height 0.9
                   :accessory1 "hat" :accessory2 "none"})
     :spawn-points ["yoro" "all"]})])
