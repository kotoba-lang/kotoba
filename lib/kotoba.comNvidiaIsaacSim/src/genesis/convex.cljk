(ns genesis.convex
  "GJK distance + intersection and EPA penetration for convex shapes
  (boxes, hulls). Clean-room, CPU/WASM, f32-class narrow-phase (same
  *class* PhysX uses — GJK distance + EPA penetration).

  Honest scope (from the original crate docs): convex-convex only
  (concave = decompose), single precision, no manifold generation /
  persistent contacts (one deepest point/normal).

  A `ConvexPoly` is represented as a plain map `{:verts [...]}` of
  world-space vertices (vec3s); support = argmax dot.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/convex.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math)."
  (:require [genesis.vec3 :as v3]))

(defn ->poly [verts] {:verts verts})

(defn box-at
  "Axis-aligned (or rotated) box from a centre, half-extents, and an
  optional rotation function `rot` (vec3 -> vec3, default identity)
  applied to the 8 corners."
  ([center half] (box-at center half identity))
  ([center half rot]
   (->poly
     (vec (for [sx [-1.0 1.0] sy [-1.0 1.0] sz [-1.0 1.0]]
            (v3/add center (rot [(* sx (nth half 0)) (* sy (nth half 1)) (* sz (nth half 2))])))))))

(defn- support [{:keys [verts]} dir]
  (reduce (fn [best v] (if (> (v3/dot v dir) (v3/dot best dir)) v best))
          (first verts) (rest verts)))

(defn- cso-support [a b dir]
  (v3/sub (support a dir) (support b (v3/neg dir))))

;; ── closest point on a simplex to the ORIGIN (Ericson) ──────────────────

(defn- closest-on-segment [a b]
  (let [ab (v3/sub b a)
        denom (max (v3/dot ab ab) 1e-12)
        t (max 0.0 (min 1.0 (/ (- (v3/dot a ab)) denom)))]
    (v3/add a (v3/scale ab t))))

(defn- closest-on-triangle [a b c]
  (let [ab (v3/sub b a) ac (v3/sub c a) ap (v3/neg a)
        d1 (v3/dot ab ap) d2 (v3/dot ac ap)]
    (cond
      (and (<= d1 0.0) (<= d2 0.0)) a
      :else
      (let [bp (v3/neg b) d3 (v3/dot ab bp) d4 (v3/dot ac bp)]
        (cond
          (and (>= d3 0.0) (<= d4 d3)) b
          :else
          (let [vc (- (* d1 d4) (* d3 d2))]
            (if (and (<= vc 0.0) (>= d1 0.0) (<= d3 0.0))
              (v3/add a (v3/scale ab (/ d1 (- d1 d3))))
              (let [cp (v3/neg c) d5 (v3/dot ab cp) d6 (v3/dot ac cp)]
                (cond
                  (and (>= d6 0.0) (<= d5 d6)) c
                  :else
                  (let [vb (- (* d5 d2) (* d1 d6))]
                    (if (and (<= vb 0.0) (>= d2 0.0) (<= d6 0.0))
                      (v3/add a (v3/scale ac (/ d2 (- d2 d6))))
                      (let [va (- (* d3 d6) (* d5 d4))]
                        (if (and (<= va 0.0) (>= (- d4 d3) 0.0) (>= (- d5 d6) 0.0))
                          (v3/add b (v3/scale (v3/sub c b) (/ (- d4 d3) (+ (- d4 d3) (- d5 d6)))))
                          (let [denom (/ 1.0 (+ va vb vc))
                                v (* vb denom) w (* vc denom)]
                            (v3/add a (v3/add (v3/scale ab v) (v3/scale ac w)))))))))))))))))

(defn- point-outside-plane? [a b c d]
  (let [n (v3/cross (v3/sub b a) (v3/sub c a))
        signp (v3/dot (v3/neg a) n)
        signd (v3/dot (v3/sub d a) n)]
    (< (* signp signd) 0.0)))

(defn- closest-on-tetra [a b c d]
  (let [faces [[a b c d] [a c d b] [a d b c] [b d c a]]]
    (reduce
      (fn [{:keys [best best-d2 any-outside?]} [p q r opp]]
        (if (point-outside-plane? p q r opp)
          (let [cp (closest-on-triangle p q r)
                d2 (v3/length-squared cp)]
            (if (< d2 best-d2)
              {:best cp :best-d2 d2 :any-outside? true}
              {:best best :best-d2 best-d2 :any-outside? true}))
          {:best best :best-d2 best-d2 :any-outside? any-outside?}))
      {:best v3/zero :best-d2 ##Inf :any-outside? false}
      faces)))

(defn gjk-closest-vec
  "GJK closest-point vector on the Minkowski difference (a - b) to the
  origin — the separation vector pointing from b toward a. `v3/zero`
  when the shapes intersect."
  [a b]
  (let [dir0 v3/x-axis]
    (loop [simplex [(cso-support a b dir0)] closest (cso-support a b dir0) iter 0]
      (if (>= iter 64)
        closest
        (let [dir (v3/neg closest)]
          (if (< (v3/length-squared dir) 1e-12)
            v3/zero
            (let [p (cso-support a b dir)]
              (if (< (- (v3/dot p dir) (v3/dot closest dir)) 1e-7)
                closest
                (let [simplex' (conj simplex p)
                      n (count simplex')
                      [cp inside?] (case n
                                     1 [(nth simplex' 0) false]
                                     2 [(closest-on-segment (nth simplex' 0) (nth simplex' 1)) false]
                                     3 [(closest-on-triangle (nth simplex' 0) (nth simplex' 1) (nth simplex' 2)) false]
                                     (let [{:keys [best any-outside?]}
                                           (closest-on-tetra (nth simplex' 0) (nth simplex' 1) (nth simplex' 2) (nth simplex' 3))]
                                       [best (not any-outside?)]))]
                  (if inside?
                    v3/zero
                    (let [simplex'' (if (= (count simplex') 4)
                                       (let [worst (apply max-key
                                                           (fn [i] (v3/length-squared (v3/sub (nth simplex' i) cp)))
                                                           (range 4))]
                                         (vec (concat (subvec simplex' 0 worst) (subvec simplex' (inc worst)))))
                                       simplex')]
                      (recur simplex'' cp (inc iter)))))))))))))

(defn gjk-distance
  "GJK closest distance between two convex polytopes (0.0 if intersecting)."
  [a b]
  (v3/length (gjk-closest-vec a b)))

;; ── boolean GJK (origin enclosure) for EPA seeding ───────────────────────

(defn- triple-cross [a b c] (v3/cross (v3/cross a b) c))

(defn- star-line [s]
  (let [ao (v3/neg (nth s 1)) ab (v3/sub (nth s 0) (nth s 1))]
    {:simplex s :dir (triple-cross ab ao ab) :done? false}))

(defn- do-simplex [s]
  (let [ao (v3/neg (last s))]
    (case (count s)
      2 (let [a (nth s 1) b (nth s 0) ab (v3/sub b a)]
          (if (> (v3/dot ab ao) 0.0)
            {:simplex s :dir (triple-cross ab ao ab) :done? false}
            {:simplex [a] :dir ao :done? false}))
      3 (let [a (nth s 2) b (nth s 1) c (nth s 0)
              ab (v3/sub b a) ac (v3/sub c a)
              abc (v3/cross ab ac)]
          (cond
            (> (v3/dot (v3/cross abc ac) ao) 0.0)
            (if (> (v3/dot ac ao) 0.0)
              {:simplex [c a] :dir (triple-cross ac ao ac) :done? false}
              (star-line [b a]))
            (> (v3/dot (v3/cross ab abc) ao) 0.0)
            (star-line [b a])
            (> (v3/dot abc ao) 0.0)
            {:simplex s :dir abc :done? false}
            :else
            {:simplex [b c a] :dir (v3/neg abc) :done? false}))
      4 (let [a (nth s 3) b (nth s 2) c (nth s 1) d (nth s 0)
              abc (v3/cross (v3/sub b a) (v3/sub c a))
              acd (v3/cross (v3/sub c a) (v3/sub d a))
              adb (v3/cross (v3/sub d a) (v3/sub b a))]
          (cond
            (> (v3/dot abc ao) 0.0) {:simplex [c b a] :dir abc :done? false}
            (> (v3/dot acd ao) 0.0) {:simplex [d c a] :dir acd :done? false}
            (> (v3/dot adb ao) 0.0) {:simplex [b d a] :dir adb :done? false}
            :else {:simplex s :dir nil :done? true}))
      {:simplex s :dir nil :done? false})))

(defn- gjk-simplex [a b]
  (loop [s [(cso-support a b v3/x-axis)] dir (v3/neg (cso-support a b v3/x-axis)) iter 0]
    (if (>= iter 64)
      nil
      (let [dir (if (< (v3/length-squared dir) 1e-12) v3/y-axis dir)
            p (cso-support a b dir)]
        (if (< (v3/dot p dir) 0.0)
          nil
          (let [s' (conj s p)
                {:keys [simplex dir done?]} (do-simplex s')]
            (if done?
              simplex
              (recur simplex dir (inc iter)))))))))

(defn gjk-intersects?
  "Boolean convex overlap test."
  [a b]
  (some? (gjk-simplex a b)))

;; ── EPA penetration depth + normal ───────────────────────────────────────

(defn- make-face [verts i j k]
  (let [n0 (v3/cross (v3/sub (nth verts j) (nth verts i)) (v3/sub (nth verts k) (nth verts i)))
        d0 (v3/dot n0 (nth verts i))
        nl (v3/length n0)
        [n dist] (if (> nl 1e-12) [(v3/scale n0 (/ 1.0 nl)) (/ d0 nl)] [n0 d0])]
    (if (< dist 0.0)
      {:i [i k j] :n (v3/neg n) :dist (- dist)}
      {:i [i j k] :n n :dist dist})))

(defn epa-penetration
  "EPA: penetration depth + outward normal (b pushed out of a along
  +normal), or nil if the shapes do not intersect."
  [a b]
  (when-let [tet (gjk-simplex a b)]
    (loop [verts (vec tet)
           faces [(make-face tet 0 1 2) (make-face tet 0 2 3)
                  (make-face tet 0 3 1) (make-face tet 1 3 2)]
           iter 0]
      (if (>= iter 48)
        (when-let [f (apply min-key :dist faces)] [(:dist f) (:n f)])
        (let [closest (apply min-key :dist faces)
              n (:n closest) cd (:dist closest)
              p (cso-support a b n)
              pd (v3/dot p n)]
          (if (< (- pd cd) 1e-4)
            [cd n]
            (let [pi (count verts)
                  verts' (conj verts p)
                  {:keys [horizon kept]}
                  (reduce
                    (fn [{:keys [horizon kept]} f]
                      (if (> (- (v3/dot (:n f) p) (:dist f)) 1e-6)
                        (let [[i0 i1 i2] (:i f)
                              es [[i0 i1] [i1 i2] [i2 i0]]
                              horizon' (reduce
                                         (fn [h [x y]]
                                           (if-let [pos (first (keep-indexed (fn [idx [a b]] (when (and (= a y) (= b x)) idx)) h))]
                                             (vec (concat (subvec h 0 pos) (subvec h (inc pos))))
                                             (conj h [x y])))
                                         horizon es)]
                          {:horizon horizon' :kept kept})
                        {:horizon horizon :kept (conj kept f)}))
                    {:horizon [] :kept []}
                    faces)
                  faces' (into kept (map (fn [[x y]] (make-face verts' x y pi)) horizon))]
              (if (empty? faces')
                [cd n]
                (recur verts' faces' (inc iter))))))))))
