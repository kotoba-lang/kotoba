(ns kami.gen.sdf-agent.sdf
  "Signed-distance-field primitive + combinator math, and a compiler from an
  EDN CSG tree (see `kami.gen.sdf-agent` for the tree grammar) to a
  `(fn [x y z] -> [dist [r g b a]])` sampler compatible with
  `kotoba-lang/mesher`'s `sdf-to-mesh` / `sdf-to-colored-mesh`.

  Why this lives here instead of in `kotoba-lang/sdf`: as of 2026-07-05 that
  repo is a scaffold with no functions (its README says so explicitly:
  \"Scaffold only — the CLJC restoration is pending\"). This namespace is the
  real, load-bearing SDF math for this repo's v0 -- not a mock -- implementing
  the standard exact signed-distance formulas for sphere / capped cylinder /
  capped cone / rounded box (Inigo Quilez's well-known `sdf` reference
  formulas) plus CSG boolean combinators (union = min, intersect = max,
  difference = max(a, -b)). If/when `kotoba-lang/sdf` grows real primitives,
  this namespace is the natural migration target -- see the repo's
  `:local/root` dependency on it in `deps.edn`, currently unused.")

;; ---------------------------------------------------------------------------
;; vec3 helpers
;; ---------------------------------------------------------------------------

(defn- v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn- vmax0 [[x y z]] [(max x 0.0) (max y 0.0) (max z 0.0)])
(defn- vlen [[x y z]] (Math/sqrt (double (+ (* x x) (* y y) (* z z)))))
(defn- vabs [[x y z]] [(Math/abs (double x)) (Math/abs (double y)) (Math/abs (double z))])

(defn- clamp [x lo hi] (max lo (min hi x)))

;; ---------------------------------------------------------------------------
;; Axis permutation -- lets every primitive be authored along +z and then
;; reoriented onto :x / :y / :z by permuting the sample point's coordinates
;; before evaluating (cheap, exact, avoids a general rotation-matrix API for v0).
;; ---------------------------------------------------------------------------

(defn- permute-for-axis
  "Rewrites [x y z] so that the requested `axis` (:x :y or :z) takes the role
  the primitive formulas below always treat as \"the long axis\" (z)."
  [axis [x y z]]
  (case axis
    :x [z y x]
    :y [x z y]
    :z [x y z]
    [x y z]))

;; ---------------------------------------------------------------------------
;; Exact SDF primitives (all take a point already relative to nothing --
;; callers subtract :center themselves so this module stays pure vec math).
;; ---------------------------------------------------------------------------

(defn sd-sphere
  "Exact SDF of a sphere of radius `r` centered at origin, sampled at `p`."
  [p r]
  (- (vlen p) (double r)))

(defn sd-round-box
  "Exact SDF of a box with half-extents `half` `[hx hy hz]` centered at
  origin, corners rounded by `round` (>= 0), sampled at `p`."
  [p half round]
  (let [round (double (or round 0.0))
        half' (mapv #(max 0.0 (- % round)) half)
        q (v- (vabs p) half')
        [qx qy qz] q
        outside (vlen (vmax0 q))
        inside (min (max qx (max qy qz)) 0.0)]
    (- (+ outside inside) round)))

(defn sd-capped-cylinder
  "Exact SDF of a cylinder centered at origin, axis z, radius `r`, full
  height `h` (spans z in [-h/2, h/2]), sampled at `p`."
  [p r h]
  (let [[px py pz] p
        radial (Math/sqrt (double (+ (* px px) (* py py))))
        dx (- radial (double r))
        dz (- (Math/abs (double pz)) (/ (double h) 2.0))
        outside (vlen [(max dx 0.0) (max dz 0.0) 0.0])
        inside (min (max dx dz) 0.0)]
    (+ outside inside)))

(defn sd-capped-cone
  "Exact SDF of a capped cone centered at origin, axis z, spanning z in
  [-h/2, h/2], base radius `r1` at z=-h/2, top radius `r2` at z=+h/2
  (Inigo Quilez's `sdCappedCone` formula, ported from the y-axis convention
  of the original to z-axis for this repo's z-up world). A true cone is
  `r2 = 0.0`."
  [p r1 r2 h]
  (let [[px py pz] p
        hh (/ (double h) 2.0)
        qx (Math/sqrt (double (+ (* px px) (* py py))))
        qy (double pz)
        k1x (double r2) k1y hh
        k2x (- (double r2) (double r1)) k2y (* 2.0 hh)
        ca-x (- qx (min qx (if (< qy 0.0) (double r1) (double r2))))
        ca-y (- (Math/abs qy) hh)
        k1-q-x (- k1x qx) k1-q-y (- k1y qy)
        dot-k1q-k2 (+ (* k1-q-x k2x) (* k1-q-y k2y))
        dot-k2-k2 (+ (* k2x k2x) (* k2y k2y))
        t (if (zero? dot-k2-k2) 0.0 (clamp (/ dot-k1q-k2 dot-k2-k2) 0.0 1.0))
        cb-x (+ (- qx k1x) (* k2x t))
        cb-y (+ (- qy k1y) (* k2y t))
        s (if (and (< cb-x 0.0) (< ca-y 0.0)) -1.0 1.0)
        d2 (min (+ (* ca-x ca-x) (* ca-y ca-y)) (+ (* cb-x cb-x) (* cb-y cb-y)))]
    (* s (Math/sqrt (double d2)))))

;; ---------------------------------------------------------------------------
;; CSG boolean combinators. Each node function returns [dist color]; the
;; combinators fold pairwise, propagating the color of whichever operand's
;; distance actually determined the combined value -- this makes color
;; attribution follow the CSG semantics exactly (e.g. after a `difference`,
;; the cut surface takes the subtrahend's color; everywhere else keeps the
;; minuend's), not just "first child wins".
;; ---------------------------------------------------------------------------

(defn combine-union [[d1 c1] [d2 c2]]
  (if (<= d1 d2) [d1 c1] [d2 c2]))

(defn combine-intersect [[d1 c1] [d2 c2]]
  (if (>= d1 d2) [d1 c1] [d2 c2]))

(defn combine-difference
  "a minus b: max(a, -b). Color follows -b (the cut surface) when it is the
  decisive (larger) term, else follows a."
  [[da ca] [db cb]]
  (let [neg-db (- db)]
    (if (>= neg-db da) [neg-db cb] [da ca])))

(def default-color [0.55 0.55 0.58 1.0])

;; ---------------------------------------------------------------------------
;; Compiler: EDN CSG tree -> (fn [x y z] -> [dist color])
;;
;; Grammar (a node is a vector `[tag & args]`):
;;   [:sphere    {:r n :center [x y z] :color [r g b a]}]
;;   [:box       {:size [sx sy sz] :center [x y z] :round n :color rgba}]
;;   [:cylinder  {:r n :h n :center [x y z] :axis :x|:y|:z :color rgba}]
;;   [:cone      {:r n :h n :at [x y z] :r2 n :axis :x|:y|:z :color rgba}]
;;       ;; :at is the BASE center (not the mid-point); apex is h further
;;       ;; along +axis. :r2 (default 0.0) is the top radius (0 = a true cone).
;;   [:union       child & children]
;;   [:intersect   child & children]
;;   [:difference  child & children]     ;; first child minus the rest
;; ---------------------------------------------------------------------------

(defn- leaf-sampler
  "Returns `(fn [p] -> [dist color])` for a single primitive node."
  [[tag {:keys [r r2 h size center round axis color at]
         :or {center [0 0 0] at [0 0 0] axis :z} :as params}]]
  (let [col (or color default-color)]
    (case tag
      :sphere
      (fn [p] [(sd-sphere (v- p center) r) col])

      :box
      (fn [p]
        (let [half (mapv #(/ (double %) 2.0) size)]
          [(sd-round-box (v- p center) half round) col]))

      :cylinder
      (fn [p]
        (let [p' (permute-for-axis axis (v- p center))]
          [(sd-capped-cylinder p' r h) col]))

      :cone
      (fn [p]
        ;; Permute into the native (axis-along-z) frame FIRST, then shift by
        ;; h/2 along the (now-native) z -- this turns the `:at` = base-point
        ;; convention into the primitive's native "centered on [-h/2,+h/2]"
        ;; convention, correctly regardless of `axis` (shifting in world
        ;; space by [0 0 h/2] before permuting, as an earlier version of
        ;; this code did, is wrong for axis :x/:y -- it shifts the wrong
        ;; world axis).
        (let [[lx ly lz] (permute-for-axis axis (v- p at))
              p' [lx ly (- lz (/ (double h) 2.0))]]
          [(sd-capped-cone p' r (or r2 0.0) h) col]))

      (throw (ex-info (str "kami.gen.sdf-agent.sdf: unknown primitive tag " tag)
                       {:tag tag :params params})))))

(declare compile-node)

(defn- combine-children [combine-fn children]
  (let [samplers (mapv compile-node children)]
    (fn [p]
      (reduce (fn [acc sampler] (combine-fn acc (sampler p)))
              ((first samplers) p)
              (rest samplers)))))

(defn compile-node
  "Compile one CSG tree node into `(fn [p] -> [dist color])`, `p` a [x y z]."
  [node]
  (let [tag (first node)]
    (case tag
      (:sphere :box :cylinder :cone) (leaf-sampler node)
      :union (combine-children combine-union (rest node))
      :intersect (combine-children combine-intersect (rest node))
      :difference (combine-children combine-difference (rest node))
      (throw (ex-info (str "kami.gen.sdf-agent.sdf: unknown CSG tag " tag)
                       {:tag tag :node node})))))

(defn compile-program
  "Compile a full CSG program (a single tree, root is a combinator or a bare
  primitive) into the `(fn [x y z] -> [dist [r g b a]])` sampler shape
  `kotoba-lang/mesher`'s `sdf-to-mesh` / `sdf-to-colored-mesh` expect."
  [program]
  (let [f (compile-node program)]
    (fn [x y z] (f [x y z]))))

(defn program->bounds
  "Coarse world-space half-extent bound covering `program`, computed by
  walking node params (not by sampling) -- used to size the marching-cubes
  grid. Adds `margin` (default 0.5) so surfaces near the edge aren't clipped."
  ([program] (program->bounds program 0.5))
  ([program margin]
   (letfn [(node-extent [[tag {:keys [r r2 h size center round axis at]
                               :or {center [0 0 0] at [0 0 0] axis :z}}]]
             (case tag
               :sphere (mapv (fn [c] (+ (Math/abs (double c)) (double r))) center)
               :box (let [half (mapv #(/ (double %) 2.0) size)]
                      (mapv (fn [c hx] (+ (Math/abs (double c)) hx)) center half))
               :cylinder (let [rext (permute-for-axis axis [r r (/ (double h) 2.0)])]
                           (mapv (fn [c e] (+ (Math/abs (double c)) e)) center rext))
               :cone (let [;; permute-for-axis is its own inverse (a coordinate
                           ;; permutation/involution), so applying it to a
                           ;; native-frame offset also converts that offset
                           ;; into world space -- same fix as leaf-sampler's
                           ;; :cone case. `:at` is the cone's base point (see
                           ;; grammar docstring above), not `:center`.
                           shift (permute-for-axis axis [0.0 0.0 (/ (double h) 2.0)])
                           mid (v+ at shift)
                           rext (permute-for-axis axis [(max r (or r2 0.0)) (max r (or r2 0.0)) (/ (double h) 2.0)])]
                       (mapv (fn [c e] (+ (Math/abs (double c)) e)) mid rext))
               [0.0 0.0 0.0]))
           (walk [node]
             (let [tag (first node)]
               (if (#{:sphere :box :cylinder :cone} tag)
                 (node-extent node)
                 (reduce (fn [acc child] (mapv max acc (walk child)))
                         [0.0 0.0 0.0] (rest node)))))]
     (let [[ex ey ez] (walk program)]
       (+ (double margin) (double (max ex ey ez)))))))
