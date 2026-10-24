(ns ui_gpu
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-ui-gpu Rust crate
  (`kami-ui-gpu/src/lib.rs`, 354 lines; deleted in kotoba-lang/kami-engine PR #82
  \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  Purpose: GPU-instanced UI primitives for wgpu. The original crate defined instance
  buffer layouts (`UiRect` / `UiText` / `UiColorGlyph`) and a `UiLayer` command batcher
  that flattens draw commands (rect / rounded-rect / bordered-rect / circle / gradient /
  text / color-glyph) into per-kind instance vectors ready for GPU upload, plus a
  reusable `ToastStack` notification-queue primitive (push / tick / render) built on top
  of the layer. This namespace ports all of that as pure data (plain maps with keyword
  keys) + pure functions: instance construction, command batching, and the
  circle->rect / gradient->rect flattening math. There is no literal wgpu pipeline,
  shader, or device code in the original file to skip — everything here is portable
  logic. Native GPU submission (wgpu / wasmtime / wasmi) stays substrate and is out of
  scope for this namespace.")

;; ── UI element instance shapes (documented as plain maps) ──────────────
;;
;; UiRect   :: {:position [x y] :size [w h] :color [r g b a]
;;              :border-color [r g b a] :corner-radius px :border-width px}
;; UiText   :: {:position [x y] :size [w h] :uv-rect [u0 v0 u1 v1] :color [r g b a]}
;; UiColorGlyph :: {:position [x y] :size [w h] :uv-rect [u0 v0 u1 v1]}
;;
;; (The Rust `_pad` field exists only for GPU struct alignment / `bytemuck::Pod`
;; layout and has no portable logic; it is omitted here.)

(defn ui-rect
  "Construct a UiRect instance map. Defaults border-color to transparent black,
  corner-radius/border-width to 0.0, matching the Rust `UiRect` field defaults used
  by `UiLayer/rect`."
  [{:keys [position size color border-color corner-radius border-width]
    :or {border-color [0.0 0.0 0.0 0.0]
         corner-radius 0.0
         border-width 0.0}}]
  {:position position
   :size size
   :color color
   :border-color border-color
   :corner-radius corner-radius
   :border-width border-width})

(defn ui-text
  "Construct a UiText instance map."
  [position size uv-rect color]
  {:position position :size size :uv-rect uv-rect :color color})

(defn ui-color-glyph
  "Construct a UiColorGlyph instance map."
  [position size uv-rect]
  {:position position :size size :uv-rect uv-rect})

;; ── Gradient direction ──────────────────────────────────────────────────

(def gradient-dir-values
  "Valid values for `:direction` on a `:gradient` UiCommand (Rust `GradientDir` enum)."
  #{:horizontal :vertical :diagonal})

;; ── UI draw commands (Rust `UiCommand` enum -> tagged maps) ─────────────
;;
;; {:kind :rect :rect <UiRect>}
;; {:kind :text :text <UiText>}
;; {:kind :color-glyph :glyph <UiColorGlyph>}
;; {:kind :circle :center [x y] :radius r :color [r g b a]}
;; {:kind :gradient :rect <UiRect> :color-end [r g b a] :direction <gradient-dir>}

;; ── UiLayer: batched draw commands for a single render pass ─────────────

(defn ui-layer
  "Create an empty UiLayer. Mirrors Rust `UiLayer::new(w, h)`."
  [screen-width screen-height]
  {:commands []
   :screen-width screen-width
   :screen-height screen-height})

(defn add-command
  "Append a draw command map to a UiLayer's command vector."
  [layer command]
  (update layer :commands conj command))

(defn rect
  "Append a sharp-cornered, borderless filled rect. Mirrors `UiLayer::rect`."
  [layer x y w h color]
  (add-command layer
               {:kind :rect
                :rect (ui-rect {:position [x y] :size [w h] :color color})}))

(defn rounded-rect
  "Append a rounded filled rect. Mirrors `UiLayer::rounded_rect`."
  [layer x y w h color radius]
  (add-command layer
               {:kind :rect
                :rect (ui-rect {:position [x y] :size [w h] :color color
                                 :corner-radius radius})}))

(defn bordered-rect
  "Append a filled + bordered rect. Mirrors `UiLayer::bordered_rect`."
  [layer x y w h color border bw radius]
  (add-command layer
               {:kind :rect
                :rect (ui-rect {:position [x y] :size [w h] :color color
                                 :border-color border :border-width bw
                                 :corner-radius radius})}))

(defn circle
  "Append a circle command. Mirrors `UiLayer::circle`."
  [layer cx cy r color]
  (add-command layer {:kind :circle :center [cx cy] :radius r :color color}))

(defn text
  "Append a text command. Mirrors `UiLayer::text`."
  [layer position size uv-rect color]
  (add-command layer {:kind :text :text (ui-text position size uv-rect color)}))

(defn color-glyph
  "Append a color-glyph command. Mirrors `UiLayer::color_glyph`."
  [layer position size uv-rect]
  (add-command layer {:kind :color-glyph :glyph (ui-color-glyph position size uv-rect)}))

(defn circle->rect
  "Flatten a `:circle` command into the equivalent bounding UiRect instance
  (square bounding box, `:corner-radius` = radius so a round-rect shader can render
  it as a circle). Mirrors the `UiCommand::Circle` arm of Rust `to_instances`."
  [{:keys [center radius color]}]
  (let [[cx cy] center]
    (ui-rect {:position [(- cx radius) (- cy radius)]
              :size [(* radius 2.0) (* radius 2.0)]
              :color color
              :corner-radius radius})))

(defn to-instances
  "Flatten all commands to UiRect instances for GPU upload: `:rect` commands pass
  their rect through, `:circle` commands flatten via `circle->rect`, `:gradient`
  commands pass their `:rect` through (color-end/direction are shader concerns, not
  instance-buffer concerns), and `:text` / `:color-glyph` commands are dropped.
  Mirrors Rust `UiLayer::to_instances`."
  [layer]
  (into []
        (keep (fn [{:keys [kind] :as cmd}]
                (case kind
                  :rect (:rect cmd)
                  :circle (circle->rect cmd)
                  :gradient (:rect cmd)
                  (:text :color-glyph) nil)))
        (:commands layer)))

(defn to-text-instances
  "Flatten all `:text` commands to UiText instances. Mirrors `UiLayer::to_text_instances`."
  [layer]
  (into [] (keep (fn [{:keys [kind text]}] (when (= kind :text) text))) (:commands layer)))

(defn to-color-glyph-instances
  "Flatten all `:color-glyph` commands to UiColorGlyph instances.
  Mirrors `UiLayer::to_color_glyph_instances`."
  [layer]
  (into [] (keep (fn [{:keys [kind glyph]}] (when (= kind :color-glyph) glyph))) (:commands layer)))

;; ── Notification / Toast primitives ──────────────────────────────────────
;; Reusable toast rendering state for any KAMI app.

(def toast-level-values
  "Valid values for toast severity (Rust `ToastLevel` enum)."
  #{:info :success :warning :error})

(defn toast-level-color
  "Fill color for a toast severity level (Nintendo-style pastels).
  Mirrors Rust `ToastLevel::color`."
  [level]
  (case level
    :info [0.36 0.58 0.95 0.95]
    :success [0.42 0.82 0.52 0.95]
    :warning [0.98 0.82 0.28 0.95]
    :error [0.95 0.42 0.42 0.95]))

(defn toast
  "Construct a Toast notification map. `remaining-ms` 0 means persistent.
  Mirrors the Rust `Toast` struct."
  [title body level remaining-ms anim-offset-y]
  {:title title :body body :level level
   :remaining-ms remaining-ms :anim-offset-y anim-offset-y})

(defn toast-stack
  "Create a ToastStack with Nintendo-style defaults. Mirrors `ToastStack::new`
  (also the `Default` impl)."
  []
  {:toasts []
   :max-visible 5
   :toast-width 320.0
   :toast-height 72.0
   :gap 8.0
   :margin-right 16.0
   :margin-top 16.0})

(defn toast-stack-push
  "Push a new toast onto the front of the stack (most-recent-first), starting its
  entrance animation offset above the stack and auto-trimming to `:max-visible`.
  Mirrors `ToastStack::push`."
  [stack title body level duration-ms]
  (let [t (toast title body level duration-ms (- (:toast-height stack)))
        toasts (into [t] (:toasts stack))
        max-visible (:max-visible stack)]
    (assoc stack :toasts
           (if (> (count toasts) max-visible)
             (subvec toasts 0 max-visible)
             toasts))))

(defn- tick-toast
  "Advance one toast's entrance animation (spring-like ease toward 0) and countdown
  timer by `dt-ms`. Mirrors the per-toast body of Rust `ToastStack::tick`."
  [dt-ms {:keys [remaining-ms anim-offset-y] :as t}]
  (let [offset' (* anim-offset-y 0.85)
        abs-offset' #?(:clj (Math/abs ^double offset') :cljs (js/Math.abs offset'))
        offset' (if (< abs-offset' 0.5) 0.0 offset')
        remaining' (if (pos? remaining-ms)
                     (max 0 (- remaining-ms dt-ms))
                     remaining-ms)]
    (assoc t :anim-offset-y offset' :remaining-ms remaining')))

(defn toast-stack-tick
  "Advance toast timers and animations by `dt-ms` (frame delta in ms), then remove
  toasts that just expired this tick (`:remaining-ms` was positive before ticking
  and reached 0). A toast pushed with `duration-ms` 0 is persistent (see `toast`)
  and is never removed here -- `tick-toast` never decrements a non-positive
  `:remaining-ms`, so distinguishing \"freshly expired\" from \"persistent\" requires
  the pre-tick value, not just the post-tick 0. Mirrors `ToastStack::tick`."
  [stack dt-ms]
  (update stack :toasts
          (fn [toasts]
            (into [] (comp (map (fn [t] [(:remaining-ms t) (tick-toast dt-ms t)]))
                            (filter (fn [[remaining-before ticked]]
                                      (or (zero? remaining-before)
                                          (pos? (:remaining-ms ticked)))))
                            (map second))
                  toasts))))

(defn toast-stack-render
  "Render the toast stack's rounded-rect backgrounds into a UiLayer, stacked
  top-right using the stack's margins/gap and each toast's current animation
  offset. Mirrors `ToastStack::render`."
  [stack layer]
  (let [x (- (:screen-width layer) (:toast-width stack) (:margin-right stack))]
    (reduce
     (fn [layer [i t]]
       (let [y (+ (:margin-top stack)
                  (* i (+ (:toast-height stack) (:gap stack)))
                  (:anim-offset-y t))]
         (rounded-rect layer x y (:toast-width stack) (:toast-height stack)
                       (toast-level-color (:level t)) 12.0)))
     layer
     (map-indexed vector (:toasts stack)))))
