(ns woff.glyf
  "Reconstruction of the transformed `glyf` and `loca` tables (WOFF2 §5.1-5.3).

   This is the transform that makes WOFF2 more than \"WOFF with brotli\". Instead of
   glyph records, the file carries seven parallel substreams — contour counts,
   point counts, point flags, packed coordinate triplets, composite-glyph data,
   bounding boxes, and instructions — which the decoder walks in lockstep, one
   glyph at a time, rebuilding both the glyph records and the `loca` offsets that
   index them.

   Two things follow from the specification and shape everything here:

   - **Bounding boxes are usually absent.** A bitmap says which glyphs carry an
     explicit box; for the others the decoder must compute xMin/yMin/xMax/yMax
     from the point coordinates it just decoded (§5.1).
   - **The output need not be byte-identical to the original.** A glyph's points
     have several valid encodings, and the spec explicitly says a reconstruction
     may differ from the input and that a decoder must not reject a font over
     `origLength`. So this emits the simple, always-valid form — one flag byte per
     point and 16-bit deltas — rather than reproducing whatever the original
     chose. Conformance is therefore checked on the *decoded outlines*, not on
     bytes."
  (:require [woff.woff2-data :as data]))

;; ---------------------------------------------------------------------------
;; Readers
;; ---------------------------------------------------------------------------

(defn- u8 [v i] (nth v i))
(defn- u16 [v i] (+ (* 256 (nth v i)) (nth v (inc i))))
(defn- i16 [v i] (let [x (u16 v i)] (if (>= x 32768) (- x 65536) x)))
(defn- u32 [v i] (+ (* 16777216 (nth v i)) (* 65536 (nth v (+ i 1)))
                    (* 256 (nth v (+ i 2))) (nth v (+ i 3))))

(defn read-255u16
  "WOFF2 §3.1: a one-to-three byte encoding of 0..65535. Returns `[value pos']`.
   The encoding is deliberately non-unique and a decoder must accept every form."
  [v pos]
  (let [code (u8 v pos)]
    (cond
      (= code 253) [(u16 v (inc pos)) (+ pos 3)]
      (= code 255) [(+ 253 (u8 v (inc pos))) (+ pos 2)]
      (= code 254) [(+ 506 (u8 v (inc pos))) (+ pos 2)]
      :else        [code (inc pos)])))

(defn- put16 [out x]
  (let [x (bit-and x 0xffff)]
    (-> out (conj! (unsigned-bit-shift-right x 8)) (conj! (bit-and x 0xff)))))

(defn- bit-set-at?
  "Bitmaps here are MSB-first: glyph 0 is the top bit of the first byte."
  [v base i]
  (pos? (bit-and (u8 v (+ base (quot i 8)))
                 (bit-shift-left 1 (- 7 (mod i 8))))))

;; ---------------------------------------------------------------------------
;; Coordinate triplets (§5.2)
;; ---------------------------------------------------------------------------

(defn- decode-triplet
  "One point's flag byte plus its coordinate bytes → `[on-curve? dx dy pos']`."
  [flag v pos]
  (let [on-curve?            (zero? (bit-and flag 0x80))
        [xb yb dxb dyb xs ys] (nth data/triplets (bit-and flag 0x7f))
        [xv yv pos']
        (cond
          (and (= xb 0) (= yb 8))   [0 (u8 v pos) (inc pos)]
          (and (= xb 8) (= yb 0))   [(u8 v pos) 0 (inc pos)]
          (and (= xb 4) (= yb 4))   (let [b (u8 v pos)]
                                      [(unsigned-bit-shift-right b 4) (bit-and b 0x0f) (inc pos)])
          (and (= xb 8) (= yb 8))   [(u8 v pos) (u8 v (inc pos)) (+ pos 2)]
          (and (= xb 12) (= yb 12)) (let [b0 (u8 v pos) b1 (u8 v (+ pos 1)) b2 (u8 v (+ pos 2))]
                                      [(bit-or (bit-shift-left b0 4) (unsigned-bit-shift-right b1 4))
                                       (bit-or (bit-shift-left (bit-and b1 0x0f) 8) b2)
                                       (+ pos 3)])
          (and (= xb 16) (= yb 16)) [(u16 v pos) (u16 v (+ pos 2)) (+ pos 4)]
          :else (throw (ex-info "woff2: unknown triplet bit widths"
                                {:reason :bad-glyf-transform :x-bits xb :y-bits yb})))]
    [on-curve?
     (if (pos? xb) (* xs (+ xv dxb)) 0)
     (if (pos? yb) (* ys (+ yv dyb)) 0)
     pos']))

;; ---------------------------------------------------------------------------
;; Composite glyph component sizing
;; ---------------------------------------------------------------------------

(def ^:private arg-1-and-2-are-words 0x0001)
(def ^:private we-have-a-scale 0x0008)
(def ^:private more-components 0x0020)
(def ^:private x-and-y-scale 0x0040)
(def ^:private two-by-two 0x0080)
(def ^:private we-have-instructions 0x0100)

(defn- component-bytes
  "Bytes following a component's flag word: glyph index, arguments, and the
   optional scale or 2×2 matrix."
  [flags]
  (+ 2                                                      ; glyphIndex
     (if (pos? (bit-and flags arg-1-and-2-are-words)) 4 2)
     (cond
       (pos? (bit-and flags two-by-two)) 8
       (pos? (bit-and flags x-and-y-scale)) 4
       (pos? (bit-and flags we-have-a-scale)) 2
       :else 0)))

;; ---------------------------------------------------------------------------
;; Reconstruction
;; ---------------------------------------------------------------------------

(defn reconstruct
  "Transformed `glyf` table bytes → `{:glyf [...] :loca [...] :num-glyphs n
   :index-format n :x-mins [...]}`.

   `:x-mins` is returned because the transformed `hmtx` table reconstructs its
   left-side-bearing arrays from exactly these values (§5.4)."
  [tv]
  (let [v (vec tv)]
    (when (< (count v) 36)
      (throw (ex-info "woff2: transformed glyf table is shorter than its header"
                      {:reason :truncated})))
    (let [option-flags  (u16 v 2)
          num-glyphs    (u16 v 4)
          index-format  (u16 v 6)
          sizes         (mapv #(u32 v (+ 8 (* 4 %))) (range 7))
          [n-contour-size n-points-size flag-size glyph-size
           composite-size bbox-size instruction-size] sizes
          bbox-bitmap-size (* 4 (quot (+ num-glyphs 31) 32))
          starts (reductions + 36 [n-contour-size n-points-size flag-size glyph-size
                                   composite-size bbox-size instruction-size])
          [n-contour-start n-points-start flag-start glyph-start
           composite-start bbox-start instruction-start overlap-start] (vec starts)
          bbox-stream-start (+ bbox-start bbox-bitmap-size)
          overlap?      (pos? (bit-and option-flags 0x0001))]
      (when (> overlap-start (count v))
        (throw (ex-info "woff2: transformed glyf substreams run past the table"
                        {:reason :truncated :declared overlap-start :actual (count v)})))
      (loop [gid 0
             pos {:n-points n-points-start :flag flag-start :glyph glyph-start
                  :composite composite-start :bbox bbox-stream-start
                  :instruction instruction-start}
             glyf []
             loca [0]
             x-mins []]
        (if (= gid num-glyphs)
          {:glyf glyf
           :num-glyphs num-glyphs
           :index-format index-format
           :x-mins x-mins
           :loca (vec (mapcat (fn [o]
                                (if (zero? index-format)
                                  (let [h (quot o 2)]
                                    [(unsigned-bit-shift-right h 8) (bit-and h 0xff)])
                                  [(bit-and (unsigned-bit-shift-right o 24) 0xff)
                                   (bit-and (unsigned-bit-shift-right o 16) 0xff)
                                   (bit-and (unsigned-bit-shift-right o 8) 0xff)
                                   (bit-and o 0xff)]))
                              loca))}
          (let [n-contours     (i16 v (+ n-contour-start (* 2 gid)))
                explicit-bbox? (bit-set-at? v bbox-start gid)]
            (cond
              ;; An empty glyph contributes no bytes: loca[n+1] = loca[n].
              (zero? n-contours)
              (do
                (when explicit-bbox?
                  (throw (ex-info "woff2: empty glyph has an explicit bounding box"
                                  {:reason :bad-glyf-transform :glyph gid})))
                (recur (inc gid) pos glyf (conj loca (count glyf)) (conj x-mins 0)))

              (pos? n-contours)
              ;; ---- simple glyph
              (let [[counts p] (loop [i 0 p (:n-points pos) acc []]
                                 (if (= i n-contours)
                                   [acc p]
                                   (let [[c p'] (read-255u16 v p)]
                                     (recur (inc i) p' (conj acc c)))))
                    n-points   (reduce + counts)
                    end-pts    (vec (rest (reductions + 0 counts)))
                    flags      (mapv #(u8 v (+ (:flag pos) %)) (range n-points))
                    [points gp] (loop [i 0 p (:glyph pos) x 0 y 0 acc []]
                                  (if (= i n-points)
                                    [acc p]
                                    (let [[on? dx dy p'] (decode-triplet (nth flags i) v p)
                                          x (+ x dx) y (+ y dy)]
                                      (recur (inc i) p' x y (conj acc [on? x y])))))
                    [ins-len gp] (read-255u16 v gp)
                    instructions (mapv #(u8 v (+ (:instruction pos) %)) (range ins-len))
                    [x-min y-min x-max y-max]
                    (if explicit-bbox?
                      [(i16 v (:bbox pos)) (i16 v (+ (:bbox pos) 2))
                       (i16 v (+ (:bbox pos) 4)) (i16 v (+ (:bbox pos) 6))]
                      ;; §5.1: inferred from every point, on- and off-curve alike.
                      [(reduce min (map second points)) (reduce min (map #(nth % 2) points))
                       (reduce max (map second points)) (reduce max (map #(nth % 2) points))])
                    overlap-bit (if (and overlap? (bit-set-at? v overlap-start gid)) 0x40 0)
                    prev-points (cons [nil 0 0] points)
                    body (persistent!
                          (as-> (transient []) out
                            (put16 out n-contours)
                            (put16 out x-min) (put16 out y-min)
                            (put16 out x-max) (put16 out y-max)
                            (reduce put16 out (map dec end-pts))
                            (put16 out ins-len)
                            (reduce conj! out instructions)
                            (reduce (fn [o [i [on? _ _]]]
                                      (conj! o (bit-or (if on? 0x01 0x00)
                                                       (if (zero? i) overlap-bit 0))))
                                    out (map-indexed vector points))
                            (reduce put16 out (map (fn [[a b]] (- (second b) (second a)))
                                                   (partition 2 1 prev-points)))
                            (reduce put16 out (map (fn [[a b]] (- (nth b 2) (nth a 2)))
                                                   (partition 2 1 prev-points)))))
                    body (into body (repeat (mod (- 4 (mod (count body) 4)) 4) 0))
                    glyf (into glyf body)]
                (recur (inc gid)
                       (assoc pos :n-points p
                              :flag (+ (:flag pos) n-points)
                              :glyph gp
                              :instruction (+ (:instruction pos) ins-len)
                              :bbox (if explicit-bbox? (+ (:bbox pos) 8) (:bbox pos)))
                       glyf (conj loca (count glyf)) (conj x-mins x-min)))

              :else
              ;; ---- composite glyph (nContours = -1)
              (let [[comp-bytes cp instructions?]
                    (loop [p (:composite pos) acc [] instr? false]
                      (let [flags  (u16 v p)
                            n      (component-bytes flags)
                            acc    (into acc (subvec v p (+ p 2 n)))
                            instr? (or instr? (pos? (bit-and flags we-have-instructions)))]
                        (if (pos? (bit-and flags more-components))
                          (recur (+ p 2 n) acc instr?)
                          [acc (+ p 2 n) instr?])))
                    [ins-len gp]  (if instructions?
                                    (read-255u16 v (:glyph pos))
                                    [0 (:glyph pos)])
                    instructions  (mapv #(u8 v (+ (:instruction pos) %)) (range ins-len))]
                (when-not explicit-bbox?
                  (throw (ex-info "woff2: composite glyph without an explicit bounding box"
                                  {:reason :bad-glyf-transform :glyph gid})))
                (let [x-min (i16 v (:bbox pos))
                      body (persistent!
                            (as-> (transient []) out
                              (put16 out 0xffff)
                              (put16 out x-min)
                              (put16 out (i16 v (+ (:bbox pos) 2)))
                              (put16 out (i16 v (+ (:bbox pos) 4)))
                              (put16 out (i16 v (+ (:bbox pos) 6)))
                              (reduce conj! out comp-bytes)
                              (if instructions?
                                (reduce conj! (put16 out ins-len) instructions)
                                out)))
                      body (into body (repeat (mod (- 4 (mod (count body) 4)) 4) 0))
                      glyf (into glyf body)]
                  (recur (inc gid)
                         (assoc pos :composite cp :glyph gp
                                :instruction (+ (:instruction pos) ins-len)
                                :bbox (+ (:bbox pos) 8))
                         glyf (conj loca (count glyf)) (conj x-mins x-min)))))))))))
