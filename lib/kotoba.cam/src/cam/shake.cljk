(ns cam.shake
  "Procedural camera shake for impact/damage feedback: a positional offset
  that jitters per axis and decays to zero over a fixed duration.

  New camera-rig implementation, not a port of anything — see the root
  `cam` namespace docstring. The per-axis jitter here is a small
  deterministic sine-based function, *not* real Perlin/simplex noise —
  see `axis-noise` for exactly what that means and why it is an honest
  simplification for this use case rather than a hidden shortcut.")

(defn shake-config
  "Build a shake config. `amplitude` is the peak offset magnitude (world
  units) at `elapsed-time = 0`. `frequency` is roughly how many jitter
  cycles per second each axis oscillates through (see `axis-noise`).
  `duration` is how many seconds the shake takes to decay to zero."
  [amplitude frequency duration]
  {:amplitude amplitude :frequency frequency :duration duration})

(defn- sin* [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))

(defn axis-noise
  "Deterministic pseudo-random value in `[-1 1]` for one shake axis at one
  instant. This is a *simplified approximation* of real Perlin/simplex
  noise, not the real thing: it has no spatial coherence, no gradient
  continuity guarantees beyond those of `sin`, and no octave layering. All
  it actually guarantees is (a) determinism — the same
  `(elapsed-time seed axis-index frequency)` always produces the same
  output, so shake is reproducible/replayable — and (b) that the three
  axes and different seeds produce visibly different values rather than
  moving in lockstep.

  `phase` combines the inputs exactly as `(+ seed axis-index (* frequency
  elapsed-time))`, fed to `sin` *directly as radians* (deliberately not
  normalized to \"cycles\" via a `2*pi` factor first): `sin` has period
  `2*pi`, so an extra `2*pi` scaling would make any integer `seed`/
  `axis-index` map to an exact multiple of the period and cancel out
  (`sin(2*pi*(n + f)) == sin(2*pi*f)` for integer `n`) — silently
  defeating the whole point of mixing in `seed`/`axis-index` whenever
  callers pass integers, which is the common case. Feeding the raw sum to
  `sin` avoids that trap; the tradeoff is that `frequency` is only an
  *angular* rate (radians of phase per second of `elapsed-time`) rather
  than an exact cycles-per-second Hz value."
  [elapsed-time seed axis-index frequency]
  (let [phase (+ seed axis-index (* frequency elapsed-time))]
    (sin* phase)))

(defn shake-offset
  "Positional `[x y z]` shake offset at `elapsed-time` seconds into a
  shake described by `config` (from `shake-config`), using `seed` to
  decorrelate independent simultaneous shakes (e.g. two impacts at once)
  from producing an identical jitter pattern.

  Falls off *linearly* from full `:amplitude` at `elapsed-time = 0` to
  zero at `elapsed-time = :duration` (`decay = 1 - elapsed-time/duration`,
  clamped so the offset is exactly `[0 0 0]` at and after `:duration` —
  a linear ramp rather than exponential falloff, chosen for
  predictability: callers can reason about \"half the duration ->
  half the amplitude\" without needing a decay-constant parameter)."
  [{:keys [amplitude frequency duration]} elapsed-time seed]
  (if (or (>= elapsed-time duration) (<= duration 0.0))
    [0.0 0.0 0.0]
    (let [decay (- 1.0 (/ elapsed-time duration))
          scale (* amplitude decay)]
      (mapv (fn [axis-index] (* scale (axis-noise elapsed-time seed axis-index frequency)))
            [0 1 2]))))
