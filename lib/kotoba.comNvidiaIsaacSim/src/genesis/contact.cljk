(ns genesis.contact
  "Rigid contact / collision solver coupled to the 3-D reduced-coordinate
  articulation.

  Scoping decision (large/mixed file, ADR-2607010930 scoped-restoration
  pattern): the `Obstacle`/`Collider` shape data and the per-obstacle
  contact-generation geometry (`obstacle-contact` — plane / AABB / convex
  sphere-contact queries against a world-space sphere) are pure math over
  `genesis.vec3`/`genesis.convex` and are ported 1:1 below. `ContactWorld`
  itself — the velocity-level sequential-impulse / projected Gauss-Seidel
  solver that couples contacts into the articulation's *joint space* via
  the CRBA joint-space inertia (`Articulation3dConfig::point_jacobian` /
  `solve_ldlt`) — is NOT ported: it depends on the full
  `genesis.articulation3d` numerical solver core, which this restoration
  scopes to config/constants-only (see `genesis.articulation3d`), and on
  `kami_articulated`-parsed URDF systems for its test fixtures. Porting a
  correct multi-body PGS contact solver without that foundation would not
  be a faithful 1:1 port, so it is excluded here per the \"lighter-weight
  config/constants-only\" scoping guidance.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/contact.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  (:require [genesis.vec3 :as v3]
            [genesis.convex :as convex]
            [genesis.articulation3d :as a3d]))

;; ── Collider shapes (body-frame) ────────────────────────────────────────

(defn collider-sphere [center radius] {:kind :sphere :center center :radius radius})
(defn collider-capsule [a b radius] {:kind :capsule :a a :b b :radius radius})
(defn collider-box [center half radius] {:kind :box :center center :half half :radius radius})

;; ── Static environment obstacles ────────────────────────────────────────

(defn obstacle-plane [normal offset] {:kind :plane :normal normal :offset offset})
(defn obstacle-aabb [mn mx] {:kind :aabb :min mn :max mx})
(defn obstacle-convex [poly] {:kind :convex :poly poly})

(def default-contact-params
  {:ground-z 0.0 :restitution 0.0 :friction 0.8 :baumgarte 0.15 :slop 1.0e-3 :iters 12})

(defn- clamp3 [[x y z] [mnx mny mnz] [mxx mxy mxz]]
  [(max mnx (min mxx x)) (max mny (min mxy y)) (max mnz (min mxz z))])

(defn obstacle-contact
  "Contact for a world-space sphere `(c, radius)` belonging to `link`, or
  nil if it is clear of `obstacle` (beyond the slop band)."
  [obstacle link c radius slop]
  (case (:kind obstacle)
    :plane
    (let [n (v3/normalize (:normal obstacle))
          d (- (v3/dot c n) (:offset obstacle))
          depth (- radius d)]
      (when (> depth (- slop)) {:link link :p (v3/sub c (v3/scale n d)) :n n :depth depth}))

    :aabb
    (let [{mn :min mx :max} obstacle
          cp (clamp3 c mn mx)
          diff (v3/sub c cp)
          dist2 (v3/length-squared diff)]
      (if (> dist2 1.0e-12)
        (let [dist (Math/sqrt dist2) n (v3/scale diff (/ 1.0 dist)) depth (- radius dist)]
          (when (> depth (- slop)) {:link link :p cp :n n :depth depth}))
        (let [dlo (v3/sub c mn) dhi (v3/sub mx c)
              axes [v3/x-axis v3/y-axis v3/z-axis]]
          (loop [ax 0 best ##Inf n v3/z-axis]
            (if (>= ax 3)
              {:link link :p c :n n :depth (+ radius best)}
              (let [[best n] (if (< (nth dlo ax) best) [(nth dlo ax) (v3/neg (nth axes ax))] [best n])
                    [best n] (if (< (nth dhi ax) best) [(nth dhi ax) (nth axes ax)] [best n])]
                (recur (inc ax) best n)))))))

    :convex
    (let [poly (:poly obstacle)
          pt (convex/->poly [c])
          cv (convex/gjk-closest-vec pt poly)
          d (v3/length cv)]
      (if (> d 1e-6)
        (let [n (v3/scale cv (/ 1.0 d)) depth (- radius d)]
          (when (> depth (- slop)) {:link link :p (v3/sub c (v3/scale n radius)) :n n :depth depth}))
        (when-let [[pd n0] (convex/epa-penetration pt poly)]
          (let [centroid (v3/scale (reduce v3/add v3/zero (:verts poly)) (/ 1.0 (max 1 (count (:verts poly)))))
                n (if (< (v3/dot n0 (v3/sub c centroid)) 0.0) (v3/neg n0) n0)]
            {:link link :p c :n n :depth (+ radius pd)}))))))

(defn resolve-static-contact
  "Apply one unilateral normal impulse for a static-obstacle contact.

  `contact` must come from `obstacle-contact` and its `:link` is the general
  articulation link name. The caller may repeat this for a manifold or over
  multiple iterations; friction and articulated-articulated contact are out
  of scope for this single-contact static-environment path."
  ([cfg state contact] (resolve-static-contact cfg state contact {}))
  ([cfg state {:keys [link p n depth] :as contact} params]
   (let [{:keys [restitution baumgarte slop]}
         (merge default-contact-params params)
         jacobian (a3d/point-jacobian cfg state link p)
         normal-row (mapv (fn [jx jy jz] (v3/dot n [jx jy jz]))
                          (nth jacobian 0) (nth jacobian 1) (nth jacobian 2))
         normal-velocity (reduce + (map * normal-row (:qdot state)))
         desired (max 0.0 (* baumgarte (/ (max 0.0 (- depth slop)) (:dt cfg))))
         restitution-target (if (< normal-velocity 0.0) (* (- restitution) normal-velocity) 0.0)
         target (max desired restitution-target)
         effective (a3d/constraint-effective-mass cfg state normal-row)
         impulse (if effective
                   (max 0.0 (/ (- target normal-velocity) (:effective-mass effective)))
                   0.0)
         normal-state (a3d/apply-velocity-impulse cfg state normal-row impulse)]
     {:state normal-state
      :contact contact :normal-velocity normal-velocity :target-velocity target
      :impulse impulse})))

(defn- tangent-basis [normal]
  (let [reference (if (< (Math/abs (nth normal 0)) 0.8) v3/x-axis v3/y-axis)
        first-tangent (v3/normalize (v3/cross normal reference))]
    [first-tangent (v3/cross normal first-tangent)]))

(defn resolve-static-contact-friction
  "Resolve one static contact with normal impulse and two Coulomb-friction
  tangential impulses. `:friction` defaults to `default-contact-params`.

  This is a deterministic one-contact sequential impulse; callers can apply
  it repeatedly for a manifold or PGS sweep."
  ([cfg state contact] (resolve-static-contact-friction cfg state contact {}))
  ([cfg state {:keys [link p n] :as contact} params]
   (let [{normal-state :state normal-impulse :impulse :as normal-result}
         (resolve-static-contact cfg state contact params)
         friction (:friction (merge default-contact-params params))
         jacobian (a3d/point-jacobian cfg normal-state link p)
         [t1 t2] (tangent-basis n)
         [state impulses]
         (reduce
          (fn [[current applied] tangent]
            (let [row (mapv (fn [jx jy jz] (v3/dot tangent [jx jy jz]))
                            (nth jacobian 0) (nth jacobian 1) (nth jacobian 2))
                  velocity (reduce + (map * row (:qdot current)))
                  effective (a3d/constraint-effective-mass cfg current row)
                  unconstrained (if effective (/ (- velocity) (:effective-mass effective)) 0.0)
                  limit (* friction normal-impulse)
                  impulse (max (- limit) (min limit unconstrained))]
              [(a3d/apply-velocity-impulse cfg current row impulse)
               (conj applied impulse)]))
          [normal-state []] [t1 t2])]
     (assoc normal-result :state state :friction-impulses impulses))))

(defn warm-start-static-contact
  "Apply a prior `resolve-static-contact-friction` result to the same contact.

  The caller owns cache matching (normally by stable collider/contact IDs).
  The function is intentionally explicit rather than guessing identity from
  floating-point positions."
  [cfg state {:keys [link p n]} {:keys [impulse friction-impulses]}]
  (let [jacobian (a3d/point-jacobian cfg state link p)
        normal-row (mapv (fn [jx jy jz] (v3/dot n [jx jy jz]))
                         (nth jacobian 0) (nth jacobian 1) (nth jacobian 2))
        normal-state (a3d/apply-velocity-impulse cfg state normal-row (or impulse 0.0))
        [t1 t2] (tangent-basis n)]
    (reduce (fn [current [tangent tangent-impulse]]
              (let [row (mapv (fn [jx jy jz] (v3/dot tangent [jx jy jz]))
                               (nth jacobian 0) (nth jacobian 1) (nth jacobian 2))]
                (a3d/apply-velocity-impulse cfg current row (or tangent-impulse 0.0))))
            normal-state
            (map vector [t1 t2] (concat (or friction-impulses []) [0.0 0.0])))))

(defn resolve-static-contacts
  "Projected Gauss-Seidel sweep for multiple static contacts on one
  articulation. `contacts` is a vector of `obstacle-contact` results.

  The solver performs `:iters` (default 12) deterministic sweeps in input
  order. It returns every per-contact result from the final sweep, suitable
  for diagnostics or a caller-owned warm-start cache."
  ([cfg state contacts] (resolve-static-contacts cfg state contacts {}))
  ([cfg state contacts params]
   (let [contacts (vec (remove nil? contacts))
         iterations (max 1 (or (:iters params) (:iters default-contact-params)))
         cached (or (:warm-start params) [])
         initial (reduce (fn [current [contact cache]]
                           (if cache (warm-start-static-contact cfg current contact cache) current))
                         state (map vector contacts cached))]
     (loop [iteration 0 current initial results []]
       (if (= iteration iterations)
         {:state current :iterations iterations :contacts results}
         (let [[next-state sweep]
               (reduce (fn [[s resolved] contact]
                         (let [result (resolve-static-contact-friction cfg s contact params)]
                           [(:state result) (conj resolved result)]))
                       [current []] contacts)]
           (recur (inc iteration) next-state sweep)))))))

(defn resolve-articulation-contact
  "Resolve one frictionless point contact between two general articulations.

  The normal points from A to B. The returned impulse is applied as `-J_A^T`
  to A and `+J_B^T` to B, preserving equal-and-opposite generalized impulse.
  This is the narrow-phase solver primitive for future articulated manifolds."
  ([cfg-a state-a link-a cfg-b state-b link-b point normal depth]
   (resolve-articulation-contact cfg-a state-a link-a cfg-b state-b link-b point normal depth {}))
  ([cfg-a state-a link-a cfg-b state-b link-b point normal depth params]
   (let [{:keys [restitution baumgarte slop]} (merge default-contact-params params)
         row-for (fn [cfg state link]
                   (let [jacobian (a3d/point-jacobian cfg state link point)]
                     (mapv (fn [jx jy jz] (v3/dot normal [jx jy jz]))
                           (nth jacobian 0) (nth jacobian 1) (nth jacobian 2))))
         row-a (row-for cfg-a state-a link-a)
         row-b (row-for cfg-b state-b link-b)
         va (reduce + (map * row-a (:qdot state-a)))
         vb (reduce + (map * row-b (:qdot state-b)))
         relative (- vb va)
         desired (max 0.0 (* baumgarte (/ (max 0.0 (- depth slop))
                                            (min (:dt cfg-a) (:dt cfg-b)))))
         restitution-target (if (< relative 0.0) (* (- restitution) relative) 0.0)
         target (max desired restitution-target)
         mass-a (a3d/constraint-effective-mass cfg-a state-a row-a)
         mass-b (a3d/constraint-effective-mass cfg-b state-b row-b)
         effective (+ (or (:effective-mass mass-a) 0.0)
                      (or (:effective-mass mass-b) 0.0))
         impulse (if (> effective 1e-12) (max 0.0 (/ (- target relative) effective)) 0.0)]
     {:state-a (a3d/apply-velocity-impulse cfg-a state-a row-a (- impulse))
      :state-b (a3d/apply-velocity-impulse cfg-b state-b row-b impulse)
      :relative-velocity relative :target-velocity target :impulse impulse})))
