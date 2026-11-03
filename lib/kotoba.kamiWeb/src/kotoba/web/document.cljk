(ns kotoba.web.document
  "PPTX slide → 2D draw-primitive layout, ported from `kami-web/src/document.rs`.

  The Rust `render_document_frame` mixes pure layout math (EMU→px
  conversion, hex-color parsing, per-shape geometry, selection-handle
  placement, slide-fit scale/offset) with a wgpu instanced-rect pipeline.
  This namespace ports **only the pure half**: given a slide EDN map and a
  canvas size, it produces a plain vector of draw primitives (`:rect`,
  `:rounded-rect`, `:bordered-rect`, `:circle`) — the render-IR-shaped data
  a real GPU/canvas backend would consume. It never touches wgpu/DOM.

  Left unported (adapter-only, stays in Rust): `create_ui_pipeline` (WGSL
  shader + wgpu pipeline for the instanced SDF rounded-rect draw),
  `check_document_gpu` / `document_gpu_info` (adapter capability probes),
  and `render_document_frame` itself (canvas lookup, surface setup,
  instance buffer upload, submit/present)."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------
;; EMU <-> px (OOXML native unit is EMU: 914400 per inch)
;; ---------------------------------------------------------------------

(def emu-per-inch 914400.0)
(def px-per-inch 96.0)

(defn emu->px [emu] (* emu (/ px-per-inch emu-per-inch)))

;; ---------------------------------------------------------------------
;; Color parsing
;; ---------------------------------------------------------------------

(defn hex->rgba
  "Parse a `#RRGGBB` (or `RRGGBB`) hex string to `[r g b a]` floats in
  `[0,1]`. Falls back to mid-gray `[0.5 0.5 0.5 1.0]` on malformed input,
  matching `document.rs::hex_to_rgba`."
  [hex]
  (let [h (if (and (string? hex) (str/starts-with? hex "#")) (subs hex 1) hex)]
    (if (or (nil? h) (< (count h) 6))
      [0.5 0.5 0.5 1.0]
      (try
        (let [parse (fn [s] #?(:clj (Integer/parseInt s 16) :cljs (js/parseInt s 16)))
              r (/ (double (parse (subs h 0 2))) 255.0)
              g (/ (double (parse (subs h 2 4))) 255.0)
              b (/ (double (parse (subs h 4 6))) 255.0)]
          [r g b 1.0])
        (catch #?(:clj Exception :cljs :default) _
          [0.5 0.5 0.5 1.0])))))

;; ---------------------------------------------------------------------
;; Slide fit — scale + centering offset for a slide (EMU) inside a canvas (px)
;; ---------------------------------------------------------------------

(def slide-margin-px 40.0)

(defn slide-fit
  "`{:scale :offset-x :offset-y}` to center a `slide` `{:width :height}`
  (EMU) inside a `canvas-width` x `canvas-height` px viewport with a 40px
  margin, uniformly scaled and never upscaled past `1.0` — matches
  `render_document_frame`'s `scale_x`/`scale_y`/`offset_x`/`offset_y`."
  [{:keys [width height]} canvas-width canvas-height]
  (let [slide-px-w (emu->px width)
        slide-px-h (emu->px height)
        scale-x (/ (- canvas-width slide-margin-px) slide-px-w)
        scale-y (/ (- canvas-height slide-margin-px) slide-px-h)
        scale (min scale-x scale-y 1.0)
        offset-x (/ (- canvas-width (* slide-px-w scale)) 2.0)
        offset-y (/ (- canvas-height (* slide-px-h scale)) 2.0)]
    {:scale scale :offset-x offset-x :offset-y offset-y}))

;; ---------------------------------------------------------------------
;; Shape -> draw primitives
;; ---------------------------------------------------------------------

(def selection-color [0.29 0.56 0.85 0.8]) ; #4a90d9

(defn- shape-rect [{:keys [x y w h]} scale offset-x offset-y]
  {:x (+ offset-x (* (emu->px x) scale))
   :y (+ offset-y (* (emu->px y) scale))
   :w (* (emu->px w) scale)
   :h (* (emu->px h) scale)})

(defn- stroke-width-px [shape scale]
  (max 1.0 (* (emu->px (or (:stroke-width shape) 0.0)) scale)))

(defn shape->primitives
  "One `shape` (a map like the Rust `DocumentShape`) -> a vector of draw
  primitives in slide-fit screen space. Mirrors `document.rs::build_slide_layer`'s
  per-shape-type `match` (ellipse/roundRect/line/triangle/default) plus the
  selection-indicator (bordered rect + 8 resize handles + rotation handle)."
  [shape scale offset-x offset-y selected?]
  (if (false? (:visible shape))
    []
    (let [{:keys [x y w h]} (shape-rect shape scale offset-x offset-y)
          fill (some-> (:fill shape) hex->rgba)
          has-fill? (and (:fill shape) (not= (:type shape) "line"))
          base
          (case (:type shape)
            "ellipse"
            (let [r (/ (min w h) 2.0)]
              (cond-> []
                has-fill? (conj {:type :rounded-rect :x x :y y :w w :h h :color fill :radius r})
                (:stroke shape)
                (conj {:type :bordered-rect :x x :y y :w w :h h
                       :color [0.0 0.0 0.0 0.0] :border-color (hex->rgba (:stroke shape))
                       :border-width (stroke-width-px shape scale) :radius r})))

            "roundRect"
            (let [r (if (:corner-radius shape) (* (emu->px (:corner-radius shape)) scale) (* (min w h) 0.1))]
              (cond-> []
                has-fill? (conj {:type :rounded-rect :x x :y y :w w :h h :color fill :radius r})
                (:stroke shape)
                (conj {:type :bordered-rect :x x :y y :w w :h h
                       :color [0.0 0.0 0.0 0.0] :border-color (hex->rgba (:stroke shape))
                       :border-width (stroke-width-px shape scale) :radius r})))

            "line"
            (let [sc (if (:stroke shape) (hex->rgba (:stroke shape)) [0.0 0.0 0.0 1.0])
                  lw (stroke-width-px shape scale)]
              [{:type :rect :x x :y (- (+ y (/ h 2.0)) (/ lw 2.0)) :w w :h lw :color sc}])

            "triangle"
            (if has-fill? [{:type :rect :x x :y y :w w :h h :color fill}] [])

            ;; rect, textBox, arrow, freeform, and any unrecognised type
            (cond-> []
              has-fill? (conj {:type :rect :x x :y y :w w :h h :color fill})
              (:stroke shape)
              (conj {:type :bordered-rect :x x :y y :w w :h h
                     :color [0.0 0.0 0.0 0.0] :border-color (hex->rgba (:stroke shape))
                     :border-width (stroke-width-px shape scale) :radius 0.0})))
          selection
          (when selected?
            (let [hs 8.0
                  handle-fill [1.0 1.0 1.0 1.0]
                  positions [[(- x (/ hs 2.0)) (- y (/ hs 2.0))]
                             [(- (+ x (/ w 2.0)) (/ hs 2.0)) (- y (/ hs 2.0))]
                             [(- (+ x w) (/ hs 2.0)) (- y (/ hs 2.0))]
                             [(- (+ x w) (/ hs 2.0)) (- (+ y (/ h 2.0)) (/ hs 2.0))]
                             [(- (+ x w) (/ hs 2.0)) (- (+ y h) (/ hs 2.0))]
                             [(- (+ x (/ w 2.0)) (/ hs 2.0)) (- (+ y h) (/ hs 2.0))]
                             [(- x (/ hs 2.0)) (- (+ y h) (/ hs 2.0))]
                             [(- x (/ hs 2.0)) (- (+ y (/ h 2.0)) (/ hs 2.0))]]
                  rot-y (- y 30.0)]
              (into
               (into [{:type :bordered-rect :x (- x 2.0) :y (- y 2.0) :w (+ w 4.0) :h (+ h 4.0)
                       :color [0.0 0.0 0.0 0.0] :border-color selection-color :border-width 2.0 :radius 0.0}]
                     (map (fn [[hx hy]]
                            {:type :bordered-rect :x hx :y hy :w hs :h hs
                             :color handle-fill :border-color selection-color :border-width 1.0 :radius 0.0}))
                     positions)
               [{:type :circle :x (+ x (/ w 2.0)) :y rot-y :r 5.0 :color selection-color}
                {:type :rect :x (- (+ x (/ w 2.0)) 0.5) :y (+ rot-y 5.0) :w 1.0 :h (- 25.0 5.0) :color selection-color}])))]
      (into base selection))))

(defn build-slide-layer
  "`slide` `{:width :height :background :shapes [...] :selected-ids #{...}}`
  -> a flat vector of draw primitives (slide background + border + each
  shape's primitives + selection indicators), in slide-fit screen space at
  `scale`/`offset-x`/`offset-y` (see [[slide-fit]]). Direct port of
  `document.rs::build_slide_layer`."
  [{:keys [width height background shapes selected-ids] :as _slide} scale offset-x offset-y]
  (let [sw (* (emu->px width) scale)
        sh (* (emu->px height) scale)
        bg (if background (hex->rgba background) [1.0 1.0 1.0 1.0])
        selected-ids (or selected-ids #{})
        base [{:type :rect :x offset-x :y offset-y :w sw :h sh :color bg}
              {:type :bordered-rect :x offset-x :y offset-y :w sw :h sh
               :color [0.0 0.0 0.0 0.0] :border-color [0.2 0.2 0.2 1.0] :border-width 1.0 :radius 0.0}]]
    (into base
          (mapcat (fn [shape]
                     (shape->primitives shape scale offset-x offset-y
                                         (contains? selected-ids (:id shape)))))
          shapes)))

(defn render-document-layer
  "Compose [[slide-fit]] + [[build-slide-layer]] for `slide` at
  `canvas-width`x`canvas-height` — the pure computation
  `render_document_frame` performs before handing primitives to wgpu."
  [slide canvas-width canvas-height]
  (let [{:keys [scale offset-x offset-y]} (slide-fit slide canvas-width canvas-height)]
    (build-slide-layer slide scale offset-x offset-y)))
