(ns brep.topology
  "Topology for a triangle mesh: welded vertices, face adjacency across edges,
  and per-edge dihedral angle and convexity.

  **Why this exists.** `brep.feature/evaluate-mesh` accumulates
  `{:positions :indices}` — a triangle soup with no edge identity and no face
  adjacency. Every feature that acts on EDGES rather than on profiles (chamfer,
  fillet, shell) needs exactly what a soup does not carry, and the feature
  constructors name their targets with BREP edge ids that the mesh side does
  not have. Mapping those ids onto soup edges by guesswork would return a
  successfully-built solid with the WRONG edges treated. This namespace supplies
  the missing half so those features can select edges by a property of the mesh
  they are actually modifying.

  Nothing here modifies geometry. It answers questions about it.

  All of it is pure `.cljc`, no I/O."
  (:require [brep.kernel :as k]
            [brep.polygon :as poly]
            [brep.config :as config]))

;; ---------------------------------------------------------------------------
;; Welding
;; ---------------------------------------------------------------------------

(defn- quantise
  "Snap a point to an integer lattice of cell size `eps`, as the weld key.

  A tolerance-based weld is not an equivalence relation — a and b may each be
  within eps of c while being 2*eps apart — so any implementation has to choose
  where to break the chain. Snapping to a lattice chooses it deterministically
  and in O(n): the answer never depends on the order the points arrive in,
  which a nearest-neighbour walk cannot promise. The cost is the usual one for
  lattices: two points either side of a cell boundary and closer than eps stay
  apart. `weld-mesh` reports the counts so a caller can see what happened
  rather than inferring it."
  [eps [x y z]]
  [(Math/round (/ (double x) eps))
   (Math/round (/ (double y) eps))
   (Math/round (/ (double z) eps))])

(defn weld-mesh
  "Merge coincident positions and reindex the triangles.

  Returns `{:positions :indices :merged :degenerate}` where `:merged` is how
  many input positions collapsed into another and `:degenerate` how many
  triangles lost a corner in the process and were dropped. Both are reported,
  never silent: a weld that quietly deletes triangles turns a hole into a
  'clean' mesh."
  ([mesh] (weld-mesh mesh (* 1.0e3 (get-in config/config [:epsilon :point-merge]))))
  ([{:keys [positions indices]} eps]
   (let [{:keys [pts key->id remap]}
         (reduce (fn [{:keys [pts key->id remap] :as acc} p]
                   (let [key (quantise eps p)]
                     (if-let [id (get key->id key)]
                       (assoc acc :remap (conj remap id))
                       (let [id (count pts)]
                         {:pts (conj pts p)
                          :key->id (assoc key->id key id)
                          :remap (conj remap id)}))))
                 {:pts [] :key->id {} :remap []}
                 positions)
         tris (partition 3 indices)
         kept (vec (for [[a b c] tris
                         :let [t [(remap a) (remap b) (remap c)]]
                         :when (= 3 (count (set t)))]
                     t))]
     {:positions pts
      :indices (vec (mapcat identity kept))
      :merged (- (count positions) (count pts))
      :degenerate (- (count tris) (count kept))})))

(defn- edge-key [a b] (if (< a b) [a b] [b a]))

(defn- signed-volume
  "Six times the signed volume of a closed triangle mesh. Positive when the
  faces wind counter-clockwise seen from outside, i.e. when normals point out."
  [pts faces]
  (reduce (fn [acc [a b c]]
            (+ acc (k/v-dot (nth pts a) (k/v-cross (nth pts b) (nth pts c)))))
          0.0 faces))

(defn orient-faces
  "Return `[faces orientable?]` with every face wound consistently, and with
  normals pointing OUT when the mesh is closed.

  Convexity cannot be read off a triangle soup as it arrives. `tessellate-solid`
  emits each face independently, so two triangles meeting at an edge may wind
  the same way rather than opposite ways, and their computed normals then
  disagree by a sign that has nothing to do with the shape. Measured on a plain
  extruded box: 8 edges read convex, 4 read concave and 0 read as the 12 convex
  edges a box has.

  So: flood-fill the adjacency, flipping any neighbour that traverses the shared
  edge in the same direction as the face it was reached from — that is what
  'consistently wound' means — then flip everything at once if the enclosed
  signed volume came out negative. `orientable?` is false for a Möbius-like
  mesh, where no consistent choice exists; callers must not read convexity off
  one."
  [pts faces]
  (let [n (count faces)
        edge->fs (reduce (fn [m [fi [a b c]]]
                           (reduce (fn [m e] (update m e (fnil conj []) fi))
                                   m [(edge-key a b) (edge-key b c) (edge-key c a)]))
                         {} (map-indexed vector faces))
        directed? (fn [face i j]
                    ;; true when `face` traverses edge i->j in that order
                    (let [[a b c] face]
                      (or (= [i j] [a b]) (= [i j] [b c]) (= [i j] [c a]))))
        flip (fn [[a b c]] [a c b])]
    (loop [oriented (vec faces)
           seen #{0}
           queue [0]
           ok true]
      (if (empty? queue)
        (let [remaining (remove seen (range n))]
          (if (seq remaining)
            ;; another connected shell: orient it independently
            (recur oriented (conj seen (first remaining)) [(first remaining)] ok)
            (let [v (signed-volume pts oriented)]
              [(if (neg? v) (mapv flip oriented) oriented) ok])))
        (let [fi (peek queue)
              face (nth oriented fi)
              [a b c] face
              nbrs (mapcat (fn [[i j]]
                             (map (fn [fj] [fj i j])
                                  (remove #{fi} (get edge->fs (edge-key i j) []))))
                           [[a b] [b c] [c a]])
              [oriented seen queue ok]
              (reduce (fn [[oriented seen queue ok] [fj i j]]
                        (let [nf (nth oriented fj)
                              same? (directed? nf i j)]
                          (cond
                            (seen fj) [oriented seen queue (and ok (not same?))]
                            same? [(assoc oriented fj (flip nf)) (conj seen fj) (conj queue fj) ok]
                            :else [oriented (conj seen fj) (conj queue fj) ok])))
                      [oriented seen (pop queue) ok]
                      nbrs)]
          (recur oriented seen queue ok))))))

;; ---------------------------------------------------------------------------
;; Adjacency
;; ---------------------------------------------------------------------------

(defn- face-normal [pts [a b c]]
  (k/v-normalize (k/v-cross (k/v- (nth pts b) (nth pts a))
                            (k/v- (nth pts c) (nth pts a)))))

(defn- edge-kind [n]
  (case (long n) 1 :boundary 2 :manifold :non-manifold))

(defn- opposite-corner
  "The corner of `face` that is not on `edge`."
  [face [i j]]
  (first (remove #{i j} face)))

(defn- classify-edge
  "Dihedral angle and convexity for a manifold edge.

  Convexity is decided by where the far corner of the second face sits relative
  to the first face's plane: outside it (along the normal) means the solid folds
  AWAY from the edge, which is a concave edge; inside means convex. Comparing
  normals alone cannot tell the two apart — a 90° convex corner and a 90° concave
  one give the same angle between normals."
  [pts faces edge f1 f2]
  (let [n1 (face-normal pts (nth faces f1))
        n2 (face-normal pts (nth faces f2))
        cosang (max -1.0 (min 1.0 (k/v-dot n1 n2)))
        angle (Math/acos cosang)
        far (nth pts (opposite-corner (nth faces f2) edge))
        on-plane (nth pts (first edge))
        side (k/v-dot n1 (k/v- far on-plane))]
    {:dihedral angle
     :convexity (cond (< angle 1.0e-9) :flat
                      (> side 1.0e-9) :concave
                      :else :convex)}))

(defn topology
  "Build the topology of `mesh` (a `{:positions :indices}` triangle soup).

  Returns
  `{:vertices :faces :edges :merged :degenerate :epsilon :manifold?}` where
  `:edges` maps `[i j]` (sorted vertex pair — the stable identity a soup lacks)
  to `{:faces [...] :kind :manifold|:boundary|:non-manifold :dihedral :convexity}`.
  `:dihedral` and `:convexity` are present only for manifold edges: on a
  boundary or non-manifold edge the question has no single answer, and
  answering it anyway is how a chamfer ends up cutting into a hole."
  ([mesh] (topology mesh (* 1.0e3 (get-in config/config [:epsilon :point-merge]))))
  ([mesh eps]
   (let [{:keys [positions indices merged degenerate]} (weld-mesh mesh eps)
         raw-faces (vec (map vec (partition 3 indices)))
         [faces orientable?] (if (seq raw-faces) (orient-faces positions raw-faces) [raw-faces true])
         edge->faces (reduce (fn [m [fi [a b c]]]
                               (reduce (fn [m e] (update m e (fnil conj []) fi))
                                       m
                                       [(edge-key a b) (edge-key b c) (edge-key c a)]))
                             {}
                             (map-indexed vector faces))
         edges (into {}
                     (map (fn [[e fs]]
                            (let [kind (edge-kind (count fs))]
                              [e (merge {:faces fs :kind kind}
                                        (when (= :manifold kind)
                                          (classify-edge positions faces e
                                                         (first fs) (second fs))))])))
                     edge->faces)]
     {:vertices positions
      :faces faces
      :edges edges
      :merged merged
      :degenerate degenerate
      :epsilon eps
      :orientable? orientable?
      :manifold? (every? #(= :manifold (:kind %)) (vals edges))})))

;; ---------------------------------------------------------------------------
;; Queries — what an edge feature actually asks
;; ---------------------------------------------------------------------------

(defn euler-characteristic
  "V - E + F. 2 for a closed surface of genus 0; a different value is the
  cheapest signal that a mesh is not the closed solid it is being treated as."
  [{:keys [vertices faces edges]}]
  (- (+ (count vertices) (count faces)) (count edges)))

(defn edges-where
  "Edge keys whose entry satisfies `pred`, in sorted order so a selection is
  reproducible."
  [{:keys [edges]} pred]
  (vec (sort (keep (fn [[e info]] (when (pred info) e)) edges))))

(defn sharp-edges
  "Manifold edges of the given `convexity` whose dihedral angle is at least
  `min-angle` radians. This is the selector an edge feature can actually use on
  a mesh: it names edges by a property of the geometry in front of it, not by a
  BREP id the mesh never carried."
  [topo convexity min-angle]
  (edges-where topo #(and (= :manifold (:kind %))
                          (= convexity (:convexity %))
                          (>= (:dihedral %) min-angle))))

(defn boundary-edges
  "Edges with a single adjacent face — the mesh has a hole there."
  [topo]
  (edges-where topo #(= :boundary (:kind %))))

(defn welded-oriented
  "`mesh` with coincident positions merged and every face wound consistently
  (outward for a closed mesh). The shape any algorithm that reads face normals
  needs its input in — `brep.mesh-csg` says so in its own docstring and had no
  way to get it until this namespace existed."
  [mesh]
  (let [{:keys [positions indices]} (weld-mesh mesh)
        faces (vec (map vec (partition 3 indices)))
        [oriented _] (if (seq faces) (orient-faces positions faces) [faces true])]
    {:positions positions :indices (vec (mapcat identity oriented))}))

;; ---------------------------------------------------------------------------
;; Coplanar merge — putting the faces back together before a boolean sees them
;; ---------------------------------------------------------------------------

(defn coplanar-regions
  "Maximal connected groups of faces that share a plane, as vectors of face
  indices. Two faces join when they share an edge, their normals agree within
  `angle-tol` radians, and they lie in the same plane within `plane-tol`.

  Both conditions are needed: parallel faces on opposite sides of a slab have
  identical normals and are not the same face."
  ([topo] (coplanar-regions topo 1.0e-9 1.0e-9))
  ([{:keys [vertices faces edges]} angle-tol plane-tol]
   (let [normal (fn [[a b c]]
                  (k/v-normalize (k/v-cross (k/v- (nth vertices b) (nth vertices a))
                                            (k/v- (nth vertices c) (nth vertices a)))))
         normals (mapv normal faces)
         offset (fn [fi] (k/v-dot (nth normals fi) (nth vertices (first (nth faces fi)))))
         offsets (mapv offset (range (count faces)))
         neighbours (reduce (fn [m [_ {:keys [faces kind]}]]
                              (if (= :manifold kind)
                                (let [[a b] faces]
                                  (-> m (update a (fnil conj #{}) b)
                                      (update b (fnil conj #{}) a)))
                                m))
                            {} edges)
         same? (fn [i j]
                 (and (< (- 1.0 (k/v-dot (nth normals i) (nth normals j))) angle-tol)
                      (< (Math/abs (- (nth offsets i) (nth offsets j))) plane-tol)))]
     (loop [remaining (set (range (count faces))) out []]
       (if (empty? remaining)
         out
         (let [seed (first remaining)
               region (loop [stack [seed] seen #{seed}]
                        (if (empty? stack)
                          seen
                          (let [fi (peek stack)
                                grow (filter #(and (remaining %) (not (seen %)) (same? fi %))
                                             (get neighbours fi #{}))]
                            (recur (into (pop stack) grow) (into seen grow)))))]
           (recur (reduce disj remaining region) (conj out (vec (sort region))))))))))

(defn region-loop
  "The single boundary loop of `region` as an ordered vector of vertex indices,
  or nil when the region's boundary is not exactly one simple loop.

  Returns nil rather than a guess for a region with a hole or a pinch: a
  polygon with two loops is not a polygon, and handing one to a BSP that
  assumes convex-decomposable simple polygons produces a shape nobody asked
  for."
  [{:keys [faces]} region]
  (let [tris (map #(nth faces %) region)
        counted (frequencies (mapcat (fn [[a b c]]
                                       [(if (< a b) [a b] [b a])
                                        (if (< b c) [b c] [c b])
                                        (if (< c a) [c a] [a c])])
                                     tris))
        border (vec (keep (fn [[e n]] (when (= 1 n) e)) counted))
        adj (reduce (fn [m [a b]] (-> m (update a (fnil conj []) b)
                                      (update b (fnil conj []) a)))
                    {} border)]
    (when (and (seq border) (every? #(= 2 (count (val %))) adj))
      (let [start (first (sort (keys adj)))]
        (loop [chain [start] prev nil cur start]
          (let [nxt (first (remove #(= % prev) (get adj cur)))]
            (cond
              (nil? nxt) nil
              (= nxt start) (when (= (count chain) (count adj)) chain)
              (some #{nxt} chain) nil
              :else (recur (conj chain nxt) cur nxt))))))))

(defn -cross
  "Cross product. Public only so tests can compute triangle areas without
  reaching into `brep.kernel`."
  [a b]
  (k/v-cross a b))

(defn -loop-normal
  "Newell normal of a closed 3D loop. Public so tests can assert that merged
  loops wind outward — the property that made three boolean cases close."
  [pts]
  (k/v-normalize
   (reduce (fn [acc [[ax ay az] [bx by bz]]]
             (k/v+ acc [(* (- ay by) (+ az bz))
                        (* (- az bz) (+ ax bx))
                        (* (- ax bx) (+ ay by))]))
           [0.0 0.0 0.0]
           (map vector pts (concat (rest pts) [(first pts)])))))

(defn merge-coplanar
  "`mesh` as a vector of planar polygons (each a vector of 3D points), with
  coplanar neighbours welded back into one face.

  A BSP boolean splits polygons against planes and discards fragments with
  fewer than three vertices. Feeding it a TRIANGULATED box hands it two
  coplanar triangles per face instead of one quad, so every plane that should
  cut one polygon cuts two, and the extra fragments are where the holes come
  from. This is the inverse operation, applied before the boolean.

  Regions whose boundary is not a single simple loop stay as their individual
  triangles — merging them would need a polygon-with-holes representation the
  BSP does not have."
  [mesh]
  (let [topo (topology mesh)
        vs (:vertices topo)
        fnorm (fn [[a b c]] (k/v-normalize (k/v-cross (k/v- (nth vs b) (nth vs a))
                                                      (k/v- (nth vs c) (nth vs a)))))
        ;; `region-loop` chains border edges without regard to which way the
        ;; region's faces are wound, so half the loops come back reversed. That
        ;; reintroduces at the POLYGON level exactly the defect `orient-faces`
        ;; removes at the face level — a BSP reading front/back off a normal
        ;; that points the wrong way. Measured: leaving this out turned three
        ;; previously-closed boolean cases open again.
        oriented (fn [loop-ids region]
                   (let [want (fnorm (nth (:faces topo) (first region)))
                         pts (mapv #(nth vs %) loop-ids)
                         got (k/v-normalize (k/v-cross (k/v- (nth pts 1) (nth pts 0))
                                                       (k/v- (nth pts 2) (nth pts 0))))]
                     (if (neg? (k/v-dot want got)) (vec (reverse pts)) pts)))]
    (vec (mapcat (fn [region]
                   (if-let [loop-ids (region-loop topo region)]
                     [(oriented loop-ids region)]
                     (map (fn [fi] (mapv #(nth vs %) (nth (:faces topo) fi))) region)))
                 (coplanar-regions topo)))))

;; ---------------------------------------------------------------------------
;; T-junction repair
;; ---------------------------------------------------------------------------

(defn- point-on-segment
  "Parameter t in (0,1) where `p` sits strictly inside segment a-b, or nil."
  [p a b tol]
  (let [ab (k/v- b a) ap (k/v- p a)
        len (k/v-length ab)]
    (when (pos? len)
      (let [t (/ (k/v-dot ab ap) (* len len))
            off (k/v-length (k/v-cross ab ap))]
        (when (and (< (/ off len) tol) (< 1.0e-9 t (- 1.0 1.0e-9)))
          t)))))

(defn repair-t-junctions
  "Re-triangulate `mesh` so that no edge of one face runs past a vertex sitting
  on it, and return `{:positions :indices :split-edges :passes}`.

  A boolean can produce a surface that is geometrically complete — total area
  exactly the analytic value — and still report boundary edges everywhere,
  because one side of a cut was split at the intersection points and the other
  was left as one span. Measured on a 10x10x4 block with a 4x4 through hole:
  the top face carried `[0,3]->[10,3]` on one side and `[0,3]->[3,3]`,
  `[3,3]->[7,3]`, `[7,3]->[10,3]` on the other. Nothing is missing; the
  triangulation is simply not conforming, so every one of those edges belongs
  to a single face and `topology` calls it a hole.

  This walks each face's edges, inserts the vertices found strictly inside
  them, and ear-clips the enlarged polygon in its own plane. It repeats until a
  pass finds nothing, because splitting one face can expose a vertex on a
  neighbour."
  ([mesh] (repair-t-junctions mesh 1.0e-9 8))
  ([mesh tol max-passes]
   (loop [m (weld-mesh mesh) pass 0 total 0]
     (let [pts (:positions m)
           faces (vec (map vec (partition 3 (:indices m))))
           splits-for (fn [a b]
                        (->> (range (count pts))
                             (keep (fn [vi]
                                     (when-not (or (= vi a) (= vi b))
                                       (when-let [t (point-on-segment (nth pts vi) (nth pts a)
                                                                      (nth pts b) tol)]
                                         [t vi]))))
                             (sort-by first)
                             (mapv second)))
           expanded (mapv (fn [[a b c]]
                            (vec (concat [a] (splits-for a b)
                                         [b] (splits-for b c)
                                         [c] (splits-for c a))))
                          faces)
           found (reduce + (map (fn [f e] (- (count e) (count f))) faces expanded))]
       (cond
         (zero? found)
         (assoc m :split-edges total :passes pass)

         (>= pass max-passes)
         ;; Refuse to loop forever on geometry that keeps producing splits. The
         ;; caller gets what has been repaired plus the count, never a silent
         ;; claim that the mesh is now conforming.
         (assoc m :split-edges total :passes pass :incomplete? true)

         :else
         (let [tris (mapcat
                     (fn [loop-ids]
                       (if (= 3 (count loop-ids))
                         [loop-ids]
                         (let [ps (mapv #(nth pts %) loop-ids)
                               n (-loop-normal ps)
                               a (if (< (Math/abs (nth n 0)) 0.9) [1.0 0.0 0.0] [0.0 1.0 0.0])
                               e1 (k/v-normalize (k/v-cross n a))
                               e2 (k/v-cross n e1)
                               o (first ps)
                               flat (mapv (fn [p] (let [d (k/v- p o)]
                                                    [(k/v-dot d e1) (k/v-dot d e2)])) ps)
                               {:keys [indices]} (poly/triangulate-rings [flat])]
                           (mapv (fn [t] (mapv #(nth loop-ids %) t)) (partition 3 indices)))))
                     expanded)]
           (recur {:positions pts :indices (vec (mapcat identity tris))
                   :merged (:merged m) :degenerate (:degenerate m)}
                  (inc pass) (+ total found))))))))

;; ---------------------------------------------------------------------------
;; Half-space solids — what an edge feature cuts with
;; ---------------------------------------------------------------------------

(defn half-space-box
  "A closed box mesh covering the half-space on the `normal` side of the plane
  through `origin`, out to `extent` in every direction.

  A chamfer on a planar-faced solid IS a plane cut, and a plane cut through a
  mesh boolean needs a solid to subtract rather than an infinite half-space.
  `extent` has to exceed the part; callers size it from the part's own bounding
  box so the cut never stops short of an edge — a chamfer that quietly ends
  mid-edge is worse than one that fails."
  [origin normal extent]
  (let [n (k/v-normalize normal)
        a (if (< (Math/abs (nth n 0)) 0.9) [1.0 0.0 0.0] [0.0 1.0 0.0])
        u (k/v-normalize (k/v-cross n a))
        v (k/v-cross n u)
        e (double extent)
        corner (fn [su sv sn]
                 (k/v+ origin (k/v+ (k/v-scale u (* su e))
                                    (k/v+ (k/v-scale v (* sv e))
                                          (k/v-scale n (* sn e))))))
        pts [(corner -1 -1 0) (corner 1 -1 0) (corner 1 1 0) (corner -1 1 0)
             (corner -1 -1 2) (corner 1 -1 2) (corner 1 1 2) (corner -1 1 2)]
        quads [[0 3 2 1] [4 5 6 7] [0 1 5 4] [1 2 6 5] [2 3 7 6] [3 0 4 7]]
        tris (mapcat (fn [[a b c d]] [[a b c] [a c d]]) quads)]
    {:positions (vec pts) :indices (vec (mapcat identity tris))}))

(defn mesh-bounds
  "`[min max]` of a mesh's positions."
  [{:keys [positions]}]
  [(mapv (fn [i] (apply min (map #(nth % i) positions))) [0 1 2])
   (mapv (fn [i] (apply max (map #(nth % i) positions))) [0 1 2])])
