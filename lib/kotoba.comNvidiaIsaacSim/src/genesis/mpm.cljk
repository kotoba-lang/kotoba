(ns genesis.mpm
  "Material Point Method continuum solver (2-D MLS-MPM) — config/data +
  obstacle-projection scoping.

  Scoping decision (large numerical-solver file, ADR-2607010930
  scoped-restoration pattern): `MpmMaterial`/`MpmObstacle` data and the
  per-obstacle boundary-condition projection (`obstacle-project` —
  cancels the inward relative-normal grid velocity component so material
  flows around a sphere/box obstacle) are pure 2-vector math, ported 1:1
  below, along with the solver's default configuration constants
  (grid resolution, dt, Young's modulus, Poisson ratio, gravity).

  The full MLS-MPM solver core (P2G scatter, grid momentum update +
  obstacle projection, G2P gather, fixed-corotated elasticity +
  return-mapping plasticity, APIC affine-velocity transfer) is a genuine
  ~600-line numerical continuum solver operating over a mutable
  particle/grid state; porting it 1:1 is out of scope for this
  restoration pass given the file's scale relative to the other 22 files
  (see README) — it is NOT PhysX/OmniKit/wgpu native code (it's clean-room
  CPU math), simply too large a solver core to port faithfully alongside
  the other 22 files in one pass. Left as a documented gap, not a
  native-code exclusion.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/mpm.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  (:require [genesis.vec3 :as v3]))

;; A Vec2 here is `[x y]` — reuses `genesis.vec3` ops on the first 2
;; components where convenient, but is otherwise plain 2-vector math.

(defn v2-sub [[ax ay] [bx by]] [(- ax bx) (- ay by)])
(defn v2-add [[ax ay] [bx by]] [(+ ax bx) (+ ay by)])
(defn v2-dot [[ax ay] [bx by]] (+ (* ax bx) (* ay by)))
(defn v2-length [v] (Math/sqrt (v2-dot v v)))

(defn material-elastic [] :elastic)  ;; soft elastic (sealant/jelly), no plasticity
(defn material-granular [] :granular) ;; granular plasticity (concrete/soil), settles into a pile
(defn material-fluid [] :fluid)       ;; weakly-compressible fluid (slurry), flows and spreads

(defn obstacle-sphere [center radius] {:kind :sphere :center center :radius radius})
(defn obstacle-box [mn mx] {:kind :box :min mn :max mx})

(defn obstacle-translate
  "Move the obstacle (kinematic/swept obstacles advance each step)."
  [obstacle d]
  (case (:kind obstacle)
    :sphere (update obstacle :center v2-add d)
    :box (-> obstacle (update :min v2-add d) (update :max v2-add d))))

(defn obstacle-project
  "Boundary condition: if `pos` is inside the obstacle and the grid
  velocity moves *into* it relative to the obstacle's own velocity
  `v-ob`, cancel the inward relative normal component — a moving obstacle
  (screed/piston/vibrator) drags the material along instead of letting it
  penetrate."
  [obstacle pos v v-ob]
  (let [vrel (v2-sub v v-ob)]
    (case (:kind obstacle)
      :sphere
      (let [{:keys [center radius]} obstacle
            d (v2-sub pos center)
            dist (v2-length d)]
        (if (< dist radius)
          (let [n (if (> dist 1e-6) [(/ (first d) dist) (/ (second d) dist)] [0.0 1.0])
                vn (v2-dot vrel n)]
            (if (< vn 0.0)
              (v2-add v-ob (v2-sub vrel (mapv #(* % vn) n)))
              v))
          v))

      :box
      (let [{mn :min mx :max} obstacle
            [px py] pos [mnx mny] mn [mxx mxy] mx]
        (if (and (> px mnx) (< px mxx) (> py mny) (< py mxy))
          (let [dl [(- px mnx) (- py mny)]
                dh [(- mxx px) (- mxy py)]
                [best n] (reduce
                           (fn [[best n] [d n']] (if (< d best) [d n'] [best n]))
                           [##Inf [0.0 1.0]]
                           [[(first dl) [-1.0 0.0]] [(first dh) [1.0 0.0]]
                            [(second dl) [0.0 -1.0]] [(second dh) [0.0 1.0]]])
                vn (v2-dot vrel n)]
            (if (< vn 0.0)
              (v2-add v-ob (v2-sub vrel (mapv #(* % vn) n)))
              v))
          v)))))

(defn default-config
  "Default `MpmSolver::new(n)` scalar parameters (grid domain = unit
  square, n = grid nodes per axis, clamped to >= 16)."
  [n]
  (let [n (max n 16)]
    {:n n :dx (/ 1.0 n) :inv-dx (double n) :dt 1e-4
     :p-mass 1.0 :p-vol 1.0 :e 1.0e4 :nu 0.2 :gravity -200.0}))
