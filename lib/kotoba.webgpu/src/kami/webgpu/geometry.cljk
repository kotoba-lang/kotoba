(ns kami.webgpu.geometry
  "Procedural mesh geometry as pure data — the canonical, cross-platform source the web
   (kami.webgpu) and native (kami-webgpu-rs) renderers both consume. A sphere is generated ONCE,
   here, and matched across platforms by a committed fixture rather than hand-mirrored in two
   languages (the manual-mirror hazard the Co-Scientist survey flagged as the weakest parity
   proof). Each generator returns a triangle-list mesh:
     {:positions [[x y z] …] :normals [[x y z] …] :indices [i …]}
   Deterministic, dependency-free, and `.cljc` so the same code runs on JVM/bb (golden tests),
   browser CLJS, and — via a shared fixture — native Rust.")

(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))
(defn- sin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn- cos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))

(defn plane
  "A flat w×d quad in the xz-plane (y=0), facing +y. 4 verts, 2 triangles."
  [w d]
  (let [x (/ w 2.0) z (/ d 2.0)]
    {:positions [[(- x) 0 z] [x 0 z] [x 0 (- z)] [(- x) 0 (- z)]]
     :normals   (vec (repeat 4 [0 1 0]))
     :uvs       [[0 0] [1 0] [1 1] [0 1]]
     :indices   [0 1 2 0 2 3]}))

(defn box
  "An axis-aligned w×h×d box centred at the origin, with per-face normals (24 verts, 12 tris)."
  [w h d]
  (let [x (/ w 2.0) y (/ h 2.0) z (/ d 2.0)
        faces [[[0 0 1]  [[(- x) (- y) z] [x (- y) z] [x y z] [(- x) y z]]]
               [[0 0 -1] [[x (- y) (- z)] [(- x) (- y) (- z)] [(- x) y (- z)] [x y (- z)]]]
               [[1 0 0]  [[x (- y) z] [x (- y) (- z)] [x y (- z)] [x y z]]]
               [[-1 0 0] [[(- x) (- y) (- z)] [(- x) (- y) z] [(- x) y z] [(- x) y (- z)]]]
               [[0 1 0]  [[(- x) y z] [x y z] [x y (- z)] [(- x) y (- z)]]]
               [[0 -1 0] [[(- x) (- y) (- z)] [x (- y) (- z)] [x (- y) z] [(- x) (- y) z]]]]]
    (loop [fs faces, pos [], nor [], idx [], base 0]
      (if (empty? fs)
        {:positions pos :normals nor :uvs (vec (take (count pos) (cycle [[0 0] [1 0] [1 1] [0 1]]))) :indices idx}
        (let [[n corners] (first fs)]
          (recur (rest fs)
                 (into pos corners)
                 (into nor (repeat 4 n))
                 (into idx [base (+ base 1) (+ base 2) base (+ base 2) (+ base 3)])
                 (+ base 4)))))))

(defn sphere
  "A UV sphere of radius r with `rings` latitude bands × `sectors` longitude segments.
   (rings+1)×(sectors+1) verts; positions double as unit normals scaled by r."
  [r rings sectors]
  (let [stride (inc sectors)
        unit (fn [i j] (let [phi (* pi (/ i (double rings)))
                             th  (* 2.0 pi (/ j (double sectors)))]
                         [(* (sin phi) (cos th)) (cos phi) (* (sin phi) (sin th))]))
        grid (for [i (range (inc rings)) j (range (inc sectors))] [i j])
        nor  (vec (map (fn [[i j]] (unit i j)) grid))
        pos  (mapv (fn [n] (mapv #(* r %) n)) nor)
        uvs  (vec (map (fn [[i j]] [(/ (double j) sectors) (/ (double i) rings)]) grid))
        idx  (vec (mapcat (fn [[i j]]
                            (let [a (+ (* i stride) j) b (+ a stride)]
                              [a (inc a) (inc b) a (inc b) b]))
                          (for [i (range rings) j (range sectors)] [i j])))]
    {:positions pos :normals nor :uvs uvs :indices idx}))

(defn cylinder
  "A cylinder of radius r, height h (axis y, centred), `sectors` around — side wall + two caps."
  [r h sectors]
  (let [hy (/ h 2.0)
        ring (fn [y] (for [j (range (inc sectors))]
                       (let [th (* 2.0 pi (/ j (double sectors)))]
                         [(* r (cos th)) y (* r (sin th))])))
        top (vec (ring hy)) bot (vec (ring (- hy)))
        side-pos (vec (interleave top bot))
        side-nor (vec (mapcat (fn [[x _ z]] (let [m (max 1e-6 (Math/sqrt (+ (* x x) (* z z))))]
                                              [[(/ x m) 0 (/ z m)] [(/ x m) 0 (/ z m)]]))
                              top))
        side-uv (vec (mapcat (fn [j] (let [u (/ (double j) sectors)] [[u 0] [u 1]]))
                             (range (inc sectors))))
        side-idx (vec (mapcat (fn [j] (let [a (* 2 j) b (+ a 1) c (+ a 2) d (+ a 3)]
                                        [a b d a d c]))
                             (range sectors)))
        nv (count side-pos)
        ;; caps: a centre vert + the ring, fanned
        cap (fn [y ny dir base]
              (let [centre [0 y 0]
                    ring-v (vec (ring y))
                    pos (into [centre] ring-v)
                    nor (vec (repeat (count pos) ny))
                    uv (into [[0.5 0.5]]
                             (map (fn [[x _ z]] [(+ 0.5 (/ x (* 2 r)))
                                                  (+ 0.5 (/ z (* 2 r)))]) ring-v))
                    idx (vec (mapcat (fn [j] (if (pos? dir)
                                               [base (+ base 1 j) (+ base 2 j)]
                                               [base (+ base 2 j) (+ base 1 j)]))
                                    (range sectors)))]
                [pos nor uv idx]))
        [tp tn tu ti] (cap hy [0 1 0] 1 nv)
        [bp bn bu bi] (cap (- hy) [0 -1 0] -1 (+ nv (count tp)))]
    {:positions (into (into side-pos tp) bp)
     :normals   (into (into side-nor tn) bn)
     :uvs       (into (into side-uv tu) bu)
     :indices   (into (into side-idx ti) bi)}))

(defn tri-count
  "Number of triangles in a mesh (handy for tests/budgeting)."
  [mesh]
  (quot (count (:indices mesh)) 3))


;; --- lofted surfaces: a varying section swept along a run of stations ---------
;;
;; The primitives above are what a scene graph needs; a skeleton needs one more.
;; A bone is not a cylinder — its shaft is narrow and its ends flare into condyles
;; — and that difference is not decoration: a viewer reads the joint centres off
;; the flares. `loft` is the general sweep and `long-bone` / `vertebral-body` are
;; two anatomical shapes expressed in terms of it.
;;
;; All three live here rather than in the apps that draw them because a mesh has
;; to be provably closed, non-degenerate and consistently wound, and that proof
;; runs on the JVM with no GPU. An app that tessellated its own bones would be
;; asserting those properties in a browser, or not at all.

(defn- v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn- dot3 [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))

(defn- cross3 [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by))
   (- (* az bx) (* ax bz))
   (- (* ax by) (* ay bx))])

(defn- normalise3 [[x y z]]
  (let [m (Math/sqrt (+ (* x x) (* y y) (* z z)))]
    (if (< m 1e-12) [0.0 1.0 0.0] [(/ x m) (/ y m) (/ z m)])))

(defn- clampd [x lo hi] (max lo (min hi x)))

(defn ring-profile
  "A closed unit section in the xz-plane: `n` points on the unit circle in
   increasing-angle order about +Y, the first at [1 0]. The first point is NOT
   repeated — `loft` duplicates the seam itself, so the wall can carry a u of 0
   and a u of 1 at the same place."
  [n]
  (mapv (fn [j] (let [th (* 2.0 pi (/ (double j) n))] [(cos th) (sin th)]))
        (range n)))

(def ^:private default-crease-cos
  "cos 60°. Two bands that meet at a sharper angle than this get their own copy of
   the shared ring — see `loft`."
  0.5)

(defn loft
  "Sweep a closed `profile` along `stations` and cap both ends.

   `profile` is `[[px pz] …]`, at least 3 points, in increasing-angle order about
   +Y (`ring-profile` makes one). `stations` is `[{:y y :radius [rx rz] :offset
   [ox oz]} …]`, at least 2, ordered by strictly increasing `:y`; `:offset`
   defaults to `[0 0]` and displaces that section off the sweep axis, which is how
   a bone gets its bow. Station k's ring point j is
   `[(+ ox (* rx px)) y (+ oz (* rz pz))]` — the profile is the SHAPE of the
   section and the station is its size, height and offset. That split is what lets
   one function cover a femur and a vertebra.

   Options: `:crease-angle-deg` (default 60).

   The result is a closed manifold wound counter-clockwise seen from outside
   (positive signed volume), with `(* 2 n (count stations))` triangles.

   SHADING NORMALS ARE PER-FACE SUMS, AND A SHARP RING IS A HARD EDGE. Each wall
   vertex takes the area-weighted sum of the faces that touch it, and a station
   where the two bands meet more sharply than `:crease-angle-deg` is DUPLICATED so
   that each side gets its own normal. Both halves of that were measured, not
   assumed:

   - A central difference along the sweep — the obvious way to get a swept normal
     — straddles the condylar ridge, where the radius stops growing and starts
     shrinking inside one station, and returns the average of two nearly opposed
     slopes. On `long-bone` defaults that put 32 of 416 shading normals in the
     opposite hemisphere from the face they shade. Lit geometry whose normal
     opposes its own face reads as a hole, and a hole reads as a shader bug.
   - Summing faces alone does not fix it. A vertex normal that is a weighted sum
     of two directions lies between them, so it can only oppose a face if those
     two faces are more than 90° apart — which at that ridge they are (measured:
     173°). Splitting the ring is what bounds the angle; the sum is what makes the
     rest of the shaft smooth.

   The consequence for callers: vertex count depends on how many rings creased, so
   assert `tri-count` (which does not) or the value for your own parameters."
  ([profile stations] (loft profile stations {}))
  ([profile stations {:keys [crease-angle-deg]}]
   (let [n (count profile)
         s (count stations)
         _ (assert (>= n 3) "loft needs a profile of at least 3 points")
         _ (assert (>= s 2) "loft needs at least 2 stations")
         cos-thresh (if crease-angle-deg (cos (* pi (/ crease-angle-deg 180.0)))
                        default-crease-cos)
         stride (inc n)
         pt (fn [k j]
              (let [{:keys [y radius offset]} (nth stations k)
                    [rx rz] radius
                    [ox oz] (or offset [0.0 0.0])
                    [px pz] (nth profile (mod j n))]
                [(+ ox (* rx px)) y (+ oz (* rz pz))]))
         y0 (:y (first stations))
         y1 (:y (last stations))
         span (max 1e-9 (- y1 y0))
         ;; the two triangles of band k, sector j — the winding used everywhere below
         quad-tris (fn [k j]
                     (let [pa (pt k j) pb (pt k (inc j))
                           pd (pt (inc k) j) pc (pt (inc k) (inc j))]
                       [[pa pd pb] [pb pd pc]]))
         face-n (fn [[p q r]] (cross3 (v- q p) (v- r p)))
         ;; per-band, per-sector unit face normal, for the crease test
         band-normals (mapv (fn [k]
                              (mapv (fn [j] (let [[t1 t2] (quad-tris k j)]
                                              (normalise3 (v+ (face-n t1) (face-n t2)))))
                                    (range n)))
                            (range (dec s)))
         creases (set (filter (fn [k]
                                (let [a (nth band-normals (dec k))
                                      b (nth band-normals k)]
                                  (boolean (some #(< (dot3 (nth a %) (nth b %)) cos-thresh)
                                                 (range n)))))
                              (range 1 (dec s))))
         ;; runs of stations joined smoothly; a creased station ends one run and
         ;; starts the next, so it gets one ring per side
         runs (loop [start 0, cuts (sort creases), acc []]
                (if (seq cuts)
                  (recur (first cuts) (rest cuts) (conj acc (vec (range start (inc (first cuts))))))
                  (conj acc (vec (range start s)))))
         ;; --- walls, one vertex block per run
         wall (reduce
               (fn [{:keys [pos nor uv idx base]} run]
                 (let [rs (count run)
                       acc (reduce (fn [a [ri j]]
                                     (let [k (nth run ri)
                                           [t1 t2] (quad-tris k j)
                                           f1 (face-n t1) f2 (face-n t2)
                                           j+ (mod (inc j) n)
                                           add (fn [a key v]
                                                 (update a key (fnil #(v+ % v) [0.0 0.0 0.0])))]
                                       (-> a
                                           (add [ri j] f1)
                                           (add [(inc ri) j] (v+ f1 f2))
                                           (add [ri j+] (v+ f1 f2))
                                           (add [(inc ri) j+] f2))))
                                   {}
                                   (for [ri (range (dec rs)) j (range n)] [ri j]))]
                   {:pos (into pos (for [ri (range rs) j (range stride)]
                                     (pt (nth run ri) j)))
                    :nor (into nor (for [ri (range rs) j (range stride)]
                                     (normalise3 (get acc [ri (mod j n)] [0.0 1.0 0.0]))))
                    :uv (into uv (for [ri (range rs) j (range stride)]
                                   [(/ (double j) n)
                                    (/ (- (:y (nth stations (nth run ri))) y0) span)]))
                    :idx (into idx (mapcat (fn [[ri j]]
                                             (let [a (+ base (* ri stride) j) b (inc a)
                                                   d (+ a stride) c (inc d)]
                                               [a d b b d c]))
                                           (for [ri (range (dec rs)) j (range n)] [ri j])))
                    :base (+ base (* rs stride))}))
               {:pos [] :nor [] :uv [] :idx [] :base 0}
               runs)
         ;; --- caps: a centre vertex on the station's own axis, fanned to the ring
         cap (fn [k ny base]
               (let [{:keys [y offset]} (nth stations k)
                     [ox oz] (or offset [0.0 0.0])
                     ring (mapv #(pt k %) (range n))]
                 [(into [[ox y oz]] ring)
                  (vec (repeat (inc n) ny))
                  (into [[0.5 0.5]] (mapv (fn [[px pz]] [(+ 0.5 (* 0.5 px)) (+ 0.5 (* 0.5 pz))])
                                          profile))
                  (vec (mapcat (fn [j]
                                 (let [u (+ base 1 j) v (+ base 1 (mod (inc j) n))]
                                   (if (pos? (second ny)) [base v u] [base u v])))
                               (range n)))]))
         wall-n (:base wall)
         [bp bn bu bi] (cap 0 [0.0 -1.0 0.0] wall-n)
         [tp tn tu ti] (cap (dec s) [0.0 1.0 0.0] (+ wall-n (count bp)))]
     {:positions (into (into (:pos wall) bp) tp)
      :normals   (into (into (:nor wall) bn) tn)
      :uvs       (into (into (:uv wall) bu) tu)
      :indices   (into (into (:idx wall) bi) ti)})))

(def long-bone-defaults
  "Proportions of a generic long bone. Radii are multiples of `:shaft-radius`;
   `:length` and `:shaft-radius` are absolute, in whatever unit the caller uses."
  {:length 1.0
   :shaft-radius 1.0
   :sectors 16
   :proximal-flare 1.7      ;; widest radius of the +Y end, × shaft-radius
   :distal-flare 1.7        ;; widest radius of the −Y end, × shaft-radius
   :epiphysis-frac 0.15     ;; fraction of the length each flared end occupies
   :bow 0.0                 ;; mid-shaft displacement along +X, × shaft-radius
   :flatten 1.0})           ;; z radius as a fraction of the x radius

(def ^:private metaphysis-mult
  "Where an epiphysis hands over to the shaft it is a little wider than the shaft
   itself — the metaphysis. One number, so the two ends cannot disagree."
  1.05)

(defn long-bone-stations
  "The station table `long-bone` sweeps: 15 `{:y :radius :offset}` maps.

   Public because it is the shape, written once as a readable table of
   (fraction-of-length, radius-multiple) pairs, and a caller that wants to know
   how wide the bone gets should read it here rather than measure a mesh."
  [opts]
  (let [{:keys [length shaft-radius proximal-flare distal-flare epiphysis-frac bow flatten]}
        (merge long-bone-defaults opts)
        e (clampd epiphysis-frac 0.05 0.28)
        ;; one end, tip → metaphysis, as (fraction of the epiphysis span, radius ×
        ;; that end's flare). `nil` means "hand over to the shaft".
        ;;
        ;; The first two entries are a DOME, and they are not cosmetic. With the
        ;; tip at 0.42 (as the first version had it) the end cap is a disc of 42%
        ;; of the condyle's radius, standing perpendicular to the axis: it faces
        ;; away from the light on one end of every bone and renders as a black
        ;; ellipse, so the bone reads as an open tube. An epiphysis is convex.
        ;; Measured after the change: the cap is 16% of the condyle radius and the
        ;; two dome bands differ by about 11 degrees, well inside the 60-degree
        ;; crease threshold, so it stays smooth rather than becoming a hard rim.
        end [[0.00 0.16] [0.07 0.55] [0.20 0.86] [0.44 1.00] [0.74 0.74] [1.00 nil]]
        shaft [[0.32 0.96] [0.50 0.92] [0.68 0.96]]
        ;; the tip multiplier is the flare's own and is NOT floored at the
        ;; metaphysis: flooring it (as the first draft did) squares the end of the
        ;; bone off at shaft width, and the rounded end is the part of the
        ;; silhouette that says "joint" rather than "rod".
        mult (fn [flare m] (if (nil? m) metaphysis-mult (* m flare)))
        ts (concat (mapv (fn [[f m]] [(* f e) (mult distal-flare m)]) end)
                   shaft
                   (mapv (fn [[f m]] [(- 1.0 (* f e)) (mult proximal-flare m)]) (reverse end)))]
    (mapv (fn [[t m]]
            (let [rx (* shaft-radius m)]
              {:y (* length (- t 0.5))
               :radius [rx (* rx flatten)]
               :offset [(* bow shaft-radius (sin (* pi t))) 0.0]}))
          ts)))

(defn long-bone
  "A long bone: a narrow, optionally bowed shaft between two flared ends.

   One function covers the class — a femur is a large `:distal-flare`, a humerus a
   smaller one, a metacarpal almost none — because at this level of detail the
   only thing that separates them is how far the epiphyses flare and over what
   fraction of the length. It is parameterised by `:length` and `:shaft-radius` in
   the caller's own units, so the mesh follows the anthropometry it is handed
   rather than being a fixed model.

   Options: see `long-bone-defaults`.

   Exactly `:length` tall. With `:bow 0` it is exactly
   2·max(`:proximal-flare`, `:distal-flare`, 1.05)·`:shaft-radius` wide in x, and
   that × `:flatten` deep in z — so a caller can assert the girth it asked for.
   15 stations, hence `(* 30 :sectors)` triangles whatever the crease splits do."
  ([] (long-bone {}))
  ([opts]
   (let [o (merge long-bone-defaults opts)]
     (loft (ring-profile (:sectors o)) (long-bone-stations o) o))))

(def vertebral-body-defaults
  "Proportions of a vertebral body. Radii are multiples of `:radius`."
  {:length 1.0
   :radius 1.0
   :sectors 16
   :endplate-flare 1.12      ;; the rims are wider than the waist
   :waist 0.86               ;; narrowest radius, at mid-height
   :posterior-flatten 0.70}) ;; the −Z wall is flattened, not round

(defn vertebral-body
  "A vertebral body: a short drum, waisted at mid-height, with rims flaring to the
   endplates and a flattened posterior (−Z) wall.

   This is the axial counterpart of `long-bone`, and the reason `loft` takes a
   profile rather than a radius: the flattening is a property of the SECTION and
   the waist is a property of the SWEEP, and neither can express the other.

   Exactly `:length` tall, 2·`:endplate-flare`·`:radius` wide in x, and
   `:endplate-flare`·`:radius`·(1 + `:posterior-flatten`) deep in z. 5 stations,
   hence `(* 10 :sectors)` triangles."
  ([] (vertebral-body {}))
  ([opts]
   (let [{:keys [length radius sectors endplate-flare waist posterior-flatten] :as o}
         (merge vertebral-body-defaults opts)
         profile (mapv (fn [[px pz]] [px (if (neg? pz) (* pz posterior-flatten) pz)])
                       (ring-profile sectors))
         rims [[0.00 endplate-flare] [0.18 (* 0.94 endplate-flare)]
               [0.50 waist]
               [0.82 (* 0.94 endplate-flare)] [1.00 endplate-flare]]]
     (loft profile
           (mapv (fn [[t m]]
                   (let [r (* radius m)]
                     {:y (* length (- t 0.5)) :radius [r r] :offset [0.0 0.0]}))
                 rims)
           o))))
