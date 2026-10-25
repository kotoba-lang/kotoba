(ns kotoba.geo.mesh
  "GIS mesh generation: tile quads, globe patches, GeoJSON lines/polygons,
  ribbons, billboards' cousin — vertex/index buffers as plain data.

  Ported from kami-engine/kami-geo/src/mesh.rs (Rust, deleted from the
  working tree pre-commit; recovered from git history). No network/IO —
  pure math. See `90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md`.

  A `GeoMesh` is `{:vertices [<float> ...] :indices [<int> ...]}` where
  `:vertices` is interleaved pos3 + norm3 + uv2 (8 floats/vertex) — the
  same layout the Rust source documented as compatible with
  `kami-render`'s `vertex_buffer_layout()`. `:indices` are triangle-list
  indices (3 per triangle).

  The three near-duplicate ear-clipping triangulation loops in the Rust
  source (`earcut_indices`, and inline copies in
  `polygon_to_fill_earcut_simple` / `polygon_to_extrude_earcut`'s roof)
  are consolidated here into one shared `earcut-indices` + `swap-12`
  post-process — same algorithm, same output, no Rust-side duplication
  carried over."
  (:require [kotoba.geo.constants :as k]
            [kotoba.geo.math :as math]
            [kotoba.geo.noise :as noise]
            [kotoba.geo.projection :as proj]
            [kotoba.geo.vec3 :as vec3]))

(def empty-mesh {:vertices [] :indices []})

;; ---------------------------------------------------------------------
;; Antimeridian (±180°) ring splitting
;; ---------------------------------------------------------------------

(defn split-antimeridian
  "Split a (lng, lat) ring into 1+ subrings whenever it crosses the
  antimeridian (180°/-180°). Without this, polygons spanning the dateline
  (Antarctica in Natural Earth ne_110m_land, Russia, Fiji, Aleutians, …)
  are passed straight to earcut and produce one giant degenerate triangle
  that wraps the whole world (the \"fragmented globe\" bug, 2026-05-05).

  Algorithm: walk the ring; when consecutive longitudes differ by > 180°,
  shift one of them by ±360° and emit a synthetic break-point at ±180°.
  The result is a list of OGC simple-features compliant subrings, each of
  which lies entirely on one side of the dateline.

  Open input ring (no duplicated closing vertex) is acceptable; each
  output subring is closed before returning. Ring points are `[lng lat]`
  2-vectors."
  [ring]
  (let [ring (vec ring)
        n (count ring)]
    (if (< n 3)
      [ring]
      (let [{:keys [subrings current]}
            (reduce
             (fn [{:keys [subrings current]} i]
               (let [[prev-lon prev-lat] (nth ring (dec i))
                     [curr-lon _curr-lat :as curr] (nth ring i)
                     dlon (- curr-lon prev-lon)]
                 (if (or (> dlon 180.0) (< dlon -180.0))
                   (let [east? (> dlon 180.0)
                         prev-unwrap (if east?
                                       [(+ prev-lon 360.0) prev-lat]
                                       [(- prev-lon 360.0) prev-lat])
                         curr-unwrap curr
                         target-lon (if east? 180.0 -180.0)
                         span (- (first curr-unwrap) (first prev-unwrap))
                         t (if (< (math/abs span) 1e-12)
                             0.5
                             (/ (- target-lon (first prev-unwrap)) span))
                         break-lat (+ (second prev-unwrap)
                                      (* t (- (second curr-unwrap) (second prev-unwrap))))
                         cap-lon-a (if east? -180.0 180.0)
                         cap-lon-b (if east? 180.0 -180.0)]
                     {:subrings (conj subrings (conj current [cap-lon-a break-lat]))
                      :current [[cap-lon-b break-lat] curr]})
                   {:subrings subrings :current (conj current curr)})))
             {:subrings [] :current [(first ring)]}
             (range 1 n))
            subrings (if (seq current) (conj subrings current) subrings)
            subrings (mapv (fn [sub]
                              (if (and (>= (count sub) 2) (not= (first sub) (peek sub)))
                                (conj sub (first sub))
                                sub))
                            subrings)]
        (if (empty? subrings) [ring] subrings)))))

;; ---------------------------------------------------------------------
;; Shared ear-clipping triangulation (2D XZ / lng-lat-plane points)
;; ---------------------------------------------------------------------

(defn- convex-cross-f64
  "Signed cross product of edges (a→b) and (a→c). f64 (double) throughout
  keeps the sign stable at world-px scale (Tokyo at zoom ≥ 7 is ~1e6 px)."
  [[ax ay] [bx by] [cx cy]]
  (- (* (- bx ax) (- cy ay)) (* (- by ay) (- cx ax))))

(defn- sign [[px py] [ax ay] [bx by]]
  (- (* (- px bx) (- ay by)) (* (- ax bx) (- py by))))

(defn- point-in-triangle? [p a b c]
  (let [s1 (sign p a b) s2 (sign p b c) s3 (sign p c a)
        has-neg (or (neg? s1) (neg? s2) (neg? s3))
        has-pos (or (pos? s1) (pos? s2) (pos? s3))]
    (not (and has-neg has-pos))))

(defn- signed-area-2d [points]
  (let [n (count points)]
    (* 0.5 (reduce + (for [i (range n)]
                        (let [[ax ay] (nth points i)
                              [bx by] (nth points (mod (inc i) n))]
                          (* (- bx ax) (+ by ay))))))))

(defn- find-ear [pv ring]
  (let [rn (count ring)]
    (first
     (keep (fn [i]
             (let [ia (nth ring (mod (+ i rn -1) rn))
                   ib (nth ring i)
                   ic (nth ring (mod (inc i) rn))
                   a (nth pv ia) b (nth pv ib) c (nth pv ic)]
               (when (> (convex-cross-f64 a b c) 0.0)
                 (when-not (some #(and (not= % ia) (not= % ib) (not= % ic)
                                        (point-in-triangle? (nth pv %) a b c))
                                 ring)
                   {:i i :ia ia :ib ib :ic ic}))))
           (range rn)))))

(defn- earcut-indices
  "Ear-clipping triangulation for a simple (possibly concave) polygon
  without holes, given as 2D `[x y]` points. No self-intersection support.
  Returns a flat vector of triangle-list indices (CCW-in-2D). Falls back
  to a fan triangulation from the first remaining vertex if the ring
  becomes degenerate/self-intersecting (matches the Rust source's
  fallback exactly)."
  [points]
  (let [n (count points)]
    (if (< n 3)
      []
      (let [pv (vec points)
            ring0 (if (neg? (signed-area-2d pv)) (vec (range n)) (vec (reverse (range n))))]
        (loop [ring ring0 indices (transient []) guard (* n n)]
          (if (or (< (count ring) 3) (<= guard 0))
            (persistent! indices)
            (if-let [ear (find-ear pv ring)]
              (recur (into (subvec ring 0 (:i ear)) (subvec ring (inc (:i ear))))
                     (-> indices (conj! (:ia ear)) (conj! (:ib ear)) (conj! (:ic ear)))
                     (dec guard))
              (let [first-idx (first ring)
                    final (reduce (fn [acc [w0 w1]] (-> acc (conj! first-idx) (conj! w0) (conj! w1)))
                                   indices
                                   (rest (partition 2 1 ring)))]
                (persistent! final)))))))))

(defn- swap-12
  "Swap index 1 and 2 within every triangle triple. Ear-clipping on
  world-px / lng-lat-plane XZ coordinates produces CCW-in-2D triangles
  whose 3D surface normal is -Y (down); this flips winding so the
  resulting triangles face +Y."
  [indices]
  (into [] (mapcat (fn [[a b c]] [a c b])) (partition 3 indices)))

;; ---------------------------------------------------------------------
;; Smooth-normal accumulation (shared by DEM-flat and globe patches)
;; ---------------------------------------------------------------------

(defn- accumulate-smooth-normals
  "Per-vertex smooth normals: accumulate each triangle's face normal onto
  its 3 vertices, then normalize."
  [positions indices]
  (let [zero (vec (repeat (count positions) [0.0 0.0 0.0]))
        acc (reduce
             (fn [normals [ia ib ic]]
               (let [a (nth positions ia) b (nth positions ib) c (nth positions ic)
                     face (vec3/normalize (vec3/cross (vec3/sub b a) (vec3/sub c a)))]
                 (-> normals
                     (update ia vec3/add face)
                     (update ib vec3/add face)
                     (update ic vec3/add face))))
             zero
             (partition 3 indices))]
    (mapv vec3/normalize acc)))

;; ---------------------------------------------------------------------
;; Tile quads / DEM patches
;; ---------------------------------------------------------------------

(defn tile-quad
  "Textured quad for a single raster tile: `tile-size-px` × `tile-size-px`
  world-pixels, placed at (0,0,0). Caller applies a transform to position
  it correctly. Normal points up (+Y). Vertices ordered TL → BL → BR → TR
  (CCW from top view)."
  []
  (let [s k/tile-size-px]
    {:vertices [0.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0
                0.0 0.0 s   0.0 1.0 0.0 0.0 1.0
                s   0.0 s   0.0 1.0 0.0 1.0 1.0
                s   0.0 0.0 0.0 1.0 0.0 1.0 0.0]
     :indices [0 1 2 0 2 3]}))

(defn sample-dem-height
  "Bilinear-sample a DEM height grid `heights` (row-major, `width` ×
  `height`) at fractional `[u v]` in `[0,1]`."
  [heights width height u v]
  (if (or (< width 2) (< height 2) (< (count heights) (* width height)))
    0.0
    (let [x (* (math/clamp u 0.0 1.0) (dec width))
          y (* (math/clamp v 0.0 1.0) (dec height))
          x0 (long (math/floor x))
          y0 (long (math/floor y))
          x1 (min (inc x0) (dec width))
          y1 (min (inc y0) (dec height))
          tx (- x x0)
          ty (- y y0)
          idx (fn [xx yy] (+ (* yy width) xx))
          h00 (nth heights (idx x0 y0))
          h10 (nth heights (idx x1 y0))
          h01 (nth heights (idx x0 y1))
          h11 (nth heights (idx x1 y1))
          hx0 (noise/lerp h00 h10 tx)
          hx1 (noise/lerp h01 h11 tx)]
      (noise/lerp hx0 hx1 ty))))

(defn flat-tile-patch-from-dem
  "Textured flat Web-Mercator tile patch displaced by DEM heights.
  Positions are local tile pixels (0..tile-size-px in X/Z) so callers can
  keep using the same per-tile transform as `tile-quad`. Height is
  converted from meters to world pixels at the tile latitude and zoom."
  [coord segments heights-m dem-width dem-height vertical-exaggeration]
  (if (or (< dem-width 2) (< dem-height 2) (< (count heights-m) (* dem-width dem-height)))
    (tile-quad)
    (let [[_ south _ north] (proj/tile-lng-lat-bounds coord)
          mid-lat (math/to-radians (* (+ south north) 0.5))
          meters-per-px (max 0.05 (/ (* k/ground-resolution-zoom0 (math/cos mid-lat))
                                      (math/pow 2.0 (:z coord))))
          meters-to-world-px (/ (max 0.0 vertical-exaggeration) meters-per-px)
          segs (long (math/clamp segments 2 64))
          stride (inc segs)
          idx-pairs (vec (for [iy (range (inc segs)) ix (range (inc segs))] [iy ix]))
          positions (mapv (fn [[iy ix]]
                             (let [v (/ (double iy) segs) u (/ (double ix) segs)
                                   h (-> (sample-dem-height heights-m dem-width dem-height u v)
                                         (* meters-to-world-px)
                                         (math/clamp (- k/dem-height-clamp-px) k/dem-height-clamp-px))]
                               [(* u k/tile-size-px) h (* v k/tile-size-px)]))
                           idx-pairs)
          uvs (mapv (fn [[iy ix]] [(/ (double ix) segs) (/ (double iy) segs)]) idx-pairs)
          indices (vec (mapcat (fn [iy]
                                  (mapcat (fn [ix]
                                            (let [a (+ (* iy stride) ix) b (+ a stride)]
                                              [a b (inc b) a (inc b) (inc a)]))
                                          (range segs)))
                                (range segs)))
          normals (accumulate-smooth-normals positions indices)
          vertices (vec (mapcat (fn [pos norm uv] (concat pos norm uv)) positions normals uvs))]
      {:vertices vertices :indices indices})))

;; ---------------------------------------------------------------------
;; Globe (sphere) geometry
;; ---------------------------------------------------------------------

(defn- lng-lat->sphere-xyz [lng lat radius]
  (let [lng-rad (math/to-radians lng)
        lat-rad (math/to-radians lat)
        cos-lat (math/cos lat-rad)
        sin-lat (math/sin lat-rad)
        sin-lng (math/sin lng-rad)
        cos-lng (math/cos lng-rad)]
    [(* radius cos-lat sin-lng) (* radius sin-lat) (- (* radius cos-lat cos-lng))]))

(defn- sphere-position [lng lat radius] (lng-lat->sphere-xyz lng lat radius))
(defn- sphere-normal [lng lat] (vec3/normalize (sphere-position lng lat 1.0)))

(defn- globe-tile-patch-from-heights
  [coord radius segments height-scale dem-heights dem-width dem-height]
  (let [[west _south east _north] (proj/tile-lng-lat-bounds coord)
        segs (long (max segments 2))
        stride (inc segs)
        ;; Tile count per axis at this zoom, for the Mercator row -> latitude
        ;; inverse below.
        tiles-n (math/pow 2.0 (:z coord))
        idx-pairs (vec (for [iy (range (inc segs)) ix (range (inc segs))] [iy ix]))
        computed (mapv (fn [[iy ix]]
                          (let [v (/ (double iy) segs)
                                ;; Latitude comes back through the Mercator
                                ;; inverse, NOT lerped between the tile's own
                                ;; north and south. A raster tile's rows are
                                ;; linear in Mercator y; latitude is the
                                ;; inverse Gudermannian of it. Lerping put the
                                ;; texture 24 degrees out of register at z0,
                                ;; 15 at z1 and 0.5 at z3 -- a distortion that
                                ;; looks like a projection choice rather than
                                ;; a bug, which is why it survived.
                                lat (proj/mercator-tile-y->lat
                                     (+ (:y coord) v) tiles-n)
                                u (/ (double ix) segs)
                                lng (+ west (* (- east west) u))
                                height (* (if dem-heights
                                            (sample-dem-height dem-heights dem-width dem-height u v)
                                            (noise/globe-relief-height lng lat))
                                          height-scale)
                                pos (lng-lat->sphere-xyz lng lat (+ radius height))]
                            {:pos pos :uv [u v]}))
                        idx-pairs)
        positions (mapv :pos computed)
        uvs (mapv :uv computed)
        indices (vec (mapcat (fn [iy]
                                (mapcat (fn [ix]
                                          (let [a (+ (* iy stride) ix) b (+ a stride)]
                                            [a (inc b) b a (inc a) (inc b)]))
                                        (range segs)))
                              (range segs)))
        normals (accumulate-smooth-normals positions indices)
        vertices (vec (mapcat (fn [pos norm uv] (concat pos norm uv)) positions normals uvs))]
    {:vertices vertices :indices indices}))

(defn globe-tile-patch-terrain
  "Sphere patch with procedural relief suitable for a globe terrain view."
  [coord radius segments terrain-scale]
  (globe-tile-patch-from-heights coord radius segments terrain-scale nil 0 0))

(defn globe-tile-patch
  "Sphere patch for a raster tile, centered on the origin and textured
  with the full tile image."
  [coord radius segments]
  (globe-tile-patch-terrain coord radius segments (* radius k/globe-default-terrain-scale-ratio)))

(defn globe-tile-patch-from-dem
  "Sphere patch from a DEM height tile. Heights are interpreted in meters."
  [coord radius segments heights-m dem-width dem-height meters-to-radius]
  (globe-tile-patch-from-heights coord radius segments meters-to-radius heights-m dem-width dem-height))

(defn- segment-tangent [points i]
  (let [n (count points)
        delta (cond
                (= i 0) (vec3/sub (nth points 1) (nth points 0))
                (= i (dec n)) (vec3/sub (nth points i) (nth points (dec i)))
                :else (vec3/add (vec3/sub (nth points (inc i)) (nth points i))
                                 (vec3/sub (nth points i) (nth points (dec i)))))]
    (vec3/normalize delta)))

(defn globe-line-to-ribbon
  "Ribbon (flat strip with width) following the globe surface."
  [coords-lng-lat radius width-world elevation]
  (if (< (count coords-lng-lat) 2)
    empty-mesh
    (let [positions (mapv (fn [[lng lat]] (sphere-position lng lat (+ radius elevation))) coords-lng-lat)
          normals (mapv (fn [[lng lat]] (sphere-normal lng lat)) coords-lng-lat)
          half-w (* width-world 0.5)
          n (count coords-lng-lat)
          verts (vec (mapcat
                      (fn [i]
                        (let [tangent (segment-tangent positions i)
                              normal (nth normals i)
                              binormal (vec3/normalize (vec3/cross normal tangent))
                              left (vec3/add (nth positions i) (vec3/mul binormal half-w))
                              right (vec3/add (nth positions i) (vec3/mul binormal (- half-w)))
                              u (/ (double i) (dec n))]
                          (concat left normal [u 0.0] right normal [u 1.0])))
                      (range n)))
          indices (vec (mapcat (fn [i]
                                  (let [base (* i 2)]
                                    [base (inc base) (+ base 3) base (+ base 3) (+ base 2)]))
                                (range (dec n))))]
      {:vertices verts :indices indices})))

(defn- unwrap-lng [lng anchor]
  (loop [out lng]
    (cond
      (> (- out anchor) 180.0) (recur (- out 360.0))
      (< (- out anchor) -180.0) (recur (+ out 360.0))
      :else out)))

(defn- combine-meshes [meshes]
  (reduce (fn [combined mesh]
            (let [base (quot (count (:vertices combined)) 8)]
              {:vertices (into (:vertices combined) (:vertices mesh))
               :indices (into (:indices combined) (map #(+ % base) (:indices mesh)))}))
          empty-mesh
          meshes))

(defn- globe-polygon-to-fill-earcut-simple [ring-lng-lat radius elevation]
  (let [coords (vec ring-lng-lat)
        coords (if (and (>= (count coords) 2) (= (first coords) (peek coords)))
                 (subvec coords 0 (dec (count coords)))
                 coords)]
    (if (< (count coords) 3)
      empty-mesh
      (let [anchor-lng (first (first coords))
            points-2d (mapv (fn [[lng lat]] [(unwrap-lng lng anchor-lng) lat]) coords)
            verts (vec (mapcat (fn [[lng lat]]
                                  (let [pos (sphere-position lng lat (+ radius elevation))
                                        n (sphere-normal lng lat)]
                                    (concat pos n [0.5 0.5])))
                                coords))
            indices (earcut-indices points-2d)]
        {:vertices verts :indices indices}))))

(defn globe-polygon-to-fill-earcut
  "Polygon fill draped on the globe surface.

  Phase A antimeridian fix (2026-05-06): split at ±180° crossings before
  triangulation. Without this, dateline-spanning rings (Antarctica in
  Natural Earth) get earcut'd in a frame where some vertices are unwrapped
  to lon = +540° and others stay at -170°, generating one huge wrong
  triangle that wraps the globe."
  [ring-lng-lat radius elevation]
  (if (< (count ring-lng-lat) 3)
    empty-mesh
    (let [subrings (split-antimeridian ring-lng-lat)]
      (if (> (count subrings) 1)
        (combine-meshes (map #(globe-polygon-to-fill-earcut-simple % radius elevation) subrings))
        (globe-polygon-to-fill-earcut-simple ring-lng-lat radius elevation)))))

(defn globe-polygon-to-extrude-earcut
  "Extrude a polygon footprint upward from the globe surface.

  The globe-frame counterpart of `polygon-to-extrude-earcut`, which does
  the same thing in the flat world-pixel frame. Both a flat extrude and a
  globe FILL already existed; this was the missing cell, and a caller
  wanting extruded buildings on a sphere had no choice but to re-derive
  sphere positions outside the library.

  `base` and `height` are in the same units as `radius`, measured from the
  surface: a building whose roof is 40 m up on an earth-radius-1 globe is
  `height` 40/6371000.

  Emits a roof cap at `base + height` plus one outward-facing quad per
  edge. Sidewall normals are the OUTWARD HORIZONTAL direction at that
  edge -- the surface normal would light every wall as though it were a
  roof, and a building lit like its own roof reads as a flat patch of
  colour rather than a solid.

  Antimeridian handling is inherited from `globe-polygon-to-fill-earcut`
  for the roof. A single building never spans the dateline, but a caller
  passing an arbitrary ring gets the same protection the fill has."
  [ring-lng-lat radius base height]
  (if (or (< (count ring-lng-lat) 3) (<= height 0.0))
    empty-mesh
    (let [ring (if (and (>= (count ring-lng-lat) 2)
                        (= (first ring-lng-lat) (peek (vec ring-lng-lat))))
                 (subvec (vec ring-lng-lat) 0 (dec (count ring-lng-lat)))
                 (vec ring-lng-lat))
          n (count ring)]
      (if (< n 3)
        empty-mesh
        (let [top (+ base height)
              roof (globe-polygon-to-fill-earcut ring radius top)
              roof-vertex-count (quot (count (:vertices roof)) 8)
              ;; The ring's centroid, only to orient the wall normals
              ;; outward. Longitudes are unwrapped against the first point
              ;; so a ring near +/-180 does not average to the far side of
              ;; the planet.
              anchor (first (first ring))
              cx (/ (reduce + (map (fn [[lng _]] (unwrap-lng lng anchor)) ring)) n)
              cy (/ (reduce + (map second ring)) n)
              walls (reduce
                     (fn [{:keys [vertices indices]} i]
                       (let [[alng alat] (nth ring i)
                             [blng blat] (nth ring (mod (inc i) n))
                             au (unwrap-lng alng anchor)
                             bu (unwrap-lng blng anchor)
                             mid-lng (* 0.5 (+ au bu))
                             mid-lat (* 0.5 (+ alat blat))
                             ;; Outward = from the centroid towards the edge
                             ;; midpoint, taken on the sphere so the normal
                             ;; is a real direction rather than a lng/lat
                             ;; difference (which is not a vector).
                             mid-pos (sphere-position mid-lng mid-lat radius)
                             ctr-pos (sphere-position cx cy radius)
                             out0 (vec3/sub mid-pos ctr-pos)
                             nrm (if (< (vec3/length out0) 1e-12)
                                   (sphere-normal mid-lng mid-lat)
                                   (vec3/normalize out0))
                             a0 (sphere-position alng alat (+ radius base))
                             b0 (sphere-position blng blat (+ radius base))
                             a1 (sphere-position alng alat (+ radius top))
                             b1 (sphere-position blng blat (+ radius top))
                             bi (+ roof-vertex-count (quot (count vertices) 8))]
                         {:vertices (into vertices
                                          (concat a0 nrm [0.0 0.0]
                                                  b0 nrm [1.0 0.0]
                                                  b1 nrm [1.0 1.0]
                                                  a1 nrm [0.0 1.0]))
                          :indices (into indices
                                         [bi (inc bi) (+ bi 2)
                                          bi (+ bi 2) (+ bi 3)])}))
                     {:vertices [] :indices []}
                     (range n))]
          {:vertices (into (:vertices roof) (:vertices walls))
           :indices (into (:indices roof) (:indices walls))})))))

(defn globe-points-to-circles
  "Circle discs tangent to the globe surface."
  [points-lng-lat radius disc-radius elevation segments]
  (if (empty? points-lng-lat)
    empty-mesh
    (let [seg (long (max segments 6))
          per-point (mapv
                     (fn [[lng lat]]
                       (let [center (sphere-position lng lat (+ radius elevation))
                             normal (sphere-normal lng lat)
                             east-seed (if (> (math/abs (nth normal 1)) 0.98)
                                         [0.0 0.0 1.0]
                                         [0.0 1.0 0.0])
                             east (vec3/normalize (vec3/cross east-seed normal))
                             north (vec3/normalize (vec3/cross normal east))
                             center-vert (concat center normal [0.5 0.5])
                             rim-verts (mapcat
                                        (fn [i]
                                          (let [theta (* (/ (double i) seg) math/tau)
                                                rim (vec3/add center
                                                               (vec3/add (vec3/mul east (* (math/cos theta) disc-radius))
                                                                          (vec3/mul north (* (math/sin theta) disc-radius))))]
                                            (concat rim normal
                                                    [(+ 0.5 (* 0.5 (math/cos theta)))
                                                     (+ 0.5 (* 0.5 (math/sin theta)))])))
                                        (range seg))
                             tris (mapcat (fn [i] [0 (inc i) (inc (mod (inc i) seg))]) (range seg))]
                         {:vertices (vec (concat center-vert rim-verts)) :indices (vec tris)}))
                     points-lng-lat)]
      (combine-meshes per-point))))

;; ---------------------------------------------------------------------
;; Flat (Web-Mercator world-px) lines / polygons / points
;; ---------------------------------------------------------------------

(defn- lng-lat->relative-px [[lng lat] zoom center-px]
  (let [wp (proj/lng-lat->world-px (proj/lng-lat lng lat) zoom)]
    [(- (:x wp) (:x center-px)) (- (:y wp) (:y center-px))]))

(defn line-to-ribbon
  "Ribbon (flat strip with width) from a polyline. Coordinates are in
  world-pixel space relative to `center-px`. The ribbon lies on the
  Y=elevation plane."
  [coords-lng-lat zoom center-px width elevation]
  (if (< (count coords-lng-lat) 2)
    empty-mesh
    (let [points (mapv #(lng-lat->relative-px % zoom center-px) coords-lng-lat)
          half-w (* width 0.5)
          n (count points)
          verts (vec (mapcat
                      (fn [i]
                        (let [[dx dz] (cond
                                        (= i 0) (let [[x0 z0] (nth points 0) [x1 z1] (nth points 1)]
                                                  [(- x1 x0) (- z1 z0)])
                                        (= i (dec n)) (let [[x0 z0] (nth points (- n 2)) [x1 z1] (nth points (dec n))]
                                                        [(- x1 x0) (- z1 z0)])
                                        :else (let [[x0 z0] (nth points (dec i)) [x1 z1] (nth points (inc i))]
                                                [(- x1 x0) (- z1 z0)]))
                              len (max 1e-6 (math/sqrt (+ (* dx dx) (* dz dz))))
                              nx (/ (- dz) len)
                              nz (/ dx len)
                              [px pz] (nth points i)
                              u (/ (double i) (dec n))]
                          (concat [(+ px (* nx half-w)) elevation (+ pz (* nz half-w)) 0.0 1.0 0.0 u 0.0]
                                  [(- px (* nx half-w)) elevation (- pz (* nz half-w)) 0.0 1.0 0.0 u 1.0])))
                      (range n)))
          indices (vec (mapcat (fn [i]
                                  (let [base (* i 2)]
                                    [base (inc base) (+ base 3) base (+ base 3) (+ base 2)]))
                                (range (dec n))))]
      {:vertices verts :indices indices})))

(defn polygon-to-fill
  "Flat polygon fill from a ring of coordinates via fan triangulation
  (works for convex-ish polygons)."
  [ring-lng-lat zoom center-px elevation]
  (if (< (count ring-lng-lat) 3)
    empty-mesh
    (let [points (mapv #(lng-lat->relative-px % zoom center-px) ring-lng-lat)
          n (count points)
          verts (vec (mapcat (fn [[px pz]]
                                [px elevation pz 0.0 1.0 0.0 (/ px k/tile-size-px) (/ pz k/tile-size-px)])
                              points))
          indices (vec (mapcat (fn [i] [0 i (inc i)]) (range 1 (dec n))))]
      {:vertices verts :indices indices})))

(defn- polygon-to-fill-earcut-simple [ring-lng-lat zoom center-px elevation]
  (if (< (count ring-lng-lat) 3)
    empty-mesh
    (let [points (mapv #(lng-lat->relative-px % zoom center-px) ring-lng-lat)
          points (if (and (>= (count points) 2) (= (first points) (peek points)))
                   (subvec points 0 (dec (count points)))
                   points)
          n (count points)]
      (if (< n 3)
        empty-mesh
        (let [verts (vec (mapcat (fn [[px pz]]
                                    [px elevation pz 0.0 1.0 0.0 (/ px k/tile-size-px) (/ pz k/tile-size-px)])
                                  points))
              indices (swap-12 (earcut-indices points))]
          {:vertices verts :indices indices})))))

(defn polygon-to-fill-earcut
  "Ear-clipping triangulation for a simple (possibly concave) polygon
  without holes (flat / world-px plane).

  Phase A antimeridian fix (2026-05-06): if the ring crosses ±180°, split
  into 1+ subrings via `split-antimeridian` and triangulate each
  independently, then concatenate."
  [ring-lng-lat zoom center-px elevation]
  (if (< (count ring-lng-lat) 3)
    empty-mesh
    (let [subrings (split-antimeridian ring-lng-lat)]
      (if (> (count subrings) 1)
        (combine-meshes (map #(polygon-to-fill-earcut-simple % zoom center-px elevation) subrings))
        (polygon-to-fill-earcut-simple ring-lng-lat zoom center-px elevation)))))

(defn points-to-circles
  "Batched circle discs for a set of point features. `radius-world-px` is
  measured in world pixels at the layer creation zoom. `segments`
  controls tessellation resolution (min 6)."
  [points-lng-lat zoom center-px radius-world-px elevation segments]
  (if (empty? points-lng-lat)
    empty-mesh
    (let [seg (long (max segments 6))
          per-point (mapv
                     (fn [pt]
                       (let [[cx cz] (lng-lat->relative-px pt zoom center-px)
                             center-vert [cx elevation cz 0.0 1.0 0.0 0.5 0.5]
                             rim-verts (mapcat
                                        (fn [i]
                                          (let [theta (* (/ (double i) seg) math/tau)
                                                dx (* (math/cos theta) radius-world-px)
                                                dz (* (math/sin theta) radius-world-px)
                                                u (+ 0.5 (* 0.5 (math/cos theta)))
                                                v (+ 0.5 (* 0.5 (math/sin theta)))]
                                            [(+ cx dx) elevation (+ cz dz) 0.0 1.0 0.0 u v]))
                                        (range seg))
                             tris (mapcat (fn [i] [0 (inc i) (inc (mod (inc i) seg))]) (range seg))]
                         {:vertices (vec (concat center-vert rim-verts)) :indices (vec tris)}))
                     points-lng-lat)]
      (combine-meshes per-point))))

(defn polygon-to-extrude-earcut
  "Extrude a polygon footprint (in lng/lat) upward by `height` world
  units. Emits: a roof capped at y=base+height (triangulated via
  ear-clipping) plus sidewall quads (2 triangles per edge) from
  y=base to y=base+height. Sidewall normals face outward (perpendicular
  to each edge)."
  [ring-lng-lat zoom center-px base height]
  (if (or (< (count ring-lng-lat) 3) (<= height 0.0))
    empty-mesh
    (let [points (mapv #(lng-lat->relative-px % zoom center-px) ring-lng-lat)
          points (if (and (>= (count points) 2) (= (first points) (peek points)))
                   (subvec points 0 (dec (count points)))
                   points)
          n (count points)]
      (if (< n 3)
        empty-mesh
        (let [top-y (+ base height)
              roof-verts (vec (mapcat (fn [[px pz]]
                                         [px top-y pz 0.0 1.0 0.0 (/ px k/tile-size-px) (/ pz k/tile-size-px)])
                                       points))
              roof-vertex-count (quot (count roof-verts) 8)
              roof-indices (swap-12 (earcut-indices points))
              cx (/ (reduce + (map first points)) n)
              cz (/ (reduce + (map second points)) n)
              sidewalls (reduce
                         (fn [{:keys [vertices indices]} i]
                           (let [[ax az] (nth points i)
                                 [bx bz] (nth points (mod (inc i) n))
                                 ex (- bx ax) ez (- bz az)
                                 mid-x (* 0.5 (+ ax bx)) mid-z (* 0.5 (+ az bz))
                                 to-mid-x (- mid-x cx) to-mid-z (- mid-z cz)
                                 [nx0 nz0] (if (> (+ (* (- ez) to-mid-x) (* ex to-mid-z)) 0.0)
                                             [(- ez) ex]
                                             [ez (- ex)])
                                 len (max 1e-6 (math/sqrt (+ (* nx0 nx0) (* nz0 nz0))))
                                 nx (/ nx0 len) nz (/ nz0 len)
                                 base-idx (+ roof-vertex-count (quot (count vertices) 8))
                                 wall-verts [ax base az nx 0.0 nz 0.0 0.0
                                             bx base bz nx 0.0 nz 1.0 0.0
                                             bx top-y bz nx 0.0 nz 1.0 1.0
                                             ax top-y az nx 0.0 nz 0.0 1.0]
                                 wall-indices [base-idx (inc base-idx) (+ base-idx 2)
                                               base-idx (+ base-idx 2) (+ base-idx 3)]]
                             {:vertices (into vertices wall-verts)
                              :indices (into indices wall-indices)}))
                         {:vertices [] :indices []}
                         (range n))]
          {:vertices (into roof-verts (:vertices sidewalls))
           :indices (into roof-indices (:indices sidewalls))})))))
