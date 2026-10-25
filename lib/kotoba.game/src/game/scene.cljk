(ns game.scene
  "Restored from kami-game/src/scene.rs (kotoba-lang/kami-engine, deleted in PR #82),
  as part of the Rust→CLJC restoration (ADR-2607010930, com-junkawasaki/root).

  Island scene definition: JSON-LD-compatible format for LLM generation +
  Engine loading (LLM generates this data → save-scene API → R2 → Engine
  loads and spawns). All types are plain CLJC maps with keyword keys; the
  original `@context`/`@type`/`@id` JSON-LD fields are optional keys here
  too. The original round-trips scenes through `serde_json`; since this repo
  is zero-dependency (no JSON lib available), `scene->edn`/`edn->scene`
  round-trip via the native EDN reader/printer instead — semantically the
  same guarantee (\"a scene value survives a serialize/deserialize cycle\"),
  just over EDN instead of JSON. A hand-rolled JSON codec can be swapped in
  later without changing the data shape.")

;; ---------------------------------------------------------------------------
;; Defaults (ported from the `default_*` fn helpers used by #[serde(default = ...)])
;; ---------------------------------------------------------------------------

(def default-fog-height-falloff 2.0)
(def default-cascade-count 2)
(def default-shadow-softness 2.0)
(def default-shadow-bias 0.005)
(def default-quat [0.0 0.0 0.0 1.0])
(def default-scale [1.0 1.0 1.0])
(def default-blend-radius 0.1)
(def default-parallax 1.0)
(def default-viewport-width 800.0)
(def default-viewport-height 450.0)
(def default-pixels-per-unit 32.0)

;; ---------------------------------------------------------------------------
;; Mesh refs (tagged maps; `:type` mirrors the Rust `#[serde(tag = "type")]` enum)
;; ---------------------------------------------------------------------------

(defn mesh-cube [color] {:type "cube" :color color})
(defn mesh-sphere [color radius] {:type "sphere" :color color :radius radius})
(defn mesh-asset [asset-id blob-key] {:type "asset" :asset-id asset-id :blob-key blob-key})
(defn mesh-plane [color width depth subdivisions]
  {:type "plane" :color color :width width :depth depth :subdivisions subdivisions})
(defn mesh-voxel [chunk-data palette] {:type "voxel" :chunk-data chunk-data :palette palette})
(defn mesh-terrain [heightmap width depth height-scale]
  {:type "terrain" :heightmap heightmap :width width :depth depth :height-scale height-scale})
(defn mesh-gaussian-splat [splat-key] {:type "gaussian_splat" :splat-key splat-key})
(defn mesh-cylinder [color h r1 r2] {:type "cylinder" :color color :h h :r1 r1 :r2 r2})
(defn mesh-scad [code] {:type "scad" :code code})
(defn mesh-hex-prism [color radius height] {:type "hex_prism" :color color :radius radius :height height})
(defn mesh-hex-grid [color rings hex-radius hex-height spacing]
  {:type "hex_grid" :color color :rings rings :hex-radius hex-radius :hex-height hex-height :spacing spacing})
(defn mesh-pipe [color radius thickness height segments]
  {:type "pipe" :color color :radius radius :thickness thickness :height height :segments segments})
(defn mesh-building [color footprint height] {:type "building" :color color :footprint footprint :height height})
(defn mesh-character-model
  ([blob-key] (mesh-character-model blob-key []))
  ([blob-key material-overrides] {:type "character_model" :blob-key blob-key :material-overrides material-overrides}))
(defn mesh-sdf-character [body-parts resolution] {:type "sdf_character" :body-parts body-parts :resolution resolution})

;; ---------------------------------------------------------------------------
;; Component defs (tagged maps)
;; ---------------------------------------------------------------------------

(def component-player-spawn {:type "player_spawn"})
(defn component-npc [name waypoints] {:type "npc" :name name :waypoints waypoints})
(defn component-portal [target-island] {:type "portal" :target-island target-island})
(defn component-item [item-id item-name] {:type "item" :item-id item-id :item-name item-name})
(defn component-physics [dynamic?] {:type "physics" :dynamic dynamic?})
(defn component-trigger [kind data] {:type "trigger" :kind kind :data data})

;; ---------------------------------------------------------------------------
;; Supporting defs
;; ---------------------------------------------------------------------------

(defn scene-layer
  ([name] (scene-layer name 0.0 default-parallax nil))
  ([name z parallax color] {:name name :z z :parallax parallax :color color}))

(defn point-light-def
  [id position color intensity range
   & {:keys [inner-cone outer-cone direction cast-shadow]
      :or {inner-cone 0.0 outer-cone 0.0 direction nil cast-shadow false}}]
  {:id id :position position :color color :intensity intensity :range range
   :inner-cone inner-cone :outer-cone outer-cone :direction direction :cast-shadow cast-shadow})

(defn atmosphere-def
  [fog-color fog-density
   & {:keys [fog-height fog-height-falloff volumetric-intensity skybox-top skybox-bottom skybox-stars]
      :or {fog-height 0.0 fog-height-falloff default-fog-height-falloff
           volumetric-intensity 0.0 skybox-top nil skybox-bottom nil skybox-stars false}}]
  {:fog-color fog-color :fog-density fog-density :fog-height fog-height
   :fog-height-falloff fog-height-falloff :volumetric-intensity volumetric-intensity
   :skybox-top skybox-top :skybox-bottom skybox-bottom :skybox-stars skybox-stars})

(defn shadow-def
  [resolution & {:keys [cascades softness bias]
                 :or {cascades default-cascade-count softness default-shadow-softness bias default-shadow-bias}}]
  {:resolution resolution :cascades cascades :softness softness :bias bias})

(defn material-override-def
  ([mesh-name preset] (material-override-def mesh-name preset nil))
  ([mesh-name preset params] {:mesh-name mesh-name :preset preset :params params}))

(defn sdf-body-part-def
  [primitive position material-preset
   & {:keys [rotation scale radius height material-params blend-radius]
      :or {rotation default-quat scale default-scale radius 0.0 height 0.0
           material-params nil blend-radius default-blend-radius}}]
  {:primitive primitive :position position :rotation rotation :scale scale
   :radius radius :height height :material-preset material-preset
   :material-params material-params :blend-radius blend-radius})

(defn scene-viewport
  ([] (scene-viewport default-viewport-width default-viewport-height default-pixels-per-unit))
  ([width height pixels-per-unit] {:width width :height height :pixels-per-unit pixels-per-unit}))

;; ---------------------------------------------------------------------------
;; Character appearance / def
;; ---------------------------------------------------------------------------

(defn character-appearance
  [{:keys [face skin-hue skin-lightness eye eye-color-hue eye-size nose mouth mouth-size
           hair hair-color-hue hair-color-lightness body height accessory1 accessory2]}]
  {:face face :skin-hue skin-hue :skin-lightness skin-lightness :eye eye
   :eye-color-hue eye-color-hue :eye-size eye-size :nose nose :mouth mouth
   :mouth-size mouth-size :hair hair :hair-color-hue hair-color-hue
   :hair-color-lightness hair-color-lightness :body body :height height
   :accessory1 accessory1 :accessory2 accessory2})

(defn character-def
  [id name appearance & {:keys [ld-type role spawn-points] :or {ld-type nil role nil spawn-points []}}]
  {:ld-type ld-type :id id :name name :role role :appearance appearance :spawn-points spawn-points})

;; ---------------------------------------------------------------------------
;; EntityDef / IslandScene
;; ---------------------------------------------------------------------------

(defn entity-def
  [id position rotation scale mesh & {:keys [components layer] :or {components [] layer nil}}]
  {:id id :position position :rotation rotation :scale scale :mesh mesh
   :components components :layer layer})

(defn island-scene
  [name entities ambient-color sun-direction sun-intensity
   & {:keys [context ld-type ld-id genre description max-players characters
             sun-color camera-mode layers viewport point-lights atmosphere
             postfx-preset ibl-env-map shadow]
      :or {context nil ld-type nil ld-id nil genre nil description nil max-players nil
           characters [] sun-color nil camera-mode nil layers [] viewport nil
           point-lights [] atmosphere nil postfx-preset nil ibl-env-map nil shadow nil}}]
  {:context context :ld-type ld-type :ld-id ld-id :name name :genre genre
   :description description :max-players max-players :characters characters
   :entities entities :ambient-color ambient-color :sun-direction sun-direction
   :sun-intensity sun-intensity :sun-color sun-color :camera-mode camera-mode
   :layers layers :viewport viewport :point-lights point-lights
   :atmosphere atmosphere :postfx-preset postfx-preset :ibl-env-map ibl-env-map
   :shadow shadow})

;; ---------------------------------------------------------------------------
;; Demo island: ground + walls + NPCs + portal + items.
;; ---------------------------------------------------------------------------

(defn demo []
  (island-scene
   "Hub Island"
   [(entity-def "ground" [0.0 -0.5 0.0] [0.0 0.0 0.0 1.0] [50.0 1.0 50.0]
                (mesh-cube [0.3 0.5 0.3 1.0]))
    (entity-def "spawn-0" [0.0 1.0 0.0] [0.0 0.0 0.0 1.0] [1.0 1.0 1.0]
                (mesh-cube [0.2 0.6 1.0 1.0])
                :components [component-player-spawn (component-physics true)])
    (entity-def "spawn-1" [3.0 1.0 0.0] [0.0 0.0 0.0 1.0] [1.0 1.0 1.0]
                (mesh-cube [1.0 0.4 0.2 1.0])
                :components [component-player-spawn (component-physics true)])
    (entity-def "guard" [8.0 0.5 0.0] [0.0 0.0 0.0 1.0] [1.0 2.0 1.0]
                (mesh-cube [0.8 0.2 0.2 1.0])
                :components [(component-npc "Guard" [[8.0 0.5 -5.0] [8.0 0.5 5.0]])])
    (entity-def "merchant" [-5.0 0.5 5.0] [0.0 0.0 0.0 1.0] [1.0 2.0 1.0]
                (mesh-cube [0.9 0.7 0.1 1.0])
                :components [(component-npc "Merchant" [[-5.0 0.5 5.0] [-5.0 0.5 -3.0]])])
    (entity-def "portal-sub" [15.0 1.5 0.0] [0.0 0.0 0.0 1.0] [2.0 3.0 0.5]
                (mesh-cube [0.5 0.0 1.0 0.8])
                :components [(component-portal "sub-island-001")])
    (entity-def "item-gem" [-3.0 0.3 -2.0] [0.0 0.0 0.0 1.0] [0.5 0.5 0.5]
                (mesh-cube [0.0 0.5 1.0 1.0])
                :components [(component-item "gem-blue" "Blue Gem")])
    (entity-def "item-sword" [2.0 0.3 4.0] [0.0 0.0 0.0 1.0] [0.3 1.2 0.3]
                (mesh-cube [0.7 0.7 0.7 1.0])
                :components [(component-item "sword-iron" "Iron Sword")])
    (entity-def "item-potion" [-6.0 0.3 -4.0] [0.0 0.0 0.0 1.0] [0.4 0.6 0.4]
                (mesh-cube [1.0 0.2 0.3 1.0])
                :components [(component-item "potion-hp" "Health Potion")])]
   [0.03 0.03 0.05]
   [-1.0 -2.0 -1.0]
   3.0))

;; ---------------------------------------------------------------------------
;; EDN codec (stand-in for the original serde_json round-trip)
;; ---------------------------------------------------------------------------

(defn scene->edn-string [scene] (pr-str scene))

(defn edn-string->scene [s]
  #?(:clj (clojure.edn/read-string s)
     :cljs (cljs.reader/read-string s)))
