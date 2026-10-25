(ns game.quarry-scene
  "Quarry walk scene: Player state + input + physics + character mesh builder.

  Restored from kami-game's `quarry_scene.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Original comment: \"Pure Rust logic, no web-sys. Consumed by kami-web
  entry point which plumbs events and WebGPU commands.\" — this CLJC port
  preserves that: pure data + pure functions, no IO/GPU/WASM host calls.
  The original used `glam::{Mat4, Vec3}` and `bytemuck::{Pod, Zeroable}`
  (GPU vertex layout markers with no runtime behavior); here `Vec3` is a
  plain 3-vector (`[x y z]`), `Mat4` is a plain 16-element column-major
  vector matching glam's memory layout, and vertices are plain maps —
  local vec/mat math is implemented below rather than depending on glam."
  )

;; ---------------------------------------------------------------------
;; Character mesh (procedural humanoid from boxes)
;; ---------------------------------------------------------------------

(defn char-vertex
  [position normal color]
  {:position position :normal normal :color color})

(defn- box-corner
  [cx cy cz hx hy hz sx sy sz]
  [(+ cx (* sx hx)) (+ cy (* sy hy)) (+ cz (* sz hz))])

(defn- push-box
  "Append one box (6 faces x 4 verts, 6 indices/face) to `verts`/`idx`.
  Returns `[verts' idx']`."
  [verts idx cx cy cz sx sy sz color]
  (let [hx (* sx 0.5) hy (* sy 0.5) hz (* sz 0.5)
        corners [[(- cx hx) (- cy hy) (- cz hz)]
                 [(+ cx hx) (- cy hy) (- cz hz)]
                 [(+ cx hx) (+ cy hy) (- cz hz)]
                 [(- cx hx) (+ cy hy) (- cz hz)]
                 [(- cx hx) (- cy hy) (+ cz hz)]
                 [(+ cx hx) (- cy hy) (+ cz hz)]
                 [(+ cx hx) (+ cy hy) (+ cz hz)]
                 [(- cx hx) (+ cy hy) (+ cz hz)]]
        faces [[[0 1 2 3] [0.0 0.0 -1.0]]
               [[5 4 7 6] [0.0 0.0 1.0]]
               [[4 0 3 7] [-1.0 0.0 0.0]]
               [[1 5 6 2] [1.0 0.0 0.0]]
               [[3 2 6 7] [0.0 1.0 0.0]]
               [[4 5 1 0] [0.0 -1.0 0.0]]]]
    (reduce
     (fn [[verts idx] [corner-idx n]]
       (let [base (count verts)
             verts' (into verts (map (fn [i] (char-vertex (nth corners i) n color)) corner-idx))
             idx' (into idx [base (+ base 1) (+ base 2) base (+ base 2) (+ base 3)])]
         [verts' idx']))
     [verts idx]
     faces)))

(defn build-character-mesh
  "Build a procedural humanoid mesh (13 boxes, ~200 verts).
  Returns `{:vertices [...] :indices [...]}`."
  []
  (let [skin [0.78 0.66 0.55]
        cloth [0.42 0.44 0.50]
        pants [0.28 0.26 0.22]
        boots [0.15 0.13 0.10]
        pack [0.38 0.32 0.24]
        boxes [;; Head
               [0.0 1.72 0.0 0.22 0.26 0.22 skin]
               ;; Torso
               [0.0 1.30 0.0 0.46 0.56 0.26 cloth]
               ;; Backpack
               [0.0 1.30 -0.22 0.42 0.55 0.24 pack]
               ;; Arms (upper)
               [-0.32 1.30 0.0 0.16 0.38 0.16 cloth]
               [0.32 1.30 0.0 0.16 0.38 0.16 cloth]
               ;; Arms (lower)
               [-0.32 0.92 0.0 0.14 0.36 0.14 skin]
               [0.32 0.92 0.0 0.14 0.36 0.14 skin]
               ;; Legs (upper)
               [-0.14 0.70 0.0 0.20 0.48 0.22 pants]
               [0.14 0.70 0.0 0.20 0.48 0.22 pants]
               ;; Legs (lower)
               [-0.14 0.26 0.0 0.18 0.40 0.20 pants]
               [0.14 0.26 0.0 0.18 0.40 0.20 pants]
               ;; Boots
               [-0.14 0.04 0.03 0.20 0.12 0.32 boots]
               [0.14 0.04 0.03 0.20 0.12 0.32 boots]]]
    (let [[verts idx]
          (reduce (fn [[v i] [cx cy cz sx sy sz color]]
                    (push-box v i cx cy cz sx sy sz color))
                  [[] []]
                  boxes)]
      {:vertices verts :indices idx})))

;; ---------------------------------------------------------------------
;; Player state / constants
;; ---------------------------------------------------------------------

(def EYE-HEIGHT 1.72)
(def GRAVITY 15.0)
(def JUMP-VELOCITY 5.5)
(def WALK-SPEED 3.5)
(def SPRINT-MULT 1.8)

(defn default-player
  []
  {:x 0.0 :y 0.0 :z 0.0 :y-vel 0.0 :on-ground true
   :yaw 0.0 :pitch 0.0 :facing 0.0 :move-speed 0.0})

(defn default-input-state
  []
  {:forward false :back false :left false :right false :sprint false
   :jump-pressed false :toggle-fp false :mouse-dx 0.0 :mouse-dy 0.0 :wheel 0.0})

(def camera-modes #{:third-person :first-person})

(defn default-camera-state
  []
  {:mode :third-person :distance 5.0})

;; ---------------------------------------------------------------------
;; Physics tick
;; ---------------------------------------------------------------------

(defn- clamp
  [x lo hi]
  (max lo (min hi x)))

(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))
(def ^:private TAU (* 2.0 PI))

(defn tick-player
  "Advance player physics + input by `dt` seconds.
  `sample-h` is `(fn [x z] height)`, supplied by the host (heightmap cache).
  Returns `[player' input']` (both updated; `input'` clears one-shot
  fields — `mouse-dx`/`mouse-dy`/`jump-pressed` — matching the Rust
  original, which mutates `input` in place as it consumes deltas)."
  [player input sample-h dt world-bound]
  (let [yaw (- (:yaw player) (* (:mouse-dx input) 0.0025))
        pitch (clamp (- (:pitch player) (* (:mouse-dy input) 0.0025)) -1.3 1.3)
        fx (Math/sin yaw)
        fz (Math/cos yaw)
        rx (Math/cos yaw)
        rz (- (Math/sin yaw))
        [mx mz] (reduce
                 (fn [[mx mz] [pred dmx dmz]]
                   (if pred [(+ mx dmx) (+ mz dmz)] [mx mz]))
                 [0.0 0.0]
                 [[(:forward input) fx fz]
                  [(:back input) (- fx) (- fz)]
                  [(:left input) (- rx) (- rz)]
                  [(:right input) rx rz]])
        mag (Math/sqrt (+ (* mx mx) (* mz mz)))
        [mx mz] (if (pos? mag) [(/ mx mag) (/ mz mag)] [mx mz])
        sprint (if (:sprint input) SPRINT-MULT 1.0)
        speed (* WALK-SPEED sprint)
        x (+ (:x player) (* mx speed dt))
        z (+ (:z player) (* mz speed dt))
        move-speed (* mag speed)
        facing (if (> mag 0.01)
                 (let [target (Math/atan2 mx mz)
                       diff0 (- target (:facing player))
                       diff (loop [d diff0]
                              (cond (> d PI) (recur (- d TAU))
                                    (< d (- PI)) (recur (+ d TAU))
                                    :else d))]
                   (+ (:facing player) (* diff (min 1.0 (* dt 10.0)))))
                 (:facing player))
        x (clamp x (- world-bound) world-bound)
        z (clamp z (- world-bound) world-bound)
        ground (sample-h x z)
        [y y-vel on-ground] (if (not (:on-ground player))
                               (let [y-vel' (- (:y-vel player) (* GRAVITY dt))
                                     y' (+ (:y player) (* y-vel' dt))]
                                 (if (<= y' ground)
                                   [ground 0.0 true]
                                   [y' y-vel' false]))
                               (if (:jump-pressed input)
                                 [ground JUMP-VELOCITY false]
                                 [ground 0.0 true]))]
    [(assoc player
            :x x :y y :z z :y-vel y-vel :on-ground on-ground
            :yaw yaw :pitch pitch :facing facing :move-speed move-speed)
     (assoc input :mouse-dx 0.0 :mouse-dy 0.0 :jump-pressed false)]))

;; ---------------------------------------------------------------------
;; Camera
;; ---------------------------------------------------------------------

(defn- vec3+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])

(defn camera-matrices
  "Compute `[eye target]` positions (plain `[x y z]` vecs) for current
  camera mode."
  [player cam sample-h]
  (case (:mode cam)
    :first-person
    (let [ey (+ (:y player) EYE-HEIGHT)
          eye [(:x player) ey (:z player)]
          look-x (* (Math/sin (:yaw player)) (Math/cos (:pitch player)))
          look-y (Math/sin (:pitch player))
          look-z (* (Math/cos (:yaw player)) (Math/cos (:pitch player)))
          target (vec3+ eye [look-x look-y look-z])]
      [eye target])

    :third-person
    (let [d (:distance cam)
          up 2.2
          cx (- (:x player) (* (Math/sin (:yaw player)) d))
          cz (- (:z player) (* (Math/cos (:yaw player)) d))
          cy0 (+ (:y player) EYE-HEIGHT up (* (Math/sin (:pitch player)) 3.0))
          ground-at-cam (sample-h cx cz)
          cy (if (< cy0 (+ ground-at-cam 1.5)) (+ ground-at-cam 1.5) cy0)
          eye [cx cy cz]
          target [(:x player) (+ (:y player) (* EYE-HEIGHT 0.7)) (:z player)]]
      [eye target])))

;; ---------------------------------------------------------------------
;; Model matrix (glam column-major Mat4, as a flat 16-element vector)
;; ---------------------------------------------------------------------

(defn mat4-identity
  []
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   0.0 0.0 0.0 1.0])

(defn mat4-translation
  [[tx ty tz]]
  [1.0 0.0 0.0 0.0
   0.0 1.0 0.0 0.0
   0.0 0.0 1.0 0.0
   tx ty tz 1.0])

(defn mat4-rotation-y
  [angle]
  (let [s (Math/sin angle) c (Math/cos angle)]
    [c 0.0 (- s) 0.0
     0.0 1.0 0.0 0.0
     s 0.0 c 0.0
     0.0 0.0 0.0 1.0]))

(defn mat4-mul
  "Column-major 4x4 matrix multiply, `a * b` (matches glam's `Mul`)."
  [a b]
  (vec
   (for [col (range 4)
         row (range 4)]
     (reduce +
             (for [k (range 4)]
               (* (nth a (+ (* k 4) row)) (nth b (+ (* col 4) k))))))))

(defn character-model-matrix
  "Model matrix for character (translate + rotate around Y by facing)."
  [player]
  (mat4-mul (mat4-translation [(:x player) (:y player) (:z player)])
            (mat4-rotation-y (:facing player))))
