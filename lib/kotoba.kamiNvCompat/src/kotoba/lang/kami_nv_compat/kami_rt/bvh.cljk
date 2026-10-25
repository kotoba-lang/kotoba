(ns kotoba.lang.kami-nv-compat.kami-rt.bvh
  "Clean-room ray-tracing core — portable .cljc port of src/kami-rt/bvh.ts. Wave 21.")

(def ^:const node-stride 8)
(def ^:private eps 1e-7)
(def ^:private pos-inf #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity))
(def ^:private neg-inf #?(:clj Double/NEGATIVE_INFINITY :cljs (- js/Infinity)))

(defn- vsub [a b]
  [(- (a 0) (b 0)) (- (a 1) (b 1)) (- (a 2) (b 2))])

(defn- vdot [a b]
  (+ (* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2))))

(defn- vcross [a b]
  [(double (- (* (a 1) (b 2)) (* (a 2) (b 1))))
   (double (- (* (a 2) (b 0)) (* (a 0) (b 2))))
   (double (- (* (a 0) (b 1)) (* (a 1) (b 0))))])

(defn- vnorm [a]
  (let [sq (+ (* (a 0) (a 0)) (* (a 1) (a 1)) (* (a 2) (a 2)))
        d (Math/sqrt sq)
        l (if (zero? d) 1.0 d)]
    [(double (/ (a 0) l)) (double (/ (a 1) l)) (double (/ (a 2) l))]))

(defn triangle-soup
  "Build flat triangle soup from [[v0 v1 v2] ...]. Returns {:verts double-array :count}."
  [triangles]
  (let [n (count triangles)
        verts (double-array (* n 9))]
    (doseq [[t tri] (map-indexed vector triangles)
            vi (range 3)
            :let [v (tri vi)]]
      (aset verts (+ (* t 9) (* vi 3) 0) (v 0))
      (aset verts (+ (* t 9) (* vi 3) 1) (v 1))
      (aset verts (+ (* t 9) (* vi 3) 2) (v 2)))
    {:verts verts :count n}))

(defn- tri-bounds
  [soup tri]
  (let [b (* tri 9)
        v (:verts soup)
        mn (double-array 3 pos-inf)
        mx (double-array 3 neg-inf)]
    (doseq [k (range 3) c (range 3)]
      (let [x (aget v (+ b (* k 3) c))]
        (when (< x (aget mn c)) (aset mn c x))
        (when (> x (aget mx c)) (aset mx c x))))
    (let [cx (* 0.5 (+ (aget mn 0) (aget mx 0)))
          cy (* 0.5 (+ (aget mn 1) (aget mx 1)))
          cz (* 0.5 (+ (aget mn 2) (aget mx 2)))]
      {:min [(aget mn 0) (aget mn 1) (aget mn 2)]
       :max [(aget mx 0) (aget mx 1) (aget mx 2)]
       :centroid [cx cy cz]})))

(defn- build-node!
  "Recursive median-split BVH builder. Mutates tri-index, appends to out-atom.
  Returns node index."
  [tri-index tmin tmax cen out start end]
  (let [mn (double-array 3 pos-inf)
        mx (double-array 3 neg-inf)
        cmn (double-array 3 pos-inf)
        cmx (double-array 3 neg-inf)]
    (doseq [i (range start end) c (range 3)
            :let [t (aget tri-index i)]]
      (when (< ((tmin t) c) (aget mn c)) (aset mn c ((tmin t) c)))
      (when (> ((tmax t) c) (aget mx c)) (aset mx c ((tmax t) c)))
      (when (< ((cen t) c) (aget cmn c)) (aset cmn c ((cen t) c)))
      (when (> ((cen t) c) (aget cmx c)) (aset cmx c ((cen t) c))))
    (let [ext0 (- (aget cmx 0) (aget cmn 0))
          ext1 (- (aget cmx 1) (aget cmn 1))
          ext2 (- (aget cmx 2) (aget cmn 2))
          axis (if (and (>= ext0 ext1) (>= ext0 ext2)) 0 (if (>= ext1 ext2) 1 2))
          ext (case axis 0 ext0 1 ext1 2 ext2)
          span (- end start)
          node-idx (count @out)]
      (swap! out conj
             {:min [(aget mn 0) (aget mn 1) (aget mn 2)]
              :max [(aget mx 0) (aget mx 1) (aget mx 2)]
              :left-first 0 :count 0})
      (if (or (<= span 2) (< ext 1e-9))
        (do
          (swap! out assoc-in [node-idx :left-first] start)
          (swap! out assoc-in [node-idx :count] span))
        (let [mid (+ start (bit-shift-right span 1))
              idxs (for [i (range start end)] (aget tri-index i))
              sorted (vec (sort-by #((cen %) axis) idxs))]
          (doseq [i (range start end)]
            (aset tri-index i (sorted (- i start))))
          (let [left (build-node! tri-index tmin tmax cen out start mid)]
            (build-node! tri-index tmin tmax cen out mid end)
            (swap! out assoc-in [node-idx :left-first] left)
            (swap! out assoc-in [node-idx :count] 0))))
      node-idx)))

(defn build-bvh
  "Build a binary BVH by recursive median split. Returns {:nodes :tri-index :node-count}."
  [soup]
  (let [n (:count soup)
        tri-index (int-array n)]
    (dotimes [i n] (aset tri-index i i))
    (if (zero? n)
      {:nodes (double-array 0) :tri-index tri-index :node-count 0}
      (let [bounds (mapv #(tri-bounds soup %) (range n))
            tmin (mapv :min bounds)
            tmax (mapv :max bounds)
            cen (mapv :centroid bounds)
            out (atom [])]
        (build-node! tri-index tmin tmax cen out 0 n)
        (let [nodes-out @out
              nc (count nodes-out)
              se (int-array nc -1)
              nodes (double-array (* nc node-stride))]
          (letfn [(cend [idx]
                    (let [cached (aget se idx)]
                      (if (>= cached 0)
                        cached
                        (let [res (if (pos? (:count (nodes-out idx)))
                                    idx
                                    (cend (inc (cend (:left-first (nodes-out idx))))))]
                          (aset se idx res)
                          res))))]
            (doseq [i (range nc)
                    :let [o (nodes-out i)
                          base (* i node-stride)]]
              (aset nodes base ((:min o) 0))
              (aset nodes (+ base 1) ((:min o) 1))
              (aset nodes (+ base 2) ((:min o) 2))
              (aset nodes (+ base 4) ((:max o) 0))
              (aset nodes (+ base 5) ((:max o) 1))
              (aset nodes (+ base 6) ((:max o) 2))
              (if (pos? (:count o))
                (do
                  (aset nodes (+ base 3) (double (:left-first o)))
                  (aset nodes (+ base 7) (double (:count o))))
                (do
                  (aset nodes (+ base 3) (double (:left-first o)))
                  (aset nodes (+ base 7) (double (- (+ (cend (:left-first o)) 1))))))))
          {:nodes nodes :tri-index tri-index :node-count nc})))))

(defn look-at
  "Build a pinhole camera. vfov-deg is vertical FOV in degrees; aspect = w/h."
  [eye target up vfov-deg aspect]
  (let [theta (* vfov-deg (/ Math/PI 180.0))
        h (Math/tan (/ theta 2.0))
        vh (* 2.0 h)
        vw (* aspect vh)
        w (vnorm (vsub eye target))
        u (vnorm (vcross up w))
        v (vcross w u)
        hw (/ vw 2.0)
        hv (/ vh 2.0)
        ll0 (- (- (- (eye 0) (* hw (u 0))) (* hv (v 0))) (w 0))
        ll1 (- (- (- (eye 1) (* hw (u 1))) (* hv (v 1))) (w 1))
        ll2 (- (- (- (eye 2) (* hw (u 2))) (* hv (v 2))) (w 2))]
    {:origin eye
     :lower-left [(double ll0) (double ll1) (double ll2)]
     :horizontal [(* vw (u 0)) (* vw (u 1)) (* vw (u 2))]
     :vertical [(* vh (v 0)) (* vh (v 1)) (* vh (v 2))]}))

(defn- intersect-tri
  "Moller-Trumbore ray/triangle intersection. Returns {:t :tri :u :v} or nil."
  [soup tri ro rd t-max]
  (let [b (* tri 9)
        v (:verts soup)
        v0 [(aget v b) (aget v (+ b 1)) (aget v (+ b 2))]
        v1 [(aget v (+ b 3)) (aget v (+ b 4)) (aget v (+ b 5))]
        v2 [(aget v (+ b 6)) (aget v (+ b 7)) (aget v (+ b 8))]
        e1 (vsub v1 v0)
        e2 (vsub v2 v0)
        p (vcross rd e2)
        det (vdot e1 p)]
    (when-not (and (> det (- eps)) (< det eps))
      (let [inv (/ 1.0 det)
            tvec (vsub ro v0)
            uu (* (vdot tvec p) inv)]
        (when (and (>= uu 0) (<= uu 1))
          (let [q (vcross tvec e1)
                vv (* (vdot rd q) inv)]
            (when (and (>= vv 0) (<= (+ uu vv) 1))
              (let [t (* (vdot e2 q) inv)]
                (when (and (> t eps) (<= t t-max))
                  {:t t :tri tri :u uu :v vv})))))))))

;; Known, deliberately unguarded: `inv-d` is infinite when the ray does not move
;; along an axis, so if a node's slab boundary on that axis exactly equals the ray
;; origin the product is `(0.0 * Infinity)` = NaN, and since every NaN comparison
;; is false the node is skipped. No guard is added here because no case could be
;; constructed where it changes a correct answer: origin-on-boundary with a
;; zero-direction component means the ray lies inside that boundary plane, which
;; is already an exact edge graze. A guard nothing exercises is a second lock on a
;; door the first one holds.
(defn- slab-hit
  [nodes base ro inv-d t-max]
  (loop [c 0 tmin 0.0 tmax t-max]
    (if (>= c 3)
      ;; `<=`, not `<`. A flat axis-aligned triangle has a zero-thickness AABB on
      ;; one axis, so a ray passing straight through it enters and leaves that
      ;; slab at the same t and `tmin` equals `tmax`. With a strict `<` the node
      ;; is rejected and the triangle is invisible — which makes every face of an
      ;; axis-aligned box invisible, the most common occluder shape there is.
      ;; This repo's own bvh_test.cljc tilts its fixtures to sidestep it and calls
      ;; the behaviour inherent; it is not. A touching interval is a real
      ;; intersection. Rays that genuinely miss still exit through the per-axis
      ;; `(< tx tn)` test above, which stays strict.
      (<= tmin tmax)
      (let [o (ro c)
            id (inv-d c)
            lo (* (- (aget nodes (+ base c)) o) id)
            hi (* (- (aget nodes (+ base 4 c)) o) id)
            t0 (min lo hi)
            t1 (max lo hi)
            tn (max tmin t0)
            tx (min tmax t1)]
        (if (< tx tn)
          false
          (recur (inc c) tn tx))))))


(defn- trace-leaf
  "Test all triangles in a BVH leaf node. Returns [best best-t]."
  [soup tri-idx first-i cnt ro rd best best-t]
  (loop [i 0 b best bt best-t]
    (if (>= i cnt)
      [b bt]
      (let [h (intersect-tri soup (aget tri-idx (+ first-i i)) ro rd bt)
            nb (if (and h (< (:t h) bt)) h b)
            nt (if (and h (< (:t h) bt)) (:t h) bt)]
        (recur (inc i) nb nt)))))

(defn trace-closest
  "Closest-hit BVH traversal. Returns {:t :tri :u :v} or nil."
  ([soup bvh ro rd]
   (trace-closest soup bvh ro rd pos-inf))
  ([soup bvh ro rd t-max]
   (when (pos? (:node-count bvh))
     (let [inv-d [(/ 1.0 (rd 0)) (/ 1.0 (rd 1)) (/ 1.0 (rd 2))]
           nodes (:nodes bvh)
           tri-idx (:tri-index bvh)
           stack (int-array 64)]
       (loop [sp 1 best nil best-t t-max]
         (if (zero? sp)
           best
           (let [ni (aget stack (dec sp))
                 base (* ni node-stride)]
             (if (not (slab-hit nodes base ro inv-d best-t))
               (recur (dec sp) best best-t)
               (let [cnt (aget nodes (+ base 7))]
                 (if (pos? cnt)
                   (let [fi (aget nodes (+ base 3))
                         [nb nt] (trace-leaf soup tri-idx fi cnt ro rd best best-t)]
                     (recur (dec sp) nb nt))
                   (let [left (int (aget nodes (+ base 3)))
                         right (int (- (aget nodes (+ base 7))))]
                     (aset stack (dec sp) left)
                     (aset stack sp right)
                     (recur (inc sp) best best-t))))))))))))

(defn tri-normal
  "Geometric normal of triangle `tri` in `soup`."
  [soup tri]
  (let [b (* tri 9)
        v (:verts soup)
        v0 [(aget v b) (aget v (+ b 1)) (aget v (+ b 2))]
        v1 [(aget v (+ b 3)) (aget v (+ b 4)) (aget v (+ b 5))]
        v2 [(aget v (+ b 6)) (aget v (+ b 7)) (aget v (+ b 8))]]
    (vnorm (vcross (vsub v1 v0) (vsub v2 v0)))))

(def default-shade
  {:light-dir (vnorm [-0.5 -1.0 -0.3])
   :albedo [0.82 0.82 0.88]
   :bg-top [0.5 0.7 1.0]
   :bg-bottom [1.0 1.0 1.0]
   :ambient 0.2})

(defn trace-image-sync
  "Render w×h RGBA float framebuffer (Lambert shade + sky background)."
  ([soup bvh cam w h]
   (trace-image-sync soup bvh cam w h default-shade))
  ([soup bvh cam w h shade]
   (let [fb (double-array (* w h 4))
         o (:origin cam)
         ll (:lower-left cam)
         hh (:horizontal cam)
         vv (:vertical cam)]
     (doseq [py (range h)
             px (range w)
             :let [s (/ (+ px 0.5) w)
                   tp (/ (+ py 0.5) h)
                   dir (vnorm [(- (+ (ll 0) (* s (hh 0)) (* tp (vv 0))) (o 0))
                               (- (+ (ll 1) (* s (hh 1)) (* tp (vv 1))) (o 1))
                               (- (+ (ll 2) (* s (hh 2)) (* tp (vv 2))) (o 2))])
                   hit (trace-closest soup bvh o dir)
                   rgb (if hit
                         (let [n0 (tri-normal soup (:tri hit))
                               n (if (pos? (vdot n0 dir))
                                   (vec (map - n0))
                                   n0)
                               ld (:light-dir shade)
                               neg-ld (vec (map - ld))
                               diff (max 0.0 (vdot n neg-ld))
                               amb (:ambient shade)
                               lit (+ amb (* (- 1 amb) diff))
                               alb (:albedo shade)]
                           [(* (alb 0) lit) (* (alb 1) lit) (* (alb 2) lit)])
                         (let [bt (:bg-bottom shade)
                               tp2 (:bg-top shade)]
                           [(+ (* (- 1 tp) (bt 0)) (* tp (tp2 0)))
                            (+ (* (- 1 tp) (bt 1)) (* tp (tp2 1)))
                            (+ (* (- 1 tp) (bt 2)) (* tp (tp2 2)))]))
                   off (* (+ (* py w) px) 4)]]
       (aset fb off (rgb 0))
       (aset fb (+ off 1) (rgb 1))
       (aset fb (+ off 2) (rgb 2))
       (aset fb (+ off 3) 1.0))
     fb)))
