(ns audio.binaural
  "Binaural spatialization — restored from kami-engine's `kami-audio`
  Rust crate (`src/binaural.rs`, deleted PR #82 \"Remove Rust workspace
  from kami-engine\") to zero-dep portable CLJC as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  Ledger class `:port-to-WGSL-compute`; restored as a plain interim CLJC
  port of the pure DSP math per owner decision — not actual WGSL compute
  code. `mix-stereo` is pure software mixing over in-memory buffers (no
  device/callback code); there is no literal real-time audio-hardware
  callback in the original to exclude.

  Physically-grounded *spherical-head* model — the native counterpart of
  the KAMI EDN-authored `kami.binaural` recipe format (that authoring
  side is out of scope here; this ports only the executor math):
    * ITD — Woodworth `itd = (a/c)(theta + sin theta)` on the lateral
      angle (front/back symmetric, elevation-aware).
    * ILD — frequency-independent head-shadow: the contralateral ear is
      attenuated by |ILD| dB.
    * distance — inverse / linear / exponential / none rolloff.

  The sibling restoration `kotoba-lang/rtc`'s `rtc.spatial` namespace
  independently implements a simpler, self-contained stereo-pan
  calculation (equal-power pan + inverse-distance rolloff) because this
  namespace did not exist yet when `rtc` was restored; the two are not
  meant to be unified, `rtc.spatial` documents its own relationship.")

;; ---------------------------------------------------------------------
;; Constants.
;; ---------------------------------------------------------------------

(def speed-of-sound
  "Speed of sound in dry air ~20C (m/s)."
  343.0)

(def default-head-radius
  "Standard adult head radius (m, ~KEMAR)."
  0.0875)

;; ---------------------------------------------------------------------
;; Data constructors (Rust `struct` -> plain CLJC map with defaults).
;; ---------------------------------------------------------------------

(defn hrtf
  "Head model parameters (matches the clj-authoring-side `:binaural/hrtf`).
  Defaults: `:head-radius` = [[default-head-radius]], `:max-ild-db` 12.0."
  ([] (hrtf {}))
  ([opts] (merge {:head-radius default-head-radius :max-ild-db 12.0} opts)))

(def rolloff-kind-values
  "Valid values for `:kind` on a rolloff map."
  #{:none :inverse :linear :exponential})

(defn rolloff
  "Distance rolloff (matches the clj-authoring-side `:binaural/rolloff`,
  OpenAL semantics). Defaults: `:kind :inverse :reference 1.0 :max 100.0
  :factor 1.0`."
  ([] (rolloff {}))
  ([opts] (merge {:kind :inverse :reference 1.0 :max 100.0 :factor 1.0} opts)))

(defn rolloff-gain
  "Linear gain in [0,1] for `dist` under `rlf` (a rolloff map)."
  [rlf dist]
  (let [{:keys [kind reference max factor]} rlf
        d (-> dist (clojure.core/max reference) (clojure.core/min max))]
    (case kind
      :none 1.0
      :inverse (/ reference (+ reference (* factor (- d reference))))
      :linear (let [span (clojure.core/max (- max reference) 1e-6)]
                (-> (- 1.0 (/ (* factor (- d reference)) span))
                    (clojure.core/max 0.0)
                    (clojure.core/min 1.0)))
      :exponential (Math/pow (/ d reference) (- factor)))))

;; ---------------------------------------------------------------------
;; Vec3 math (local; independent from `audio`'s private helpers so this
;; namespace stays a self-contained restoration of `binaural.rs`).
;; ---------------------------------------------------------------------

(defn- v-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v-length [[x y z]] (Math/sqrt (+ (* x x) (* y y) (* z z))))
(defn- v-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn- v-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- v-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn- v-normalize-or-zero [v]
  (let [l (v-length v)]
    (if (zero? l) [0.0 0.0 0.0] (v-scale v (/ 1.0 l)))))
(defn- clamp [x lo hi] (clojure.core/max lo (clojure.core/min hi x)))

;; ---------------------------------------------------------------------
;; Core spatialization.
;; ---------------------------------------------------------------------

(defn sample-delays
  "Integer ITD sample delays `[dl dr]` at `sample-rate` (the `:native`
  emit form) for a `binaural-params` map (as returned by [[spatialize]])."
  [params sample-rate]
  (let [sr (double sample-rate)]
    [(Math/round (* (:delay-l-s params) sr))
     (Math/round (* (:delay-r-s params) sr))]))

(defn spatialize
  "Spatialize a source at `source-pos` against `listener` — the core of
  the model. `hrtf-params` / `rolloff-params` are maps from [[hrtf]] /
  [[rolloff]]. `source-gain` folds in the source's own volume (in
  [0,1]). Returns a `binaural-params` map:
  `:distance :azimuth :elevation :lateral :itd-s :ild-db :gain-l :gain-r
  :delay-l-s :delay-r-s`."
  [listener hrtf-params rolloff-params source-pos source-gain]
  (let [forward (v-normalize-or-zero (:forward listener))
        right (v-normalize-or-zero (v-cross forward (:up listener)))
        up (v-cross right forward)
        rel (v-sub source-pos (:position listener))
        distance (v-length rel)
        dir (if (> distance 1e-6) (v-scale rel (/ 1.0 distance)) [0.0 0.0 0.0])
        lateral (clamp (v-dot dir right) -1.0 1.0)
        front (v-dot dir forward)
        vert (clamp (v-dot dir up) -1.0 1.0)
        azimuth (Math/atan2 lateral front)
        elevation (Math/asin vert)
        theta (Math/asin lateral)
        head-radius (:head-radius hrtf-params)
        itd-s (* (/ head-radius speed-of-sound) (+ theta (Math/sin theta)))
        ild-db (* (:max-ild-db hrtf-params) lateral)
        dgain (* (rolloff-gain rolloff-params distance) source-gain)
        shadow (Math/pow 10.0 (/ (- (Math/abs ild-db)) 20.0))
        right-side? (>= lateral 0.0)
        gain-l (* dgain (if right-side? shadow 1.0))
        gain-r (* dgain (if right-side? 1.0 shadow))
        delay-l-s (if (>= itd-s 0.0) itd-s 0.0)
        delay-r-s (if (< itd-s 0.0) (- itd-s) 0.0)]
    {:distance distance
     :azimuth azimuth
     :elevation elevation
     :lateral lateral
     :itd-s itd-s
     :ild-db ild-db
     :gain-l gain-l
     :gain-r gain-r
     :delay-l-s delay-l-s
     :delay-r-s delay-r-s}))

;; ---------------------------------------------------------------------
;; Software mixing.
;; ---------------------------------------------------------------------

(defn voice
  "A spatialized voice ready to mix: a mono signal (vector/seq of floats)
  placed in 3D via `params` (a `binaural-params` map)."
  [params mono]
  {:params params :mono mono})

(defn mix-stereo
  "Software-mix spatialized `voices` (a seq of [[voice]] maps) into one
  interleaved stereo float vector of `frames` frames (`out[2i]` = left,
  `out[2i+1]` = right). Each voice's mono signal is offset by its
  per-ear ITD sample delay and scaled by its per-ear gain; samples past
  the block are dropped. Pure DSP — the device sink (cpal / Web Audio /
  console mixer) is intentionally out of scope, matching the original's
  documented separation."
  [voices sample-rate frames]
  (letfn [(add-at [out idx v] (assoc out idx (+ (nth out idx) v)))
          (mix-voice [out {:keys [params mono]}]
            (let [[dl dr] (sample-delays params sample-rate)
                  gain-l (:gain-l params)
                  gain-r (:gain-r params)]
              (reduce
               (fn [out [i s]]
                 (let [li (+ i dl)
                       ri (+ i dr)
                       out (if (< li frames) (add-at out (* li 2) (* s gain-l)) out)
                       out (if (< ri frames) (add-at out (inc (* ri 2)) (* s gain-r)) out)]
                   out))
               out
               (map-indexed vector mono))))]
    (reduce mix-voice (vec (repeat (* frames 2) 0.0)) voices)))
