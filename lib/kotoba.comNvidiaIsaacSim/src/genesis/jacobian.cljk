(ns genesis.jacobian
  "Articulation Jacobians — foundation for IK / operational-space control.

  For each supported topology + named link, returns the 6xn geometric
  Jacobian J(q) such that the link's spatial twist in world frame equals
  J(q) . qdot, twist = [v_x v_y v_z w_x w_y w_z].

  Mirrors the public API of `isaacsim.core.api.Articulation.get_jacobians()`
  (Isaac Sim 4.x). Topologies live in the xz-plane with joint axes along
  world +/-y, so rows 1 (v_y), 3 (w_x), 5 (w_z) are always zero; rows 0
  (v_x), 2 (v_z), 4 (w_y) carry all the structure. The full 6-row layout
  is kept so the API surface is byte-identical to the original.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/jacobian.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math). One original Rust test,
  `dp_jacobian_times_qdot_matches_link_state_velocity`, cross-checked the
  analytical Jacobian against `world.rs::Articulation::link_state` built
  from a URDF fixture via the `kami_articulated` crate — that crate and
  the URDF-driven `World`/`Articulation` integration are out of scope for
  this restoration (see README, `genesis.world`), so that one test is
  excluded here; all the other (pure math) Jacobian tests are ported."
  )

(defn jac-zeros [n]
  {:rows (vec (repeat 6 (vec (repeat n 0.0))))})

(defn cols [{:keys [rows]}] (count (first rows)))

(defn flatten-jac
  "Row-major flatten of a Jacobian's 6 x n rows into a single vector."
  [{:keys [rows]}]
  (vec (mapcat identity rows)))

(defn- set-row [j r v] (assoc-in j [:rows r] v))

;; ─── Cartpole ─────────────────────────────────────────────────────────────

(defn cartpole-link-jacobian
  "q = [x theta]; cart is prismatic slider, pole revolute about +y."
  [theta link _cfg]
  (case link
    "world" (jac-zeros 2)
    "cart" (set-row (jac-zeros 2) 0 [1.0 0.0])
    "pole_link"
    (let [lc 0.25 st (Math/sin theta) ct (Math/cos theta)]
      (-> (jac-zeros 2)
          (set-row 0 [1.0 (* lc ct)])
          (set-row 2 [0.0 (* -1.0 lc st)])
          (set-row 4 [0.0 1.0])))
    nil))

;; ─── Double pendulum ──────────────────────────────────────────────────────

(defn dp-link-jacobian
  [q1 q2 link {:keys [l1 l2]}]
  (case link
    "world" (jac-zeros 2)
    "link1"
    (let [lc1 (* l1 0.5) s1 (Math/sin q1) c1 (Math/cos q1)]
      (-> (jac-zeros 2)
          (set-row 0 [(* lc1 c1) 0.0])
          (set-row 2 [(* lc1 s1) 0.0])
          (set-row 4 [1.0 0.0])))
    "link2"
    (let [lc2 (* l2 0.5) s1 (Math/sin q1) c1 (Math/cos q1)
          s12 (Math/sin (+ q1 q2)) c12 (Math/cos (+ q1 q2))]
      (-> (jac-zeros 2)
          (set-row 0 [(+ (* l1 c1) (* lc2 c12)) (* lc2 c12)])
          (set-row 2 [(+ (* l1 s1) (* lc2 s12)) (* lc2 s12)])
          (set-row 4 [1.0 1.0])))
    nil))

;; ─── Planar n-link chain ──────────────────────────────────────────────────
;;
;; `link-index` is 0-based (0 = link1).

(defn planar-chain-link-jacobian
  [q link-index {:keys [n lengths]}]
  (when (< link-index n)
    (let [theta (vec (reductions + q))
          j (jac-zeros n)]
      (reduce
        (fn [j col]
          (if (> col link-index)
            j
            (let [sum-lin
                  (reduce (fn [[vx vz] i]
                            [(+ vx (* (nth lengths i) (Math/cos (nth theta i))))
                             (+ vz (* (nth lengths i) (Math/sin (nth theta i))))])
                          [0.0 0.0] (range col link-index))
                  lc (* (nth lengths link-index) 0.5)
                  vx (+ (first sum-lin) (* lc (Math/cos (nth theta link-index))))
                  vz (+ (second sum-lin) (* lc (Math/sin (nth theta link-index))))]
              (-> j
                  (assoc-in [:rows 0 col] vx)
                  (assoc-in [:rows 2 col] vz)
                  (assoc-in [:rows 4 col] 1.0)))))
        j (range n)))))
