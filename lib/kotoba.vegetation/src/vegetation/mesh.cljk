(ns vegetation.mesh
  "Per-species procedural meshes driven by a `TaxonomicProfile`.

  Restored from `kami-vegetation/src/mesh.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Core entry: `mesh-from-profile` -> SpeciesMesh. Adding a new species
  means creating a new TaxonomicProfile (`vegetation.taxonomy`) — no new
  mesh function required. Vertex format: [pos.x pos.y pos.z uv.x uv.y]
  (5 floats / vertex, matching the original 20-byte GPU vertex layout).
  Pure data + pure functions; no GPU dispatch."
  (:require [vegetation.species :as species]
            [vegetation.taxonomy :as taxonomy]))

(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))
(def ^:private TAU (* 2.0 PI))

(defn- cos* [x] #?(:clj (Math/cos (double x)) :cljs (js/Math.cos x)))
(defn- sin* [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- sqrt* [x] #?(:clj (Math/sqrt (double x)) :cljs (js/Math.sqrt x)))
(defn- abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))

;; ---------------------------------------------------------------------
;; SpeciesMesh — CPU side, ready to upload as GPU vertex buffer
;; ---------------------------------------------------------------------
;; {:vertices [f32 ...]   ; 5 floats per vertex (pos3 + uv2), flat
;;  :indices  [u32 ...]
;;  :vertex-count n
;;  :index-count n}

(defn- finalize [vertices indices]
  {:vertices vertices
   :indices indices
   :vertex-count (quot (count vertices) 5)
   :index-count (count indices)})

;; ── Vertex pushers (shared primitives) ──
;; These operate on plain vectors, mimicking the Rust `&mut Vec<f32>` /
;; `&mut Vec<u32>` accumulator pattern via reduce-style threading:
;; each `push-*` fn takes [v i ...] and returns [v' i'].

(defn- rot-xz [[x y z] c s]
  [(- (* c x) (* s z)) y (+ (* s x) (* c z))])

(defn- push-quad [v i corners uv-min uv-max]
  (let [base (quot (count v) 5)
        uvs [[(nth uv-min 0) (nth uv-max 1)]
             [(nth uv-max 0) (nth uv-max 1)]
             [(nth uv-min 0) (nth uv-min 1)]
             [(nth uv-max 0) (nth uv-min 1)]]
        v' (reduce (fn [v [[cx cy cz] [ux uy]]]
                     (conj v cx cy cz ux uy))
                   v
                   (map vector corners uvs))
        i' (conj i base (+ base 1) (+ base 2) (+ base 2) (+ base 1) (+ base 3))]
    [v' i']))

(defn- push-tapered-blade [v i angle width height curve]
  (let [c (cos* angle) s (sin* angle)
        hw (* width 0.5)
        tip-narrow 0.15
        bl (rot-xz [(- hw) 0.0 0.0] c s)
        br (rot-xz [hw 0.0 0.0] c s)
        tl (rot-xz [(- (* hw tip-narrow)) height curve] c s)
        tr (rot-xz [(* hw tip-narrow) height curve] c s)
        base (quot (count v) 5)
        v' (-> v
               (into [(nth bl 0) (nth bl 1) (nth bl 2) 0.0 1.0])
               (into [(nth br 0) (nth br 1) (nth br 2) 1.0 1.0])
               (into [(nth tl 0) (nth tl 1) (nth tl 2) 0.1 0.0])
               (into [(nth tr 0) (nth tr 1) (nth tr 2) 0.9 0.0]))
        i' (conj i base (+ base 1) (+ base 2) (+ base 2) (+ base 1) (+ base 3))]
    [v' i']))

(defn- push-trunk-cross [v i r-base r-top h]
  (let [[v i] (push-quad v i
                         [[(- r-base) 0.0 0.0] [r-base 0.0 0.0] [(- r-top) h 0.0] [r-top h 0.0]]
                         [0.3 1.0] [0.5 0.5])
        [v i] (push-quad v i
                         [[0.0 0.0 (- r-base)] [0.0 0.0 r-base] [0.0 h (- r-top)] [0.0 h r-top]]
                         [0.3 1.0] [0.5 0.5])]
    [v i]))

;; ── CanopyShape generators ──

(defn- gen-blade [p]
  ;; Grass / tussock: N tapered blades fanned at equal angles.
  (let [n (max 1 (long (:leaf-count p)))]
    (loop [k 0 v [] i []]
      (if (>= k n)
        (finalize v i)
        (let [angle (* (/ (double k) n) PI)
              [v' i'] (push-tapered-blade v i angle (:leaf-size p) 1.0 (* (:leaf-size p) 0.8))]
          (recur (inc k) v' i'))))))

(defn- gen-fan [p]
  ;; Fern: central stem + N leaflet pairs.
  (let [r (max 0.02 (:stem-radius-base p))
        [v0 i0] (push-quad [] [] [[(- r) 0.0 0.0] [r 0.0 0.0] [(- r) 1.0 0.0] [r 1.0 0.0]]
                            [0.45 1.0] [0.55 0.0])
        n (max 1 (long (:leaf-count p)))]
    (loop [k 0 v v0 i i0]
      (if (>= k n)
        (finalize v i)
        (let [y (+ 0.15 (* (/ 0.75 n) k))
              size (* (:leaf-size p) (- 1.0 (* k 0.1)))
              tilt 0.05
              [v1 i1] (reduce
                       (fn [[v i] sign]
                         (push-quad v i
                                    [[0.0 y 0.0]
                                     [(* sign size) (+ y tilt) 0.0]
                                     [0.0 (+ y (* size 0.3)) 0.0]
                                     [(* sign size) (+ y (* size 0.3) tilt) 0.0]]
                                    (if (< sign 0.0) [0.0 0.8] [0.5 0.8])
                                    (if (< sign 0.0) [0.5 0.0] [1.0 0.0])))
                       [v i]
                       [-1.0 1.0])]
          (recur (inc k) v1 i1))))))

(defn- gen-radial [p]
  ;; Palm: trunk + N radial fronds at top.
  (let [trunk-h 0.85
        [v0 i0] (push-trunk-cross [] [] (:stem-radius-base p) (:stem-radius-top p) trunk-h)
        n (max 1 (long (:leaf-count p)))
        frond-len (:leaf-size p)
        droop 0.15
        base-w 0.08
        tip-w 0.04]
    (loop [k 0 v v0 i i0]
      (if (>= k n)
        (finalize v i)
        (let [angle (* (/ (double k) n) TAU)
              c (cos* angle) s (sin* angle)
              rot (fn [q] (rot-xz q c s))
              [v' i'] (push-quad v i
                                  [(rot [(- base-w) trunk-h 0.0])
                                   (rot [base-w trunk-h 0.0])
                                   (rot [(* tip-w -0.5) (- (+ trunk-h 0.05) droop) frond-len])
                                   (rot [(* tip-w 0.5) (- (+ trunk-h 0.05) droop) frond-len])]
                                  [0.0 1.0] [1.0 0.0])]
          (recur (inc k) v' i'))))))

(defn- gen-cone [p]
  ;; Conifer: trunk + N cone layers (6-side pyramids).
  (let [[v0 i0] (push-trunk-cross [] [] (:stem-radius-base p) (:stem-radius-top p) 0.4)
        layers (max 1 (long (:leaf-count p)))
        top-y 0.98
        base-y 0.30
        step (/ (- top-y base-y) layers)
        sides 6]
    (loop [k 0 v v0 i i0]
      (if (>= k layers)
        (finalize v i)
        (let [t (/ (double k) layers)
              y-base (+ base-y (* step k))
              y-top (+ y-base (* step 1.2))
              radius (* (:leaf-size p) (- 1.0 (* t 0.6)))
              apex [0.0 y-top 0.0]
              [v' i'] (loop [s 0 v v i i]
                        (if (>= s sides)
                          [v i]
                          (let [a0 (* (/ (double s) sides) TAU)
                                a1 (* (/ (double (inc s)) sides) TAU)
                                p0 [(* radius (cos* a0)) y-base (* radius (sin* a0))]
                                p1 [(* radius (cos* a1)) y-base (* radius (sin* a1))]
                                base (quot (count v) 5)
                                v' (-> v
                                       (into [(nth p0 0) (nth p0 1) (nth p0 2) 0.0 1.0])
                                       (into [(nth p1 0) (nth p1 1) (nth p1 2) 1.0 1.0])
                                       (into [(nth apex 0) (nth apex 1) (nth apex 2) 0.5 0.0]))
                                i' (conj i base (+ base 1) (+ base 2))]
                            (recur (inc s) v' i'))))]
          (recur (inc k) v' i'))))))

(defn- gen-dome [p]
  ;; Bush: N overlapping rotated quads forming a sphere silhouette.
  (let [n (max 1 (long (:leaf-count p)))
        r (:leaf-size p)]
    (loop [k 0 v [] i []]
      (if (>= k n)
        (finalize v i)
        (let [t (/ (double k) n)
              angle (* t PI)
              y-c (+ 0.4 (* 0.3 (+ t (* (sin* (* k 0.37)) 0.3))))
              rad (* r (+ 0.7 (* 0.3 (cos* (* k 0.61)))))
              c (cos* angle) s (sin* angle)
              rot (fn [q] (rot-xz q c s))
              [v' i'] (push-quad v i
                                  [(rot [(- rad) (- y-c (* rad 0.5)) 0.0])
                                   (rot [rad (- y-c (* rad 0.5)) 0.0])
                                   (rot [(- rad) (+ y-c (* rad 0.5)) 0.0])
                                   (rot [rad (+ y-c (* rad 0.5)) 0.0])]
                                  [0.0 1.0] [1.0 0.0])]
          (recur (inc k) v' i'))))))

(defn- gen-column [p]
  ;; Cactus: tall fluted cylinder — 8-sided prism with vertical ribs + top cap.
  (let [sides 8
        r-b (max 0.1 (:stem-radius-base p))
        r-t (max 0.08 (:stem-radius-top p))
        h 1.0
        [v0 i0] (loop [s 0 v [] i []]
                  (if (>= s sides)
                    [v i]
                    (let [a0 (* (/ (double s) sides) TAU)
                          a1 (* (/ (double (inc s)) sides) TAU)
                          p0-b [(* r-b (cos* a0)) 0.0 (* r-b (sin* a0))]
                          p1-b [(* r-b (cos* a1)) 0.0 (* r-b (sin* a1))]
                          p0-t [(* r-t (cos* a0)) h (* r-t (sin* a0))]
                          p1-t [(* r-t (cos* a1)) h (* r-t (sin* a1))]
                          [v' i'] (push-quad v i [p0-b p1-b p0-t p1-t]
                                              [(/ (double s) sides) 1.0]
                                              [(/ (double (inc s)) sides) 0.0])]
                      (recur (inc s) v' i'))))
        center-top [0.0 h 0.0]
        top-base (quot (count v0) 5)
        v1 (into v0 [(nth center-top 0) (nth center-top 1) (nth center-top 2) 0.5 0.5])
        v2 (reduce (fn [v s]
                     (let [a (* (/ (double s) sides) TAU)
                           p [(* r-t (cos* a)) h (* r-t (sin* a))]]
                       (into v [(nth p 0) (nth p 1) (nth p 2)
                                (+ 0.5 (* 0.5 (cos* a))) (+ 0.5 (* 0.5 (sin* a)))])))
                   v1
                   (range sides))
        i1 (reduce (fn [i s]
                     (let [a top-base
                           b (+ top-base 1 s)
                           c (+ top-base 1 (mod (inc s) sides))]
                       (conj i a b c)))
                   i0
                   (range sides))]
    (finalize v2 i1)))

(defn- gen-carpet [p]
  ;; Moss: flat multi-patch carpet — N overlapping horizontal quads at slight tilt.
  (let [patches (max 3 (long (:leaf-count p)))
        r (max 0.25 (:leaf-size p))]
    (loop [k 0 v [] i []]
      (if (>= k patches)
        (finalize v i)
        (let [t (/ (double k) patches)
              angle (* t TAU)
              c (cos* angle) s (sin* angle)
              cx (* 0.15 c) cz (* 0.15 s)
              y (+ 0.05 (* 0.05 (abs* (sin* (+ (* t 4.0) 0.7)))))
              rot (fn [[qx qy qz]] (rot-xz [(+ qx cx) qy (+ qz cz)] c s))
              [v' i'] (push-quad v i
                                  [(rot [(* r -0.5) y (* r -0.5)])
                                   (rot [(* r 0.5) y (* r -0.5)])
                                   (rot [(* r -0.5) y (* r 0.5)])
                                   (rot [(* r 0.5) y (* r 0.5)])]
                                  [0.0 1.0] [1.0 0.0])]
          (recur (inc k) v' i'))))))

;; ── Public API ──

(defn mesh-from-profile
  "Generate a mesh from a taxonomic profile. Switches on `:canopy`; uses
   other profile fields (leaf-count, leaf-size, stem radii) to
   parameterize the generator."
  [profile]
  (case (:canopy profile)
    :blade (gen-blade profile)
    :fan (gen-fan profile)
    :radial (gen-radial profile)
    :cone (gen-cone profile)
    :dome (gen-dome profile)
    :column (gen-column profile)
    :carpet (gen-carpet profile)))

(defn mesh-for
  "Convenience: map SpeciesId keyword -> preset profile -> mesh."
  [species-id]
  (mesh-from-profile
   (case species-id
     :grass (taxonomy/grass)
     :fern (taxonomy/fern)
     :palm-tree (taxonomy/palm)
     :conifer (taxonomy/conifer)
     :bush (taxonomy/bush))))

(defn species-mesh-library
  "Full 5-species library (kept for the existing scene_pipelines upload API)."
  []
  (mapv (fn [s] [s (mesh-for s)]) species/species-ids))

(defn extended-mesh-library
  "7-species library including Cactus and Moss (new taxonomic extensions)."
  []
  (mapv (fn [p] [(:common-name p) (mesh-from-profile p)]) (taxonomy/default-catalog)))
