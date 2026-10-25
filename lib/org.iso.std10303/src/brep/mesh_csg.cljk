(ns brep.mesh-csg
  "Portable BSP-based boolean operations for closed triangle meshes."
  (:require [brep.topology :as topo]
            [brep.polygon :as poly]))

(def ^:private epsilon 1.0e-7)
(def ^:private coplanar 0)
(def ^:private front 1)
(def ^:private back 2)
(def ^:private spanning 3)

(defn- v+ [a b] (mapv + a b))
(defn- v- [a b] (mapv - a b))
(defn- scale [v s] (mapv #(* s %) v))
(defn- dot [a b] (reduce + (map * a b)))
(defn- cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- normalize [v]
  (let [length (#?(:clj Math/sqrt :cljs js/Math.sqrt) (dot v v))]
    (if (pos? length) (scale v (/ 1.0 length)) [0.0 0.0 0.0])))

(defn- plane-from-vertices [vertices]
  (let [[a b c] (map :position (take 3 vertices))
        normal (normalize (cross (v- b a) (v- c a)))]
    {:normal normal :w (dot normal a)}))

(defn- polygon [vertices]
  {:vertices (vec vertices) :plane (plane-from-vertices vertices)})

(defn- flipped-polygon [poly]
  (let [vertices (mapv #(update % :normal (fn [normal] (mapv - normal)))
                       (reverse (:vertices poly)))
        plane (:plane poly)]
    {:vertices vertices :plane {:normal (mapv - (:normal plane)) :w (- (:w plane))}}))

(defn- interpolate-vertex [a b t]
  {:position (v+ (:position a) (scale (v- (:position b) (:position a)) t))
   :normal (normalize (v+ (:normal a) (scale (v- (:normal b) (:normal a)) t)))})

(defn- split-polygon [plane poly]
  (let [types (mapv (fn [vertex]
                      (let [distance (- (dot (:normal plane) (:position vertex)) (:w plane))]
                        (cond (< distance (- epsilon)) back
                              (> distance epsilon) front
                              :else coplanar)))
                    (:vertices poly))
        polygon-type (reduce bit-or coplanar types)]
    (case polygon-type
      0 (if (pos? (dot (:normal plane) (get-in poly [:plane :normal])))
          {:coplanar-front [poly]} {:coplanar-back [poly]})
      1 {:front [poly]}
      2 {:back [poly]}
      3 (let [vertices (:vertices poly) count-vertices (count vertices)
              [front-vertices back-vertices]
              (reduce (fn [[front-result back-result] i]
                        (let [j (mod (inc i) count-vertices)
                              ti (nth types i) tj (nth types j)
                              vi (nth vertices i) vj (nth vertices j)
                              front-result (cond-> front-result (not= ti back) (conj vi))
                              back-result (cond-> back-result (not= ti front) (conj vi))]
                          (if (= spanning (bit-or ti tj))
                            (let [direction (v- (:position vj) (:position vi))
                                  t (/ (- (:w plane) (dot (:normal plane) (:position vi)))
                                       (dot (:normal plane) direction))
                                  vertex (interpolate-vertex vi vj t)]
                              [(conj front-result vertex) (conj back-result vertex)])
                            [front-result back-result])))
                      [[] []] (range count-vertices))]
          (cond-> {}
            (>= (count front-vertices) 3) (assoc :front [(polygon front-vertices)])
            (>= (count back-vertices) 3) (assoc :back [(polygon back-vertices)]))))))

(defn- partition-polygons [plane polygons]
  (reduce (fn [result poly]
            (merge-with into result (split-polygon plane poly)))
          {:coplanar-front [] :coplanar-back [] :front [] :back []} polygons))

(declare build-node clip-to)

(defn- build-node
  ([polygons] (build-node nil polygons))
  ([node polygons]
   (if (empty? polygons)
     node
     (let [plane (or (:plane node) (:plane (first polygons)))
           parts (partition-polygons plane polygons)]
       {:plane plane
        :polygons (vec (concat (:polygons node) (:coplanar-front parts)
                               (:coplanar-back parts)))
        :front (build-node (:front node) (:front parts))
        :back (build-node (:back node) (:back parts))}))))

(defn- clip-polygons [node polygons]
  (if-not (:plane node)
    polygons
    (let [parts (partition-polygons (:plane node) polygons)
          front-polygons (vec (concat (:coplanar-front parts) (:front parts)))
          back-polygons (vec (concat (:coplanar-back parts) (:back parts)))
          front-polygons (if (:front node) (clip-polygons (:front node) front-polygons)
                             front-polygons)
          back-polygons (if (:back node) (clip-polygons (:back node) back-polygons) [])]
      (vec (concat front-polygons back-polygons)))))

(defn- clip-to [node other]
  (when node
    (assoc node
           :polygons (clip-polygons other (:polygons node))
           :front (clip-to (:front node) other)
           :back (clip-to (:back node) other))))

(defn- invert-node [node]
  (when node
    (let [plane (:plane node)]
      {:plane {:normal (mapv - (:normal plane)) :w (- (:w plane))}
       :polygons (mapv flipped-polygon (:polygons node))
       :front (invert-node (:back node))
       :back (invert-node (:front node))})))

(defn- all-polygons [node]
  (if node
    (vec (concat (:polygons node) (all-polygons (:front node)) (all-polygons (:back node))))
    []))

(defn- merged->polygons
  "Build BSP polygons from coplanar-merged planar loops. Each loop becomes ONE
  polygon, which is the shape csg.js was written for — see `mesh-boolean`."
  [loops]
  (mapv (fn [pts]
          (let [n (normalize (cross (v- (nth pts 1) (nth pts 0))
                                    (v- (nth pts 2) (nth pts 0))))]
            (polygon (mapv (fn [p] {:position p :normal n}) pts))))
        loops))

(defn- mesh->polygons [{:keys [positions indices normals]}]
  (mapv (fn [[a b c]]
          (let [face-normal (normalize (cross (v- (nth positions b) (nth positions a))
                                              (v- (nth positions c) (nth positions a))))]
            (polygon (mapv (fn [index]
                             {:position (nth positions index)
                              :normal (if (seq normals) (nth normals index) face-normal)})
                           [a b c]))))
        (partition 3 indices)))

(defn- basis-2d
  "An orthonormal in-plane basis for `normal`, used to project a polygon to 2D
  so it can be triangulated by an ear-clipper rather than a fan."
  [normal]
  (let [a (if (< (#?(:clj Math/abs :cljs js/Math.abs) (nth normal 0)) 0.9)
            [1.0 0.0 0.0] [0.0 1.0 0.0])
        e1 (normalize (cross normal a))]
    [e1 (cross normal e1)]))

(defn- polygons->mesh
  "Triangulate BSP output polygons.

  A fan from vertex 0 is only correct for a CONVEX polygon. The polygons a
  boolean produces are routinely concave — the top face of a box with a corner
  notched out is L-shaped — and a fan over one of those emits triangles that
  cover area outside the polygon and miss area inside it, which shows up
  downstream as boundary edges where the surface should be closed. Projecting
  onto the polygon's own plane and ear-clipping via `brep.polygon` handles both."
  [polygons]
  (let [tris (mapcat
              (fn [poly]
                (let [verts (:vertices poly)
                      n (get-in poly [:plane :normal])
                      [e1 e2] (basis-2d n)
                      origin (:position (first verts))
                      to-2d (fn [{:keys [position]}]
                              (let [d (v- position origin)]
                                [(dot d e1) (dot d e2)]))
                      {:keys [indices]} (poly/triangulate-rings [(mapv to-2d verts)])]
                  (map (fn [i] (nth verts i)) indices)))
              polygons)
        vertices (vec tris)]
    {:positions (mapv :position vertices)
     :normals (mapv :normal vertices)
     :indices (vec (range (count vertices)))}))

(defn mesh-boolean
  "Apply `:union`, `:difference`, or `:intersection` to two closed triangle
  meshes.

  **The inputs are welded and re-wound before use.** A BSP boolean classifies
  every polygon as front or back of a plane, and that classification is read off
  the polygon's own normal — so a mesh whose faces are not wound consistently
  feeds the tree normals that point in directions unrelated to the shape.
  `brep.tessellate/tessellate-solid` emits each face independently and does NOT
  guarantee consistent winding, so every caller coming from a feature tree was
  handing this function exactly that. Measured 2026-08-21: a union of two boxes
  standing 20 apart — nothing to intersect at all — came back with 4 boundary
  edges. Welding and orienting first makes that case, and a union of two boxes
  sharing a face, come back closed.

  The operands are also coplanar-MERGED before the tree is built. csg.js takes
  a cube as six quads; a tessellated solid arrives as twelve triangles, so every
  plane that should cut one polygon cuts two and the extra fragments fall below
  the three-vertex floor in `split-polygon`. `brep.topology/merge-coplanar` puts
  the faces back together first.

  The output is then **T-junction repaired**. A BSP splits one side of a cut at
  the intersection points and can leave the other side as a single span, which
  is a surface that is geometrically complete — total area exactly the analytic
  value — while every one of those long edges belongs to a single face and reads
  as a hole. Measured on a 10x10x4 block with a 4x4 through hole: area 392.000
  against an analytic 392, and 20 boundary edges. `brep.topology/repair-t-junctions`
  inserts the vertices that sit on those spans and re-triangulates.

  Measured 2026-08-21, after welding + orientation + coplanar merge + repair:

      union, disjoint               closed, euler 4 (two shells)
      union, touching               closed, euler 2
      union, overlapping            closed, euler 2   (was 20 boundary edges)
      difference, no overlap        closed, euler 2
      difference, through hole      closed, euler 0   (genus 1 — a block with a hole)
      difference, corner notch      closed, euler 2   (was 6)
      intersection, overlapping     closed, euler 2

  Three suspects were ruled out before the real one was found, recorded so they
  are not re-tried: the csg.js transcription (checked step by step against the
  original — union, subtract, intersect, clipPolygons, clipTo, invert and build
  all match), the fan triangulation of the output (replacing it with an ear
  clipper changed no number), and missing polygons (the area measurement above
  falsified that outright — nothing was ever lost).

  Check the result with `brep.topology/topology` if closure matters to you; it
  is what these numbers were measured with."
  [operation mesh-a mesh-b]
  (let [a (build-node (merged->polygons (topo/merge-coplanar (topo/welded-oriented mesh-a))))
        b (build-node (merged->polygons (topo/merge-coplanar (topo/welded-oriented mesh-b))))
        result
        (case operation
          :union (let [a1 (clip-to a b)
                       b1 (clip-to b a1)
                       b2 (-> b1 invert-node (clip-to a1) invert-node)]
                   (build-node a1 (all-polygons b2)))
          :difference (let [a1 (invert-node a)
                            a2 (clip-to a1 b)
                            b1 (clip-to b a2)
                            b2 (-> b1 invert-node (clip-to a2) invert-node)]
                        (-> (build-node a2 (all-polygons b2)) invert-node))
          :intersection (let [a1 (invert-node a)
                              b1 (clip-to b a1)
                              b2 (invert-node b1)
                              a2 (clip-to a1 b2)
                              b3 (clip-to b2 a2)]
                          (-> (build-node a2 (all-polygons b3)) invert-node)))]
    (-> (polygons->mesh (all-polygons result))
        topo/repair-t-junctions
        (select-keys [:positions :indices]))))
