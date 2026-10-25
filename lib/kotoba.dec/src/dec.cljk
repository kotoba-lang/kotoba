(ns dec
  "Discrete Exterior Calculus on the voxel cubical complex — restored from
  kami-dec/src/lib.rs in kotoba-lang/kami-engine (deleted in PR #82, \"Remove
  Rust workspace from kami-engine\"). Part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root); kami-dec's migration-ledger class is
  :port-to-WGSL-compute (\"chunk management + dispatch; field ops → WGSL
  compute\"), but per owner decision this restoration is a plain, zero-dep
  portable CLJC interim implementation standing in for what would eventually
  be authored as real WGSL compute shaders — pure data + pure functions, no
  IO/GPU, safe to load on both JVM Clojure and ClojureScript.

  DEC primitives on a 6-connected voxel lattice, mirroring the Rust source:

    - `d`  — exterior derivative (`d-0` gradient 0-form→1-form, `d-1` curl
      1-form→2-form).
    - `*`  — Hodge star: on a flat unit-spacing grid it is the identity up to
      a metric factor, so (as in the original) it is left implicit/deferred.
    - `Δ = *d*d + d*d*` — Laplacian; on 0-forms this is the 7-point stencil
      `(Σ neighbours) − 6·φ` used by `scalar-diffuse` and the Poisson solvers.

  Field types (all sparse, keyed by 16³ chunk coordinate):
    - `scalar-field`  — 0-form on cell centres (heat / density / pressure).
    - `edge-field`    — 1-form on the three outgoing (+X +Y +Z) edges per cell
      (wind / velocity / electric field).
    - `face-field`    — 2-form on the three outgoing (+YZ +ZX +XY) faces per
      cell (magnetic flux).

  Solvers / dynamics ported 1:1: damped-Jacobi and 2-level-V-cycle multigrid
  Poisson solvers plus Helmholtz (divergence-free) projection, a Yee-leapfrog
  Maxwell integrator, and Fedkiw-style vorticity confinement.

  Representation notes (Rust → CLJC):
    - `HashMap<ChunkCoord, Box<[f32; 4096]>>`      → `{:chunks {[cx cy cz] cells}}`
      where `cells` is a plain persistent vector of 4096 floats (ScalarField)
      or of 4096 `[a b c]` triples (EdgeField / FaceField), indexed by the
      same `lx + ly*16 + lz*256` flat formula as the original.
    - `glam::Vec3` / `[f32; 3]`                    → plain `[x y z]` vectors,
      with small local `v3-*` helpers (add/sub/scale/cross/length/normalize)
      so this repo has zero cross-repo dependency.
    - `div_euclid` / `rem_euclid`                  → `div-euclid` / `rem-euclid`
      below, built on Clojure's `mod` (which — unlike `rem` — already returns
      a non-negative remainder for a positive divisor, matching Rust's
      Euclidean division semantics exactly).
    - `&mut self` methods                          → pure functions that take
      the field value and return a new field value (idiomatic immutable
      CLJC, the convention used throughout this migration wave).")

;; ─────────────────────────────────────────────────────────────────────────
;; Platform shims
;; ─────────────────────────────────────────────────────────────────────────

(defn- flr [x] #?(:clj (Math/floor (double x)) :cljs (js/Math.floor x)))
(defn- abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))
(defn- sqrt* [x] #?(:clj (Math/sqrt (double x)) :cljs (js/Math.sqrt x)))

;; ─────────────────────────────────────────────────────────────────────────
;; Chunk-lattice constants and coordinate helpers
;; ─────────────────────────────────────────────────────────────────────────

(def chunk-size
  "Voxel chunk size in cells per axis. Must match kami-pipelines::CHUNK_SIZE."
  16)

(def chunk-cells
  "Voxels per chunk (16³)."
  (* chunk-size chunk-size chunk-size))

(defn rem-euclid
  "Euclidean remainder matching Rust's `i32::rem_euclid` for positive `b`:
  always in `[0, b)`, unlike `rem` which can be negative."
  [a b]
  (mod a b))

(defn div-euclid
  "Euclidean division matching Rust's `i32::div_euclid` for positive `b`."
  [a b]
  (quot (- a (rem-euclid a b)) b))

(defn chunk-coord
  "Chunk coordinate `[cx cy cz]` containing world voxel `(x y z)`."
  [x y z]
  [(div-euclid x chunk-size) (div-euclid y chunk-size) (div-euclid z chunk-size)])

(defn local-index
  "Flat cell index within a chunk for world voxel `(x y z)`, matching Rust's
  `lx + ly*CHUNK_SIZE + lz*CHUNK_SIZE*CHUNK_SIZE`."
  [x y z]
  (+ (rem-euclid x chunk-size)
     (* (rem-euclid y chunk-size) chunk-size)
     (* (rem-euclid z chunk-size) chunk-size chunk-size)))

(defn- local-index-lxyz
  "Flat cell index from already-local `lx ly lz` (each in `[0, chunk-size)`)."
  [lx ly lz]
  (+ lx (* ly chunk-size) (* lz chunk-size chunk-size)))

(defn- chunk-base
  "World voxel coordinate of the `(0,0,0)` corner of chunk `cc`."
  [[cx cy cz]]
  [(* cx chunk-size) (* cy chunk-size) (* cz chunk-size)])

(def ^:private neighbor-offsets
  [[-1 0 0] [1 0 0] [0 -1 0] [0 1 0] [0 0 -1] [0 0 1]])

(defn- chunk-neighbors
  "The 6 face-adjacent chunk coordinates of `cc`."
  [[cx cy cz]]
  (mapv (fn [[dx dy dz]] [(+ cx dx) (+ cy dy) (+ cz dz)]) neighbor-offsets))

(defn- local-coords
  "Sequence of `[lx ly lz]` covering a whole chunk, in flat-index order
  (lx fastest, matching `local-index-lxyz`)."
  []
  (for [lz (range chunk-size) ly (range chunk-size) lx (range chunk-size)]
    [lx ly lz]))

;; ─────────────────────────────────────────────────────────────────────────
;; Vec3 (plain [x y z], zero-dep local math — stands in for glam::Vec3)
;; ─────────────────────────────────────────────────────────────────────────

(defn v3-add [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v3-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v3-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn v3-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn v3-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])
(defn v3-length-squared [v] (v3-dot v v))
(defn v3-length [v] (sqrt* (v3-length-squared v)))
(defn v3-normalize [v]
  (let [l (v3-length v)]
    (if (zero? l) v (v3-scale v (/ 1.0 l)))))

;; ─────────────────────────────────────────────────────────────────────────
;; ScalarField — 0-form on voxel cell centres
;; ─────────────────────────────────────────────────────────────────────────
;;
;; Sparse — chunks conceptually allocate on first write. Reading an absent
;; chunk returns 0.0. Numerically stable under explicit Euler with
;; `scalar-diffuse` when α·dt ≤ 1/6.

(def ^:private empty-scalar-cells (vec (repeat chunk-cells 0.0)))

(defn scalar-field
  "A fresh, empty 0-form field."
  []
  {:chunks {}})

(defn scalar-get
  "Read at world voxel coordinate. Absent chunk = 0.0."
  [field x y z]
  (if-let [cells (get (:chunks field) (chunk-coord x y z))]
    (nth cells (local-index x y z))
    0.0))

(defn scalar-set
  "Write at world voxel coordinate, creating the chunk if needed. Returns a
  new field (pure — Rust's `&mut self` mutator becomes a return value)."
  [field x y z v]
  (let [cc (chunk-coord x y z)
        li (local-index x y z)
        cells (get (:chunks field) cc empty-scalar-cells)]
    (assoc-in field [:chunks cc] (assoc cells li v))))

(defn scalar-add
  "In-place-style add. Convenience for source terms."
  [field x y z delta]
  (scalar-set field x y z (+ (scalar-get field x y z) delta)))

(defn- scalar-chunk-any-nonzero?
  "True if chunk `cc` or any of its 6 neighbours has data in `chunks`."
  [chunks cc]
  (or (contains? chunks cc)
      (some #(contains? chunks %) (chunk-neighbors cc))))

(defn scalar-diffuse
  "Diffusion step (heat equation): `φ_new = φ + α·dt·Δφ`, 7-point Laplacian
  on a 6-connected voxel graph. Stable when `α·dt ≤ 1/6`. Also applies an
  optional linear decay `φ *= 1 - k·dt` (pass `decay = 0.0` for pure
  diffusion). Prunes chunks that decay to ~0 to reclaim memory."
  [field alpha dt decay]
  (let [old field
        old-chunks (:chunks old)
        coeff (* alpha dt)
        decay-coeff (max 0.0 (- 1.0 (* decay dt)))
        active (into #{} (mapcat (fn [cc] (cons cc (chunk-neighbors cc))) (keys old-chunks)))
        new-chunks
        (reduce
         (fn [acc cc]
           (if-not (scalar-chunk-any-nonzero? old-chunks cc)
             acc
             (let [[bx by bz] (chunk-base cc)
                   cells (vec (for [[lx ly lz] (local-coords)]
                                (let [wx (+ bx lx) wy (+ by ly) wz (+ bz lz)
                                      p (scalar-get old wx wy wz)
                                      nsum (+ (scalar-get old (inc wx) wy wz)
                                              (scalar-get old (dec wx) wy wz)
                                              (scalar-get old wx (inc wy) wz)
                                              (scalar-get old wx (dec wy) wz)
                                              (scalar-get old wx wy (inc wz))
                                              (scalar-get old wx wy (dec wz)))
                                      lap (- nsum (* 6.0 p))]
                                  (* (+ p (* coeff lap)) decay-coeff))))]
               (assoc acc cc cells))))
         {}
         active)
        pruned (into {} (filter (fn [[_ cells]] (some #(> (abs* %) 1e-4) cells)) new-chunks))]
    (assoc field :chunks pruned)))

(defn emit-from
  "Source term: emit a value per solid voxel whose material passes `source`.
  `emitters` is a seq of `[x y z mat]`. `source` maps `mat -> emit-rate` or
  `nil` for non-emitters."
  [field emitters source dt]
  (reduce (fn [f [x y z mat]]
            (if-let [rate (source mat)]
              (scalar-add f x y z (* rate dt))
              f))
          field
          emitters))

(defn scalar-for-each-nonzero
  "Call `(f world-x world-y world-z value)` for every cell above `threshold`
  in magnitude."
  [field threshold f]
  (doseq [[cc cells] (:chunks field)]
    (let [[bx by bz] (chunk-base cc)]
      (doseq [[lx ly lz] (local-coords)]
        (let [v (nth cells (local-index-lxyz lx ly lz))]
          (when (> (abs* v) threshold)
            (f (+ bx lx) (+ by ly) (+ bz lz) v)))))))

(defn scalar-memory-bytes [field] (* (count (:chunks field)) chunk-cells 4))
(defn scalar-chunk-count [field] (count (:chunks field)))

(defn scalar-prune-outside
  "Drop chunks outside an AABB of `chunk-radius` around `center`."
  [field center chunk-radius]
  (let [[ccx ccy ccz] center]
    (update field :chunks
            (fn [chunks]
              (into {} (filter (fn [[[cx cy cz] _]]
                                  (and (<= (abs* (- cx ccx)) chunk-radius)
                                       (<= (abs* (- cy ccy)) chunk-radius)
                                       (<= (abs* (- cz ccz)) chunk-radius)))
                                chunks))))))

(defn scalar-sample-trilinear
  "Trilinear sample at fractional world position `[px py pz]`. Underpins
  semi-Lagrangian advection (back-trace sampling)."
  [field [px py pz]]
  (let [x0 (long (flr px)) y0 (long (flr py)) z0 (long (flr pz))
        tx (- px (flr px)) ty (- py (flr py)) tz (- pz (flr pz))
        c000 (scalar-get field x0 y0 z0)
        c100 (scalar-get field (inc x0) y0 z0)
        c010 (scalar-get field x0 (inc y0) z0)
        c110 (scalar-get field (inc x0) (inc y0) z0)
        c001 (scalar-get field x0 y0 (inc z0))
        c101 (scalar-get field (inc x0) y0 (inc z0))
        c011 (scalar-get field x0 (inc y0) (inc z0))
        c111 (scalar-get field (inc x0) (inc y0) (inc z0))
        c00 (+ (* c000 (- 1.0 tx)) (* c100 tx))
        c10 (+ (* c010 (- 1.0 tx)) (* c110 tx))
        c01 (+ (* c001 (- 1.0 tx)) (* c101 tx))
        c11 (+ (* c011 (- 1.0 tx)) (* c111 tx))
        c0 (+ (* c00 (- 1.0 ty)) (* c10 ty))
        c1 (+ (* c01 (- 1.0 ty)) (* c11 ty))]
    (+ (* c0 (- 1.0 tz)) (* c1 tz))))

(defn scalar-advect-uniform
  "Semi-Lagrangian advection under a uniform wind vector. Unconditionally
  stable (no CFL restriction) — Jos Stam's \"Stable Fluids\" trick."
  [field wind dt]
  (let [old field
        step (v3-scale wind dt)
        new-chunks (reduce
                    (fn [acc cc]
                      (let [[bx by bz] (chunk-base cc)
                            cells (vec (for [[lx ly lz] (local-coords)]
                                         (let [wp [(+ bx lx) (+ by ly) (+ bz lz)]]
                                           (scalar-sample-trilinear old (v3-sub wp step)))))]
                        (assoc acc cc cells)))
                    {}
                    (keys (:chunks old)))
        pruned (into {} (filter (fn [[_ cells]] (some #(> (abs* %) 1e-4) cells)) new-chunks))]
    (assoc field :chunks pruned)))

(declare edge-vec-at)

(defn scalar-advect-field
  "Semi-Lagrangian advection under a spatially-varying `EdgeField` wind."
  [field wind dt]
  (let [old field
        new-chunks (reduce
                    (fn [acc cc]
                      (let [[bx by bz] (chunk-base cc)
                            cells (vec (for [[lx ly lz] (local-coords)]
                                         (let [wx (+ bx lx) wy (+ by ly) wz (+ bz lz)
                                               w (edge-vec-at wind wx wy wz)
                                               wp [wx wy wz]]
                                           (scalar-sample-trilinear old (v3-sub wp (v3-scale w dt))))))]
                        (assoc acc cc cells)))
                    {}
                    (keys (:chunks old)))
        pruned (into {} (filter (fn [[_ cells]] (some #(> (abs* %) 1e-4) cells)) new-chunks))]
    (assoc field :chunks pruned)))

;; ─────────────────────────────────────────────────────────────────────────
;; EdgeField — 1-form on voxel edges
;; ─────────────────────────────────────────────────────────────────────────
;;
;; Each voxel cell owns three outgoing edges (to +X, +Y, +Z neighbours).
;; Use cases: wind / flow velocity, discrete gradient `d-0`, divergence-free
;; projection, advection.

(def ^:private empty-vec-cells (vec (repeat chunk-cells [0.0 0.0 0.0])))

(defn edge-field
  "A fresh, empty 1-form field."
  []
  {:chunks {}})

(defn edge-get
  "Raw edge value along axis `a` (0=X, 1=Y, 2=Z) at cell `(x y z)`."
  [field x y z a]
  (if-let [cells (get (:chunks field) (chunk-coord x y z))]
    (nth (nth cells (local-index x y z)) a)
    0.0))

(defn edge-set
  [field x y z a val]
  (let [cc (chunk-coord x y z)
        li (local-index x y z)
        cells (get (:chunks field) cc empty-vec-cells)
        triple (nth cells li)]
    (assoc-in field [:chunks cc] (assoc cells li (assoc triple a val)))))

(defn edge-vec-at
  "Sample the full vector at a cell centre."
  [field x y z]
  [(edge-get field x y z 0) (edge-get field x y z 1) (edge-get field x y z 2)])

(defn edge-fill-uniform
  "Fill every cell in `[min, max)` with a uniform vector `wind`."
  [field [minx miny minz] [maxx maxy maxz] wind]
  (reduce (fn [f [x y z]]
            (-> f
                (edge-set x y z 0 (nth wind 0))
                (edge-set x y z 1 (nth wind 1))
                (edge-set x y z 2 (nth wind 2))))
          field
          (for [z (range minz maxz) y (range miny maxy) x (range minx maxx)] [x y z])))

(defn edge-chunk-count [field] (count (:chunks field)))
(defn edge-memory-bytes [field] (* (count (:chunks field)) chunk-cells 3 4))

(defn edge-prune-outside
  [field center chunk-radius]
  (let [[ccx ccy ccz] center]
    (update field :chunks
            (fn [chunks]
              (into {} (filter (fn [[[cx cy cz] _]]
                                  (and (<= (abs* (- cx ccx)) chunk-radius)
                                       (<= (abs* (- cy ccy)) chunk-radius)
                                       (<= (abs* (- cz ccz)) chunk-radius)))
                                chunks))))))

(defn edge-damp
  "Multiply every edge value by `factor` (per-frame linear damping)."
  [field factor]
  (update field :chunks
          (fn [chunks]
            (into {} (map (fn [[cc cells]]
                             [cc (mapv (fn [[a b c]] [(* a factor) (* b factor) (* c factor)]) cells)])
                           chunks)))))

(defn edge-populate-from-scalar-footprint
  "Populate every cell in `scalar-f`'s active chunk footprint with a uniform
  wind vector, clearing any previous values in those chunks."
  [field scalar-f uniform-wind]
  (reduce (fn [f cc] (assoc-in f [:chunks cc] (vec (repeat chunk-cells uniform-wind))))
          field
          (keys (:chunks scalar-f))))

(defn edge-mask-solid
  "Zero out edges whose endpoints touch a solid voxel (`solid?` is
  `(fn [x y z] bool)`). Simplest no-slip / no-penetration boundary."
  [field solid?]
  (update field :chunks
          (fn [chunks]
            (into {}
                  (map (fn [[cc cells]]
                         (let [[bx by bz] (chunk-base cc)]
                           [cc (vec (for [[lx ly lz] (local-coords)]
                                      (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                                            [a b c] (nth cells (local-index-lxyz lx ly lz))
                                            me (solid? x y z)]
                                        [(if (or me (solid? (inc x) y z)) 0.0 a)
                                         (if (or me (solid? x (inc y) z)) 0.0 b)
                                         (if (or me (solid? x y (inc z))) 0.0 c)])))]))
                       chunks)))))

(defn edge-add-buoyancy-from
  "Thermal buoyancy: \"hot air rises\". For each cell where `scalar-f`
  exceeds `threshold`, add `scale · value` to the +Y edge."
  [field scalar-f scale threshold]
  (let [updates (atom [])]
    (scalar-for-each-nonzero scalar-f threshold (fn [x y z v] (swap! updates conj [x y z v])))
    (reduce (fn [f [x y z v]]
              (edge-set f x y z 1 (+ (edge-get f x y z 1) (* scale v))))
            field
            @updates)))

(defn edge-subtract
  "self ← self − other (per-axis). Only touches chunks already present in
  `field` (matches Rust's `get_mut`-based in-place subtract, which never
  creates new chunks)."
  [field other]
  (update field :chunks
          (fn [chunks]
            (reduce (fn [cs [cc other-cells]]
                      (if (contains? cs cc)
                        (update cs cc
                                (fn [cells]
                                  (mapv (fn [[a b c] [oa ob oc]] [(- a oa) (- b ob) (- c oc)])
                                        cells other-cells)))
                        cs))
                    chunks
                    (:chunks other)))))

;; ─────────────────────────────────────────────────────────────────────────
;; d-0 (discrete gradient) / div (discrete divergence)
;; ─────────────────────────────────────────────────────────────────────────

(defn d-0
  "Exterior derivative `d_0 : Λ⁰ → Λ¹` (discrete gradient). Forward
  difference, exact for linear fields. `d-0 ∘ d-0 = 0` in the Hodge sense
  (grad has zero curl)."
  [field]
  {:chunks
   (into {}
         (map (fn [cc]
                (let [[bx by bz] (chunk-base cc)]
                  [cc (vec (for [[lx ly lz] (local-coords)]
                             (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                                   p (scalar-get field x y z)]
                               [(- (scalar-get field (inc x) y z) p)
                                (- (scalar-get field x (inc y) z) p)
                                (- (scalar-get field x y (inc z)) p)])))]))
              (keys (:chunks field))))})

(defn div
  "Codifferential applied to a 1-form → 0-form (discrete divergence)."
  [e]
  {:chunks
   (into {}
         (map (fn [cc]
                (let [[bx by bz] (chunk-base cc)]
                  [cc (vec (for [[lx ly lz] (local-coords)]
                             (let [x (+ bx lx) y (+ by ly) z (+ bz lz)]
                               (+ (- (edge-get e x y z 0) (edge-get e (dec x) y z 0))
                                  (- (edge-get e x y z 1) (edge-get e x (dec y) z 1))
                                  (- (edge-get e x y z 2) (edge-get e x y (dec z) 2))))))]))
              (keys (:chunks e))))})

;; ─────────────────────────────────────────────────────────────────────────
;; Pressure projection (incompressible flow, "stable fluids" style)
;; ─────────────────────────────────────────────────────────────────────────

(defn solve-poisson-jacobi
  "Solve `Δp = rhs` via damped Jacobi iteration (ω=2/3). Active set = rhs
  chunks + one neighbour layer. Prunes near-zero result."
  [rhs iterations]
  (let [active-seed (set (keys (:chunks rhs)))
        active (into active-seed (mapcat chunk-neighbors active-seed))
        omega (/ 2.0 3.0)
        p (loop [p {:chunks {}} n iterations]
            (if (zero? n)
              p
              (let [p-old p
                    new-chunks
                    (into {}
                          (map (fn [cc]
                                 (let [[bx by bz] (chunk-base cc)]
                                   [cc (vec (for [[lx ly lz] (local-coords)]
                                              (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                                                    nsum (+ (scalar-get p-old (inc x) y z)
                                                            (scalar-get p-old (dec x) y z)
                                                            (scalar-get p-old x (inc y) z)
                                                            (scalar-get p-old x (dec y) z)
                                                            (scalar-get p-old x y (inc z))
                                                            (scalar-get p-old x y (dec z)))
                                                    target (/ (- nsum (scalar-get rhs x y z)) 6.0)
                                                    old-v (scalar-get p-old x y z)]
                                                (+ old-v (* omega (- target old-v))))))]))
                               active))]
                (recur {:chunks new-chunks} (dec n)))))]
    (update p :chunks (fn [chunks] (into {} (filter (fn [[_ cells]] (some #(> (abs* %) 1e-5) cells)) chunks))))))

;; ─── Multigrid Poisson (2-level V-cycle) ───────────────────────────────────

(defn smooth-jacobi-h
  "Damped-Jacobi smoother on a sparse scalar field with arbitrary grid
  spacing `h`. Active set fixed at entry = rhs chunks ∪ p chunks ∪ one
  neighbour layer."
  [p rhs iterations h]
  (let [h2 (* h h)
        omega (/ 2.0 3.0)
        active-seed (into (set (keys (:chunks rhs))) (keys (:chunks p)))
        active (into active-seed (mapcat chunk-neighbors active-seed))]
    (loop [p p n iterations]
      (if (zero? n)
        p
        (let [p-old p
              new-chunks
              (into {}
                    (map (fn [cc]
                           (let [[bx by bz] (chunk-base cc)]
                             [cc (vec (for [[lx ly lz] (local-coords)]
                                        (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                                              nsum (+ (scalar-get p-old (inc x) y z)
                                                      (scalar-get p-old (dec x) y z)
                                                      (scalar-get p-old x (inc y) z)
                                                      (scalar-get p-old x (dec y) z)
                                                      (scalar-get p-old x y (inc z))
                                                      (scalar-get p-old x y (dec z)))
                                              target (/ (- nsum (* h2 (scalar-get rhs x y z))) 6.0)
                                              old-v (scalar-get p-old x y z)]
                                          (+ old-v (* omega (- target old-v))))))]))
                         active))]
          (recur {:chunks new-chunks} (dec n)))))))

(defn compute-residual
  "Residual `r = rhs − Δp` on the active footprint at spacing `h`."
  [p rhs h]
  (let [h2 (* h h)
        active (into (set (keys (:chunks rhs))) (keys (:chunks p)))]
    (reduce
     (fn [r cc]
       (let [[bx by bz] (chunk-base cc)]
         (reduce
          (fn [r [lx ly lz]]
            (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                  nsum (+ (scalar-get p (inc x) y z) (scalar-get p (dec x) y z)
                          (scalar-get p x (inc y) z) (scalar-get p x (dec y) z)
                          (scalar-get p x y (inc z)) (scalar-get p x y (dec z)))
                  lap (/ (- nsum (* 6.0 (scalar-get p x y z))) h2)
                  val (- (scalar-get rhs x y z) lap)]
              (if (> (abs* val) 1e-6) (scalar-set r x y z val) r)))
          r
          (local-coords))))
     (scalar-field)
     active)))

(defn restrict-scalar
  "Restrict (fine → coarse, 2× downsample): averages 2×2×2 fine cells into
  each coarse cell (divide by 8, not by population)."
  [f]
  (let [sums (reduce
              (fn [acc [cc cells]]
                (let [[bx by bz] (chunk-base cc)]
                  (reduce
                   (fn [acc2 [lx ly lz]]
                     (let [v (nth cells (local-index-lxyz lx ly lz))]
                       (if (zero? v)
                         acc2
                         (let [k [(div-euclid (+ bx lx) 2) (div-euclid (+ by ly) 2) (div-euclid (+ bz lz) 2)]]
                           (update acc2 k (fnil + 0.0) v)))))
                   acc
                   (local-coords))))
              {}
              (:chunks f))]
    (reduce (fn [out [[x y z] sum]] (scalar-set out x y z (/ sum 8.0)))
            (scalar-field)
            sums)))

(defn prolongate-scalar
  "Prolongate (coarse → fine, 2× upsample): piecewise-constant fill of each
  coarse cell's 2×2×2 fine-cell block."
  [f]
  (reduce
   (fn [out [cc cells]]
     (let [[bx by bz] (chunk-base cc)]
       (reduce
        (fn [out2 [lx ly lz]]
          (let [v (nth cells (local-index-lxyz lx ly lz))]
            (if (zero? v)
              out2
              (let [cx (+ bx lx) cy (+ by ly) cz (+ bz lz)]
                (reduce (fn [out3 [dx dy dz]]
                          (scalar-set out3 (+ (* 2 cx) dx) (+ (* 2 cy) dy) (+ (* 2 cz) dz) v))
                        out2
                        (for [dz (range 2) dy (range 2) dx (range 2)] [dx dy dz]))))))
        out
        (local-coords))))
   (scalar-field)
   (:chunks f)))

(defn solve-poisson-multigrid
  "Solve `Δp = rhs` via a 2-level V-cycle. Typical call:
  `fine-pre=2, coarse=6, fine-post=2`."
  [rhs fine-pre coarse fine-post]
  (let [p (smooth-jacobi-h (scalar-field) rhs fine-pre 1.0)
        r (compute-residual p rhs 1.0)
        r-c (restrict-scalar r)
        e-c (smooth-jacobi-h (scalar-field) r-c coarse 2.0)
        e (prolongate-scalar e-c)
        p2 (reduce (fn [acc [cc cells]]
                     (update-in acc [:chunks cc]
                                (fn [existing] (mapv + (or existing empty-scalar-cells) cells))))
                   p
                   (:chunks e))
        p3 (smooth-jacobi-h p2 rhs fine-post 1.0)]
    (update p3 :chunks (fn [chunks] (into {} (filter (fn [[_ cells]] (some #(> (abs* %) 1e-5) cells)) chunks))))))

(defn project-divergence-free
  "Helmholtz projection: make `wind` divergence-free by solving `Δp =
  div(wind)` (Jacobi, `iterations` steps) then subtracting `∇p`. No-op on an
  empty field."
  [wind iterations]
  (if (empty? (:chunks wind))
    wind
    (let [pressure (solve-poisson-jacobi (div wind) iterations)]
      (edge-subtract wind (d-0 pressure)))))

(defn project-divergence-free-mg
  "Multigrid variant of `project-divergence-free`."
  [wind]
  (if (empty? (:chunks wind))
    wind
    (let [pressure (solve-poisson-multigrid (div wind) 2 6 2)]
      (edge-subtract wind (d-0 pressure)))))

;; ─────────────────────────────────────────────────────────────────────────
;; FaceField — 2-form on voxel faces
;; ─────────────────────────────────────────────────────────────────────────
;;
;; Each cell owns three face normals: +YZ (a=0), +ZX (a=1), +XY (a=2).

(defn face-field
  "A fresh, empty 2-form field."
  []
  {:chunks {}})

(defn face-get
  [field x y z a]
  (if-let [cells (get (:chunks field) (chunk-coord x y z))]
    (nth (nth cells (local-index x y z)) a)
    0.0))

(defn face-set
  [field x y z a val]
  (let [cc (chunk-coord x y z)
        li (local-index x y z)
        cells (get (:chunks field) cc empty-vec-cells)
        triple (nth cells li)]
    (assoc-in field [:chunks cc] (assoc cells li (assoc triple a val)))))

(defn face-vec-at
  [field x y z]
  [(face-get field x y z 0) (face-get field x y z 1) (face-get field x y z 2)])

(defn face-magnitude [field x y z] (v3-length (face-vec-at field x y z)))
(defn face-chunk-count [field] (count (:chunks field)))
(defn face-memory-bytes [field] (* (count (:chunks field)) chunk-cells 3 4))

(defn face-for-each-nonzero
  "Call `(f world-x world-y world-z [a b c])` for every face whose vector
  magnitude exceeds `threshold`."
  [field threshold f]
  (let [thr2 (* threshold threshold)]
    (doseq [[cc cells] (:chunks field)]
      (let [[bx by bz] (chunk-base cc)]
        (doseq [[lx ly lz] (local-coords)]
          (let [v (nth cells (local-index-lxyz lx ly lz))]
            (when (> (v3-length-squared v) thr2)
              (f (+ bx lx) (+ by ly) (+ bz lz) v))))))))

;; ─────────────────────────────────────────────────────────────────────────
;; d-1 (discrete curl) and its adjoint
;; ─────────────────────────────────────────────────────────────────────────

(defn d-1
  "`d_1: EdgeField → FaceField`. Discrete curl: circulation of edges around
  each face. Preserves Stokes exactly on the cubical complex."
  [e]
  (let [seed (set (keys (:chunks e)))
        active (into seed (mapcat chunk-neighbors seed))
        chunks (into {}
                     (keep (fn [cc]
                             (let [[bx by bz] (chunk-base cc)
                                   cells (vec (for [[lx ly lz] (local-coords)]
                                                (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                                                      cx (- (- (edge-get e x (inc y) z 2) (edge-get e x y z 2))
                                                            (- (edge-get e x y (inc z) 1) (edge-get e x y z 1)))
                                                      cy (- (- (edge-get e x y (inc z) 0) (edge-get e x y z 0))
                                                            (- (edge-get e (inc x) y z 2) (edge-get e x y z 2)))
                                                      cz (- (- (edge-get e (inc x) y z 1) (edge-get e x y z 1))
                                                            (- (edge-get e x (inc y) z 0) (edge-get e x y z 0)))]
                                                  [cx cy cz])))]
                               (when (some (fn [[a b c]] (> (+ (abs* a) (abs* b) (abs* c)) 1e-5)) cells)
                                 [cc cells])))
                           active))]
    {:chunks chunks}))

(defn curl-face-to-edge
  "Adjoint of `d-1` on a unit-metric cubical grid: 2-form → 1-form.
  Used by the Maxwell Ampere update `∂E/∂t = c²·curl B`."
  [b]
  (let [seed (set (keys (:chunks b)))
        active (into seed (mapcat chunk-neighbors seed))
        chunks (into {}
                     (keep (fn [cc]
                             (let [[bx by bz] (chunk-base cc)
                                   cells (vec (for [[lx ly lz] (local-coords)]
                                                (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                                                      ex (- (- (face-get b x y z 2) (face-get b x (dec y) z 2))
                                                            (- (face-get b x y z 1) (face-get b x y (dec z) 1)))
                                                      ey (- (- (face-get b x y z 0) (face-get b x y (dec z) 0))
                                                            (- (face-get b x y z 2) (face-get b (dec x) y z 2)))
                                                      ez (- (- (face-get b x y z 1) (face-get b (dec x) y z 1))
                                                            (- (face-get b x y z 0) (face-get b x (dec y) z 0)))]
                                                  [ex ey ez])))]
                               (when (some (fn [[a b2 c]] (> (+ (abs* a) (abs* b2) (abs* c)) 1e-5)) cells)
                                 [cc cells])))
                           active))]
    {:chunks chunks}))

(defn step-maxwell
  "Free-function Yee-style leapfrog step. Faraday then Ampere. Returns
  `[e' b']` (pure — takes the place of Rust's externally-owned `&mut`
  fields)."
  [e b c dt]
  (let [curl-e (d-1 e)
        b2 (reduce (fn [acc [cc cells]]
                     (update-in acc [:chunks cc]
                                (fn [existing]
                                  (mapv (fn [[a b3 c3] [da db dc]] [(- a (* dt da)) (- b3 (* dt db)) (- c3 (* dt dc))])
                                        (or existing empty-vec-cells) cells))))
                   b
                   (:chunks curl-e))
        curl-b (curl-face-to-edge b2)
        k (* c c dt)
        e2 (reduce (fn [acc [cc cells]]
                     (update-in acc [:chunks cc]
                                (fn [existing]
                                  (mapv (fn [[a b3 c3] [da db dc]] [(+ a (* k da)) (+ b3 (* k db)) (+ c3 (* k dc))])
                                        (or existing empty-vec-cells) cells))))
                   e
                   (:chunks curl-b))]
    [e2 b2]))

;; ─────────────────────────────────────────────────────────────────────────
;; Maxwell — vacuum EM on the voxel cubical complex
;; ─────────────────────────────────────────────────────────────────────────
;;
;; DEC allocation mirroring Yee's staggered grid: E (electric field) is a
;; 1-form on edges, B (magnetic flux) is a 2-form on faces.
;;   Faraday : ∂B/∂t = −curl E  →  B ← B − dt · d_1(E)
;;   Ampere  : ∂E/∂t = c² curl B → E ← E + c² · dt · adjoint_d_1(B)
;; Leapfrog stable under CFL: c·dt ≤ h/√3 with h=1.

(defn maxwell
  "A fresh Maxwell state with speed-of-light `c` (normalised; choose ≤ 0.5
  for CFL safety at dt=1, or scale dt down)."
  [c]
  {:e (edge-field) :b (face-field) :c c})

(defn maxwell-step
  "Advance one leapfrog step."
  [m dt]
  (let [[e2 b2] (step-maxwell (:e m) (:b m) (:c m) dt)]
    (assoc m :e e2 :b b2)))

(defn maxwell-energy
  "Total field energy `½ Σ (E² + c²·B²)`. Conserved (up to O(dt²) leapfrog
  drift) for vacuum Maxwell without sources or absorbers."
  [m]
  (let [e2 (reduce + 0.0 (mapcat (fn [cells] (map v3-length-squared cells)) (vals (:chunks (:e m)))))
        b2 (reduce + 0.0 (mapcat (fn [cells] (map v3-length-squared cells)) (vals (:chunks (:b m)))))]
    (* 0.5 (+ e2 (* (:c m) (:c m) b2)))))

(defn maxwell-dipole-e
  "Inject an electric dipole: set E along `axis` at `(x y z)`. Radiates as
  an EM wave once `maxwell-step` is called."
  [m x y z axis amplitude]
  (update m :e edge-set x y z axis amplitude))

;; ─────────────────────────────────────────────────────────────────────────
;; Vorticity confinement (Fedkiw et al. 2001)
;; ─────────────────────────────────────────────────────────────────────────

(defn- vorticity-magnitude-field
  [omega footprint]
  (reduce
   (fn [mag cc]
     (let [[bx by bz] (chunk-base cc)]
       (reduce
        (fn [mag2 [lx ly lz]]
          (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                mm (face-magnitude omega x y z)]
            (if (> mm 1e-4) (scalar-set mag2 x y z mm) mag2)))
        mag
        (local-coords))))
   (scalar-field)
   footprint))

(defn vorticity-confine
  "Re-inject small-scale rotational energy lost to numerical diffusion
  during advection/projection (Fedkiw et al. 2001). Computes `ω =
  curl(wind)`, the normalised gradient of `|ω|`, and adds a force
  `ε · (N × ω) · dt` back into the edge field. `epsilon = 0` is a no-op."
  [wind epsilon dt]
  (if (or (<= epsilon 0.0) (empty? (:chunks wind)))
    wind
    (let [omega (d-1 wind)
          seed (set (keys (:chunks omega)))
          footprint (into seed (mapcat chunk-neighbors seed))
          mag (vorticity-magnitude-field omega footprint)]
      (reduce
       (fn [w cc]
         (let [[bx by bz] (chunk-base cc)]
           (reduce
            (fn [w2 [lx ly lz]]
              (let [x (+ bx lx) y (+ by ly) z (+ bz lz)
                    gx (* 0.5 (- (scalar-get mag (inc x) y z) (scalar-get mag (dec x) y z)))
                    gy (* 0.5 (- (scalar-get mag x (inc y) z) (scalar-get mag x (dec y) z)))
                    gz (* 0.5 (- (scalar-get mag x y (inc z)) (scalar-get mag x y (dec z))))
                    g [gx gy gz]
                    gl (v3-length g)]
                (if (< gl 1e-5)
                  w2
                  (let [n (v3-scale g (/ 1.0 gl))
                        wv (face-vec-at omega x y z)
                        f (v3-scale (v3-cross n wv) (* epsilon dt))]
                    (if (< (v3-length-squared f) 1e-10)
                      w2
                      (-> w2
                          (edge-set x y z 0 (+ (edge-get w2 x y z 0) (nth f 0)))
                          (edge-set x y z 1 (+ (edge-get w2 x y z 1) (nth f 1)))
                          (edge-set x y z 2 (+ (edge-get w2 x y z 2) (nth f 2)))))))))
            w
            (local-coords))))
       wind
       footprint))))
