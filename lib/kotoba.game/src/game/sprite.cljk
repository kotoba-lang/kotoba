(ns game.sprite
  "Sprite2D: 2D sprite representation for side-scroll mode.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/sprite.rs`.
  Converts to a SceneEntity (Plane mesh + material) for rendering via the
  existing PBR pipeline (that conversion lives outside this cluster).")

;; Sprite2D: {:position [x y] :size [w h] :layer :color [r g b a]
;;            :texture-key :flip-x? :frame :frames-total}
;; Layer2D: {:name :z :parallax :color}
;; Viewport2D: {:width :height :pixels-per-unit}

(defn sprite2d-default
  []
  {:position [0.0 0.0]
   :size [1.0 1.0]
   :layer 0.0
   :color [1.0 1.0 1.0 1.0]
   :texture-key nil
   :flip-x? false
   :frame 0
   :frames-total 1})

(defn viewport2d-default
  []
  {:width 800.0
   :height 450.0
   :pixels-per-unit 32.0})

(defn parallax-offset
  "Apply parallax offset to an entity's X position based on camera and
  layer parallax factor."
  [entity-x camera-x parallax]
  (+ camera-x (* (- entity-x camera-x) parallax)))
