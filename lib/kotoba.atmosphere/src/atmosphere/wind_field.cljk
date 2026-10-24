(ns atmosphere.wind-field
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-atmosphere
  Rust crate's `src/wind_field.rs` (deleted from kotoba-lang/kami-engine in PR #82,
  \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  Wind field: spatially + temporally varying wind vector. Uses value noise
  (hash-based, cosine/smoothstep interpolation) at 2 octaves to produce
  \"ripple\" patterns across the ground plane. A tussock at world position
  (x, z) at time `t` sees a wind vector that is the base wind ± local
  perturbation — this gives the characteristic wave motion of wind through
  grass/wheat fields. The same algorithm structure (octave count, spatial /
  temporal frequency composition) is mirrored here so CPU-side simulation
  matches the original GPU-side WGSL rendering intent, even though this port
  is not required to be bit-identical to the original hash implementation.

  Vec2 values are represented as plain CLJC vectors `[x z]`.")

;; ════════════════════════════════════════════════════════════════════════
;; vec2 helpers
;; ════════════════════════════════════════════════════════════════════════

(defn v2-length
  "Euclidean length of a 2D vector [x z]."
  [[x z]]
  #?(:clj  (Math/sqrt (+ (* x x) (* z z)))
     :cljs (.sqrt js/Math (+ (* x x) (* z z)))))

(defn v2-normalize-or-zero
  "Normalize a 2D vector; returns [0 0] if the vector is (near) zero length,
  mirroring glam's `Vec2::normalize_or_zero`."
  [v]
  (let [len (v2-length v)]
    (if (or (zero? len) (< len 1e-12))
      [0.0 0.0]
      (let [[x z] v]
        [(/ x len) (/ z len)]))))

(defn v2-scale
  "Scale a 2D vector [x z] by scalar `s`."
  [[x z] s]
  [(* x s) (* z s)])

(defn v2-add
  "Add two 2D vectors."
  [[x1 z1] [x2 z2]]
  [(+ x1 x2) (+ z1 z2)])

(defn v2-sub
  "Subtract 2D vector b from a."
  [[ax az] [bx bz]]
  [(- ax bx) (- az bz)])

;; ════════════════════════════════════════════════════════════════════════
;; value noise — hash-based, smoothstep interpolation (2 octaves used above)
;; ════════════════════════════════════════════════════════════════════════

(def ^:private i32-mask 0xffffffff)

(defn- wrap-i32
  "Wrap an integer into signed 32-bit range, mirroring Rust's wrapping_* arithmetic."
  [n]
  (let [m (bit-and n i32-mask)]
    (if (>= m 0x80000000) (- m 0x100000000) m)))

(defn- mul32
  "32-bit wrapping multiply. Uses `Math.imul` on cljs to avoid losing
  precision past JS's 2^53 safe-integer range (32-bit products can reach
  ~2^62); on clj, JVM longs are exact so a plain wrapped multiply suffices."
  [a b]
  #?(:clj  (wrap-i32 (*' a b))
     :cljs (js/Math.imul a b)))

(defn- add32
  "32-bit wrapping add."
  [a b]
  (wrap-i32 (+ a b)))

(defn hash2d
  "Deterministic hash-based pseudo-random value in [0, 1) for integer lattice
  point (x, y). Structurally mirrors the original Rust `hash2d`: wrapping
  integer multiply/xor/shift chain, ported with explicit 32-bit wraparound
  since CLJC integers are not fixed-width."
  [x y]
  (let [n  (add32 (mul32 x 1619) (mul32 y 31337))
        n  (mul32 n (mul32 n n))
        n  (wrap-i32 (bit-xor (bit-shift-right n 13) n))
        n  (add32 (mul32 n (add32 (mul32 n (mul32 n 60493)) 19990303))
                   1376312589)]
    (/ (double (bit-and n 0x7fffffff)) (double 0x7fffffff))))

(defn smoothstep01
  "Cubic smoothstep on t in [0, 1]: t*t*(3-2t)."
  [t]
  (* t t (- 3.0 (* 2.0 t))))

(defn- floor-int [x]
  #?(:clj  (long (Math/floor x))
     :cljs (Math/floor x)))

(defn value-noise
  "2D value noise sampled at (x, y): bilinear interpolation (via smoothstep) of
  `hash2d` at the surrounding integer lattice. Returns a value in [0, 1)."
  [x y]
  (let [xi (floor-int x)
        yi (floor-int y)
        xf (- x (Math/floor x))
        yf (- y (Math/floor y))
        v00 (hash2d xi yi)
        v10 (hash2d (inc xi) yi)
        v01 (hash2d xi (inc yi))
        v11 (hash2d (inc xi) (inc yi))
        sx (smoothstep01 xf)
        sy (smoothstep01 yf)
        a (+ (* v00 (- 1.0 sx)) (* v10 sx))
        b (+ (* v01 (- 1.0 sx)) (* v11 sx))]
    (+ (* a (- 1.0 sy)) (* b sy))))

;; ════════════════════════════════════════════════════════════════════════
;; wind field config + sampling
;; ════════════════════════════════════════════════════════════════════════

(def default-wind-field-config
  "Default `WindFieldConfig` map, mirroring the Rust `Default` impl.
  :base-dir       — base wind direction, [x z] (not required to be pre-normalized)
  :base-speed     — base wind speed (m/s)
  :gust-mul       — global gust multiplier (1.0 = calm, 1.3 = gusty)
  :spatial-freq   — spatial frequency of the ripple (cycles per world unit)
  :temporal-freq  — temporal frequency (scrolling speed in noise units/second)
  :local-variation — amplitude of local perturbation [0, 1]"
  {:base-dir [1.0 0.3]
   :base-speed 5.0
   :gust-mul 1.0
   :spatial-freq 0.012
   :temporal-freq 0.25
   :local-variation 0.5})

(defn sample-wind
  "Sample the wind field at world position (x, z) at time `t` (seconds) given a
  `WindFieldConfig` map `cfg` (see `default-wind-field-config`).

  Returns a 2D wind vector [x z] whose magnitude and direction vary with
  position + time. Base wind drifts over longer scales; local ripples add
  2-octave value-noise perturbation."
  [x z t cfg]
  (let [{:keys [base-dir base-speed gust-mul spatial-freq temporal-freq local-variation]} cfg
        dir (v2-normalize-or-zero base-dir)
        [dx dz] dir
        perp [(- dz) dx]

        ;; Main ripple (large scale)
        nx1 (+ (* x spatial-freq) (* t temporal-freq))
        nz1 (+ (* z spatial-freq) (* t temporal-freq 0.7))
        n1 (- (* (value-noise nx1 nz1) 2.0) 1.0)

        ;; Finer ripple (half wavelength)
        nx2 (+ (* x spatial-freq 2.0) (* t temporal-freq 1.5) 13.0)
        nz2 (+ (* z spatial-freq 2.0) (* t temporal-freq 1.1) 7.0)
        n2 (- (* (value-noise nx2 nz2) 2.0) 1.0)

        magnitude-mod (+ 1.0 (* (+ (* n1 0.7) (* n2 0.3)) local-variation))
        direction-shift (* (+ (* n1 0.3) (* n2 0.2)) local-variation)

        local-dir (v2-add dir (v2-scale perp direction-shift))
        speed (* base-speed gust-mul (max magnitude-mod 0.0))]
    (v2-scale (v2-normalize-or-zero local-dir) speed)))

(defn sample-gust-scalar
  "Sample only the signed gust scalar at (x, z, t) — useful for per-instance
  bending. Returns a value in [-1, 1] representing \"less than base\" vs
  \"more than base\" gust."
  [x z t cfg]
  (let [{:keys [spatial-freq temporal-freq]} cfg
        nx (+ (* x spatial-freq) (* t temporal-freq))
        nz (+ (* z spatial-freq) (* t temporal-freq 0.7))]
    (- (* (value-noise nx nz) 2.0) 1.0)))
