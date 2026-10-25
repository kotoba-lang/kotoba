(ns kami-ui-sdk.widgets
  "DOM-materializing UI components — `slider!`, `color-swatch!`,
   `carousel!` — ported from kami-engine's live `kami-ui-sdk/kami-ui.js`
   `Slider`/`ColorSwatch`/`Carousel` (added in kami-engine commit
   `0924d040e1aab528491a779f934e6969c32a203a`, ADR-2607031200 Phase 4).

   **Deliberate, scoped exception to this repo's own 'no DOM in CLJC'
   rule** (see root README / `kami-ui-sdk.ui`'s docstring, which excluded
   *all* DOM construction from the `kami-ui.js` port). That exclusion was
   the right call for a 1:1 restoration of many small, DOM-heavy
   components with no cross-platform reader — the pure logic (theme,
   layout math, style derivation) was the only genuinely portable part.
   These 3 components are different: they are *browser-only widgets* by
   nature (a draggable slider has no meaning outside a DOM), so keeping
   them JS-only bought no cross-platform benefit, only a second
   implementation to keep in sync with `kotoba-lang/kami-ui-sdk`'s spring/
   easing math (`kami-ui-sdk.motion`). The `#?(:cljs ... :clj (throw
   ...))` guard pattern already has precedent in this org —
   `kotoba-lang/kami-app-character-creator`'s `character-creator.persistence`
   namespace (`localStorage`/file-download) uses the identical shape.

   Each widget's `:cljs` body does real `js/document` construction but
   reuses this repo's already-ported *pure* logic wherever it can instead
   of re-deriving it: `kami-ui-sdk.ui/theme` (colors/radii/shadows),
   `kami-ui-sdk.motion/spring-init-state` + `spring-tick` +
   `apply-transform` (the thumb spring-settle, the swatch selection pulse,
   the carousel page slide — all driven by this repo's already-tested pure
   physics step, not a re-implementation). Only the `requestAnimationFrame`
   driver loop (`run-spring!`, below) and the DOM tree itself are new.

   `KamiSound.play(...)` calls in the JS original are NOT reproduced as
   live Web Audio playback here — `kami-ui-sdk.sound` only ported the
   *pure* preset/envelope data (no live `AudioContext`, same exclusion
   rationale as the rest of this repo). Instead each widget takes an
   optional `:on-sound (fn [preset-kw])` callback (default a no-op) so a
   caller who *does* have a live sound engine wired up can react to it;
   this is a deliberate behavior difference from the JS version's
   `if (root.KamiSound) root.KamiSound.play(...)` auto-play, not an
   oversight.

   `:clj` calls throw a clear `ex-info` rather than silently no-op'ing."
  (:require [kotoba.lang.text] [kami-ui-sdk.ui :as ui]
            [kami-ui-sdk.motion :as motion]))

(defn- browser-only! [fn-name]
  (throw (ex-info (str "kami-ui-sdk.widgets/" fn-name
                        " is browser-only (ClojureScript); not available under :clj.")
                   {:kami-ui-sdk/error :not-browser :fn fn-name})))

;; ─── :cljs-only implementation ───────────────────────────────────────
;; Everything below this reader-conditional boundary is real DOM code;
;; it is simply absent from :clj compilation (not merely guarded).

#?(:cljs
   (do

(defn- apply-base!
  "Sets `font-family`/`box-sizing` (mirrors JS `_applyBase`'s defaults)
   then every `styles` entry via `CSSStyleDeclaration.setProperty` with
   the keyword's own name as the (kebab-case) CSS property — no
   kebab->camel conversion needed, `setProperty` takes real CSS names."
  [el styles]
  (.setProperty (.-style el) "font-family" (:font ui/theme))
  (.setProperty (.-style el) "box-sizing" "border-box")
  (doseq [[k v] styles]
    (.setProperty (.-style el) (name k) (str v)))
  el)

(defn- el! [tag styles]
  (apply-base! (.createElement js/document tag) styles))

(defn- run-spring!
  "Drives one spring animation to settle via `requestAnimationFrame`,
   using this repo's already-ported `kami-ui-sdk.motion/spring-init-state`
   + `spring-tick` (pure physics step) — only the RAF clock/loop is new.
   `target-props` is `spring-init-state`-shaped (`{prop [from to]}` or
   `{prop to}`). `on-frame` is called every tick with the full state map
   (feed it to `motion/apply-transform`). `on-complete` (optional) fires
   once, after the frame in which every property settles."
  ([target-props opts on-frame] (run-spring! target-props opts on-frame nil))
  ([target-props opts on-frame on-complete]
   (let [!state (atom (motion/spring-init-state target-props))
         !last-ts (atom nil)]
     (letfn [(tick [ts]
               (let [dt (if @!last-ts (/ (- ts @!last-ts) 1000) (/ 1 60))
                     _ (reset! !last-ts ts)
                     {:keys [state settled?]} (motion/spring-tick @!state dt opts)]
                 (reset! !state state)
                 (on-frame state)
                 (if settled?
                   (when on-complete (on-complete))
                   (js/requestAnimationFrame tick))))]
       (js/requestAnimationFrame tick)))))

;; ─── Slider ────────────────────────────────────────────────────────

(defn- slider-impl!
  [container opts]
  (let [lo (get opts :min 0)
        hi (get opts :max 1)
        step (get opts :step 0.01)
        color (get opts :color (get-in ui/theme [:accent :blue]))
        on-change (get opts :on-change (fn [_]))
        on-sound (get opts :on-sound (fn [_]))
        !value (atom (-> (get opts :value lo) (max lo) (min hi)))
        wrap (el! "div" {:display "grid" :gap "6px" :width "100%"})
        row (el! "div" {:display "flex" :justify-content "space-between" :align-items "baseline"})
        label-el (el! "span" {:color (:text-secondary ui/theme) :font-size "12px" :font-weight "800"})
        value-el (el! "span" {:color (:text-primary ui/theme) :font-size "12px" :font-weight "900"})
        track (el! "div" {:position "relative" :height "18px" :cursor "pointer" :touch-action "none"})
        track-line (el! "div" {:position "absolute" :top "7px" :left "0" :right "0" :height "4px"
                                :border-radius "2px" :background (:card-border ui/theme)})
        track-fill (el! "div" {:position "absolute" :top "7px" :left "0" :height "4px"
                                :border-radius "2px" :background color :width "0px"})
        thumb (el! "div" {:position "absolute" :top "2px" :left "0" :width "14px" :height "14px"
                           :border-radius "50%" :background "#fff" :border (str "3px solid " color)
                           :box-shadow (:shadow-small ui/theme) :transform "translateX(-7px)"})]
    (set! (.-textContent label-el) (or (:label opts) ""))
    (.appendChild track track-line) (.appendChild track track-fill) (.appendChild track thumb)
    (.appendChild row label-el) (.appendChild row value-el)
    (.appendChild wrap row) (.appendChild wrap track)
    (when container (.appendChild container wrap))
    (let [!current-x (atom -7.0)]
     (letfn [(paint! [v animate?]
              (let [p (-> (/ (- v lo) (- hi lo)) (max 0) (min 1))
                    rect-w (.-width (.getBoundingClientRect track))
                    track-w (if (pos? rect-w) rect-w 100)
                    x (* p track-w)
                    tx (- x 7)]
                (.setProperty (.-style track-fill) "width" (str x "px"))
                (set! (.-textContent value-el)
                      (if (< step 1) (.toFixed v 2) (str (js/Math.round v))))
                (if animate?
                  ;; spring FROM wherever the thumb currently sits (@!current-x), not
                  ;; from 0 — `spring-init-state`'s `current-val-fn` default reads
                  ;; `getComputedStyle` in the JS original (excluded, see motion.cljc's
                  ;; docstring), so the "from" is passed explicitly here instead.
                  (run-spring! {:x [@!current-x tx]} {:stiffness 420 :damping 24}
                               (fn [state]
                                 (let [x' (get-in state [:x :pos])]
                                   (reset! !current-x x')
                                   (.setProperty (.-style thumb) "transform"
                                                 (:transform (motion/apply-transform state))))))
                  (do (reset! !current-x tx)
                      (.setProperty (.-style thumb) "transform" (str "translateX(" tx "px)"))))))
            (from-client-x [client-x]
              (let [rect (.getBoundingClientRect track)
                    p (-> (/ (- client-x (.-left rect)) (.-width rect)) (max 0) (min 1))
                    v (+ lo (* p (- hi lo)))
                    v (* (js/Math.round (/ v step)) step)]
                (-> v (max lo) (min hi))))]
      (let [dragging? (atom false)]
        (.addEventListener track "pointerdown"
          (fn [e]
            (reset! dragging? true)
            (.setPointerCapture track (.-pointerId e))
            (let [v (from-client-x (.-clientX e))]
              (when (not= v @!value) (reset! !value v) (on-change v)))
            (paint! @!value false)
            (on-sound :click)))
        (.addEventListener track "pointermove"
          (fn [e]
            (when @dragging?
              (let [v (from-client-x (.-clientX e))]
                (when (not= v @!value)
                  (reset! !value v) (on-change v) (paint! v false) (on-sound :tick))))))
        (.addEventListener track "pointerup"
          (fn [e]
            (reset! dragging? false)
            (.releasePointerCapture track (.-pointerId e))
            (paint! @!value true))))
      (js/requestAnimationFrame (fn [_] (paint! @!value false)))
      {:el wrap
       :get-value (fn [] @!value)
       :set-value (fn
                    ([v] (reset! !value (-> v (max lo) (min hi))) (paint! @!value true))
                    ([v animate?] (reset! !value (-> v (max lo) (min hi))) (paint! @!value animate?)))
       :destroy (fn [] (.remove wrap))}))))

;; ─── ColorSwatch ───────────────────────────────────────────────────

(defn- color-swatch-impl!
  [container opts]
  (let [presets (or (:presets opts) (vals (:accent ui/theme)))
        on-change (get opts :on-change (fn [_]))
        on-sound (get opts :on-sound (fn [_]))
        !value (atom (or (:value opts) (first presets)))
        wrap (el! "div" {:display "flex" :gap "8px" :align-items "center" :flex-wrap "wrap"})
        swatch-els (atom {})
        make-swatch (fn [hex]
                      (let [sw (el! "button"
                                    {:appearance "none" :width "26px" :height "26px" :border-radius "50%"
                                     :background hex :cursor "pointer" :padding "0"
                                     :border (str "3px solid " (if (= hex @!value) (:text-primary ui/theme) "transparent"))
                                     :box-shadow (:shadow-small ui/theme)
                                     :transition "border-color 120ms ease"})]
                        (set! (.-type sw) "button")
                        sw))]
    (doseq [hex presets]
      (let [sw (make-swatch hex)]
        (swap! swatch-els assoc hex sw)
        (.appendChild wrap sw)))
    (letfn [(select! [hex]
              (when-let [prev (get @swatch-els @!value)]
                (.setProperty (.-style prev) "border-color" "transparent"))
              (reset! !value hex)
              (when-let [sw (get @swatch-els hex)]
                (.setProperty (.-style sw) "border-color" (:text-primary ui/theme))
                (let [{:keys [phase-1 phase-2]} (motion/pulse-target 1.25)]
                  (run-spring! {:scale (:scale phase-1)} (select-keys phase-1 [:stiffness :damping])
                               (fn [state]
                                 (.setProperty (.-style sw) "transform"
                                               (:transform (motion/apply-transform state))))
                               (fn []
                                 (run-spring! {:scale (:scale phase-2)} (select-keys phase-2 [:stiffness :damping])
                                              (fn [state]
                                                (.setProperty (.-style sw) "transform"
                                                              (:transform (motion/apply-transform state)))))))))
              (on-sound :click)
              (on-change hex))]
      (doseq [[hex sw] @swatch-els]
        (.addEventListener sw "click" (fn [_] (select! hex))))
      (let [custom-input (when (not= (:allow-custom opts) false)
                            (let [inp (el! "input" {:width "26px" :height "26px" :border "none"
                                                     :border-radius "50%" :cursor "pointer" :padding "0"
                                                     :background "none"})]
                              (set! (.-type inp) "color")
                              (set! (.-value inp) @!value)
                              (.addEventListener inp "input" (fn [_] (select! (.-value inp))))
                              (.appendChild wrap inp)
                              inp))]
        (when container (.appendChild container wrap))
        {:el wrap
         :get-value (fn [] @!value)
         :set-value (fn [hex]
                      (select! hex)
                      (when custom-input (set! (.-value custom-input) hex)))
         :destroy (fn [] (.remove wrap))}))))

;; ─── Carousel ──────────────────────────────────────────────────────

(defn- carousel-impl!
  [container opts]
  (let [items (or (:items opts) [])
        on-change (get opts :on-change (fn [_]))
        on-sound (get opts :on-sound (fn [_]))
        find-idx (fn [id] (some #(when (= (:id (nth items %)) id) %) (range (count items))))
        !index (atom (or (find-idx (:value opts)) 0))
        wrap (el! "div" {:display "flex" :align-items "center" :gap "10px"})
        stage (el! "div" {:position "relative" :width "96px" :height "96px" :overflow "hidden"
                           :border-radius (:radius-small ui/theme) :background "#fff"
                           :border (str "2px solid " (:card-border ui/theme))
                           :box-shadow (:shadow-small ui/theme)
                           :display "flex" :align-items "center" :justify-content "center"
                           :font-size "28px" :font-weight "900" :color (:text-muted ui/theme)})
        label-el (el! "div" {:font-size "12px" :font-weight "800" :color (:text-primary ui/theme)
                              :min-width "64px" :text-align "center"})
        make-arrow (fn [dir]
                     (let [btn (el! "button" {:appearance "none" :width "28px" :height "28px"
                                               :border-radius "50%" :border (str "1px solid " (:card-border ui/theme))
                                               :background "#fff" :color (:text-primary ui/theme)
                                               :font-size "16px" :font-weight "900" :cursor "pointer"
                                               :line-height "1" :padding "0"})]
                       (set! (.-type btn) "button")
                       (set! (.-textContent btn) (if (neg? dir) "‹" "›"))
                       btn))]
    (letfn [(render-thumb! []
              (set! (.-textContent stage) "")
              (let [item (get items @!index)]
                (when item
                  (let [thumbnail (:thumbnail item)]
                    (cond
                      (fn? thumbnail)
                      (when-let [node (thumbnail stage)] (.appendChild stage node))
                      thumbnail
                      (let [img (el! "img" {:max-width "100%" :max-height "100%"})]
                        (set! (.-src img) thumbnail)
                        (.appendChild stage img))
                      :else
                      (set! (.-textContent stage)
                            (-> (or (:label item) (:id item) "?") str (subs 0 1) kotoba.lang.text/upper))))
                  (set! (.-textContent label-el) (str (or (:label item) (:id item) ""))))))
            (page! [dir]
              (when (seq items)
                (reset! !index (mod (+ @!index dir (count items)) (count items)))
                (render-thumb!)
                ;; prime the offset synchronously (the JS `el.style.opacity = '0'`-style
                ;; priming this repo's `slide-in-props` docstring says was excluded from
                ;; the pure port) before spring-animating x -> 0, else the first frame
                ;; would jump-cut instead of visibly sliding in.
                (let [[from-x _] (:x (motion/slide-in-props {:direction (if (pos? dir) :right :left) :distance 24}))]
                  (.setProperty (.-style stage) "transform" (str "translateX(" from-x "px)"))
                  (run-spring! {:x [from-x 0]} {:stiffness 260 :damping 22}
                               (fn [state]
                                 (.setProperty (.-style stage) "transform"
                                               (:transform (motion/apply-transform state))))))
                (on-sound :navigate)
                (on-change (get items @!index))))]
      (render-thumb!)
      (let [prev-btn (make-arrow -1) next-btn (make-arrow 1)]
        (.addEventListener prev-btn "click" (fn [_] (page! -1)))
        (.addEventListener next-btn "click" (fn [_] (page! 1)))
        (.appendChild wrap prev-btn)
        (let [center (el! "div" {:display "grid" :gap "4px" :justify-items "center"})]
          (.appendChild center stage) (.appendChild center label-el)
          (.appendChild wrap center))
        (.appendChild wrap next-btn))
      (when container (.appendChild container wrap))
      {:el wrap
       :get-value (fn [] (:id (get items @!index)))
       :set-value (fn [id]
                    (when-let [i (find-idx id)] (reset! !index i) (render-thumb!)))
       :destroy (fn [] (.remove wrap))})))

)) ;; end #?(:cljs (do ...))

;; ─── Public API ────────────────────────────────────────────────────

(defn slider!
  "Labeled numeric slider (drag or click-to-set), thumb spring-settles on
   release. `opts`: `{:label :min :max :step :value :color :on-change
   :on-sound}`. Returns `{:el :get-value :set-value :destroy}`."
  [container opts]
  #?(:cljs (slider-impl! container opts)
     :clj (browser-only! "slider!")))

(defn color-swatch!
  "Row of preset color swatches + optional native free-pick input. Hex
   format `#rrggbb` throughout. `opts`: `{:presets :value :allow-custom
   :on-change :on-sound}`. Returns `{:el :get-value :set-value :destroy}`."
  [container opts]
  #?(:cljs (color-swatch-impl! container opts)
     :clj (browser-only! "color-swatch!")))

(defn carousel!
  "Horizontal paged picker for discrete choices (hair styles, outfits).
   `items[].thumbnail` accepts a URL string or a `(fn [stage-el] node)`
   for inline/procedural previews (e.g. `kami-app-character-creator`'s
   2D EDN sprite thumbnails — no baked `<img>` required). `opts`:
   `{:items :value :on-change :on-sound}`. Returns `{:el :get-value
   :set-value :destroy}`."
  [container opts]
  #?(:cljs (carousel-impl! container opts)
     :clj (browser-only! "carousel!")))
