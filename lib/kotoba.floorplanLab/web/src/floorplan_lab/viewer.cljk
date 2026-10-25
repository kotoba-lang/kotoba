(ns floorplan-lab.viewer
  "Browser 3D viewer for floorplan-lab's wall-point cloud / room-outline
  output. Renders through `kotoba-lang/webgpu`'s declarative render-IR
  executor (`kami.webgpu`/`kami.webgpu.ir`) -- no new 3D rendering code is
  written here, this namespace only turns floorplan-lab's 2D [x y] wall
  points/hull into render-IR box instances and a camera, per README /
  ADR-2607078000 addendum (native-desktop targets wrap the browser-proven
  cljs path instead of new native rendering code).

  RESPONSIBILITY BOUNDARY (per the task that authored this): this is the
  ONLY place sensor fusion runs. The iOS WKWebView host
  (`ios/FloorplanLabApp/FloorplanMapView.swift`) hands this namespace RAW
  sensor data only (motion samples, chirp/echo audio buffers, BLE RSSI
  scans) via `window.FloorplanLabViewer`'s exported functions below --
  `floorplan-lab.motion`/`sonar`/`ble`/`fusion` (this lab's existing,
  already-tested `.cljc` algorithms) do all the actual estimation here,
  in cljs, not in Swift.

  2D -> 3D convention: floorplan-lab's [x y] world-frame plane maps to
  this renderer's [x _ z] ground plane (world y = up, always 0 for
  floorplan geometry -- this lab does not estimate elevation)."
  (:require [kami.webgpu :as gpu]
            [kami.webgpu.ir :as ir]
            [floorplan-lab.motion :as motion]
            [floorplan-lab.sonar :as sonar]
            [floorplan-lab.ble :as ble]
            [floorplan-lab.fusion :as fusion]))

;; ---------- app state ----------
;; :motion-samples / :sonar-readings / :ble-fix are the RAW-derived inputs
;; this namespace folds through motion/sonar/ble/fusion on every ingest
;; call (see `recompute!`); :wall-points / :hull are the fusion OUTPUT this
;; namespace last computed and is currently drawing; :ctx is the WebGPU/
;; WebGL2 viewport `kami.webgpu/init!` resolved (nil until that Promise
;; settles).

(defonce state
  (atom {:motion-samples []
         :sonar-readings []
         :ble-fix        nil
         :wall-points    []
         :hull           []
         :ctx            nil}))

;; ---------- floorplan geometry -> render-IR instances ----------
;; All authored as small `:box` cube instances (the executor's default
;; geo, `ir/default-geometry`'s `:box`) -- no custom geometry spec is
;; registered, per the task's "small cube instances / grid-level floor,
;; nothing fancy, working beats polished" guidance.

(def wall-marker-size  [0.18 0.5])
(def wall-marker-color [0.86 0.36 0.30])   ;; warm red -- a raw sensor hit

(def hull-dash-size     [0.14 1.8])
(def hull-dash-color    [0.55 0.60 0.70])  ;; cool grey -- the estimated wall
(def hull-dash-spacing-m 0.35)

(def floor-tile-size  [0.95 0.03])
(def floor-tile-color [0.16 0.17 0.20])
(def floor-margin-m   1.0)

(defn- lerp [a b t] (+ a (* t (- b a))))

(defn- bounds
  "Bounding box of POINTS (seq of [x z]); a fixed fallback box when empty
  so the camera/floor grid always have something sane to frame."
  [points]
  (if (empty? points)
    {:min-x -2.0 :max-x 2.0 :min-z -2.0 :max-z 2.0}
    {:min-x (apply min (map first points))
     :max-x (apply max (map first points))
     :min-z (apply min (map second points))
     :max-z (apply max (map second points))}))

(defn- wall-point-instance [[x z]]
  (ir/instance [x 0 z] wall-marker-color wall-marker-size))

(defn- edge-dash-instances
  "A [p1 p2] hull edge as a dashed line of small cubes (spaced ~
  `hull-dash-spacing-m` apart) -- this executor's `instance` only scales a
  box's [w h] footprint/height uniformly (see kami-webgpu README), so a
  single elongated wall segment isn't directly expressible; a dashed cube
  line reads as a wall outline without needing a custom geometry spec."
  [[x1 z1] [x2 z2]]
  (let [dx (- x2 x1) dz (- z2 z1)
        len (js/Math.sqrt (+ (* dx dx) (* dz dz)))
        n (max 1 (js/Math.ceil (/ len hull-dash-spacing-m)))]
    (for [i (range (inc n))
          :let [t (/ i n)]]
      (ir/instance [(lerp x1 x2 t) 0 (lerp z1 z2 t)] hull-dash-color hull-dash-size))))

(defn- hull-instances [hull]
  (let [n (count hull)]
    (if (< n 2)
      []
      (mapcat (fn [i] (edge-dash-instances (nth hull i) (nth hull (mod (inc i) n))))
              (range n)))))

(defn- floor-grid-instances
  "A rough tile grid covering BOUNDS + a margin -- the task's 'floor is
  just a grid, nothing fancy' guidance. Each tile is one thin :box
  instance; top face sits at world y=0 (`ir/instance`'s `:pos` is the
  box's base before the executor's own +h/2 centering, so the tile's
  world-y is set to -(tile height) to land its TOP at 0)."
  [{:keys [min-x max-x min-z max-z]}]
  (let [min-x (- min-x floor-margin-m) max-x (+ max-x floor-margin-m)
        min-z (- min-z floor-margin-m) max-z (+ max-z floor-margin-m)
        tile-h (second floor-tile-size)]
    (for [x (range (js/Math.floor min-x) (inc (js/Math.ceil max-x)))
          z (range (js/Math.floor min-z) (inc (js/Math.ceil max-z)))]
      (ir/instance [(+ x 0.5) (- tile-h) (+ z 0.5)] floor-tile-color floor-tile-size))))

(defn- auto-camera
  "eye/target framing BOUNDS from a fixed 3/4 elevated corner, sized off
  the room's own span so small and large rooms both fit with margin."
  [{:keys [min-x max-x min-z max-z]}]
  (let [cx (/ (+ min-x max-x) 2.0) cz (/ (+ min-z max-z) 2.0)
        span (max 3.0 (- max-x min-x) (- max-z min-z))
        dist (* span 0.9) height (* span 0.7)]
    {:eye [(+ cx dist) height (+ cz dist)] :target [cx 0 cz]}))

(defn- floorplan->render-ir [{:keys [wall-points hull]}]
  (let [all-pts (concat wall-points hull)
        bb (bounds (if (seq all-pts) all-pts [[0 0]]))
        {:keys [eye target]} (auto-camera bb)
        insts (vec (concat (floor-grid-instances bb)
                            (map wall-point-instance wall-points)
                            (hull-instances hull)))
        sky (ir/sky [0.74 0.84 0.95] [-0.4 -0.85 -0.35] [1.0 0.96 0.85])]
    (ir/render-ir sky insts eye target)))

;; ---------- draw + fusion recompute ----------

(defn- render!
  "Always builds + validates the current render-IR frame (cheap, pure data
  -- catches a malformed frame regardless of whether the GPU is ready),
  then draws it only once `:ctx` (`kami.webgpu/init!`'s resolved viewport)
  exists. This unconditional build+validate step is also what a headless
  check (no WebGPU/WebGL2 available -- Node, CI, a browser without GPU
  access) can observe: `ingestMotion!`/`loadSyntheticRoom!`/etc. always
  reach `kami.webgpu.ir/render-ir` and log the result even when `draw!`
  never runs."
  []
  (let [frame (floorplan->render-ir @state)
        valid? (ir/valid? frame)]
    (js/console.log "floorplan-lab: render-ir frame ready --"
                     (count (:instances frame)) "instances, valid?" valid?)
    (when-not valid?
      (js/console.error "floorplan-lab: constructed an invalid render-IR frame" frame))
    (when-let [ctx (:ctx @state)]
      (gpu/draw! ctx frame))))

(defn- recompute!
  "Re-run the fusion pipeline end to end from this namespace's currently
  accumulated raw inputs and redraw. This is the ONLY place
  `floorplan-lab.motion/sonar/ble/fusion` are called -- see namespace
  docstring's responsibility boundary."
  []
  (let [{:keys [motion-samples sonar-readings ble-fix]} @state
        trajectory (motion/walk-trajectory motion-samples)
        ;; Crude, documented-simple BLE correction (mirrors
        ;; `fusion/correct-with-ble`'s own "no covariance, no Kalman gain"
        ;; honesty): only the CURRENT (last) pose is corrected toward the
        ;; latest BLE trilateration fix, not the whole trajectory.
        trajectory (if (and ble-fix (seq trajectory))
                     (update (vec trajectory) (dec (count trajectory))
                             #(fusion/correct-with-ble % ble-fix 0.4))
                     trajectory)
        wall-points (fusion/collect-wall-points trajectory sonar-readings)
        hull (fusion/floorplan-from-points wall-points)]
    (swap! state assoc :wall-points wall-points :hull hull))
  (render!))

;; ---------- raw-data ingest (called FROM Swift; no fusion logic in Swift) ----------

(defn- js-floats [arr] (vec (js->clj arr)))

(defn ingest-motion-sample!
  "RAW9 is a JS array/Float32Array of 9 floats [ax ay az gx gy gz mx my mz]
  -- `SensingBridge.motionRead()`'s exact CoreMotion order (mirrors
  `kotoba.sensing-host/read-motion`, same shape
  `floorplan-lab.sensing-bridge/motion-sample-from-raw9` expects on the
  JVM/native side). DT-S is the seconds elapsed since the previous sample
  (Swift's timer/loop interval, not computed here)."
  [raw9 dt-s]
  (let [[ax ay az gx gy gz mx my mz] (js-floats raw9)]
    (swap! state update :motion-samples conj
           {:ax ax :ay ay :az az :gx gx :gy gy :gz gz :mx mx :my my :mz mz :dt dt-s})
    (recompute!)))

(defn ingest-sonar-ping!
  "CHIRP/RECORDED are JS arrays/Float32Arrays of floats -- the transmitted
  chirp (`SensingBridge.audioPlay`'s sweep, regenerated identically via
  `floorplan-lab.sonar/generate-chirp` so both sides agree) and the
  recorded echo buffer (`SensingBridge.audioRecord`'s raw PCM), per
  `sonar/estimate-wall-distance-m`'s CONTRACT (recording starts the same
  instant playback begins). SAMPLE-RATE-HZ matches both. SAMPLE-INDEX is
  which trajectory pose (this namespace's running `walk-trajectory`
  result) the ping was fired from -- Swift passes the motion-sample count
  at fire time (0 = the pre-walk pose, matching `walk-trajectory`'s own
  indexing contract)."
  [chirp recorded sample-rate-hz sample-index]
  (let [distance-m (sonar/estimate-wall-distance-m
                     (js-floats chirp) (js-floats recorded) sample-rate-hz)]
    (swap! state update :sonar-readings conj
           {:sample-index sample-index :distance-m distance-m})
    (recompute!)))

(defn ingest-ble-scan!
  "READINGS is a JS array of {id, rssi} objects (`SensingBridge.bleScan`'s
  shape, mirrors `kotoba.sensing-host/scan-ble`). BEACONS is a JS array of
  {id, x, y} objects -- this lab's beacon survey/config (out of scope for
  auto-discovery, same caveat as
  `floorplan-lab.sensing-bridge/ble-readings->beacons`). Trilaterates a
  position fix (dropped silently if fewer than 3 known-position beacons
  are present or the beacons are degenerate -- see `ble/trilaterate`)."
  [readings beacons]
  (let [readings (js->clj readings :keywordize-keys true)
        beacons (js->clj beacons :keywordize-keys true)
        known (reduce (fn [m {:keys [id x y]}] (assoc m id {:x x :y y})) {} beacons)
        tri-beacons (keep (fn [{:keys [id rssi]}]
                             (when-let [{:keys [x y]} (get known id)]
                               {:x x :y y :distance (ble/rssi->distance-m rssi)}))
                           readings)
        fix (ble/trilaterate tri-beacons)]
    (when fix (swap! state assoc :ble-fix fix))
    (recompute!)))

(defn reset-floorplan!
  "Clears all accumulated raw data and redraws an empty scene -- for
  starting a fresh walk-through without reloading the page."
  []
  (swap! state assoc :motion-samples [] :sonar-readings [] :ble-fix nil
         :wall-points [] :hull [])
  (render!))

(defn load-synthetic-square-room!
  "Loads the exact synthetic 4x4m-room fixture
  `floorplan-lab.fusion-test`'s `collect-and-hull-recovers-square-room-wall-points`
  test uses (walker at the center, 4 cardinal-direction chirps, half-width
  2m) directly as wall-points/hull, bypassing motion/sonar entirely. For
  demoing/verifying the viewer on the simulator (or in CI) without real
  sensors."
  []
  (let [wall-points [[2.0 0.0] [4.0 2.0] [2.0 4.0] [0.0 2.0]]]
    (swap! state assoc :wall-points wall-points
           :hull (fusion/floorplan-from-points wall-points)))
  (render!))

;; ---------- entry point ----------

(defn init!
  "shadow-cljs :init-fn. Exposes `window.FloorplanLabViewer` (the ONLY
  surface `FloorplanMapView.swift`'s WKWebView host calls into -- every
  fn is raw-data-in, nothing sensor/fusion-shaped on the Swift side) and
  boots the WebGPU/WebGL2 viewport on `#gpu-canvas`."
  []
  (set! (.-FloorplanLabViewer js/window)
        #js {:ingestMotion      ingest-motion-sample!
             :ingestSonar       ingest-sonar-ping!
             :ingestBle         ingest-ble-scan!
             :reset             reset-floorplan!
             :loadSyntheticRoom load-synthetic-square-room!})
  (if-let [canvas (js/document.getElementById "gpu-canvas")]
    (-> (gpu/init! canvas)
        (.then (fn [ctx]
                 (swap! state assoc :ctx ctx)
                 (render!)
                 (set! (.-floorplanLabReady js/window) true)))
        (.catch (fn [err] (js/console.error "floorplan-lab: gpu/init! failed" err))))
    (js/console.error "floorplan-lab: #gpu-canvas not found")))
