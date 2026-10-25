(ns kami-ui-sdk.motion
  "Ported from kami-engine's live `kami-ui-sdk/kami-motion.js` (JS, not
   deleted Rust — see `kami-ui-sdk` root docstring). ADR-2607010930.

   `kami-motion.js` is an animation-primitives SDK: easing functions,
   a numeric tween runner, spring physics, preset entrance/exit
   animations, stagger orchestration, and a CSS-transition helper.

   Ported (pure, portable):
   - `ease` — all 9 easing functions (`linear`, `ease-out`, `ease-in`,
     `ease-in-out`, `bounce`, `elastic`, `back`, `back-out`, `pop`).
   - `tween-value` — value-at-t for a numeric `from`/`to` tween,
     replacing the JS `tween()`'s `requestAnimationFrame` loop with a
     pure `(f elapsed) -> {:v :t :done?}` function; callers drive the
     clock (e.g. an `advance` loop, a test, a game-tick) themselves.
   - `spring-step` / `spring-tick` — one physics-integration step of
     the JS `spring()` closure's per-frame body, as
     `(state dt opts) -> new-state`, settle-threshold checked the same
     way (`|vel| <= 0.01 && |pos - target| <= 0.001`).
   - `apply-transform` — pure port of `_applyProps`: builds the same
     CSS `transform` string (translate/scale/rotate) and opacity value
     from a spring state map, without touching `el.style`.
   - Preset prop builders (`fade-in-props`, `fade-out-props`,
     `pop-in-props`, `pop-out-props`, `slide-in-props`) — the
     `{prop: [from to]}` spring targets used by `fadeIn`/`fadeOut`/
     `popIn`/`popOut`/`slideIn`, minus the DOM `el.style.opacity = '0'`
     priming and the actual `spring()` call.
   - `shake-offset-at` / `pulse-target` — pure per-frame math for
     `shake()` (decaying sine wobble) and `pulse()` (breathe scale
     target).
   - `stagger-delays` — the `i * delay` schedule used by `stagger()`,
     as a pure seq, replacing the `setTimeout` fan-out.

   Excluded (DOM/browser-only, no CLJC equivalent):
   - `tween`/`spring`'s `requestAnimationFrame` driver loops and
     `performance.now()` clock reads.
   - `_getCurrentValue` (reads `getComputedStyle`).
   - `transition()` (CSS `transitionend` + `Promise` DOM helper).
   - `stagger()`'s DOM selector resolution
     (`document.querySelectorAll`) and `setTimeout` fan-out — only the
     delay *schedule* (`stagger-delays`) was ported.

   No overlap with `kotoba-lang/rtc` or `kotoba-lang/audio` — this is
   UI/DOM animation math, a distinct domain."
  (:require [kotoba.lang.text :as str]))

(def PI #?(:clj Math/PI :cljs js/Math.PI))

;; ─── Easing ──────────────────────────────────────────────────────

(defn ease-linear [t] t)

(defn ease-out
  "Cubic ease-out (smooth deceleration)."
  [t]
  (- 1 (Math/pow (- 1 t) 3)))

(defn ease-in
  "Cubic ease-in."
  [t]
  (Math/pow t 3))

(defn ease-in-out [t]
  (if (< t 0.5)
    (* 4 (Math/pow t 3))
    (- 1 (/ (Math/pow (+ (* -2 t) 2) 3) 2))))

(defn ease-bounce
  "Mario-coin-bounce easing."
  [t]
  (cond
    (< t 0.3636) (* 7.5625 t t)
    (< t 0.7272) (let [t (- t 0.5454)] (+ (* 7.5625 t t) 0.75))
    (< t 0.9090) (let [t (- t 0.8181)] (+ (* 7.5625 t t) 0.9375))
    :else (let [t (- t 0.9545)] (+ (* 7.5625 t t) 0.984375))))

(defn ease-elastic
  "Splatoon-splat elastic easing."
  [t]
  (cond
    (zero? t) 0
    (= t 1) 1
    :else (* (- (Math/pow 2 (- (* 10 t) 10)))
              (Math/sin (* (- (* t 10) 10.75) (/ (* 2 PI) 3))))))

(defn ease-back
  "Overshoot-snap easing (in)."
  [t]
  (let [c 1.70158]
    (- (* (+ c 1) (Math/pow t 3)) (* c (Math/pow t 2)))))

(defn ease-back-out
  "Overshoot-snap easing (out)."
  [t]
  (let [c 1.70158]
    (+ 1 (* (+ c 1) (Math/pow (- t 1) 3)) (* c (Math/pow (- t 1) 2)))))

(defn ease-pop
  "Nintendo-Switch-style pop: overshoot to 1.1 then settle to 1.0."
  [t]
  (cond
    (< t 0.4) (* (ease-out (/ t 0.4)) 1.1)
    (< t 0.7) (- 1.1 (* 0.1 (ease-in-out (/ (- t 0.4) 0.3))))
    :else 1.0))

(def ease
  "Map of easing-name -> easing-fn, mirroring the JS `ease` object."
  {:linear ease-linear
   :ease-out ease-out
   :ease-in ease-in
   :ease-in-out ease-in-out
   :bounce ease-bounce
   :elastic ease-elastic
   :back ease-back
   :back-out ease-back-out
   :pop ease-pop})

;; ─── Tween ───────────────────────────────────────────────────────

(defn tween-value
  "Pure port of `tween()`'s per-frame body. Given `{:from :to :duration
   :easing}` (easing a fn or a keyword in `ease`, defaulting to
   `ease-out`) and an elapsed-ms value, returns `{:v :t :done?}` where
   `v` is the eased interpolated value, `t` the clamped 0-1 ratio."
  [{:keys [from to duration easing]
    :or {from 0 to 1 duration 300 easing :ease-out}}
   elapsed]
  (let [ease-fn (if (fn? easing) easing (get ease easing ease-out))
        t (min (/ elapsed duration) 1)
        v (+ from (* (- to from) (ease-fn t)))]
    {:v v :t t :done? (>= t 1)}))

;; ─── Spring ──────────────────────────────────────────────────────

(defn spring-init-state
  "Build the initial per-property spring state map, mirroring the JS
   `spring()` setup loop. `props` is `{prop-key [from to]}` or
   `{prop-key to}` (from defaults to `current-val-fn(prop-key)`, or 0
   if no `current-val-fn` given, i.e. the DOM `_getCurrentValue`
   default)."
  ([props] (spring-init-state props (constantly 0)))
  ([props current-val-fn]
   (into {}
         (for [[k v] props]
           (let [[from to] (if (sequential? v) v [nil v])
                 from (if (some? from) from (current-val-fn k))]
             [k {:pos from :vel 0 :target to}])))))

(defn spring-step
  "One physics-integration step for a single spring property state
   `{:pos :vel :target}`, given `dt` seconds and `{:stiffness :damping
   :mass}`. Pure port of the per-key body inside `spring()`'s `tick`.
   Returns `{:pos :vel :target :settled?}`."
  [{:keys [pos vel target]} dt {:keys [stiffness damping mass]
                                 :or {stiffness 200 damping 15 mass 1}}]
  (let [force (* (- stiffness) (- pos target))
        damp-force (* (- damping) vel)
        accel (/ (+ force damp-force) mass)
        vel' (+ vel (* accel dt))
        pos' (+ pos (* vel' dt))
        settled? (and (<= (Math/abs vel') 0.01)
                       (<= (Math/abs (- pos' target)) 0.001))]
    (if settled?
      {:pos target :vel 0 :target target :settled? true}
      {:pos pos' :vel vel' :target target :settled? false})))

(defn spring-tick
  "One physics-integration step across a whole spring state map
   (multiple properties at once), the multi-key analogue of the JS
   `spring()` tick loop. `dt` is capped at 0.064s (~15fps floor),
   matching the JS `Math.min(dt, 0.064)`. Returns
   `{:state new-state-map :settled? bool}` where `settled?` is true
   only when every property has settled."
  [state dt opts]
  (let [dt (min dt 0.064)
        stepped (into {} (for [[k s] state] [k (spring-step s dt opts)]))]
    {:state (into {} (for [[k s] stepped] [k (dissoc s :settled?)]))
     :settled? (every? :settled? (vals stepped))}))

;; ─── Transform string (pure port of `_applyProps`) ─────────────────

(defn- format-n [n places]
  #?(:clj (format (str "%." places "f") (double n))
     :cljs (.toFixed n places)))

(defn- format-1 [n] (format-n n 1))
(defn- format-3 [n] (format-n n 3))

(defn apply-transform
  "Pure port of `_applyProps`: given a spring state map (as produced by
   `spring-tick`/`spring-init-state`), returns
   `{:transform css-transform-string :opacity opacity-or-nil}` — the
   same string kami-motion.js would assign to `el.style.transform`,
   without touching any element."
  [state]
  (let [x (get-in state [:x :pos] 0)
        y (get-in state [:y :pos] 0)
        has-xy? (or (contains? state :x) (contains? state :y))
        parts (cond-> []
                has-xy? (conj (str "translate(" (format-1 x) "px," (format-1 y) "px)"))
                (contains? state :scale)
                (conj (str "scale(" (format-3 (get-in state [:scale :pos])) ")"))
                (contains? state :rotate)
                (conj (str "rotate(" (format-1 (get-in state [:rotate :pos])) "deg)")))]
    {:transform (when (seq parts) (str/join " " parts))
     :opacity (when (contains? state :opacity)
                (format-3 (get-in state [:opacity :pos])))}))

;; ─── Preset prop builders ────────────────────────────────────────

(defn fade-in-props [{:keys [y] :or {y 12}}]
  {:opacity [0 1] :y [y 0]})

(defn fade-out-props [{:keys [y] :or {y 8}}]
  {:opacity [1 0] :y [0 y]})

(defn pop-in-props [_opts]
  {:scale [0 1] :opacity [0 1]})

(defn pop-out-props [_opts]
  {:scale [1 0] :opacity [1 0]})

(defn slide-in-props
  "Pure port of `slideIn`'s from-offset derivation for
   `{:direction :distance}` (`:left`/`:right`/`:up`/`:down`)."
  [{:keys [direction distance] :or {direction :left distance 40}}]
  (let [dir (keyword direction)
        from-x (case dir :left (- distance) :right distance 0)
        from-y (case dir :up (- distance) :down distance 0)]
    {:opacity [0 1] :x [from-x 0] :y [from-y 0]}))

;; ─── Per-frame math for shake/pulse ─────────────────────────────

(defn shake-offset-at
  "Pure port of `shake()`'s onUpdate body: horizontal wobble offset at
   ratio `t` (0-1) for a given `intensity`."
  [t intensity]
  (let [decay (- 1 t)]
    (* (Math/sin (* t PI 6)) intensity decay)))

(defn pulse-target
  "Target scale springs used by `pulse()` — first phase 1 -> scale,
   second phase scale -> 1 (fired on the first spring's onComplete)."
  ([] (pulse-target 1.08))
  ([scale] {:phase-1 {:scale [1 scale] :stiffness 150 :damping 8}
            :phase-2 {:scale [scale 1] :stiffness 200 :damping 14}}))

;; ─── Stagger schedule ────────────────────────────────────────────

(defn stagger-delays
  "Pure port of the `stagger()` fan-out schedule: `n` items each
   delayed `i * delay` ms, replacing the JS `setTimeout` loop."
  [n delay]
  (map #(* % delay) (range n)))
