(ns cam.follow
  "Follow-cam: smoothly tracks a moving target position with a configurable
  positional offset and a damping/smoothing factor.

  New camera-rig implementation, not a port of anything — see the root
  `cam` namespace docstring for why this repo has no legacy Rust source to
  restore. Pure 3-vector math only; no external vector/linalg dependency
  (zero-dep, same convention as e.g. `kotoba.fea.vec3` in the sibling
  `fea` repo, just inlined here since this namespace only needs three
  operations).")

;; ---------------------------------------------------------------------
;; Minimal private vec3 helpers. Only add/sub/scale are needed here, so
;; there is no shared vec3 module pulled in.
;; ---------------------------------------------------------------------

(defn- v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn- v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v* [[x y z] s] [(* x s) (* y s) (* z s)])

(defn follow-config
  "Build a follow-cam config. `target-offset` is a `[x y z]` vector added
  to the tracked target's position to get the camera's *desired*
  position (e.g. `[0 2 -5]` to sit above and behind the target). `damping`
  is in `(0 1]`: `1.0` snaps the camera to the desired position instantly
  on every `update-follow` call; smaller values trail the target more,
  i.e. a smoother/slower-following camera."
  [target-offset damping]
  {:pre [(< 0.0 damping) (<= damping 1.0)]}
  {:target-offset target-offset :damping damping})

(defn- exp* [x] #?(:clj (Math/exp x) :cljs (js/Math.exp x)))

(defn smoothing-alpha
  "Interpolation factor for one `update-follow` step of `dt` seconds.

  `damping` in `(0 1]` is remapped to an exponential-decay rate
  `damping / (1 - damping)` (`0` as `damping -> 0`, `+Infinity` as
  `damping -> 1`), then plugged into the standard frame-rate-independent
  exponential-smoothing factor `1 - exp(-rate * dt)`. This form is
  genuinely frame-rate independent in the sense that matters for a
  follow-cam: calling `update-follow` twice in a row with `dt/2` each
  converges (up to floating-point error) to the same camera position as
  calling it once with `dt`, unlike a naive per-frame `lerp(pos, target,
  k)` whose effective speed changes with the caller's tick rate. `damping
  = 1.0` is special-cased to a literal `1.0` (instant snap), both because
  the remapped rate would otherwise divide by zero and because
  `follow-config`'s contract promises an exact snap at `1.0`. `dt <= 0`
  (no time elapsed, or a bad caller) is treated as \"don't move\"."
  [damping dt]
  (cond
    (<= dt 0.0) 0.0
    (>= damping 1.0) 1.0
    :else (let [rate (/ damping (- 1.0 damping))]
            (- 1.0 (exp* (* (- rate) dt))))))

(defn update-follow
  "One camera-tracking step. Returns the new `[x y z]` camera position:
  `camera-pos` moved a fraction of the way toward the desired position
  `(+ target-pos target-offset)`, where the fraction is the frame-rate-
  independent smoothing factor from `smoothing-alpha` (derived from
  `:damping` in `config` and `dt`, the seconds elapsed since the previous
  call)."
  [camera-pos target-pos {:keys [target-offset damping]} dt]
  (let [desired (v+ target-pos target-offset)
        alpha (smoothing-alpha damping dt)]
    (v+ camera-pos (v* (v- desired camera-pos) alpha))))
