(ns brep.feature
  "Parametric feature tree: sketch, extrude, revolve, fillet, chamfer,
  boolean, etc. Restored from kami-cad's `feature` module (deleted
  PR #82). A `FeatureId` is a plain number (the original's newtype
  `FeatureId(u64)` wrapper adds no behavior). Sketch constraint kinds use
  the same keyword vocabulary as `kotoba-lang/engineer`'s
  `engineer.constraint/kinds` (:coincident/:parallel/etc.) — the original
  duplicated `ConstraintKind` as `SketchConstraintKind` for serde
  independence rather than a hard crate dependency; this mirrors that by
  using the same keywords without an explicit inter-repo dependency."
  (:require [brep.kernel :as k]
            [brep.topology :as topo]
            [brep.tessellate :as tess]
            [brep.polygon :as poly]
            [brep.mesh-csg :as csg]))

(def boolean-ops #{:new :add :cut :intersect})

(def sketch-constraint-kinds
  "Mirrors engineer.constraint/kinds — see namespace docstring."
  #{:coincident :parallel :perpendicular :tangent :equal :horizontal :vertical
    :fixed :symmetric :concentric :midpoint :collinear :distance :angle
    :radius :diameter})

;; SketchPlane
(defn sketch-plane-xy [] {:kind :xy})
(defn sketch-plane-xz [] {:kind :xz})
(defn sketch-plane-yz [] {:kind :yz})
(defn sketch-plane-custom [origin normal] {:kind :custom :origin origin :normal normal})

(defn sketch-plane-normal [plane]
  (case (:kind plane)
    :xy [0.0 0.0 1.0]
    :xz [0.0 1.0 0.0]
    :yz [1.0 0.0 0.0]
    :custom (k/v-normalize (:normal plane))))

(defn sketch-plane-origin [plane]
  (case (:kind plane)
    (:xy :xz :yz) [0.0 0.0 0.0]
    :custom (:origin plane)))

;; SketchEntity variants
(defn sketch-line [start end] {:kind :line :start start :end end})
(defn sketch-arc [center radius start-angle end-angle]
  {:kind :arc :center center :radius radius :start-angle start-angle :end-angle end-angle})
(defn sketch-circle [center radius] {:kind :circle :center center :radius radius})
(defn sketch-spline [control-points] {:kind :spline :control-points control-points})
(defn sketch-dimension [entity-ref value] {:kind :dimension :entity-ref entity-ref :value value})
(defn sketch-constraint [kind entity-refs] {:kind :constraint :constraint-kind kind :entity-refs entity-refs})

;; Feature variants — each a map with :kind + :id + variant-specific fields
(defn sketch-feature [id plane entities] {:kind :sketch :id id :plane plane :entities entities})
(defn extrude-feature [id sketch-ref direction distance operation]
  {:kind :extrude :id id :sketch-ref sketch-ref :direction direction :distance distance :operation operation})
(defn revolve-feature [id sketch-ref axis angle operation]
  {:kind :revolve :id id :sketch-ref sketch-ref :axis axis :angle angle :operation operation})
(defn fillet-feature [id edges radius] {:kind :fillet :id id :edges edges :radius radius})
(defn chamfer-feature [id edges distance] {:kind :chamfer :id id :edges edges :distance distance})
(defn sweep-feature [id profile-ref path-ref operation]
  {:kind :sweep :id id :profile-ref profile-ref :path-ref path-ref :operation operation})
(defn loft-feature [id profiles operation] {:kind :loft :id id :profiles profiles :operation operation})
(defn shell-feature [id removed-faces thickness] {:kind :shell :id id :removed-faces removed-faces :thickness thickness})
(defn pattern-feature [id source-features direction count spacing]
  {:kind :pattern :id id :source-features source-features :direction direction :count count :spacing spacing})
(defn boolean-feature [id operation tool-body] {:kind :boolean :id id :operation operation :tool-body tool-body})

(defn feature-id [feature] (:id feature))

;; FeatureTree
(defn feature-tree
  "A fresh, empty parametric feature tree."
  []
  {:entries []})

(defn add-feature [tree feature]
  (update tree :entries conj {:feature feature :suppressed false}))

(defn suppress [tree id]
  (update tree :entries
          (fn [entries] (mapv (fn [e] (if (= (feature-id (:feature e)) id) (assoc e :suppressed true) e)) entries))))

(defn unsuppress [tree id]
  (update tree :entries
          (fn [entries] (mapv (fn [e] (if (= (feature-id (:feature e)) id) (assoc e :suppressed false) e)) entries))))

(defn reorder
  "Move the feature with `id` to `new-index`."
  [tree id new-index]
  (let [entries (:entries tree)
        pos (first (keep-indexed (fn [i e] (when (= (feature-id (:feature e)) id) i)) entries))]
    (if-not pos
      tree
      (let [entry (nth entries pos)
            without (vec (concat (subvec entries 0 pos) (subvec entries (inc pos))))
            idx (min new-index (count without))]
        (assoc tree :entries (vec (concat (subvec without 0 idx) [entry] (subvec without idx))))))))

(defn tree-len [tree] (count (:entries tree)))
(defn tree-empty? [tree] (empty? (:entries tree)))

(defn- sketch-by-id
  "Non-suppressed :sketch features in `entries`, keyed by :id — revolve
  looks its profile up by :sketch-ref, and (unlike extrude) actually
  needs it."
  [entries]
  (into {}
        (keep (fn [{:keys [feature suppressed]}]
                (when (and (not suppressed) (= :sketch (:kind feature)))
                  [(:id feature) feature])))
        entries))

(defn- revolve-profile-cylinder
  "The only revolve profile this evaluator supports today: `sketch`'s
  :entities contains exactly one sketch-line, and both its 2D [x y]
  endpoints share the same x (an axis-parallel profile — x is radius, y
  is axial offset from the sketch plane's origin). Returns
  {:radius :axial-min :axial-max}, or nil if the sketch doesn't match
  that shape (an angled line — a cone/frustum profile — or any other
  entity count/kind is not yet implemented; no cone tessellation exists
  in brep.tessellate yet to render one correctly)."
  [sketch]
  (let [lines (filter #(= :line (:kind %)) (:entities sketch))]
    (when (= 1 (count lines))
      (let [{:keys [start end]} (first lines)
            [x0 y0] start [x1 y1] end]
        (when (< (Math/abs (- x0 x1)) 1e-9)
          {:radius x0 :axial-min (min y0 y1) :axial-max (max y0 y1)})))))


;; ---------------------------------------------------------------------------
;; Sketch profile -> prism (2026-07-27).
;;
;; Before this, `evaluate`'s `:extrude :new` branch built a **unit-square**
;; prism and ignored the sketch entirely ("sketch entities are not yet
;; consumed here, only :direction/:distance"). So a feature tree describing a
;; 305 x 192 enclosure panel evaluated to a 1 x 1 box, and nothing in the
;; return value said so. The sketch was decorative.
;;
;; These helpers make the profile real for the case that is both common and
;; exactly representable in STEP: a single closed loop of straight segments,
;; extruded along the sketch-plane normal. The resulting prism has only planar
;; faces and linear edges, which is precisely the subset `brep.step/write-step`
;; accepts — so an extruded sketch now round-trips to STEP.
;; ---------------------------------------------------------------------------

(defn- pt2= [[ax ay] [bx by]]
  (and (< (Math/abs (- (double ax) (double bx))) 1e-7)
       (< (Math/abs (- (double ay) (double by))) 1e-7)))

(defn- circle->segments
  "Polygonise a sketch-circle into `n` straight segments. A circle is not
  exactly representable as a planar-faced prism, so this is an explicit
  approximation, not a silent one: callers asking for STEP get a prism whose
  facet count they chose."
  [{:keys [center radius]} n]
  (let [[cx cy] center]
    (mapv (fn [i]
            (let [t0 (* 2.0 Math/PI (/ (double i) n))
                  t1 (* 2.0 Math/PI (/ (double (inc i)) n))]
              {:kind :line
               :start [(+ cx (* radius (Math/cos t0))) (+ cy (* radius (Math/sin t0)))]
               :end   [(+ cx (* radius (Math/cos t1))) (+ cy (* radius (Math/sin t1)))]}))
          (range n))))

(defn sketch->ring
  "Chain a sketch's straight segments into one ordered closed ring of 2D
  points, or nil when the entities do not form exactly one closed loop.

  Returns nil (never a guess) when: there are no segments, an endpoint has
  no continuation, or the walk does not return to its start. `circle-facets`
  (default 32) controls circle polygonisation. Arcs and splines are not
  chained — they would need tessellation this function deliberately does not
  invent."
  ([sketch] (sketch->ring sketch 32))
  ([sketch circle-facets]
   (let [ents (:entities sketch)
         segs (vec (concat (filter #(= :line (:kind %)) ents)
                           (mapcat #(circle->segments % circle-facets)
                                   (filter #(= :circle (:kind %)) ents))))]
     (when (>= (count segs) 3)
       (loop [ring [(:start (first segs))]
              cur (:end (first segs))
              remaining (set (range 1 (count segs)))]
         (cond
           ;; closed the loop and used every segment
           (and (pt2= cur (first ring)) (empty? remaining)) ring
           ;; closed early, leaving segments over -> more than one loop
           (pt2= cur (first ring)) nil
           (empty? remaining) nil
           :else
           (if-let [i (first (filter (fn [i]
                                       (let [sg (nth segs i)]
                                         (or (pt2= cur (:start sg)) (pt2= cur (:end sg)))))
                                     remaining))]
             (let [sg (nth segs i)
                   nxt (if (pt2= cur (:start sg)) (:end sg) (:start sg))]
               (recur (conj ring cur) nxt (disj remaining i)))
             nil)))))))

(defn sketch->polyline
  "Chain a sketch's straight segments into one ordered OPEN polyline of 2D
  points, or nil when they do not form exactly one open chain.

  `sketch->ring` above answers the closed question; a sweep path is normally
  open, and the two cannot share a walk: the ring walk starts anywhere because
  a loop has no ends, while an open chain has to start at one of its two
  endpoints or it walks off the near end and reports a break that is not there.

  Returns nil (never a guess) when: fewer than one segment, any point has three
  or more segments meeting at it (a branch — which branch is the path is a
  decision, not a default), the chain closes (that is a ring, ask the other
  function), or segments are left over (more than one chain). Circles, arcs and
  splines are not chained here."
  [sketch]
  (let [segs (vec (filter #(= :line (:kind %)) (:entities sketch)))]
    (when (>= (count segs) 1)
      (let [pts (mapcat (juxt :start :end) segs)
            degree (reduce (fn [m p]
                             (let [k (first (filter #(pt2= p %) (keys m)))]
                               (if k (update m k inc) (assoc m p 1))))
                           {} pts)
            ends (keep (fn [[p n]] (when (= 1 n) p)) degree)]
        (when (and (= 2 (count ends))
                   (every? #(<= (val %) 2) degree))
          (loop [chain [(first ends)]
                 cur (first ends)
                 remaining (set (range (count segs)))]
            (if (empty? remaining)
              (when (= (inc (count segs)) (count chain)) chain)
              (if-let [i (first (filter (fn [i]
                                          (let [sg (nth segs i)]
                                            (or (pt2= cur (:start sg)) (pt2= cur (:end sg)))))
                                        remaining))]
                (let [sg (nth segs i)
                      nxt (if (pt2= cur (:start sg)) (:end sg) (:start sg))]
                  (recur (conj chain nxt) nxt (disj remaining i)))
                nil))))))))

(defn- to-3d
  "Lift a 2D sketch point onto the sketch plane."
  [plane [u v]]
  (case (:kind plane)
    :xy [(double u) (double v) 0.0]
    :xz [(double u) 0.0 (double v)]
    :yz [0.0 (double u) (double v)]
    :custom (let [n (k/v-normalize (:normal plane))
                  o (:origin plane)
                  ;; any vector not parallel to n, made orthonormal
                  a (if (< (Math/abs (nth n 0)) 0.9) [1.0 0.0 0.0] [0.0 1.0 0.0])
                  e1 (k/v-normalize (k/v-cross n a))
                  e2 (k/v-cross n e1)]
              (k/v+ o (k/v+ (k/v-scale e1 (double u)) (k/v-scale e2 (double v)))))))

(defn- plane-basis
  "`[origin e1 e2 normal]` for a sketch plane, matching `to-3d` exactly: a 2D
  point `[u v]` lifts to `origin + u*e1 + v*e2`. Kept next to `to-3d` because
  the two must agree — a sweep places the profile with this basis and would
  otherwise sweep a different shape than the one that was drawn."
  [plane]
  (case (:kind plane)
    :xy [[0.0 0.0 0.0] [1.0 0.0 0.0] [0.0 1.0 0.0] [0.0 0.0 1.0]]
    :xz [[0.0 0.0 0.0] [1.0 0.0 0.0] [0.0 0.0 1.0] [0.0 1.0 0.0]]
    :yz [[0.0 0.0 0.0] [0.0 1.0 0.0] [0.0 0.0 1.0] [1.0 0.0 0.0]]
    :custom (let [n (k/v-normalize (:normal plane))
                  a (if (< (Math/abs (nth n 0)) 0.9) [1.0 0.0 0.0] [0.0 1.0 0.0])
                  e1 (k/v-normalize (k/v-cross n a))
                  e2 (k/v-cross n e1)]
              [(:origin plane) e1 e2 n])))

(defn- rotate-about
  "Rodrigues rotation of `x` about unit `axis` by `angle`."
  [x axis angle]
  (let [c (Math/cos angle) s (Math/sin angle)]
    (k/v+ (k/v+ (k/v-scale x c)
                (k/v-scale (k/v-cross axis x) s))
          (k/v-scale axis (* (k/v-dot axis x) (- 1.0 c))))))

(defn- transport-frame
  "Rotate `[e1 e2]` by the minimal rotation carrying `t0` onto `t1`.

  This is what makes a swept profile keep its orientation around a corner. A
  sweep that only TRANSLATES the profile is right on a straight path and
  silently wrong the moment the path turns — the section stops being
  perpendicular to the path and the solid pinches. Returns nil for a 180°
  reversal, where the minimal rotation is not unique."
  [t0 t1 [e1 e2]]
  (let [axis (k/v-cross t0 t1)
        len (k/v-length axis)
        d (k/v-dot t0 t1)]
    (cond
      (and (< len 1.0e-12) (pos? d)) [e1 e2]        ; same direction, nothing to do
      (< len 1.0e-12) nil                            ; reversal: ambiguous
      :else (let [a (k/v-scale axis (/ 1.0 len))
                  angle (Math/atan2 len d)]
              [(rotate-about e1 a angle) (rotate-about e2 a angle)]))))

(defn- path-tangents
  "Unit tangent at each station of a polyline. Interior stations average the
  incoming and outgoing directions so the section splits the corner, which is
  what keeps a mitred corner from self-intersecting on the inside."
  [pts]
  (let [n (count pts)
        seg (fn [i] (k/v-normalize (k/v- (nth pts (inc i)) (nth pts i))))]
    (mapv (fn [i]
            (cond
              (zero? i) (seg 0)
              (= i (dec n)) (seg (- n 2))
              :else (k/v-normalize (k/v+ (seg (dec i)) (seg i)))))
          (range n))))

(defn- newell-normal
  "Face normal from its own vertex loop (Newell's method) — robust to the
  ring's winding, unlike assuming CCW."
  [pts]
  (let [n (count pts)]
    (k/v-normalize
     (reduce (fn [acc i]
               (let [[x0 y0 z0] (nth pts i)
                     [x1 y1 z1] (nth pts (mod (inc i) n))]
                 (k/v+ acc [(* (- y0 y1) (+ z0 z1))
                            (* (- z0 z1) (+ x0 x1))
                            (* (- x0 x1) (+ y0 y1))])))
             [0.0 0.0 0.0] (range n)))))

(defn- centroid [pts]
  (k/v-scale (reduce k/v+ [0.0 0.0 0.0] pts) (/ 1.0 (count pts))))

(defn extrude-prism
  "Build a prism solid by extruding a closed 2D `ring` on `plane` along
  `dir` by `distance`. Returns `[solid edges vertices]` in `make-box`'s shape.

  All faces are `:plane` and all edges are `:line`, so the result is
  STEP-exportable via `brep.step/write-step`. Face normals are computed per
  face with Newell's method and then flipped to point away from the solid
  centroid, so the winding of the incoming ring does not matter."
  [id ring plane dir distance]
  (let [n (count ring)
        ext (k/v-scale (k/v-normalize dir) (double distance))
        base (mapv #(to-3d plane %) ring)
        top (mapv #(k/v+ % ext) base)
        all (into base top)
        verts (mapv (fn [i p] (k/brep-vertex (inc i) p)) (range) all)
        vid (fn [i] (:id (nth verts i)))
        pt (fn [i] (nth all i))
        mk-edge (fn [eid a b]
                  (k/brep-edge eid
                               (k/line-curve (pt a) (k/v-normalize (k/v- (pt b) (pt a))))
                               (vid a) (vid b)
                               [0.0 (k/v-distance (pt a) (pt b))]))
        base-edges (mapv (fn [i] (mk-edge (+ 100 i) i (mod (inc i) n))) (range n))
        top-edges (mapv (fn [i] (mk-edge (+ 200 i) (+ n i) (+ n (mod (inc i) n)))) (range n))
        vert-edges (mapv (fn [i] (mk-edge (+ 300 i) i (+ n i))) (range n))
        edges (into (into base-edges top-edges) vert-edges)
        solid-c (centroid all)
        mk-face (fn [fid eids face-pts]
                  (let [nrm (newell-normal face-pts)
                        c (centroid face-pts)
                        outward (if (neg? (k/v-dot nrm (k/v- c solid-c)))
                                  (k/v-scale nrm -1.0) nrm)]
                    (k/brep-face fid (k/plane-surface c outward)
                                 [(vec eids)] :forward)))
        bottom-face (mk-face 200 (map :id base-edges) base)
        top-face (mk-face 201 (map :id top-edges) top)
        side-faces (mapv (fn [i]
                           (let [j (mod (inc i) n)]
                             (mk-face (+ 210 i)
                                      [(:id (nth base-edges i)) (:id (nth vert-edges j))
                                       (:id (nth top-edges i)) (:id (nth vert-edges i))]
                                      [(pt i) (pt j) (pt (+ n j)) (pt (+ n i))])))
                         (range n))
        shell (k/brep-shell 300 (into [bottom-face top-face] side-faces) :forward)]
    [(k/brep-solid id [shell]) edges verts]))

(defn evaluate
  "Evaluate the feature tree, producing a BREP solid. Handles two base-
  feature cases:

  - `:extrude` with `:operation :new` generates a box-like prism from a
    unit-square cross-section along the extrusion direction (matches the
    original kami-cad Rust restoration — sketch entities are not yet
    consumed here, only :direction/:distance).
  - `:revolve` generates a real solid of revolution (brep.kernel/
    make-cylinder) ONLY for a full 2π turn of a single axis-parallel
    sketch-line profile (see revolve-profile-cylinder) — a cone/frustum
    profile (an angled line) or a partial-angle revolve returns
    `:error`, not a silently wrong shape; no cone tessellation exists
    yet to render either correctly.

  boolean/fillet/chamfer/sweep/loft/shell/pattern evaluation remain
  future work, tracked as TODOs in the source (a general boolean CSG
  kernel and arbitrary-profile revolve/sweep both need real geometry
  algorithms — polygon/polyhedron clipping, cone/freeform tessellation —
  that are correctness-critical enough not to rush).

  Returns `[:ok [solid edges verts]]` or `[:error msg]`."
  [tree]
  (let [sketches (sketch-by-id (:entries tree))]
    (loop [entries (:entries tree)
           result nil]
      (if (empty? entries)
        (if result [:ok result] [:error "feature tree produced no solid"])
        (let [{:keys [feature suppressed]} (first entries)]
          (if suppressed
            (recur (rest entries) result)
            (case (:kind feature)
              :extrude
              (case (:operation feature)
                :new
                (let [sk (get sketches (:sketch-ref feature))
                      ring (when sk (sketch->ring sk))]
                  (cond
                    ring
                    (recur (rest entries)
                           (extrude-prism 1 ring (:plane sk)
                                          (:direction feature) (:distance feature)))

                    ;; A sketch was named but is not one closed loop of
                    ;; segments -> refuse rather than fall back to a
                    ;; unit square that silently discards the profile.
                    sk
                    [:error (str "extrude: sketch " (:sketch-ref feature)
                                 " is not a single closed loop of straight"
                                 " segments (arcs/splines/multi-loop profiles"
                                 " are not implemented)")]

                    ;; No sketch reference at all: the documented legacy
                    ;; unit-square prism, kept for callers that relied on it.
                    :else
                    (let [half 0.5
                          ext (k/v-scale (k/v-normalize (:direction feature)) (:distance feature))
                          vmin [(- half) (- half) 0.0]
                          vmax (k/v+ [half half 0.0] ext)]
                      (recur (rest entries) (k/make-box 1 vmin vmax)))))

                (:add :cut :intersect)
                (if (nil? result)
                  [:error "no base solid to apply boolean to"]
                  ;; Previously this returned `result` unchanged — a boolean
                  ;; feature was a silent no-op that looked like success.
                  ;; Booleans need mesh CSG and produce a mesh, not a BREP,
                  ;; so they cannot be served by this BREP-returning fn.
                  [:error (str "evaluate: boolean operation " (:operation feature)
                               " on feature " (:id feature)
                               " cannot produce a BREP solid — use"
                               " brep.feature/evaluate-mesh, which applies it"
                               " via brep.mesh-csg and returns a triangle mesh")]))

              :revolve
              (let [full-turn? (>= (:angle feature) (- (* 2.0 Math/PI) 1e-6))
                    sketch (get sketches (:sketch-ref feature))
                    profile (when sketch (revolve-profile-cylinder sketch))]
                (cond
                  (not full-turn?)
                  [:error "revolve: only a full 2π turn is implemented (partial-angle pie-slice revolve is not yet supported)"]
                  (nil? sketch)
                  [:error (str "revolve: sketch-ref " (:sketch-ref feature) " not found")]
                  (nil? profile)
                  [:error "revolve: only a single axis-parallel sketch-line profile is implemented (an angled line -> cone/frustum, or any other profile shape, is not yet supported)"]
                  :else
                  (let [axis (k/v-normalize (:axis feature))
                        base (k/v+ (sketch-plane-origin (:plane sketch))
                                   (k/v-scale axis (:axial-min profile)))
                        height (- (:axial-max profile) (:axial-min profile))]
                    (recur (rest entries) (k/make-cylinder 1 base axis (:radius profile) height)))))

              :sketch (recur (rest entries) result)

              (recur (rest entries) result))))))))


;; ---------------------------------------------------------------------------
;; Boolean evaluation (2026-07-27).
;;
;; `evaluate` returns a BREP `[solid edges verts]`. A boolean of two BREPs is
;; not a BREP this kernel can build — there is no BREP-level clipper here —
;; but `brep.mesh-csg/mesh-boolean` does real CSG on triangle meshes. So
;; booleans get their own entry point with an honest return type: a mesh.
;;
;; Consequence to keep in view: a mesh cannot be written by
;; `brep.step/write-step` (which needs :plane faces and :line edges). A tree
;; containing cuts therefore yields a mesh for inspection/volume/rendering,
;; and the STEP path is only available for the pure-extrude subset. That is a
;; real limit of this kernel, stated rather than papered over.
;; ---------------------------------------------------------------------------

(defn- solid->mesh [[solid edges verts]]
  (let [[positions indices] (tess/tessellate-solid solid edges verts)]
    {:positions positions :indices indices}))

(defn- combine
  "Fold one feature's own geometry into the accumulated mesh, per its
  `:operation`. `:new` (or nil) replaces; the boolean operations need an
  accumulator to act on."
  [acc mesh operation]
  (if (nil? acc)
    (if (contains? #{:add :cut :intersect} operation)
      [:error "no base geometry to apply boolean to"]
      [:ok mesh])
    [:ok (csg/mesh-boolean (case operation :add :union :cut :difference
                                 :intersect :intersection :union)
                           acc mesh)]))

(defn- translate-mesh [mesh [dx dy dz]]
  (update mesh :positions (fn [ps] (mapv (fn [[x y z]] [(+ x dx) (+ y dy) (+ z dz)]) ps))))

;; ---------------------------------------------------------------------------
;; The feature registry.
;;
;; `apply-feature` is `state + feature -> state`: it takes the accumulated mesh
;; (nil before the first solid) and returns the next one. **Registering a method
;; here IS the claim that this kernel evaluates that feature kind.** There is no
;; second list of "supported kinds" to drift out of step with the constructors
;; above — the constructors describe a feature tree, this multimethod describes
;; what can be built from one, and `supported-feature-kinds` derives the answer
;; from the registry rather than restating it.
;;
;; The `:default` method refuses and names what IS registered, the same shape
;; `cae.solver/solve` uses in kotoba-lang/kami-engine-cae-solver. A caller that
;; asks for an unimplemented feature gets a structured error naming the gap, not
;; silence and not a plausible-looking wrong shape.
;; ---------------------------------------------------------------------------

(defmulti apply-feature
  "Fold `feature` into the accumulated mesh `acc`. `ctx` carries `:sketches`
  (id -> sketch feature) and `:entries` (the tree's entries, for features that
  refer to earlier ones). Returns `[:ok mesh]` or `[:error msg]`."
  (fn [feature _ctx _acc] (:kind feature)))

(defn supported-feature-kinds
  "The feature kinds this kernel can actually evaluate — read off the registry,
  never maintained by hand."
  []
  (disj (set (keys (methods apply-feature))) :default))

(defmethod apply-feature :default [feature _ctx _acc]
  [:error (str "brep.feature: no evaluator is registered for feature kind "
               (:kind feature) " (feature " (:id feature) "). Registered: "
               (pr-str (vec (sort (supported-feature-kinds)))) ".")])

;; A sketch carries no geometry of its own; it is the profile other features cite.
(defmethod apply-feature :sketch [_feature _ctx acc] [:ok acc])

(defmethod apply-feature :extrude [feature {:keys [sketches]} acc]
  (let [sk (get sketches (:sketch-ref feature))
        ring (when sk (sketch->ring sk))]
    (if-not ring
      [:error (str "extrude " (:id feature) " needs a sketch that is a single"
                   " closed loop of straight segments")]
      (combine acc
               (solid->mesh (extrude-prism 1 ring (:plane sk)
                                           (:direction feature) (:distance feature)))
               (:operation feature)))))

(defn- cap-mesh
  "Triangulate `ring2d` in its own 2D plane and place the result with `place`
  (a 2D point -> 3D point). `flip?` reverses the winding for the far cap.
  Triangulating in 2D via `brep.polygon` is what makes concave profiles work —
  a fan from vertex 0 would cut outside the profile."
  [ring2d place flip? offset]
  (let [{:keys [vertices indices]} (poly/triangulate-rings [ring2d])
        idx (mapv #(+ offset %) indices)]
    [(mapv place vertices)
     (if flip? (vec (mapcat (fn [[a b c]] [a c b]) (partition 3 idx))) (vec idx))]))

(defmethod apply-feature :sweep [feature {:keys [sketches]} acc]
  (let [profile (get sketches (:profile-ref feature))
        path-sk (get sketches (:path-ref feature))
        ring (when profile (sketch->ring profile))
        path2d (when path-sk (sketch->polyline path-sk))
        path (when path2d (mapv #(to-3d (:plane path-sk) %) path2d))
        [_ pe1 pe2 pn] (when profile (plane-basis (:plane profile)))
        tangents (when (and path (>= (count path) 2)) (path-tangents path))]
    (cond
      (nil? ring)
      [:error (str "sweep " (:id feature) " needs :profile-ref to name a sketch that"
                   " is a single closed loop of straight segments")]

      (nil? path2d)
      [:error (str "sweep " (:id feature) " needs :path-ref to name a sketch that is a"
                   " single OPEN chain of straight segments (a closed path, a branch, or"
                   " leftover segments are all refused — which chain is the path would"
                   " otherwise be a guess)")]

      ;; The profile is placed with its OWN plane basis, so what is swept is what
      ;; was drawn. That only makes sense if the profile faces along the path at
      ;; the start; otherwise the first section is oblique and every downstream
      ;; frame inherits the error. Refuse instead of quietly reinterpreting the
      ;; profile in a frame it was not drawn in.
      (< (Math/abs (k/v-dot pn (first tangents))) (- 1.0 1.0e-6))
      [:error (str "sweep " (:id feature) " needs the profile plane to be perpendicular"
                   " to the start of the path: profile normal " (pr-str (mapv double pn))
                   " vs initial tangent " (pr-str (mapv double (first tangents))))]

      :else
      (let [t0 (first tangents)
            ;; face the profile basis down the path
            [e1 e2] (if (neg? (k/v-dot pn t0)) [pe2 pe1] [pe1 pe2])
            frames (reductions (fn [[f prev-t] t]
                                 (when f [(transport-frame prev-t t f) t]))
                               [[e1 e2] t0]
                               (rest tangents))]
        (if (some (fn [fr] (or (nil? fr) (nil? (first fr)))) frames)
          [:error (str "sweep " (:id feature) " has a 180° reversal in its path;"
                       " the minimal rotation carrying the section across it is not"
                       " unique, so no section is chosen")]
          (let [place (fn [origin [u v] [f1 f2]]
                        (k/v+ origin (k/v+ (k/v-scale f1 (double u)) (k/v-scale f2 (double v)))))
                stations (mapv (fn [p [f _]] [p f]) path frames)
                n (count ring)
                positions (vec (mapcat (fn [[p f]] (mapv #(place p % f) ring)) stations))
                sides (vec (mapcat
                            (fn [si]
                              (mapcat (fn [j]
                                        (let [j2 (mod (inc j) n)
                                              a (+ (* si n) j) b (+ (* si n) j2)
                                              c (+ (* (inc si) n) j2) d (+ (* (inc si) n) j)]
                                          [a b c a c d]))
                                      (range n)))
                            (range (dec (count stations)))))
                [p0 f0] (first stations)
                [pl fl] (last stations)
                [start-pts start-idx] (cap-mesh ring #(place p0 % f0) true (count positions))
                positions (into positions start-pts)
                [end-pts end-idx] (cap-mesh ring #(place pl % fl) false (count positions))
                positions (into positions end-pts)]
            (combine acc
                     {:positions positions
                      :indices (vec (concat sides start-idx end-idx))}
                     (:operation feature))))))))

(defmethod apply-feature :pattern [feature {:keys [entries]} acc]
  (let [{:keys [source-features direction count spacing]} feature
        solid-ids (->> entries (map :feature) (remove #(= :sketch (:kind %)))
                       (remove #(= :pattern (:kind %))) (map :id) set)
        covered (set source-features)
        n (long (or count 0))
        step (double (or spacing 0))
        [dx dy dz] (or direction [0 0 0])
        len (Math/sqrt (+ (* dx dx) (* dy dy) (* dz dz)))]
    (cond
      (nil? acc)
      [:error (str "pattern " (:id feature) " has no geometry to repeat")]

      (< n 2)
      [:error (str "pattern " (:id feature) " needs :count >= 2 (got " count ")")]

      (or (zero? len) (not (pos? step)))
      [:error (str "pattern " (:id feature) " needs a non-zero :direction and a"
                   " positive :spacing (got " (pr-str direction) ", " spacing ")")]

      ;; Selective patterning would require evaluating a SUBSET of the tree in
      ;; isolation. This evaluator folds features into one accumulator, so it can
      ;; only repeat everything built so far. Refuse rather than silently
      ;; patterning more than was asked for.
      (not= covered solid-ids)
      [:error (str "pattern " (:id feature) " names :source-features "
                   (pr-str (vec (sort covered))) " but this evaluator can only"
                   " repeat the whole accumulated body, which is built from "
                   (pr-str (vec (sort solid-ids)))
                   ". Selective patterning is not implemented.")]

      :else
      (let [unit [(/ dx len) (/ dy len) (/ dz len)]]
        [:ok (reduce (fn [m i]
                       (csg/mesh-boolean
                        :union m
                        (translate-mesh acc (mapv #(* % step i) unit))))
                     acc
                     (range 1 n))]))))

(defmethod apply-feature :loft [feature {:keys [sketches]} acc]
  (let [refs (:profiles feature)
        sks (mapv #(get sketches %) refs)
        rings (mapv #(when % (sketch->ring %)) sks)
        counts (mapv #(when % (count %)) rings)]
    (cond
      (< (count refs) 2)
      [:error (str "loft " (:id feature) " needs at least 2 profiles (got "
                   (count refs) ")")]

      (some nil? rings)
      [:error (str "loft " (:id feature) " needs every profile to be a sketch that"
                   " is a single closed loop of straight segments; missing or"
                   " unusable: "
                   (pr-str (vec (keep (fn [[r id]] (when (nil? r) id))
                                      (map vector rings refs)))))]

      ;; Lofting between rings of different vertex counts needs a correspondence
      ;; rule (resample, or match by arc length). That is a real algorithm with
      ;; visible consequences for the surface, so refuse rather than invent one.
      (not (apply = counts))
      [:error (str "loft " (:id feature) " needs all profiles to have the same"
                   " vertex count (got " (pr-str counts) "); automatic"
                   " resampling is not implemented")]

      :else
      (let [n (first counts)
            lifted (mapv (fn [sk ring] (mapv #(to-3d (:plane sk) %) ring)) sks rings)
            positions (vec (apply concat lifted))
            base (fn [pi] (* pi n))
            ;; side walls: one quad per edge per adjacent profile pair
            sides (vec (mapcat
                        (fn [pi]
                          (mapcat (fn [j]
                                    (let [j2 (mod (inc j) n)
                                          a (+ (base pi) j) b (+ (base pi) j2)
                                          c (+ (base (inc pi)) j2) d (+ (base (inc pi)) j)]
                                      [a b c a c d]))
                                  (range n)))
                        (range (dec (count lifted)))))
            ;; caps: triangulated in the sketch plane so concave profiles work
            cap (fn [pi reverse?]
                  (let [sk (nth sks pi) ring (nth rings pi)
                        {:keys [vertices indices]} (poly/triangulate-rings [ring])
                        offset (count positions)
                        pts (mapv #(to-3d (:plane sk) %) vertices)
                        idx (mapv #(+ offset %) indices)]
                    [pts (if reverse?
                           (vec (mapcat (fn [[a b c]] [a c b]) (partition 3 idx)))
                           (vec idx))]))
            [first-pts first-idx] (cap 0 true)
            positions (into positions first-pts)
            [last-pts last-idx] (let [sk (nth sks (dec (count sks)))
                                      ring (nth rings (dec (count rings)))
                                      {:keys [vertices indices]} (poly/triangulate-rings [ring])
                                      offset (count positions)]
                                  [(mapv #(to-3d (:plane sk) %) vertices)
                                   (mapv #(+ offset %) indices)])
            positions (into positions last-pts)
            mesh {:positions positions
                  :indices (vec (concat sides first-idx last-idx))}]
        (combine acc mesh (:operation feature))))))

(defn- face-normal-of [{:keys [vertices faces]} fi]
  (let [[a b c] (nth faces fi)]
    (k/v-normalize (k/v-cross (k/v- (nth vertices b) (nth vertices a))
                              (k/v- (nth vertices c) (nth vertices a))))))

(defmethod apply-feature :chamfer [feature _ctx acc]
  ;; A chamfer on a solid with planar faces IS a plane cut — no blend surface is
  ;; involved. That is exactly why chamfer is reachable here and fillet is not:
  ;; a fillet needs a rolling-ball surface this kernel has no representation for.
  ;; Each selected edge contributes one half-space, subtracted through
  ;; `brep.mesh-csg`, which returns closed solids as of 2026-08-21.
  (let [{:keys [edges distance]} feature
        d (double (or distance 0))]
    (cond
      (nil? acc)
      [:error (str "chamfer " (:id feature) " has no body to cut")]

      (not (pos? d))
      [:error (str "chamfer " (:id feature) " needs a positive :distance (got "
                   distance ")")]

      ;; The constructor names edges with BREP ids. A mesh accumulator has no
      ;; such ids, and inventing a mapping would chamfer edges nobody selected.
      ;; Two selectors are understood, both expressed in terms of the mesh that
      ;; is actually being cut.
      (not (or (= :all-convex edges)
               (and (coll? edges) (seq edges)
                    (every? #(and (vector? %) (= 2 (count %))) edges))))
      [:error (str "chamfer " (:id feature) " :edges must be :all-convex or a"
                   " collection of [i j] mesh edge keys from"
                   " brep.topology/sharp-edges — BREP edge ids do not exist on"
                   " the mesh this evaluates, and guessing a mapping would"
                   " chamfer edges that were not selected (got "
                   (pr-str edges) ")")]

      :else
      (let [topo0 (topo/topology acc)
            selected (if (= :all-convex edges)
                       (topo/sharp-edges topo0 :convex 0.2)
                       (vec edges))
            [lo hi] (topo/mesh-bounds acc)
            extent (* 4.0 (apply max 1.0 (map - hi lo)))
            ;; Cut planes are computed ONCE, from the original body. Each cut
            ;; renumbers vertices, so an edge key read from the result of the
            ;; previous cut would refer to something else.
            planes (keep (fn [[i j :as e]]
                           (when-let [info (get (:edges topo0) e)]
                             (when (= :manifold (:kind info))
                               (let [[f1 f2] (:faces info)
                                     n1 (face-normal-of topo0 f1)
                                     n2 (face-normal-of topo0 f2)
                                     pi (nth (:vertices topo0) i)
                                     pj (nth (:vertices topo0) j)
                                     along (k/v-normalize (k/v- pj pi))
                                     ;; in each face, perpendicular to the edge,
                                     ;; pointing away from the other face
                                     step (fn [n other]
                                            (let [c (k/v-normalize (k/v-cross n along))]
                                              (if (pos? (k/v-dot c other))
                                                (k/v-scale c -1.0) c)))
                                     p1 (k/v+ pi (k/v-scale (step n1 n2) d))
                                     p2 (k/v+ pi (k/v-scale (step n2 n1) d))]
                                 [(k/v-scale (k/v+ p1 p2) 0.5)
                                  (k/v-normalize (k/v+ n1 n2))]))))
                         selected)]
        (cond
          (empty? selected)
          [:error (str "chamfer " (:id feature) " selected no edges")]

          (empty? planes)
          [:error (str "chamfer " (:id feature) " selected " (count selected)
                       " edge(s), none of which is a manifold edge of this body")]

          :else
          ;; The result IS the accumulator — a chamfer modifies the body in
          ;; place. Routing it through `combine` with `:new` would fall to that
          ;; function's default of :union and quietly put the removed material
          ;; back: measured, the volume came out unchanged at 600 and every
          ;; dihedral was still 90 degrees while the triangle count had grown
          ;; from 12 to 52. A cut that adds triangles and changes nothing is
          ;; the most convincing kind of wrong.
          [:ok (reduce (fn [m [origin normal]]
                         (csg/mesh-boolean :difference m
                                           (topo/half-space-box origin normal extent)))
                       acc planes)])))))

(defn- prism-mesh
  "A closed triangle mesh for the solid swept by `section` (a closed 2D loop in
  the plane spanned by `u` and `v`, about `origin`) along `axis` for `length`."
  [origin u v axis length section]
  (let [n (count section)
        place (fn [[a b] t]
                (k/v+ origin (k/v+ (k/v-scale u a)
                                   (k/v+ (k/v-scale v b) (k/v-scale axis t)))))
        near (mapv #(place % 0.0) section)
        far (mapv #(place % length) section)
        positions (into near far)
        sides (vec (mapcat (fn [i]
                             (let [j (mod (inc i) n)]
                               [i j (+ n j) i (+ n j) (+ n i)]))
                           (range n)))
        {:keys [indices]} (poly/triangulate-rings [(vec section)])
        cap-near (vec (mapcat (fn [[a b c]] [a c b]) (partition 3 indices)))
        cap-far (mapv #(+ n %) indices)]
    {:positions positions :indices (vec (concat sides cap-near cap-far))}))

(defn- fillet-tool
  "The material a constant-radius fillet removes from ONE convex edge: the
  sharp corner minus the rolling ball's cylinder.

  A fillet is not a plane cut, which is why `:chamfer` could be a half-space
  subtraction and this cannot. What it removes has a closed form all the same —
  the cross-section is an r-by-r square with a quarter disc taken out of it, so
  the volume is `L r^2 (1 - pi/4)` — and that is what the tests assert.

  `segments` controls how finely the arc is tessellated. The arc is INSCRIBED,
  so the tool is slightly too small and the volume removed slightly under the
  closed form; the error is second order in the segment angle and the tests
  bound it rather than pretending it is zero."
  [topo edge-key radius segments overshoot]
  (let [{:keys [vertices]} topo
        info (get (:edges topo) edge-key)
        [i j] edge-key
        [f1 f2] (:faces info)
        n1 (face-normal-of topo f1)
        n2 (face-normal-of topo f2)
        pi* (nth vertices i)
        pj (nth vertices j)
        along (k/v-normalize (k/v- pj pi*))
        ;; in-plane directions pointing INTO each face, away from the other
        step (fn [n other]
               (let [c (k/v-normalize (k/v-cross n along))]
                 (if (pos? (k/v-dot c other)) (k/v-scale c -1.0) c)))
        u (step n1 n2)          ; along face 1, away from face 2
        v (step n2 n1)          ; along face 2, away from face 1
        ;; The section is drawn in the (u, v) frame with the sharp corner at
        ;; the origin: out to r along u, arc back to r along v.
        arc (mapv (fn [s]
                    (let [t (* (/ s (double segments)) (/ Math/PI 2.0))]
                      [(- radius (* radius (Math/sin t)))
                       (- radius (* radius (Math/cos t)))]))
                  (range (inc segments)))
        ;; The tool's two flat sides are pushed OUTSIDE the body by `d` instead
        ;; of lying on its faces.
        ;;
        ;; A section that stopped at the faces made the tool's sides exactly
        ;; coplanar with two faces of the body, and coplanar faces are the
        ;; degenerate case a BSP boolean handles by choosing a side — which
        ;; side depending on the order polygons arrive in. That is why the
        ;; failures were sporadic in the segment count and different on each
        ;; host: `brep.topology` seeds its region walk with `(first some-set)`,
        ;; the JVM and ClojureScript iterate a set in different orders, and the
        ;; order decided which coplanar case the tree met. Moving the sides off
        ;; the faces removes the degeneracy rather than the disagreement about
        ;; it, so the only intersection left is the arc, which crosses the
        ;; faces transversally. The extra material is outside the body and the
        ;; difference clips it, so the volume removed is unchanged.
        d (* 0.05 radius)
        section (vec (concat [[(- d) (- d)] [radius (- d)] [radius 0.0]]
                             (rest (butlast arc))
                             [[0.0 radius] [(- d) radius]]))
        origin (k/v+ pi* (k/v-scale along (- overshoot)))]
    (prism-mesh origin u v along (+ (k/v-length (k/v- pj pi*)) (* 2.0 overshoot))
                section)))

(defn- region-planes
  "One `[point outward-normal]` per coplanar face region of `topo`.

  The regions come from `brep.topology/coplanar-regions`, so a box arrives as
  six planes rather than the twelve its triangles would give — offsetting a
  plane twice is harmless for the intersection below, but the error messages
  would count faces that a reader of the model does not believe exist."
  [topo]
  (mapv (fn [region]
          (let [fi (first region)]
            [(nth (:vertices topo) (first (nth (:faces topo) fi)))
             (face-normal-of topo fi)]))
        (topo/coplanar-regions topo)))

(defn- convex-body?
  "Every vertex on the inner side of every face plane, within `tol`."
  [topo planes tol]
  (every? (fn [[p n]]
            (every? #(<= (k/v-dot n (k/v- % p)) tol) (:vertices topo)))
          planes))

(defmethod apply-feature :shell [feature _ctx acc]
  ;; Hollowing a solid is an inward OFFSET followed by a difference. This kernel
  ;; has no offset surface, so the inner body is built the only way planar faces
  ;; allow: intersect each face's own plane pushed inward by the wall thickness.
  ;;
  ;; That construction is the true inward offset for a CONVEX body and is WRONG
  ;; for a concave one — at a reflex edge the two offset planes cross on the far
  ;; side of the material and eat wall that should have stayed. The wrong answer
  ;; is a perfectly closed solid of plausible size, so it would pass a closure
  ;; check and a triangle count; only a volume against a known one catches it.
  ;; Rather than return it, `:shell` refuses on a concave body and says which
  ;; part of itself is missing.
  (let [{:keys [thickness removed-faces]} feature
        t (double (or thickness 0))]
    (cond
      (nil? acc)
      [:error (str "shell " (:id feature) " has no body to hollow")]

      (not (pos? t))
      [:error (str "shell " (:id feature) " needs a positive :thickness (got "
                   thickness ")")]

      (not (or (nil? removed-faces) (= [] removed-faces)
               (and (coll? removed-faces) (seq removed-faces)
                    (every? #(and (vector? %) (= 3 (count %))
                                  (every? number? %)) removed-faces))))
      [:error (str "shell " (:id feature) " :removed-faces must be a collection of"
                   " outward directions like [0 0 1] — face ids do not exist on"
                   " the mesh this evaluates, and guessing a mapping would open"
                   " a face nobody selected (got " (pr-str removed-faces) ")")]

      :else
      (let [body (topo/welded-oriented acc)
            topo (topo/topology body)
            planes (region-planes topo)
            [lo hi] (topo/mesh-bounds body)
            span (apply max 1.0 (map - hi lo))
            extent (* 4.0 span)
            matches (fn [dir]
                      (let [d (k/v-normalize dir)]
                        (filter (fn [[_ n]] (> (k/v-dot n d) 0.999)) planes)))
            unmatched (remove #(seq (matches %)) (or removed-faces []))
            open-set (set (mapcat matches (or removed-faces [])))
            kept (remove open-set planes)]
        (cond
          (not (convex-body? topo planes 1.0e-6))
          [:error (str "shell " (:id feature) " has a concave body (" (count planes)
                       " face planes). This kernel offsets inward by intersecting"
                       " a body's own face planes, which is the true offset only"
                       " for a convex body — at a reflex edge two offset planes"
                       " cross outside the material and remove wall that should"
                       " remain, and the result is a closed solid of plausible"
                       " size that no closure check would reject. A concave"
                       " shell needs an offset-surface representation this"
                       " kernel does not have.")]

          (seq unmatched)
          [:error (str "shell " (:id feature) " :removed-faces named "
                       (pr-str (vec unmatched)) ", which matches no face of this"
                       " body (its outward normals are "
                       (pr-str (mapv (fn [[_ n]] (mapv #(/ (Math/round (* 1000.0 %)) 1000.0) n))
                                     planes)) ")")]

          (empty? kept)
          [:error (str "shell " (:id feature) " opens every face — there is no"
                       " wall left to keep")]

          :else
          (let [cavity (reduce (fn [m [p n]]
                                 (let [inner (topo/half-space-box
                                              (k/v+ p (k/v-scale n (- t)))
                                              (k/v-scale n -1.0) extent)]
                                   (if (nil? m) inner
                                       (csg/mesh-boolean :intersection m inner))))
                               nil kept)]
            ;; The cavity has to BE the inward offset, and the check is the
            ;; definition: every cavity vertex at least `t` inside every wall
            ;; that was kept. When the offset planes cross — a thickness too
            ;; large for the body — the intersection does not come back empty,
            ;; it comes back as an extent-sized sliver, and subtracting that
            ;; leaves a solid of very nearly the original volume that reports
            ;; success. Measured on a 10-cube with thickness 9: volume 990 of
            ;; 1000, closed, Euler 2 — a "shell" indistinguishable from the
            ;; block it started as. The same measurement puts the worst cavity
            ;; vertex 49 outside a wall, which is what this rejects. A genuinely
            ;; thin cavity is not caught by it: thickness 4.9 on that cube
            ;; leaves a 0.2 cube and the worst intrusion is 1.8e-15.
            (let [intrusion (when (seq (:positions cavity))
                              (apply max (for [v (:positions cavity) [p n] kept]
                                           (+ t (k/v-dot n (k/v- v p))))))
                  tol (* 1.0e-9 (max 1.0 span))]
              (if (or (nil? intrusion) (> intrusion tol))
                [:error (str "shell " (:id feature) " with thickness " t
                             " does not fit a body spanning " span
                             (if intrusion
                               (str " — the offset walls cross, putting the cavity "
                                    (/ (Math/round (* 1000.0 intrusion)) 1000.0)
                                    " outside a wall it should stay inside")
                               " — the offset planes enclose nothing"))]
                [:ok (csg/mesh-boolean :difference body cavity)]))))))))

(defmethod apply-feature :fillet [feature _ctx acc]
  ;; The kernel has no rolling-ball SURFACE, and this does not invent one: the
  ;; blend is TESSELLATED, which is exactly what `:chamfer` and every other
  ;; feature here produce, since `evaluate-mesh` returns a triangle mesh and
  ;; says so. What a fillet cannot be is a plane cut — that is the whole
  ;; difference from chamfer, and it is why the tool is a swept section rather
  ;; than a half-space.
  ;;
  ;; The tool is the sharp corner minus the cylinder the ball sweeps. Its
  ;; cross-section is an r-by-r square with a quarter disc removed, so the
  ;; volume it takes off one edge of length L is exactly L r^2 (1 - pi/4).
  (let [{:keys [edges radius segments]} feature
        r (double (or radius 0))
        segs (int (or segments 16))]
    (cond
      (nil? acc)
      [:error (str "fillet " (:id feature) " has no body to round")]

      (not (pos? r))
      [:error (str "fillet " (:id feature) " needs a positive :radius (got " radius ")")]

      (< segs 2)
      [:error (str "fillet " (:id feature) " needs :segments >= 2 (got " segments
                   ") — one segment is a chamfer, and a chamfer that calls"
                   " itself a fillet is the kind of thing nobody notices"
                   " until the part is machined")]

      (not (or (= :all-convex edges)
               (and (coll? edges) (seq edges)
                    (every? #(and (vector? %) (= 2 (count %))) edges))))
      [:error (str "fillet " (:id feature) " :edges must be :all-convex or a"
                   " collection of [i j] mesh edge keys from"
                   " brep.topology/sharp-edges — BREP edge ids do not exist on"
                   " the mesh this evaluates, and guessing a mapping would"
                   " round edges that were not selected (got " (pr-str edges) ")")]

      :else
      (let [body (topo/welded-oriented acc)
            topo0 (topo/topology body)
            selected (if (= :all-convex edges)
                       (topo/sharp-edges topo0 :convex 0.2)
                       (vec edges))
            [lo hi] (topo/mesh-bounds body)
            overshoot (* 0.01 (apply max 1.0 (map - hi lo)))
            manifold (filter (fn [e] (= :manifold (:kind (get (:edges topo0) e)))) selected)
            ;; A radius larger than the shortest adjacent face can hold does
            ;; not fail — it produces a tool that cuts through the far side of
            ;; the body and returns a closed solid of the wrong shape.
            too-big (filter (fn [[i j]]
                              (> (* 2.0 r) (k/v-distance (nth (:vertices topo0) i)
                                                         (nth (:vertices topo0) j))))
                            manifold)]
        (cond
          (empty? selected)
          [:error (str "fillet " (:id feature) " selected no edges")]

          (empty? manifold)
          [:error (str "fillet " (:id feature) " selected " (count selected)
                       " edge(s), none of which is a manifold edge of this body")]

          (seq too-big)
          [:error (str "fillet " (:id feature) " radius " r " is at least half the"
                       " length of " (count too-big) " selected edge(s) — the tool"
                       " would cut past the far end and return a closed solid of"
                       " the wrong shape, which no closure check would reject")]

          :else
          ;; Tools are computed ONCE from the original body: each subtraction
          ;; renumbers vertices, so an edge key read from the previous result
          ;; would refer to something else.
          ;;
          ;; The boolean is RETRIED over the tool's overshoot, and the reason
          ;; that is sound rather than answer-shopping is that the overshoot
          ;; is the one parameter of the tool that cannot change the result:
          ;; it extends the tool along the edge, entirely OUTSIDE the body, so
          ;; the difference clips every bit of it. Measured on a 10x10x6 block
          ;; filleted at r=1 with 12 segments, every overshoot that produced a
          ;; closed solid produced the same removed volume to nine decimal
          ;; places — 2.168428467 at 0.02, 0.05, 0.06 and 0.37 — while 0.1,
          ;; 0.13 and 0.2 came back with 6 boundary edges. The failures are a
          ;; degeneracy in `brep.mesh-csg`, not a disagreement about the shape,
          ;; and perturbing a parameter the shape does not depend on is the
          ;; cheapest way past one until the boolean itself is fixed.
          ;;
          ;; Four attempts at fixing `brep.mesh-csg` directly are recorded so
          ;; they are not retried. Widening its epsilon over 1e-7, 1e-6 and
          ;; 1e-5 changed nothing on either host. Clamping the split parameter
          ;; to [0,1] and keeping sub-triangle fragments instead of dropping
          ;; them changed nothing — both were written, measured, found not to
          ;; be load-bearing, and REVERTED rather than left in a fragile
          ;; component as unverified behaviour. Seeding `brep.topology`'s
          ;; region walk deterministically made the two hosts agree and agree
          ;; on failing everywhere, breaking ten assertions.
          ;;
          ;; What did work is here and in the tool: keeping the tool off the
          ;; body's face planes, and retrying the overshoot. Together they take
          ;; a single edge from failing at 2 of 9 segment counts on the JVM and
          ;; 4 of 9 under nbb — different ones — to 9 of 9 on both.
          (let [span (apply max 1.0 (map - hi lo))
                attempts (mapv #(* % span) [0.011 0.002 0.005 0.023 0.037 0.047 0.091 0.29])
                try-one (fn [ov]
                          (let [tools (mapv #(fillet-tool topo0 % r segs ov) manifold)]
                            (try
                              (let [m (reduce (fn [m tool]
                                                (csg/mesh-boolean :difference m tool))
                                              body tools)]
                                (when (empty? (topo/boundary-edges (topo/topology m))) m))
                              (catch #?(:clj Throwable :cljs :default) _ nil))))
                result (some try-one attempts)]
            (if result
              [:ok result]
              [:error (str "fillet " (:id feature) " could not be cut: the boolean in"
                           " brep.mesh-csg returned an open surface or exhausted"
                           " itself for all " (count attempts) " tool overshoots tried,"
                           " on " (count manifold) " edge(s) at " segs " segments."
                           " An open result is a surface whose volume is wrong, so it"
                           " is not returned. A different :segments usually gets"
                           " through — the failure is a degeneracy in the boolean,"
                           " sporadic in that number rather than monotone.")])))))))

(defn evaluate-mesh
  "Evaluate a feature tree to a **triangle mesh** by folding each feature
  through `apply-feature`.

  Which kinds are evaluable is answered by `supported-feature-kinds`, which
  reads the registry — an unregistered kind returns a structured `[:error …]`
  naming itself and the registered set, so a feature tree can never report
  success for a shape that was not built.

  Returns `[:ok {:positions :indices}]` or `[:error msg]`.

  Not STEP-exportable — see the note above."
  [tree]
  (let [ctx {:sketches (sketch-by-id (:entries tree))
             :entries (remove :suppressed (:entries tree))}]
    (loop [entries (:entries tree) acc nil]
      (if (empty? entries)
        (if acc [:ok acc] [:error "feature tree produced no geometry"])
        (let [{:keys [feature suppressed]} (first entries)]
          (if suppressed
            (recur (rest entries) acc)
            (let [[st v] (apply-feature feature ctx acc)]
              (if (= :error st)
                [:error v]
                (recur (rest entries) v)))))))))
