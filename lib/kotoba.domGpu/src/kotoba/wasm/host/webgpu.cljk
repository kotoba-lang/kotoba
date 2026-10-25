(ns kotoba.wasm.host.webgpu
  "Browser WebGPU reference host for kotoba:dom.
  It consumes the same ABI as the WebGL host, keeps a retained host tree, emits
  layout draw ops, renders rects with WebGPU, and paints text on a canvas
  overlay until glyph atlas/text shaping is implemented."
  (:require [kotoba.wasm.host.browser-events :as browser-events]
            [kotoba.wasm.host.color :as color]
            [kotoba.wasm.host.retained :as retained]))

(def shader-source
  "struct VsOut {
     @builtin(position) pos: vec4<f32>,
     @location(0) color: vec4<f32>,
   };

   @vertex
   fn vs(@location(0) position: vec2<f32>,
         @location(1) color: vec4<f32>) -> VsOut {
     var out: VsOut;
     out.pos = vec4<f32>(position, 0.0, 1.0);
     out.color = color;
     return out;
   }

   @fragment
   fn fs(in: VsOut) -> @location(0) vec4<f32> {
     return in.color;
   }")

(defn- resize-canvas! [canvas width height dpr]
  (let [pixel-w (long (* width dpr))
        pixel-h (long (* height dpr))]
    (when (or (not= (.-width canvas) pixel-w)
              (not= (.-height canvas) pixel-h))
      (set! (.-width canvas) pixel-w)
      (set! (.-height canvas) pixel-h))
    (set! (.. canvas -style -width) (str width "px"))
    (set! (.. canvas -style -height) (str height "px"))))

(defn- clip-x [width x]
  (- (* 2 (/ x width)) 1))

(defn- clip-y [height y]
  (- 1 (* 2 (/ y height))))

(defn- rect-vertices [width height {:keys [x y w h color opacity]}]
  (let [[r g b a] (color/->rgba color (or opacity 1))
        x0 (clip-x width x)
        x1 (clip-x width (+ x w))
        y0 (clip-y height y)
        y1 (clip-y height (+ y h))]
    [x0 y0 r g b a
     x1 y0 r g b a
     x0 y1 r g b a
     x0 y1 r g b a
     x1 y0 r g b a
     x1 y1 r g b a]))

(defn- text-font-string
  "See kotoba.wasm.host.webgl's identical helper for the full rationale
   (shared here since the WebGPU host paints text through the same
   Canvas 2D text overlay technique). Also reused by measure-text-fn
   below, same as that host. `:font-family` is interpolated ahead of
   the same fixed system-font fallback this always used -- see
   kotoba.wasm.host.webgl/text-font-string's own docstring for the
   full rationale."
  [op]
  (str (when-let [fw (:font-weight op)] (when (not= "normal" fw) (str fw " ")))
       (when-let [fs (:font-style op)] (when (not= "normal" fs) (str fs " ")))
       (:font-size op 14) "px " (or (:font-family op) "ui-sans-serif, system-ui, sans-serif")))

(defn- font-metrics-fn
  "Builds a (fn [font-size font-weight font-style font-family]
   {:ascent px :descent px}) backed by `ctx`'s real
   `CanvasRenderingContext2D.measureText`, whose TextMetrics carries
   `fontBoundingBoxAscent`/`fontBoundingBoxDescent` -- the font's own
   vertical metrics, which is what a CSS line box is really built from.

   cssom.layout takes these through its `:font-metrics` theme hook and
   falls back to a documented 1.2em approximation when no host supplies
   them. Measured against a real browser, that approximation is wrong by
   a couple of pixels in every direction at once: 14px monospace is
   ascent 12 / descent 3 (a 15px content area, not 16.8), and its bold
   face is 14 / 4 (18). Since this host already sets `.font` and calls
   `measureText` for word-wrap WIDTHS at this same point, the vertical
   half costs one more property read -- and without it the engine's line
   boxes stay approximate in the one place that actually paints them.

   Falls back to the same approximation cssom.layout uses if a runtime
   does not expose the fontBoundingBox* fields (they are comparatively
   recent, and this host must not crash on an older one)."
  [ctx]
  (fn [font-size font-weight font-style font-family]
    (set! (.-font ctx) (text-font-string {:font-size font-size
                                          :font-weight font-weight
                                          :font-style font-style
                                          :font-family font-family}))
    (let [m (.measureText ctx "Hxg")
          a (.-fontBoundingBoxAscent m)
          d (.-fontBoundingBoxDescent m)
          fs (or font-size 14)]
      ;; `:x-height` -- the INK top of a lowercase `x` -- rides along
      ;; because it is one more read off an object this already has, and
      ;; because `vertical-align: middle` centres a box on
      ;; `baseline - x-height/2` and has nothing else to read it from.
      ;; Measured in Brave, 14px monospace is 6.34375, and reading the
      ;; same number back off a real `middle` box agrees to LayoutUnit's
      ;; own 1/64px. Left OUT of the map when the runtime does not expose
      ;; `actualBoundingBoxAscent`, which keeps cssom.layout's documented
      ;; baseline fallback for `middle` rather than inventing an em
      ;; fraction (measured, it ranges 0.453em to 0.545em across four
      ;; families, so there is no single one to invent).
      (let [xh (.-actualBoundingBoxAscent (.measureText ctx "x"))]
        (cond-> (if (and (number? a) (number? d))
                  {:ascent a :descent d}
                  {:ascent fs :descent (* 0.2 fs)})
          (number? xh) (assoc :x-height xh))))))

;; The families whose summary metrics Blink distrusts, measured in Brave
;; 151 on 2026-08-05 by reading `<input size=n>` and `<textarea cols=n>`
;; widths back: a control in one of these is sized from the `0` advance
;; with no max-advance slack at all, whatever its `x` advance says.
;;
;; It is keyed on the NAME, not on anything measurable about the font, and
;; Arial/Helvetica are the demonstration: identical canvas metrics here to
;; the last bit, 6%-different control widths. (Skia, Thonburi and Zapfino,
;; which older copies of Blink's list also name, measured as NOT on it.)
(def ^:private distrusted-avg-char-width-families
  #{"American Typewriter" "Arial Hebrew" "Chalkboard" "Cochin" "Courier"
    "Euphemia UCAS" "Geneva" "Gill Sans" "Helvetica" "Hoefler Text"
    "Lucida Grande" "Marker Felt" "Monaco" "Osaka" "Times"})

(defn- avg-advance-fn
  "Builds a (fn [font-size font-weight font-style font-family] px) for
   cssom.layout's `:avg-advance` hook -- the font's AVERAGE character
   advance, which is what a form control's intrinsic width is `size` (or
   `cols`) of and what no string measurement produces.

   Measured in Brave 151 on 2026-08-05 over 10 families x 11 sizes x 14
   column counts, exact on all 1,540 `<textarea cols=n>` widths:

     avg = max(w, round(w))   where w is the `x` glyph's advance

   -- the `x` advance, rounded UP to a whole pixel when its fraction is
   over a half (half-UP: Zapfino at 20px has an `x` advance of exactly
   12.5 and its controls are sized from 13) and left alone when it is
   under. Not the mean of an advance table, which is 5.4% out at 26.6666px
   and 40px; not the `0` advance, which is 6% too wide in the UA control
   face; not a fixed em fraction, which ranges 0.5em to 0.5918em across
   the families measured.

   Supplying it here matters rather than merely helping: cssom.layout's
   fallback when no host answers is the `0` advance, and its UA control
   font is the browser's real 13.3333px, so a host that leaves this
   unsupplied charges 7.4135 per character where the browser charges 7 --
   an <input size=20> 4px too wide. The engine's own comment for this is
   in avg-advance; this is the production end of it.

   Rounds at the ASKED size, never at a reference one, which is the whole
   content of the law."
  [ctx]
  (fn [font-size font-weight font-style font-family]
    (set! (.-font ctx) (text-font-string {:font-size font-size
                                          :font-weight font-weight
                                          :font-style font-style
                                          :font-family font-family}))
    (if (contains? distrusted-avg-char-width-families font-family)
      (.-width (.measureText ctx "0"))
      (let [w (.-width (.measureText ctx "x"))]
        (max w (js/Math.round w))))))

(defn- max-advance-fn
  "Builds a (fn [font-size font-weight font-style font-family] px) for
   cssom.layout's `:max-advance` hook -- the font's MAXIMUM character
   width, which an `<input size=n>` adds one glyph's worth of on top of
   its `n` average characters (`ceil(avg * n + (max - avg))`, which is why
   an `<input size=1>` is 12px of content in a face whose average
   character is 7).

   Measured the same way and on the same day over the 1,540 matching
   `<input size=n>` widths: this quantity is the font's ASCENT, exactly.
   Not a max over any advance table -- in Arial the widest ASCII glyph is
   1.015em where this is 0.9em -- and not a per-family em ratio, since no
   single ratio reproduces it across sizes. Blink says so out loud:
   `SimpleFontData::PlatformInit` falls back to `-fAscent` when the
   platform carries no max-char-width, and macOS is such a platform.

   So it is the same `fontBoundingBoxAscent` font-metrics-fn already
   reads, rounded to a whole pixel -- and 0 for a family whose metrics
   Blink distrusts, which measured as no slack at all.

   Falls back to `nil` when the runtime does not expose the field, which
   leaves cssom.layout on its own documented fallback (avg, i.e. no
   slack) rather than on an invented number."
  [ctx]
  (fn [font-size font-weight font-style font-family]
    (if (contains? distrusted-avg-char-width-families font-family)
      0
      (do (set! (.-font ctx) (text-font-string {:font-size font-size
                                                :font-weight font-weight
                                                :font-style font-style
                                                :font-family font-family}))
          (let [a (.-fontBoundingBoxAscent (.measureText ctx "Hxg"))]
            (when (number? a) (js/Math.round a)))))))

(defn- measure-text-fn
  "Builds a (fn [text font-size font-weight font-style font-family]
   width-in-px) backed by `ctx`'s real
   `CanvasRenderingContext2D.measureText` -- see
   kotoba.wasm.host.webgl's identical helper for the full rationale
   (shared here since the WebGPU host paints text through the same
   Canvas 2D text overlay technique, see render-text! below). Closes
   the same previously-documented gap that helper closes: word-wrap
   measurement now uses the REAL, resolved font-weight/font-style/
   font-family, not always normal-weight/upright/system-default
   metrics."
  [ctx]
  (fn [text font-size font-weight font-style font-family]
    (set! (.-font ctx) (text-font-string {:font-size font-size :font-weight font-weight :font-style font-style
                                          :font-family font-family}))
    (.-width (.measureText ctx text))))

(defn- draw-text-decoration!
  "See kotoba.wasm.host.webgl's identical helper for the full rationale
   (shared here since the WebGPU host paints text through the same
   Canvas 2D text overlay technique)."
  [text-ctx op baseline]
  (when-let [decoration (:text-decoration op)]
    (let [font-size (:font-size op 14)
          line-y (case decoration
                   "underline" (+ baseline (* font-size 0.12))
                   "line-through" (- baseline (* font-size 0.3))
                   "overline" (- baseline (* font-size 0.9))
                   nil)]
      (when line-y
        (let [text-width (.-width (.measureText text-ctx (:text op)))
              thickness (max 1 (/ font-size 12))]
          (.fillRect text-ctx (:x op) line-y text-width thickness))))))

(defn- render-text! [state ops]
  (let [{:keys [text-ctx text-canvas width height dpr]} state]
    (resize-canvas! text-canvas width height dpr)
    (.save text-ctx)
    (.setTransform text-ctx dpr 0 0 dpr 0 0)
    (.clearRect text-ctx 0 0 width height)
    (doseq [op ops]
      (case (:draw/op op)
        :clip (case (:clip/op op)
                ;; Canvas2D's own .clip() intersects with whatever clip
                ;; path is already active at the time of the matching
                ;; .save() (per spec), so nested `:clip` push/pop pairs
                ;; (a scrollable container inside another) need no manual
                ;; rect-intersection bookkeeping the way render-gpu!'s
                ;; scissor rects below do -- each :push's .save()+.clip()
                ;; naturally narrows down from its enclosing :push's own
                ;; clip, and :pop's .restore() naturally reverts to it.
                :push (do (.save text-ctx)
                          (.beginPath text-ctx)
                          (.rect text-ctx (:x op) (:y op) (:w op) (:h op))
                          (.clip text-ctx))
                :pop (.restore text-ctx))
        :text (let [baseline (+ (:y op) (:font-size op 14))]
                (set! (.-fillStyle text-ctx) (:color op))
                (set! (.-font text-ctx) (text-font-string op))
                (set! (.-globalAlpha text-ctx) (:opacity op 1))
                (.fillText text-ctx (:text op) (:x op) baseline)
                (draw-text-decoration! text-ctx op baseline)
                (set! (.-globalAlpha text-ctx) 1))
        nil))
    (.restore text-ctx)))

(defn- rect-intersect
  "Intersects two `{:x :y :w :h}` rects -- see kotoba.wasm.host.webgl's
   identical helper for the full rationale (shared here since nested
   `:clip` push/pop ops need the same narrowing-to-ancestor behavior
   regardless of backend)."
  [a b]
  (let [x1 (max (:x a) (:x b))
        y1 (max (:y a) (:y b))
        x2 (min (+ (:x a) (:w a)) (+ (:x b) (:w b)))
        y2 (min (+ (:y a) (:h a)) (+ (:y b) (:h b)))]
    {:x x1 :y y1 :w (max 0 (- x2 x1)) :h (max 0 (- y2 y1))}))

(defn- clip-rect-px
  "Scales a `:clip` draw op's x/y/w/h -- CSS/logical pixels, the same
   coordinate space rect-vertices' own x/y/w/h already use -- into
   physical framebuffer pixels by `dpr`, matching what `setScissorRect`
   expects (the physical swapchain texture, not the logical CSS pixel
   grid draw ops are expressed in). See kotoba.wasm.host.webgl's
   identical helper for the WebGL-side counterpart; unlike WebGL,
   `setScissorRect`'s origin is already top-left, so no y-flip is needed
   here."
  [dpr op]
  {:x (long (* dpr (:x op))) :y (long (* dpr (:y op)))
   :w (long (* dpr (:w op))) :h (long (* dpr (:h op)))})

(defn- clip-segments
  "Walks `ops` in order, threading a clip-rect stack through `:clip`
   push/pop ops (see cssom.layout/layout-block, which brackets any
   element whose `overflow` isn't `visible` with matched
   `{:draw/op :clip :clip/op :push/:pop}` pairs carrying that element's
   own x/y/w/h border box), and groups consecutive `:rect` ops that share
   the same active clip rect into one segment.

   This exists because, unlike webgl.cljs's render! (which walks ops one
   at a time in its own doseq, so a scissor rect can simply be changed
   in between individual draw calls), render-gpu! below batches every
   `:rect` op across the WHOLE frame into one vertex buffer and issues a
   SINGLE `.draw` call -- a scissor rect can only take effect BETWEEN
   draw calls, not mid-draw, so supporting per-element clipping means
   splitting that one draw call into one per contiguous run of rects that
   share an active clip.

   When no `:clip` ops are present at all (the common case: nothing on
   the page uses non-visible `overflow`), every `:rect` op shares the
   same (nil) active clip and this collapses back to exactly one segment
   -- i.e. exactly the single whole-frame draw call render-gpu! always
   issued before clip support existed, with no performance regression for
   pages that don't scroll/clip anything."
  [ops dpr fb-width fb-height]
  (let [full {:x 0 :y 0 :w fb-width :h fb-height}]
    (loop [remaining ops stack [] segments [] current nil]
      (if-let [op (first remaining)]
        (case (:draw/op op)
          :rect
          (let [scissor (peek stack)]
            (if (and current (= (:scissor current) scissor))
              (recur (rest remaining) stack segments (update current :rects conj op))
              (recur (rest remaining) stack (cond-> segments current (conj current))
                     {:scissor scissor :rects [op]})))
          :clip
          (recur (rest remaining)
                 (case (:clip/op op)
                   :push (conj stack (rect-intersect (or (peek stack) full)
                                                      (clip-rect-px dpr op)))
                   :pop (pop stack))
                 segments current)
          (recur (rest remaining) stack segments current))
        (cond-> segments current (conj current))))))

(defn- render-gpu! [state ops]
  (let [{:keys [device context pipeline vertex-buffer width height dpr]} state
        ^js device device
        ^js context context
        ^js pipeline pipeline
        ^js vertex-buffer vertex-buffer
        ^js gpu-canvas (:gpu-canvas state)
        ^js queue (.-queue device)
        fb-width (.-width gpu-canvas)
        fb-height (.-height gpu-canvas)
        segments (clip-segments ops dpr fb-width fb-height)
        seg-floats (mapv (fn [seg] (vec (mapcat #(rect-vertices width height %) (:rects seg)))) segments)
        data (js/Float32Array. (clj->js (vec (mapcat identity seg-floats))))
        byte-length (.-byteLength data)]
    ;; All segments' vertex data is written in ONE writeBuffer call (at
    ;; increasing offsets implied by concatenation order) so every
    ;; segment's later .draw call can address its own slice via
    ;; `first-vertex` below -- writing each segment separately right
    ;; before its own .draw would NOT work: queue.writeBuffer calls are
    ;; all ordered before this function's single .submit, but a command
    ;; buffer's draw calls only actually read the buffer's contents when
    ;; the GPU executes them AFTER .submit, by which point a second
    ;; writeBuffer to the same bytes would have already silently
    ;; clobbered the first segment's data underneath both draw calls.
    (when (pos? byte-length)
      (.writeBuffer queue vertex-buffer 0 data))
    (let [^js encoder (.createCommandEncoder device)
          ^js texture (.getCurrentTexture context)
          view (.createView texture)
          ^js pass (.beginRenderPass
                    encoder
                    #js {:colorAttachments
                         #js [#js {:view view
                                   :clearValue #js {:r 0.043 :g 0.055 :b 0.078 :a 1}
                                   :loadOp "clear"
                                   :storeOp "store"}]})]
      (.setPipeline pass pipeline)
      (when (pos? byte-length)
        (.setVertexBuffer pass 0 vertex-buffer)
        (loop [segs segments floats-seq seg-floats first-vertex 0]
          (when-let [seg (first segs)]
            (let [vcount (/ (count (first floats-seq)) 6)
                  {:keys [x y w h]} (or (:scissor seg) {:x 0 :y 0 :w fb-width :h fb-height})]
              (.setScissorRect pass x y w h)
              (when (pos? vcount)
                (.draw pass vcount 1 first-vertex))
              (recur (rest segs) (rest floats-seq) (+ first-vertex vcount))))))
      (.end pass)
      (.submit queue #js [(.finish encoder)]))))

(defn- render! [state]
  (let [ops (retained/draw-ops state {:measure-text (measure-text-fn (:text-ctx state))
                                      :font-metrics (font-metrics-fn (:text-ctx state))
                                      :avg-advance (avg-advance-fn (:text-ctx state))
                                      :max-advance (max-advance-fn (:text-ctx state))
                                      :theme (:theme state)})
        ;; (max ...), never a bare replacement: a caller-supplied :height
        ;; stays an honored MINIMUM, the content's own real extent only
        ;; ever grows the canvas, never shrinks it below that floor --
        ;; mirrors kotoba.wasm.host.webgl/render!'s own identical fix (see
        ;; retained/content-height's own docstring). Previously missing
        ;; here entirely: this host's render! resized the canvas straight
        ;; from the raw, never-updated :height in state, so any page
        ;; taller than the initial viewport height rendered permanently
        ;; clipped under WebGPU while the identical ops rendered full
        ;; height under WebGL.
        height (max (:height state) (retained/content-height ops))
        state (assoc state :height height)]
    (resize-canvas! (:gpu-canvas state) (:width state) (:height state) (:dpr state))
    (render-gpu! state ops)
    (render-text! state ops)
    (assoc state :draw-ops ops)))

(defn- apply-webgpu-op! [webgpu-host op]
  (swap! (:state webgpu-host) retained/apply-op op)
  nil)

(defn- present-webgpu! [webgpu-host]
  (swap! (:state webgpu-host) render!)
  nil)

(defn- poll-webgpu-event! [webgpu-host]
  (let [[event state] (retained/poll-event @(:state webgpu-host))]
    (when event
      (reset! (:state webgpu-host) state)
      event)))

(defn enqueue-event! [webgpu-host event]
  (swap! (:state webgpu-host) retained/enqueue-event event)
  nil)

(defn install-pointer-events! [webgpu-host canvas pump!]
  (browser-events/install-canvas-events! webgpu-host canvas pump!))

(defn create-host!
  "Returns a Promise resolving to a function-map DomHost."
  [{:keys [gpu-canvas text-canvas width height theme]}]
  (if-not (.-gpu js/navigator)
    (js/Promise.reject (js/Error. "WebGPU is not available in this browser"))
    (-> (.requestAdapter (.-gpu js/navigator))
        (.then (fn [adapter]
                 (if-not adapter
                   (js/Promise.reject (js/Error. "No WebGPU adapter available"))
                   (let [^js adapter adapter]
                     (.requestDevice adapter)))))
        (.then
         (fn [device]
           (let [^js device device
                 ^js context (.getContext gpu-canvas "webgpu")
                 format (.getPreferredCanvasFormat (.-gpu js/navigator))
                 text-ctx (.getContext text-canvas "2d")
                 module (.createShaderModule device #js {:code shader-source})
                 pipeline (.createRenderPipeline
                           device
                           #js {:layout "auto"
                                :vertex #js {:module module
                                             :entryPoint "vs"
                                             :buffers
                                             #js [#js {:arrayStride 24
                                                       :attributes
                                                       #js [#js {:shaderLocation 0 :offset 0 :format "float32x2"}
                                                            #js {:shaderLocation 1 :offset 8 :format "float32x4"}]}]}
                                :fragment #js {:module module
                                               :entryPoint "fs"
                                               ;; Standard "over" alpha blending so :rect ops
                                               ;; carrying a fractional :opacity (nested CSS
                                               ;; `opacity` cascaded down by cssom.layout, threaded
                                               ;; through rect-vertices' per-vertex color above)
                                               ;; actually blend against whatever this render pass
                                               ;; already drew/cleared instead of just overwriting
                                               ;; it -- without this, the fragment shader's alpha
                                               ;; output has no visual effect at all.
                                               :targets #js [#js {:format format
                                                                  :blend #js {:color #js {:srcFactor "src-alpha"
                                                                                          :dstFactor "one-minus-src-alpha"
                                                                                          :operation "add"}
                                                                              :alpha #js {:srcFactor "src-alpha"
                                                                                          :dstFactor "one-minus-src-alpha"
                                                                                          :operation "add"}}}]}
                                :primitive #js {:topology "triangle-list"}})
                 vertex-buffer (.createBuffer device #js {:size (* 6 4096 4)
                                                          :usage (bit-or js/GPUBufferUsage.VERTEX
                                                                         js/GPUBufferUsage.COPY_DST)})]
             ;; alphaMode only governs how this canvas's own final output
             ;; alpha composites against the DOM page behind it (parity
             ;; with webgl.cljs's `#js {:alpha false}` context attribute);
             ;; it has no effect on how draw ops within a single frame
             ;; blend against each other or against the pass's own
             ;; clearValue -- that is entirely the render pipeline's
             ;; :blend state above. So "opaque" stays correct here and
             ;; does not need to become "premultiplied" for this fix.
             (.configure context #js {:device device :format format :alphaMode "opaque"})
             {:state (atom (merge retained/base-state
                                  {:device device
                                   :context context
                                   :pipeline pipeline
                                   :vertex-buffer vertex-buffer
                                   :gpu-canvas gpu-canvas
                                   :text-canvas text-canvas
                                   :text-ctx text-ctx
                                   :width (or width 640)
                                   :height (or height 360)
                                   :dpr (or (.-devicePixelRatio js/window) 1)
                                   ;; nil unless the embedder says
                                   ;; otherwise, leaving cssom.layout's own
                                   ;; default theme in charge exactly as
                                   ;; before. A host painting web pages
                                   ;; should pass one (see
                                   ;; retained/draw-ops).
                                   :theme theme}))
              :apply-op! apply-webgpu-op!
              :present! present-webgpu!
              :poll-event! poll-webgpu-event!}))))))

(defn state [webgpu-host]
  @(:state webgpu-host))
