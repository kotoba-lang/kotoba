(ns byoubu-gpu.core
  "Tier 2: mount a backdrop as a live WebGPU scene.

  This namespace is deliberately thin. Everything that can be decided without
  a GPU — the WGSL, the uniform packing, the render graph — lives in `.cljc`
  next door and is unit-tested on two runtimes. What is left here is the part
  that genuinely needs a device: get one, hand the graph to `kami.webgpu`,
  write the uniform each frame, and stop cleanly.

  Fallback. `mount!` resolves to `{:tier :gpu}` when WebGPU is available and
  `{:tier :poster :reason ...}` when it is not. It does NOT fall back to
  WebGL 2.0: the engine's WebGL path runs its own pre-transpiled GLSL (naga,
  at build time — see `kami.webgl.glsl`, a generated file), so arbitrary WGSL
  cannot reach it without adding that transpile step. A caller that gets
  `:poster` should leave `byoubu-ui`'s plate in place, which is the T1 still
  over the T0 gradients — a complete backdrop, not a blank canvas."
  (:require [byoubu.core :as byoubu]
            [byoubu-gpu.graph :as graph]
            [byoubu-gpu.uniforms :as uniforms]
            [kami.webgpu :as gpu]
            [kami.webgpu.ir :as ir]))

(defn supported?
  "Is there a WebGPU entry point at all? A device request can still fail —
  `mount!` reports that as `:tier :poster` rather than throwing."
  []
  (boolean (and (exists? js/navigator) (.-gpu js/navigator))))

(defn- empty-scene
  "Render-IR with no instances. The engine's frame loop runs `:fullscreen`
  passes regardless of instance count (`draw-geom` no-ops at zero), so a
  backdrop needs no geometry — it just needs a well-formed IR to satisfy
  `draw!`'s contract.

  The sky map is `ir/sky`'s own shape and goes unread by this graph: nothing
  in it binds to the byoubu pipeline, whose only resource is its uniform. It
  is here because `render-ir` takes one."
  []
  (let [{:keys [eye target]} (ir/rig->camera ir/default-rig [0.0 0.0])]
    (ir/render-ir (ir/sky [0.0 0.0 0.0] [0.0 1.0 0.0] [1.0 1.0 1.0])
                  []
                  eye target)))

(defn- frame-state [canvas t0]
  {:time  (/ (- (js/performance.now) t0) 1000.0)
   :width (.-width canvas)
   :height (.-height canvas)})

(defn- resize! [canvas]
  (let [dpr (min 2.0 (or (.-devicePixelRatio js/window) 1.0))
        w   (js/Math.round (* dpr (max 1 (.-clientWidth canvas))))
        h   (js/Math.round (* dpr (max 1 (.-clientHeight canvas))))]
    (when (or (not= w (.-width canvas)) (not= h (.-height canvas)))
      (set! (.-width canvas) w)
      (set! (.-height canvas) h)
      true)))

(defn mount!
  "Mount `backdrop` (id or map) on `canvas`. Returns a Promise of a handle.

  opts:
    :animate?  run a rAF loop (default true). false renders exactly one frame,
               which is what a screenshot test wants.
    :on-frame  optional (fn [n]) called after each presented frame.

  The handle is `{:tier :gpu :ctx ... :stop! (fn []) :frames (atom n)}` or
  `{:tier :poster :reason <string>}`."
  ([canvas backdrop] (mount! canvas backdrop nil))
  ([canvas backdrop opts]
   (let [b (byoubu/fetch (if (map? backdrop) (:byoubu/id backdrop) backdrop))]
     (if-not (supported?)
       (js/Promise.resolve {:tier :poster :reason "navigator.gpu unavailable"})
       (-> (gpu/init! canvas {:graph (graph/render-graph b)})
           (.then
            (fn [ctx]
              (if (not= :webgpu (:backend ctx))
                ;; init! fell back to WebGL2 — correct for the engine's own
                ;; scenes, useless for this shader. Say so instead of drawing
                ;; nothing.
                {:tier :poster :reason "WebGPU device unavailable; engine fell back to WebGL2"}
                (let [t0      (js/performance.now)
                      running (atom (not (false? (:animate? opts))))
                      frames  (atom 0)
                      scene   (empty-scene)
                      render!
                      (fn render! []
                        (resize! canvas)
                        (gpu/write-uniform! ctx graph/uniform-name
                                            (uniforms/pack b (frame-state canvas t0)))
                        (gpu/draw! ctx scene)
                        (swap! frames inc)
                        (when-let [f (:on-frame opts)] (f @frames)))
                      loop! (fn loop! []
                              (when @running
                                (render!)
                                (js/requestAnimationFrame loop!)))]
                  (render!)                      ;; always present one frame
                  (when @running (js/requestAnimationFrame loop!))
                  {:tier   :gpu
                   :ctx    ctx
                   :frames frames
                   :render! render!
                   :stop!  (fn [] (reset! running false))}))))
           (.catch (fn [e]
                     {:tier :poster
                      :reason (str "WebGPU init failed: " (.-message e))})))))))

(defn stop!
  "Stop a handle's animation loop. Safe on a :poster handle."
  [handle]
  (when-let [f (:stop! handle)] (f))
  handle)
