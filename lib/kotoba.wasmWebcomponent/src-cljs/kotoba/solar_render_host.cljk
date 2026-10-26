(ns kotoba.solar-render-host
  "Track B Phase 1 + follow-up (ADR-2607078000): the browser host for
  `gpu-set-position`/`gpu-draw-frame`/`now-days`/`galactic-frame?` —
  renders `kami-solar-helix-scene`'s 9 bodies (Sun + 8 planets) as
  spheres, animated, with a heliocentric/galactic (\"helix\") view toggle.

  Architecture (deliberate, not a shortcut): the guest (`.kotoba`, compiled
  from `demo_solar_helix.kotoba`) computes each body's position every frame
  via real `cos`/`sin` host-imports (orbital math) and calls
  `gpu-set-position(body-id, x, y, z)` once per body, then
  `gpu-draw-frame()` once. All matrix/camera/pipeline/mesh mechanics stay
  host-side: `.kotoba` has no vector/matrix type or loops-beyond-recursion
  yet, so 'guest computes orbital physics, host renders' is the natural
  split, not a workaround. Every WebGPU call in `gpu_draw_frame` is
  synchronous (same proof `gpu-clear-host.cljs`/Phase 0 already established
  for a single clear) — one draw call per body (9 total), not true
  GPU-instanced rendering, since 9 is small enough that the simplicity is
  worth more than the throughput.

  Animation is driven the same way, one step further: `.kotoba` has no
  clock and no loop beyond recursion, so it can't animate itself. Instead
  `main` stays a 0-arity, single-frame function — the PAGE calls
  `instance.exports.main()` again every `requestAnimationFrame` tick (see
  `examples/solar-helix/index.html`), and each call the guest asks this
  host, via the `now-days` host-import, \"what time is it now\" instead of
  using a fixed constant. `now-days` returns an already-WRAPPED simulated
  day count (plain JS `%`, computed host-side) so the guest never needs a
  modulo/floor op it doesn't have, and the Sun's forward galactic drift
  (added when `galactic-frame?` is on) stays bounded in view instead of
  drifting the whole scene out of the camera frustum forever.
  `galactic-frame?` similarly lets the guest branch (via a plain wasm `if`
  — an i32 works directly as its condition) between the flat heliocentric
  view and the tilt+forward-drift view, driven by a page-owned checkbox
  via `setGalacticFrame` (see `setup-solar-render-host`'s return value).

  `:advanced` shadow-cljs optimization requires `unchecked-get`/`js-invoke`
  throughout (see `gpu_clear_host.cljs`'s header for why — Closure's
  property renaming silently breaks bare `.method`/`.-prop` interop against
  externs-less browser APIs).")

;; ---------------------------------------------------------------------------
;; Animation clock tuning (host-owned, purely illustrative -- see
;; demo_solar_helix.kotoba's header for the matching forward-per-day
;; compromise on the guest side). DAYS-PER-SECOND * WRAP-DAYS-worth of
;; wall-clock time = one full wrap cycle (10s at these defaults) before the
;; simulated day count resets to 0 and the whole animation loops.

(def days-per-second 8.0)
(def wrap-days 80.0)

(defn wrap-now-days
  "elapsed-s (real wall-clock seconds since the host started) -> the
  wrapped simulated day count `now_days` returns -- a pure function of
  the two tuning constants above, pulled out of the `now_days` closure
  specifically so it's directly unit-testable without a fake clock or a
  GPU (`elapsed-s * days-per-second` scaled up, then wrapped into
  [0, wrap-days) via `mod` so the forward-drift term in
  demo_solar_helix.kotoba's galactic-frame math never grows unbounded)."
  [elapsed-s]
  (mod (* elapsed-s days-per-second) wrap-days))

;; ---------------------------------------------------------------------------
;; Body palette — id 0-8 matches kami-solar-helix-scene's `all-body-names`
;; order (sun, mercury, venus, earth, mars, jupiter, saturn, uranus,
;; neptune); color/size copied from that repo's `resources/solar-helix.edn`.
;; The guest only sends position (scalar f32 x/y/z) -- color/size are a
;; fixed host-side palette, not a guest-controllable render parameter, to
;; keep the guest's own job (orbital math) as small as possible for this
;; first vertical slice.

(def body-palette
  [{:color [1.0 0.86 0.2] :radius 0.09} ;; sun (visually oversized vs AU-scale orbits, same convention every solar-system diagram uses)
   {:color [0.6 0.6 0.6] :radius 0.02} ;; mercury
   {:color [0.9 0.85 0.6] :radius 0.03} ;; venus
   {:color [0.25 0.5 0.9] :radius 0.032} ;; earth
   {:color [0.8 0.35 0.2] :radius 0.025} ;; mars
   {:color [0.85 0.65 0.4] :radius 0.06} ;; jupiter
   {:color [0.9 0.8 0.55] :radius 0.05} ;; saturn
   {:color [0.55 0.85 0.9] :radius 0.04} ;; uranus
   {:color [0.2 0.35 0.85] :radius 0.04}]) ;; neptune

;; ---------------------------------------------------------------------------
;; mat4/vec3 helpers (column-major, WGSL/WebGPU convention) -- no external
;; dep. Public (not `defn-`) specifically so they're directly unit-testable
;; without a GPU -- see test/solar_render_host_test.cljs.

(defn mat4-multiply
  "a * b, both column-major Float32Array(16)."
  [a b]
  (let [out (js/Float32Array. 16)]
    (dotimes [col 4]
      (dotimes [row 4]
        (let [b0 (aget b (+ (* col 4) 0)) b1 (aget b (+ (* col 4) 1))
              b2 (aget b (+ (* col 4) 2)) b3 (aget b (+ (* col 4) 3))]
          (aset out (+ (* col 4) row)
                (+ (* (aget a (+ 0 row)) b0)
                   (* (aget a (+ 4 row)) b1)
                   (* (aget a (+ 8 row)) b2)
                   (* (aget a (+ 12 row)) b3))))))
    out))

(defn mat4-perspective
  "Right-handed perspective projection, WebGPU depth range [0,1] (not
  OpenGL's [-1,1]). fovy-radians/aspect/near/far standard."
  [fovy-radians aspect near far]
  (let [f (/ 1.0 (js/Math.tan (/ fovy-radians 2)))
        range-inv (/ 1.0 (- near far))]
    (js/Float32Array.
     #js [(/ f aspect) 0 0 0
          0 f 0 0
          0 0 (* far range-inv) -1
          0 0 (* far near range-inv) 0])))

(defn vec3-normalize [[x y z]]
  (let [len (js/Math.sqrt (+ (* x x) (* y y) (* z z)))]
    (if (< len 1e-9) [0 0 0] [(/ x len) (/ y len) (/ z len)])))

(defn vec3-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn vec3-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn vec3-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))

(defn mat4-look-at
  "Right-handed view matrix. eye/target/up are [x y z] vectors."
  [eye target up]
  (let [z (vec3-normalize (vec3-sub eye target))
        x (vec3-normalize (vec3-cross up z))
        y (vec3-cross z x)]
    (js/Float32Array.
     #js [(nth x 0) (nth y 0) (nth z 0) 0
          (nth x 1) (nth y 1) (nth z 1) 0
          (nth x 2) (nth y 2) (nth z 2) 0
          (- (vec3-dot x eye)) (- (vec3-dot y eye)) (- (vec3-dot z eye)) 1])))

(defn mat4-translation-scale
  "Translate by [x y z] then uniformly scale by `s` -- enough for a sphere
  instance (no rotation needed, spheres look the same from every angle)."
  [x y z s]
  (js/Float32Array.
   #js [s 0 0 0
        0 s 0 0
        0 0 s 0
        x y z 1]))

;; ---------------------------------------------------------------------------
;; Sphere mesh -- a small UV sphere (positions + normals interleaved,
;; 16-bit indices), generated once and reused for every instance.

(defn build-sphere-mesh
  "Public (not `defn-`) specifically so it's directly unit-testable without a
  GPU -- see test/solar_render_host_test.cljs."
  [lat-bands lon-bands]
  (let [vertices (transient [])
        indices (transient [])]
    (dotimes [lat (inc lat-bands)]
      (let [theta (* js/Math.PI (/ lat lat-bands))
            sin-t (js/Math.sin theta) cos-t (js/Math.cos theta)]
        (dotimes [lon (inc lon-bands)]
          (let [phi (* 2 js/Math.PI (/ lon lon-bands))
                sin-p (js/Math.sin phi) cos-p (js/Math.cos phi)
                x (* cos-p sin-t) y cos-t z (* sin-p sin-t)]
            (conj! vertices x) (conj! vertices y) (conj! vertices z)
            (conj! vertices x) (conj! vertices y) (conj! vertices z)))))
    (dotimes [lat lat-bands]
      (dotimes [lon lon-bands]
        (let [first (+ (* lat (inc lon-bands)) lon)
              second (+ first lon-bands 1)]
          (conj! indices first) (conj! indices second) (conj! indices (inc first))
          (conj! indices second) (conj! indices (inc second)) (conj! indices (inc first)))))
    #js {"vertices" (js/Float32Array. (clj->js (persistent! vertices)))
         "indices" (js/Uint16Array. (clj->js (persistent! indices)))}))

;; ---------------------------------------------------------------------------
;; WGSL shader: per-vertex position+normal (unit sphere, model-space),
;; per-draw uniform {mvp: mat4x4, color: vec4} -- one draw call per body,
;; uniform rewritten via writeBuffer before each draw (see gpu_draw_frame).

(def ^:private wgsl-shader
  "struct Uniforms {
  mvp: mat4x4<f32>,
  color: vec4<f32>,
}
@group(0) @binding(0) var<uniform> u: Uniforms;

struct VertexOut {
  @builtin(position) clip_position: vec4<f32>,
  @location(0) normal: vec3<f32>,
}

@vertex
fn vs_main(@location(0) position: vec3<f32>, @location(1) normal: vec3<f32>) -> VertexOut {
  var out: VertexOut;
  out.clip_position = u.mvp * vec4<f32>(position, 1.0);
  out.normal = normal;
  return out;
}

@fragment
fn fs_main(in: VertexOut) -> @location(0) vec4<f32> {
  let light_dir = normalize(vec3<f32>(0.4, 0.7, 0.6));
  let ndotl = max(dot(normalize(in.normal), light_dir), 0.0);
  let lit = u.color.rgb * (0.35 + 0.65 * ndotl);
  return vec4<f32>(lit, u.color.a);
}
")

;; ---------------------------------------------------------------------------
;; Public API

(defn setup-solar-render-host
  "Async, host-side, one-time WebGPU setup (device/context/pipeline/mesh/
  camera) -- call and await BEFORE instantiating the guest wasm module.
  Resolves to a JS object `{imports: (fn [] importsObject), setGalacticFrame:
  (fn [bool]), setFixedNowDays: (fn [days-or-null])}` -- `imports()` returns
  the WebAssembly import object (`now_days`/`galactic_frame` included),
  `setGalacticFrame` flips the view-toggle state `galactic_frame` reads on
  its next call (wire it up to a page checkbox's `onchange`).
  `setFixedNowDays` is a TEST-ONLY escape hatch: passing a number makes
  `now_days` return exactly that value forever instead of computing it
  from wall-clock time, making the render fully deterministic (no
  dependency on real elapsed time between page load and the moment a
  screenshot is taken) -- see `test/render/verify-render-solar-helix.mjs`,
  which drives this via `?test_fixed_t=<days>` on the page URL. Passing
  `nil`/`undefined` reverts to the normal wall-clock-driven behavior. The
  page owns instantiating the guest module AND the `requestAnimationFrame`
  loop that calls `instance.exports.main()` again every tick -- this fn
  only sets up the one-time device/pipeline state and the per-tick
  host-import closures over it, same division of responsibility Phase 0/1
  already established."
  [canvas]
  (let [gpu (unchecked-get js/navigator "gpu")]
    (if (nil? gpu)
      (js/Promise.reject (js/Error. "setup-solar-render-host: navigator.gpu unavailable"))
      (-> (js-invoke gpu "requestAdapter")
          (.then (fn [adapter]
                   (if (nil? adapter)
                     (throw (js/Error. "setup-solar-render-host: requestAdapter returned null"))
                     (js-invoke adapter "requestDevice"))))
          (.then
           (fn [device]
             (let [ctx (js-invoke canvas "getContext" "webgpu")
                   format (js-invoke gpu "getPreferredCanvasFormat")
                   queue (unchecked-get device "queue")
                   width (unchecked-get canvas "width")
                   height (unchecked-get canvas "height")
                   _ (js-invoke ctx "configure" #js {"device" device "format" format "alphaMode" "opaque"})

                   depth-texture (js-invoke device "createTexture"
                                  #js {"size" #js {"width" width "height" height "depthOrArrayLayers" 1}
                                       "format" "depth24plus"
                                       "usage" (unchecked-get js/GPUTextureUsage "RENDER_ATTACHMENT")})
                   depth-view (js-invoke depth-texture "createView")

                   mesh (build-sphere-mesh 12 16)
                   mesh-vertices (unchecked-get mesh "vertices")
                   mesh-indices (unchecked-get mesh "indices")
                   vertex-buffer (js-invoke device "createBuffer"
                                  #js {"size" (* (.-length mesh-vertices) 4)
                                       "usage" (bit-or (unchecked-get js/GPUBufferUsage "VERTEX")
                                                        (unchecked-get js/GPUBufferUsage "COPY_DST"))})
                   index-buffer (js-invoke device "createBuffer"
                                 #js {"size" (* (js/Math.ceil (/ (.-length mesh-indices) 2)) 4)
                                      "usage" (bit-or (unchecked-get js/GPUBufferUsage "INDEX")
                                                       (unchecked-get js/GPUBufferUsage "COPY_DST"))})
                   _ (js-invoke queue "writeBuffer" vertex-buffer 0 mesh-vertices)
                   _ (js-invoke queue "writeBuffer" index-buffer 0 mesh-indices)
                   index-count (.-length mesh-indices)

                   shader-module (js-invoke device "createShaderModule" #js {"code" wgsl-shader})
                   bind-group-layout (js-invoke device "createBindGroupLayout"
                                      #js {"entries" #js [#js {"binding" 0
                                                                "visibility" (bit-or (unchecked-get js/GPUShaderStage "VERTEX")
                                                                                      (unchecked-get js/GPUShaderStage "FRAGMENT"))
                                                                "buffer" #js {"type" "uniform"}}]})
                   ;; ONE uniform buffer + bind group PER body slot (not one
                   ;; shared buffer reused across the draw loop): queue.
                   ;; writeBuffer executes immediately, but pass.drawIndexed
                   ;; calls only RECORD into the command encoder -- they
                   ;; don't actually run until queue.submit() at the very
                   ;; end of gpu_draw_frame. A single shared buffer written
                   ;; 9x in a row before any of the 9 recorded draws
                   ;; executes means every draw would see only the LAST
                   ;; write (found via real-browser verification: nothing
                   ;; rendered until this fix). Per-slot buffers make each
                   ;; draw call reference its own body's data regardless of
                   ;; write/submit timing.
                   uniform-buffers (mapv (fn [_]
                                            (js-invoke device "createBuffer"
                                             #js {"size" 80 ; 64 (mat4) + 16 (vec4 color)
                                                  "usage" (bit-or (unchecked-get js/GPUBufferUsage "UNIFORM")
                                                                   (unchecked-get js/GPUBufferUsage "COPY_DST"))}))
                                          body-palette)
                   bind-groups (mapv (fn [buf]
                                        (js-invoke device "createBindGroup"
                                         #js {"layout" bind-group-layout
                                              "entries" #js [#js {"binding" 0 "resource" #js {"buffer" buf}}]}))
                                      uniform-buffers)
                   pipeline-layout (js-invoke device "createPipelineLayout"
                                    #js {"bindGroupLayouts" #js [bind-group-layout]})
                   pipeline (js-invoke device "createRenderPipeline"
                             #js {"layout" pipeline-layout
                                  "vertex" #js {"module" shader-module
                                                "entryPoint" "vs_main"
                                                "buffers" #js [#js {"arrayStride" 24
                                                                      "attributes" #js [#js {"shaderLocation" 0 "offset" 0 "format" "float32x3"}
                                                                                        #js {"shaderLocation" 1 "offset" 12 "format" "float32x3"}]}]}
                                  "fragment" #js {"module" shader-module
                                                  "entryPoint" "fs_main"
                                                  "targets" #js [#js {"format" format}]}
                                  ;; "none" not "back": untested triangle
                                  ;; winding order for the procedural UV
                                  ;; sphere -- avoid an entire class of
                                  ;; "invisible because backface-culled" bug
                                  ;; risk for this first vertical slice; can
                                  ;; tighten to "back" once winding is
                                  ;; verified against a real render.
                                  "primitive" #js {"topology" "triangle-list" "cullMode" "none"}
                                  "depthStencil" #js {"format" "depth24plus" "depthWriteEnabled" true "depthCompare" "less"}})

                   ;; Fixed camera: looking at the origin from outside the
                   ;; scaled-down orbit cluster (positions arrive already
                   ;; scaled by the guest into a roughly [-1,1] box).
                   ;; Pulled back + widened from the first pass, which cut
                   ;; off Uranus/Neptune (found via real-browser
                   ;; verification -- 7/9 bodies visible, outer two just
                   ;; outside the frustum) -- enough margin for Neptune's
                   ;; r~1.37 scaled orbit at any angle, not just this one t.
                   view (mat4-look-at [0 1.5 2.7] [0 0 0] [0 1 0])
                   proj (mat4-perspective (/ js/Math.PI 3) (/ width height) 0.05 20.0)
                   view-proj (mat4-multiply proj view)

                   positions (atom {})
                   galactic-frame? (atom false)
                   fixed-now-days (atom nil)
                   start-ms (js/performance.now)]
               #js {"imports"
                    (fn []
                      #js {"kotoba"
                           #js {"cos" (fn [x] (js/Math.cos x))
                                "sin" (fn [x] (js/Math.sin x))
                                "now_days"
                                (fn []
                                  (if-let [fixed @fixed-now-days]
                                    fixed
                                    (wrap-now-days (/ (- (js/performance.now) start-ms) 1000))))
                                "galactic_frame"
                                (fn [] (if @galactic-frame? 1 0))
                                "gpu_set_position"
                                (fn [body-id x y z]
                                  (swap! positions assoc body-id [x y z])
                                  0)
                                "gpu_draw_frame"
                                (fn []
                                  (let [texture (js-invoke ctx "getCurrentTexture")
                                        view-tex (js-invoke texture "createView")
                                        encoder (js-invoke device "createCommandEncoder")
                                        pass (js-invoke encoder "beginRenderPass"
                                              #js {"colorAttachments"
                                                   #js [#js {"view" view-tex
                                                             "loadOp" "clear"
                                                             "storeOp" "store"
                                                             "clearValue" #js {"r" 0.03 "g" 0.03 "b" 0.05 "a" 1}}]
                                                   "depthStencilAttachment"
                                                   #js {"view" depth-view
                                                        "depthLoadOp" "clear"
                                                        "depthStoreOp" "store"
                                                        "depthClearValue" 1.0}})]
                                    (js-invoke pass "setPipeline" pipeline)
                                    (js-invoke pass "setVertexBuffer" 0 vertex-buffer)
                                    (js-invoke pass "setIndexBuffer" index-buffer "uint16")
                                    (doseq [[id [x y z]] @positions]
                                      (let [palette (nth body-palette id {:color [1 1 1] :radius 0.03})
                                            model (mat4-translation-scale x y z (:radius palette))
                                            mvp (mat4-multiply view-proj model)
                                            [r g b] (:color palette)
                                            uniform-data (js/Float32Array. 20)]
                                        (.set uniform-data mvp 0)
                                        (aset uniform-data 16 r) (aset uniform-data 17 g)
                                        (aset uniform-data 18 b) (aset uniform-data 19 1.0)
                                        (js-invoke queue "writeBuffer" (nth uniform-buffers id) 0 uniform-data)
                                        (js-invoke pass "setBindGroup" 0 (nth bind-groups id))
                                        (js-invoke pass "drawIndexed" index-count)))
                                    (js-invoke pass "end")
                                    (js-invoke queue "submit" #js [(js-invoke encoder "finish")])
                                    0))}})
                    "setGalacticFrame"
                    (fn [on] (reset! galactic-frame? (boolean on)))
                    "setFixedNowDays"
                    (fn [days] (reset! fixed-now-days (when (some? days) (float days))))})))))))
