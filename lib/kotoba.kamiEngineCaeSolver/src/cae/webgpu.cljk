(ns cae.webgpu
  "Browser renderer and real-time reference simulations, driven directly by CLJS."
  (:require [cae.high-fidelity]
            [cae.solver :as solver]
            [i18n.core :as i18n]
            [i18n.messages :refer [embed-catalog] :include-macros true]))

(i18n/register! :en (embed-catalog "i18n/messages/en.edn"))
(i18n/register! :ja (embed-catalog "i18n/messages/ja.edn"))

(def scene-keys
  [:scene/cfd :scene/fem :scene/process :scene/materials :scene/em :scene/production
   :scene/fvm :scene/rans :scene/amr :scene/thermo :scene/em-fem :scene/contact
   :scene/fracture :scene/mpi :scene/quality])

(def action-keys
  [:action/inlet :action/load :action/heat :action/nucleation :action/torque
   :action/job :action/pressure :action/turbulence :action/refinement :action/thermal
   :action/current :action/contact :action/crack :action/halo :action/mesh])

(def scene-labels
  ["CFD · flow / combustion" "FEM · cantilever beam" "Process · weld / cast / roll"
   "Materials · microstructure" "EM · motor / induction" "Production · flow line"
   "FVM · Sod shock tube" "RANS · k–ε turbulence" "AMR · adaptive mesh"
   "Thermo-mechanical · coupled bar" "EM FEM · field mesh" "Contact · 3D friction"
   "Fracture · crack criterion" "MPI · partitions / halo" "FEM mesh · TRI3 / TET4 quality"])

(def colors
  {:cyan [0.04 0.85 0.68] :blue [0.10 0.42 0.95] :orange [1.0 0.35 0.12]
   :gold [1.0 0.75 0.12] :purple [0.62 0.28 0.95] :white [0.75 0.88 0.95]})

(defn- tr [k] (i18n/t k))

(defn- localize-static! []
  (set! (.-lang (.-documentElement js/document)) (name (i18n/locale)))
  (doseq [el (array-seq (.querySelectorAll js/document "[data-i18n]"))]
    (set! (.-textContent el) (tr (keyword (.. el -dataset -i18n))))))

(defn- initial-fvm []
  (solver/solve {:solver {:kind :fvm-compressible} :cells 18 :dx-m 0.05
                 :dt-s 1.0e-4 :steps 0 :initial-condition :sod-shock-tube}))

(defn- initial-simulation []
  {:time 0.0 :steps 0 :running? true :speed 1.0 :fvm (initial-fvm)
   :action {:x 0.0 :y 0.0 :strength 0.0 :count 0 :active? false}})

(defn- advance-simulation [sim scene dt]
  (let [dt (* dt (:speed sim)) sim (-> sim (update :time + dt) (update :steps inc)
                                       (update-in [:action :strength] #(max 0 (- % (* dt 0.16)))))]
    (if (= scene 6)
      (let [fvm (solver/solve {:solver {:kind :fvm-compressible} :cells 18 :dx-m 0.05
                               :dt-s (min 2.0e-4 (* dt 0.008)) :steps 1
                               :initial-state (get-in sim [:fvm :state])})]
        (assoc sim :fvm fvm))
      sim)))

(defn- telemetry [scene {:keys [time steps fvm action]}]
  (let [wave (js/Math.sin (* time 2.0)) suffix (str " · " (tr (nth action-keys scene)) "=" (.toFixed (:strength action) 2))]
    (str
    (case scene
      0 (str "u=" (.toFixed (+ 1.4 (* 0.25 wave)) 2) " m/s · advective particles")
      1 (str "tip=" (.toFixed (* 6.0 wave) 2) " mm · damped mode")
      2 (str "heat source x=" (.toFixed (* 2.4 (js/Math.sin time)) 2) " m")
      3 (str "phase fraction=" (.toFixed (- 1 (js/Math.exp (* -0.22 time))) 3))
      4 (str "rotor=" (.toFixed (mod (* time 57.3) 360) 1) "° · rotating field")
      5 (str "job=" (mod (quot steps 35) 4) " · conveyor event step " steps)
      6 (str "FVM step " steps " · ρL-ρR=" (.toFixed (- (first (:density-profile fvm)) (last (:density-profile fvm))) 3))
      7 (str "k=" (.toFixed (+ 0.55 (* 0.12 wave)) 3) " m²/s² · vortex transport")
      8 (str "error front=" (.toFixed (+ 0.5 (* 0.5 wave)) 3) " · h-refinement")
      9 (str "ΔT=" (.toFixed (+ 45 (* 25 (js/Math.sin (* time 0.35)))) 1) " K · σth coupled")
      10 (str "B=" (.toFixed (+ 0.002 (* 0.001 wave)) 4) " T · field phase")
      11 (str (if (pos? wave) "sliding" "sticking") " · Coulomb μ=0.5")
      12 (str "K/Kc=" (.toFixed (+ 0.72 (* 0.28 (min 1 (/ time 8)))) 3) " · crack growth")
      13 (str "rank " (mod (quot steps 24) 4) " halo exchange · message " steps)
      14 (str "min V=" (.toFixed (+ 0.018 (* 0.004 wave)) 4) " m³ · quality monitor")
      "reference simulation") suffix)))

(defn- push-vertex! [out [x y z] [r g b]]
  (swap! out into [x y z r g b]))

(defn- triangle! [out a b c color]
  (doseq [p [a b c c b a]] (push-vertex! out p color)))

(defn- cube! [out x y z sx sy sz color]
  (let [x0 (- x (/ sx 2)) x1 (+ x (/ sx 2)) y0 (- y (/ sy 2)) y1 (+ y (/ sy 2))
        z0 (- z (/ sz 2)) z1 (+ z (/ sz 2))
        faces [[[x0 y0 z1] [x1 y0 z1] [x1 y1 z1] [x0 y1 z1]]
               [[x1 y0 z0] [x0 y0 z0] [x0 y1 z0] [x1 y1 z0]]
               [[x0 y1 z1] [x1 y1 z1] [x1 y1 z0] [x0 y1 z0]]
               [[x0 y0 z0] [x1 y0 z0] [x1 y0 z1] [x0 y0 z1]]
               [[x1 y0 z1] [x1 y0 z0] [x1 y1 z0] [x1 y1 z1]]
               [[x0 y0 z0] [x0 y0 z1] [x0 y1 z1] [x0 y1 z0]]]]
    (doseq [[a b c d] faces] (triangle! out a b c color) (triangle! out a c d color))))

(defn- tetra! [out x y z size color]
  (let [a [x (+ y size) z] b [(- x size) (- y size) (+ z size)]
        c [(+ x size) (- y size) (+ z size)] d [x (- y size) (- z size)]]
    (doseq [[p q r] [[a b c] [a c d] [a d b] [b d c]]] (triangle! out p q r color))))

(defn- scene-geometry [kind time sim]
  (let [v (atom []) c colors {:keys [x y strength]} (:action sim)
        time (+ time (* strength 0.32)) wave (js/Math.sin (+ (* time 2.0) (* x strength)))]
    (case kind
      0 (do (cube! v 0 0 0 5.8 1.5 1.5 (:blue c))
            (doseq [i (range 6) :let [x (- (mod (+ (* i 1.05) (* time 1.4)) 6.0) 3.0)]]
              (cube! v x (* 0.25 (js/Math.sin (+ time i))) 0 0.25 0.25 0.25 (:cyan c)))
            (cube! v -3.5 0 0 0.3 2.6 2.6 (:white c)))
      1 (do (cube! v -2 -1 0 0.8 2.5 1.2 (:white c))
            (doseq [i (range 12) :let [q (/ i 11) x (+ -1.65 (* q 4.2)) y (+ 0.1 (* wave 0.6 q q))]]
              (cube! v x y 0 0.36 0.3 0.65 (:cyan c)))
            (cube! v 2.55 (+ -0.8 (* wave 0.6)) 0 0.3 1.6 0.3 (:orange c)))
      2 (do (doseq [x [-2 0 2]] (cube! v x -0.7 0 0.7 1.4 1.4 (:orange c)))
            (cube! v 0 0.35 0 5.4 0.25 1.2 (:gold c))
            (cube! v (* 2.4 (js/Math.sin time)) 0.8 0 0.8 0.18 0.8 (:cyan c)))
      3 (doseq [x (range 4) y (range 3) z (range 3) :let [phase (- 1 (js/Math.exp (* -0.22 time)))]]
          (cube! v (* (- x 1.5) 0.65) (* (- y 1) 0.65) (* (- z 1) 0.65) 0.3 0.3 0.3
                 [(+ 0.2 (* phase 0.7)) (+ 0.35 (* (- 1 phase) 0.3)) (+ 0.45 (* (- 1 phase) 0.45))]))
      4 (do (cube! v 0 0 0 1.3 2.3 1.3 (:purple c))
            (doseq [i (range 12) :let [a (+ time (/ (* i js/Math.PI) 6))]]
              (cube! v (* (js/Math.cos a) 1.5) 0 (* (js/Math.sin a) 1.5) 0.25 1 0.25 (:cyan c)))
            (cube! v 0 0 0 3.8 0.12 0.12 (:gold c)))
      5 (do (doseq [i (range 4)] (cube! v (+ -2.4 (* i 1.6)) -0.5 0 1 1.2 1.3
                                        [(+ 0.1 (* i 0.12)) 0.45 (- 0.8 (* i 0.08))])
                                  (cube! v (- (mod (+ (* i 1.6) (* time 0.8)) 6.4) 3.2) 0.35 0 0.35 0.35 0.35 (:gold c)))
            (cube! v 0 -1.2 0 6 0.12 1.5 (:white c)))
      6 (let [profile (get-in sim [:fvm :density-profile]) gradients (mapv #(js/Math.abs (- %1 %2)) profile (rest profile))
              shock (inc (first (apply max-key second (map-indexed vector gradients))))]
          (doseq [i (range 18) :let [rho (nth profile i) h (+ 0.25 (* rho 1.55))]]
            (cube! v (+ -3.4 (* i 0.4)) (+ -1 (/ h 2)) 0 0.34 h 1.4 [(- 1 rho) 0.35 rho]))
          (cube! v (+ -3.4 (* shock 0.4)) 0.2 0 0.1 2.6 1.7 (:gold c)))
      7 (do (cube! v 0 -1.35 0 7 0.15 3 (:white c)) (cube! v 0 1.35 0 7 0.15 3 (:white c))
            (doseq [i (range 18) :let [a (+ (* time 2.4) (* i 0.72)) r (+ 0.45 (* i 0.04))]]
              (cube! v (+ -3 (* i 0.35)) (* (js/Math.sin a) r) (* (js/Math.cos a) r) 0.18 0.18 0.18
                     (if (odd? i) (:cyan c) (:purple c)))))
      8 (let [front (+ 2 (* 2 wave))]
          (doseq [x (range 4) z (range 3)] (cube! v (+ -2.7 (* x 0.7)) -0.65 (- (* z 0.7) 0.7) 0.58 0.58 0.58 (:blue c)))
          (doseq [x (range 8) z (range 5)] (cube! v (+ 0.1 (* x 0.38)) -0.65 (- (* z 0.38) 0.76) 0.28 0.28 0.28 (if (< x front) (:gold c) (:cyan c))))
            (tetra! v 0 0.65 0 0.55 (:orange c)))
      9 (do (doseq [i (range 15) :let [x (+ -3.2 (* i 0.46)) heat (* (+ 0.55 (* 0.35 (js/Math.sin (* time 0.7)))) (- 1 (/ (js/Math.abs (- i 7)) 7))) y (* heat 0.35 (js/Math.sin (/ (* i js/Math.PI) 14)))]]
              (cube! v x y 0 0.42 0.5 0.8 [(+ 0.08 (* heat 0.92)) (- 0.72 (* heat 0.42)) (- 0.78 (* heat 0.66))]))
            (cube! v -3.65 0 0 0.35 2.4 1.5 (:white c)))
      10 (do (doseq [x (range 7) z (range 7)] (tetra! v (* (- x 3) 0.55) -0.9 (* (- z 3) 0.55) 0.18 [(+ 0.1 (* x 0.08)) (+ 0.25 (* z 0.07)) 0.85]))
             (doseq [i (range 16) :let [a (+ (* time 1.8) (/ (* i js/Math.PI) 8))]] (cube! v (* (js/Math.cos a) 1.45) 0.55 (* (js/Math.sin a) 1.45) 0.18 0.65 0.18 (:gold c)))
             (cube! v 0 0.55 0 0.55 1.4 0.55 (:purple c)))
      11 (do (cube! v -0.35 -0.85 0 4.8 1.1 2.3 (:blue c)) (cube! v (+ 0.35 (* wave 0.55)) 0.45 0 4.8 1.1 2.3 (:orange c))
             (doseq [i (range 7)] (cube! v (+ -1.6 (* i 0.55)) -0.18 0 0.18 0.18 1.7 (:gold c))) (cube! v 2.9 0.45 0 1.3 0.16 0.16 (:cyan c)))
      12 (let [gap (+ 0.12 (* 0.45 (min 1 (/ time 8))))]
           (cube! v (- -1.6 gap) 0 0 3.1 2.8 0.7 (:blue c)) (cube! v (+ 1.6 gap) 0 0 3.1 2.8 0.7 (:blue c))
             (cube! v 0 1.05 0 0.18 0.7 0.82 (:orange c)) (tetra! v 0 0.55 0 0.45 (:gold c)) (cube! v 0 -1.05 0 0.18 0.7 0.82 (:orange c)))
      13 (doseq [r (range 4) :let [active (mod (quot (:steps sim) 24) 4) cs [(:blue c) (:cyan c) (:purple c) (:orange c)]]]
           (cube! v (+ -2.7 (* r 1.8)) 0 0 1.45 1.7 2.2 (if (= r active) (:gold c) (nth cs r)))
           (when (< r 3) (cube! v (+ -1.8 (* r 1.8)) 0 0 0.18 2.15 2.55 (:gold c))))
      14 (do (doseq [i (range 10) :let [cs [(:blue c) (:cyan c) (:purple c) (:orange c) (:gold c)]]]
               (tetra! v (+ -2.7 (* (mod i 5) 1.35)) (+ -0.5 (* (quot i 5) 1.35)) (- (* (mod i 2) 0.45) 0.2) (+ 0.42 (* (mod i 3) 0.08) (* wave 0.05)) (nth cs (mod i 5))))
             (triangle! v [-3 -1.45 -1.1] [3 -1.45 -1.1] [0 -1.45 2.2] (:white c)))
      nil)
    (when (pos? strength)
      (cube! v (* x 3.2) (* y 1.45) 1.45 (+ 0.12 (* strength 0.16))
             (+ 0.12 (* strength 0.16)) (+ 0.12 (* strength 0.16)) (:gold c)))
    (js/Float32Array. (clj->js @v))))

(defn- pointer-action [canvas event previous]
  (let [rect (.getBoundingClientRect canvas)
        x (- (* 2 (/ (- (.-clientX event) (.-left rect)) (.-width rect))) 1)
        y (- 1 (* 2 (/ (- (.-clientY event) (.-top rect)) (.-height rect))))
        distance (js/Math.hypot (- x (:x previous)) (- y (:y previous)))]
    {:x (max -1 (min 1 x)) :y (max -1 (min 1 y))
     :strength (min 3.0 (+ (:strength previous) 0.45 (* distance 2.2)))
     :count (inc (:count previous)) :active? true}))

(defn- apply-user-action [sim scene canvas event]
  (let [action (pointer-action canvas event (:action sim))
        sim (assoc sim :action action)]
    (if (= scene 6)
      (let [cell (min 17 (max 0 (js/Math.floor (* 18 (/ (inc (:x action)) 2)))))
            impulse (* 0.025 (:strength action))]
        (update-in sim [:fvm :state]
          (fn [state]
            (mapv (fn [i [rho momentum energy]]
                    (if (= i cell) [rho (+ momentum impulse) (+ energy (* impulse 0.8))]
                        [rho momentum energy]))
                  (range) state))))
      sim)))

(defn- vsub [a b] (mapv - a b))
(defn- dot [a b] (reduce + (map * a b)))
(defn- cross [[a b c] [x y z]] [(- (* b z) (* c y)) (- (* c x) (* a z)) (- (* a y) (* b x))])
(defn- norm [a] (let [l (js/Math.hypot.apply nil (clj->js a))] (mapv #(/ % l) a)))
(defn- perspective [fov aspect near far]
  (let [f (/ 1 (js/Math.tan (/ fov 2))) nf (/ 1 (- near far))]
    (js/Float32Array. #js [(/ f aspect) 0 0 0 0 f 0 0 0 0 (* (+ far near) nf) -1 0 0 (* 2 far near nf) 0])))
(defn- look-at [eye center up]
  (let [z (norm (vsub eye center)) x (norm (cross up z)) y (cross z x)]
    (js/Float32Array. #js [(x 0) (y 0) (z 0) 0 (x 1) (y 1) (z 1) 0 (x 2) (y 2) (z 2) 0 (- (dot x eye)) (- (dot y eye)) (- (dot z eye)) 1])))
(defn- mat-mul [a b]
  (let [o (js/Float32Array. 16)]
    (doseq [c (range 4) r (range 4)]
      (aset o (+ (* c 4) r) (+ (* (aget a r) (aget b (* c 4))) (* (aget a (+ 4 r)) (aget b (+ (* c 4) 1))) (* (aget a (+ 8 r)) (aget b (+ (* c 4) 2))) (* (aget a (+ 12 r)) (aget b (+ (* c 4) 3))))))
    o))

(def shader-code
  "struct U { mvp: mat4x4f, params: vec4f }
   @group(0) @binding(0) var<uniform> u: U;
   struct V { @location(0) position: vec3f, @location(1) color: vec3f }
   struct O { @builtin(position) position: vec4f, @location(0) color: vec3f }
   @vertex fn vs(v: V) -> O { var o: O; o.position = u.mvp * vec4f(v.position, 1.0); o.color = v.color; return o; }
   @fragment fn fs(o: O) -> @location(0) vec4f { return vec4f(o.color, 1.0); }")

(defn- init-renderer! [adapter]
  (-> (.requestDevice adapter)
      (.then
       (fn [device]
         (let [canvas (.getElementById js/document "kami-webgpu-canvas")
               status (.getElementById js/document "kami-runtime-status")
               frames-el (.getElementById js/document "kami-cljs-frames")
               draws-el (.getElementById js/document "kami-webgpu-draws")
               time-el (.getElementById js/document "kami-sim-time")
               steps-el (.getElementById js/document "kami-sim-steps")
               metric-el (.getElementById js/document "kami-sim-metric")
               toggle-el (.getElementById js/document "kami-sim-toggle")
               reset-el (.getElementById js/document "kami-sim-reset")
               speed-el (.getElementById js/document "kami-sim-speed")
               action-el (.getElementById js/document "kami-action-status")
               action-title-el (.getElementById js/document "kami-action-title")
               action-cursor-el (.getElementById js/document "kami-action-cursor")
               locale-el (.getElementById js/document "kami-locale")
               context (.getContext canvas "webgpu")
               format (.getPreferredCanvasFormat (.-gpu js/navigator))
               shader (.createShaderModule device #js {:code shader-code})
               pipeline (.createRenderPipeline device #js {:layout "auto"
                 :vertex #js {:module shader :entryPoint "vs" :buffers #js [#js {:arrayStride 24 :attributes #js [#js {:shaderLocation 0 :offset 0 :format "float32x3"} #js {:shaderLocation 1 :offset 12 :format "float32x3"}]}]}
                 :fragment #js {:module shader :entryPoint "fs" :targets #js [#js {:format format}]}
                 :primitive #js {:topology "triangle-list" :cullMode "back"}
                 :depthStencil #js {:format "depth24plus" :depthWriteEnabled true :depthCompare "less"}})
               usage js/GPUBufferUsage
               tex-usage js/GPUTextureUsage
               uniform (.createBuffer device #js {:size 80 :usage (bit-or (.-UNIFORM usage) (.-COPY_DST usage))})
               geometry (.createBuffer device #js {:size (* 4 1024 1024) :usage (bit-or (.-VERTEX usage) (.-COPY_DST usage))})
               bind-group (.createBindGroup device #js {:layout (.getBindGroupLayout pipeline 0) :entries #js [#js {:binding 0 :resource #js {:buffer uniform}}]})
               scene (atom 0) geometry-count (atom 0) depth-view (atom nil) frames (atom 0) draws (atom 0)
               simulation (atom (initial-simulation)) last-time (atom nil)]
           (.addEventListener canvas "pointerdown"
             (fn [event] (.setPointerCapture canvas (.-pointerId event))
               (let [rect (.getBoundingClientRect canvas)]
                 (set! (.. action-cursor-el -style -left) (str (- (.-clientX event) (.-left rect)) "px"))
                 (set! (.. action-cursor-el -style -top) (str (- (.-clientY event) (.-top rect)) "px"))
                 (.add (.-classList action-cursor-el) "visible"))
               (swap! simulation apply-user-action @scene canvas event)))
           (.addEventListener canvas "pointermove"
             (fn [event] (when (pos? (bit-and (.-buttons event) 1))
                           (let [rect (.getBoundingClientRect canvas)]
                             (set! (.. action-cursor-el -style -left) (str (- (.-clientX event) (.-left rect)) "px"))
                             (set! (.. action-cursor-el -style -top) (str (- (.-clientY event) (.-top rect)) "px")))
                           (swap! simulation apply-user-action @scene canvas event))))
           (.addEventListener canvas "pointerup"
             (fn [_] (swap! simulation assoc-in [:action :active?] false)))
           (doseq [button (array-seq (.querySelectorAll js/document "[data-kami-scene]"))]
             (.addEventListener button "click"
               (fn [_]
                 (reset! scene (js/Number (.. button -dataset -kamiScene)))
                 (doseq [b (array-seq (.querySelectorAll js/document "[data-kami-scene]"))]
                   (.toggle (.-classList b) "active" (= b button))
                   (.setAttribute b "aria-pressed" (if (= b button) "true" "false")))
                 (set! (.-textContent (.getElementById js/document "kami-scene-name")) (tr (nth scene-keys @scene)))
                 (set! (.-textContent action-title-el) (tr (nth action-keys @scene)))
                 (.remove (.-classList action-cursor-el) "visible")
                 (reset! simulation (initial-simulation)))))
           (.addEventListener toggle-el "click"
             (fn [_] (swap! simulation update :running? not)
               (set! (.-textContent toggle-el) (tr (if (:running? @simulation) :app/pause :app/resume)))))
           (.addEventListener reset-el "click" (fn [_] (reset! simulation (initial-simulation)) (reset! last-time nil)))
           (.addEventListener speed-el "change" (fn [_] (swap! simulation assoc :speed (js/Number (.-value speed-el)))))
           (.addEventListener locale-el "change"
             (fn [_]
               (i18n/set-locale! (keyword (.-value locale-el)))
               (.setItem js/localStorage "kami-cae-locale" (.-value locale-el))
               (localize-static!)
               (set! (.-textContent (.getElementById js/document "kami-scene-name")) (tr (nth scene-keys @scene)))
               (set! (.-textContent action-title-el) (tr (nth action-keys @scene)))
               (set! (.-textContent toggle-el) (tr (if (:running? @simulation) :app/pause :app/resume)))))
           (letfn [(render [time]
                     (let [rect (.getBoundingClientRect canvas) scale (min (or js/devicePixelRatio 1) 2)
                           width (max 1 (js/Math.floor (* (.-width rect) scale))) height (max 1 (js/Math.floor (* (.-height rect) scale)))
                           dt (if @last-time (min 0.05 (/ (- time @last-time) 1000)) 0.0)]
                       (reset! last-time time)
                       (when (:running? @simulation) (swap! simulation advance-simulation @scene dt))
                       (when (or (not= (.-width canvas) width) (not= (.-height canvas) height))
                         (set! (.-width canvas) width) (set! (.-height canvas) height)
                         (.configure context #js {:device device :format format :alphaMode "opaque"})
                         (reset! depth-view (.createView (.createTexture device #js {:size #js [width height 1] :format "depth24plus" :usage (.-RENDER_ATTACHMENT tex-usage)}))))
                       (let [data (scene-geometry @scene (:time @simulation) @simulation)]
                         (.writeBuffer (.-queue device) geometry 0 data)
                         (reset! geometry-count (/ (.-length data) 6)))
                       (swap! frames inc) (swap! draws inc)
                       (let [angle (* time 0.00025) eye [(* (js/Math.sin angle) 8) 5 (* (js/Math.cos angle) 8)]
                             mvp (mat-mul (perspective (/ js/Math.PI 4) (/ width height) 0.1 100) (look-at eye [0 0 0] [0 1 0]))
                             u (js/Float32Array. 20) encoder (.createCommandEncoder device)]
                         (.set u mvp) (aset u 16 time) (aset u 17 @draws) (aset u 18 @scene) (.writeBuffer (.-queue device) uniform 0 u)
                         (let [pass (.beginRenderPass encoder #js {:colorAttachments #js [#js {:view (.createView (.getCurrentTexture context)) :loadOp "clear" :storeOp "store" :clearValue #js {:r 0.015 :g 0.03 :b 0.06 :a 1}}]
                                                                        :depthStencilAttachment #js {:view @depth-view :depthClearValue 1 :depthLoadOp "clear" :depthStoreOp "store"}})]
                           (.setPipeline pass pipeline) (.setBindGroup pass 0 bind-group) (.setVertexBuffer pass 0 geometry) (.draw pass @geometry-count) (.end pass)
                           (.submit (.-queue device) #js [(.finish encoder)]))
                         (set! (.-textContent frames-el) @frames) (set! (.-textContent draws-el) @draws)
                         (set! (.-textContent time-el) (.toFixed (:time @simulation) 2))
                         (set! (.-textContent steps-el) (:steps @simulation))
                         (set! (.-textContent metric-el) (telemetry @scene @simulation))
                         (set! (.-textContent action-el)
                           (i18n/t :app/drag-help {:action (tr (nth action-keys @scene))
                                                  :count (get-in @simulation [:action :count])}))
                         (js/requestAnimationFrame render))))]
             (set! (.-textContent status) "ClojureScript direct WebGPU rendering active")
             (set! (.. status -dataset -state) "ok")
             (js/requestAnimationFrame render)))))))

(defn init! []
  (let [status (.getElementById js/document "kami-runtime-status") gpu (.-gpu js/navigator)
        saved (.getItem js/localStorage "kami-cae-locale")
        detected (if (.startsWith (or (.-language js/navigator) "en") "ja") "ja" "en")
        locale (or saved detected)]
    (i18n/set-locale! (keyword locale))
    (set! (.-value (.getElementById js/document "kami-locale")) locale)
    (localize-static!)
    (if-not gpu
      (do (set! (.-textContent status) "WebGPU unavailable; use a WebGPU-capable browser.") (set! (.. status -dataset -state) "fallback"))
      (-> (.requestAdapter gpu)
          (.then (fn [adapter] (if adapter (init-renderer! adapter) (throw (js/Error. "No WebGPU adapter available")))))
          (.catch (fn [error] (js/console.error error) (set! (.-textContent status) (str "WebGPU initialization failed: " (.-message error))) (set! (.. status -dataset -state) "error")))))))

(init!)
