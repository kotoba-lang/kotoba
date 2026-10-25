(ns kami-ui-sdk.effect
  "Ported from kami-engine's live `kami-ui-sdk/kami-effect.js` (JS, not
   deleted Rust — see `kami-ui-sdk` root docstring). ADR-2607010930.

   `kami-effect.js` is a DOM-particle visual-effects library
   (`confetti`, `sparkle`, `ripple`, `floatText`, `trail`, `flash`).
   Each effect spawns `<div>`s and animates them per-frame via
   `requestAnimationFrame`; the per-frame *trajectory math* (position/
   scale/opacity as a pure function of normalized time `t`) is
   portable, the DOM spawning/pooling/removal is not.

   Ported (pure, portable):
   - `colors` — the `COLORS` palette constant.
   - `confetti-particle-at` — pure port of `confetti()`'s per-particle
     `animate()` body: given spawn params (`angle`, `velocity`,
     `rotation`) and `t`, returns `{:dx :dy :rot :opacity}` (easeOut-
     quad horizontal/vertical drift + gravity + rotation + fade-out
     after t=0.7).
   - `sparkle-particle-at` — pure port of `sparkle()`'s per-particle
     `animate()` body: given `angle`, `radius`, and `t`, returns
     `{:dx :dy :scale :opacity}` (pop-in/hold/fade-out scale envelope
     + orbiting drift).
   - `ripple-at` — pure port of `ripple()`'s `animate()` body: `t` ->
     `{:size :opacity :border-width}` (easeOut-cubic ring expansion).
   - `float-text-at` — pure port of `floatText()`'s `animate()` body:
     `t` -> `{:y-offset :scale :opacity}` (rising easeOut-quad + pop
     scale envelope + fade-out).
   - `flash-opacity-at` — pure port of `flash()`'s `animate()` body:
     `t` -> linear-fade opacity.
   - `trail-follow-step` — pure port of one iteration of `trail()`'s
     per-dot lerp-follow chain (`dots[i] += (dots[i-1] - dots[i]) *
     (1 - decay)`), as `(prev-pos pos decay) -> new-pos`, plus
     `trail-dot-style` for the per-dot size/opacity falloff.

   Excluded (DOM-only, no CLJC equivalent):
   - `_ensure`/`_container` (creates/reuses the fixed full-screen
     overlay `<div>`).
   - All `document.createElement`, `el.style.cssText =`, `appendChild`,
     `el.remove()` calls.
   - `requestAnimationFrame` loops and `performance.now()` clock reads
     in every effect.
   - `trail()`'s `document.addEventListener('mousemove', ...)` wiring
     and `target.getBoundingClientRect()` in `sparkle()`.
   - Random particle-parameter generation (`_rnd`/`_pick` /
     `Math.random()`) — callers supply spawn params explicitly so the
     trajectory functions stay deterministic and testable.

   No overlap with `kotoba-lang/rtc` or `kotoba-lang/audio` — this is
   DOM visual-effect math, a distinct domain.")

(def PI #?(:clj Math/PI :cljs js/Math.PI))
(def TAU (* PI 2))

(def colors
  "Pure data port of the `COLORS` palette."
  ["#fa5757" "#33bfff" "#66e673" "#ffbf33" "#b366f2" "#26d9b3" "#ff8c4d" "#f272b3" "#5555ff" "#f5e642"])

;; ─── Confetti ────────────────────────────────────────────────────

(defn confetti-particle-at
  "Pure port of `confetti()`'s per-particle `animate()` body.
   `spawn` is `{:angle :velocity :rotation}`; `spread` and `t` (0-1,
   normalized elapsed/duration) drive the trajectory."
  [{:keys [angle velocity rotation]} spread t]
  (let [ease-v (- 1 (* (- 1 t) (- 1 t))) ;; easeOut quad
        dx (* (Math/cos angle) velocity)
        dy (- (* (Math/sin angle) velocity) (* spread 0.5))
        px (* dx ease-v)
        py (+ (* dy ease-v) (* 400 t t))
        rot (* rotation t)
        opacity (if (< t 0.7) 1 (- 1 (/ (- t 0.7) 0.3)))]
    {:dx px :dy py :rot rot :opacity opacity}))

;; ─── Sparkle ─────────────────────────────────────────────────────

(defn sparkle-particle-at
  "Pure port of `sparkle()`'s per-particle `animate()` body.
   `angle`/`radius` are spawn params, `t` is normalized elapsed/duration
   (already delay-adjusted by the caller, i.e. clamped >= 0)."
  [angle radius t]
  (let [scale (cond (< t 0.3) (/ t 0.3)
                     (< t 0.7) 1
                     :else (- 1 (/ (- t 0.7) 0.3)))
        px (* (Math/cos (+ angle (* t PI))) radius (+ 1 (* t 0.5)))
        py (- (* (Math/sin (+ angle (* t PI))) radius (+ 1 (* t 0.5)))
              (* 10 t))]
    {:dx px :dy py :scale scale :opacity scale}))

;; ─── Ripple ──────────────────────────────────────────────────────

(defn ripple-at
  "Pure port of `ripple()`'s `animate()` body: `t` (0-1) -> ring
   size/opacity/border-width for a given `max-size`."
  [max-size t]
  (let [size (* max-size (- 1 (Math/pow (- 1 t) 3)))]
    {:size size
     :opacity (* (- 1 t) 0.8)
     :border-width (max 1 (* 3 (- 1 t)))}))

;; ─── Float text ──────────────────────────────────────────────────

(defn float-text-at
  "Pure port of `floatText()`'s `animate()` body: `t` (0-1) ->
   `{:y-offset :scale :opacity}`."
  [t]
  (let [y-offset (* -60 (- 1 (Math/pow (- 1 t) 2)))
        scale (cond (< t 0.15) (* (/ t 0.15) 1.2)
                     (< t 0.3) (- 1.2 (* 0.2 (/ (- t 0.15) 0.15)))
                     :else 1)
        opacity (if (< t 0.7) 1 (- 1 (/ (- t 0.7) 0.3)))]
    {:y-offset y-offset :scale scale :opacity opacity}))

;; ─── Screen flash ────────────────────────────────────────────────

(defn flash-opacity-at
  "Pure port of `flash()`'s `animate()` body: `t` (0-1) -> opacity,
   linear fade from 0.6."
  [t]
  (* 0.6 (- 1 t)))

;; ─── Trail ───────────────────────────────────────────────────────

(defn trail-follow-step
  "Pure port of one dot's per-frame lerp toward the previous dot in
   `trail()`'s chain: `pos + (prev-pos - pos) * (1 - decay)`."
  [prev-pos pos decay]
  (+ pos (* (- prev-pos pos) (- 1 decay))))

(defn trail-dot-style
  "Pure port of the per-dot size/opacity falloff in `trail()`'s
   `animate()`: dot `i` of `n` total, base `size` -> `{:size
   :opacity}`."
  [i n size]
  (let [frac (/ i (double n))]
    {:size (* size (- 1 frac))
     :opacity (* (- 1 frac) 0.6)}))
