(ns woff.sfnt-compare
  "Test-side sfnt reader used to compare a reconstructed font against a reference
   one *semantically*.

   WOFF2 reconstruction is explicitly allowed to differ from the original bytes:
   a glyph's points have several valid encodings, and §5.1 forbids rejecting a
   font over a size mismatch. So `glyf` cannot be compared byte-for-byte with the
   reference decoder's output. What must match is the decoded outline — contour
   ends, on/off-curve flags, absolute coordinates, bounding box, instructions —
   and every other table byte-for-byte.

   This namespace lives in `test/` on purpose: it exists to check the decoder, not
   to be part of it."
  (:refer-clojure :exclude [bytes]))

(defn- u8 [v i] (nth v i))
(defn- u16 [v i] (+ (* 256 (nth v i)) (nth v (inc i))))
(defn- i16 [v i] (let [x (u16 v i)] (if (>= x 32768) (- x 65536) x)))
(defn- u32 [v i] (+ (* 16777216 (nth v i)) (* 65536 (nth v (+ i 1)))
                    (* 256 (nth v (+ i 2))) (nth v (+ i 3))))

(defn table-directory
  "tag → {:offset :length :checksum} for an sfnt."
  [font]
  (let [v (vec font)
        n (u16 v 4)]
    (into {} (for [i (range n)
                   :let [base (+ 12 (* 16 i))]]
               [(apply str (map char (subvec v base (+ base 4))))
                {:checksum (u32 v (+ base 4))
                 :offset (u32 v (+ base 8))
                 :length (u32 v (+ base 12))}]))))

(defn table
  "One table's bytes."
  [font tag]
  (let [dir (table-directory font)
        {:keys [offset length]} (get dir tag)]
    (when offset (subvec (vec font) offset (+ offset length)))))

(defn- loca-offsets [font]
  (let [head (table font "head")
        index-format (i16 head 50)
        maxp (table font "maxp")
        n (u16 maxp 4)
        loca (table font "loca")]
    (vec (for [i (range (inc n))]
           (if (zero? index-format)
             (* 2 (u16 loca (* 2 i)))
             (u32 loca (* 4 i)))))))

(defn glyph
  "Decode one glyph record into `{:contours :bbox :instructions :points}` with
   *absolute* coordinates, or nil for an empty glyph. Composite glyphs return
   their component bytes instead of points."
  [font gid]
  (let [offs (loca-offsets font)
        glyf (table font "glyf")
        from (nth offs gid)
        to   (nth offs (inc gid))]
    (when (> to from)
      (let [g (subvec glyf from to)
            n-contours (i16 g 0)
            bbox [(i16 g 2) (i16 g 4) (i16 g 6) (i16 g 8)]]
        (if (neg? n-contours)
          {:composite? true :bbox bbox :bytes (subvec g 10)}
          (let [end-pts (mapv #(u16 g (+ 10 (* 2 %))) (range n-contours))
                n-points (if (zero? n-contours) 0 (inc (peek end-pts)))
                ins-off (+ 10 (* 2 n-contours))
                ins-len (u16 g ins-off)
                instructions (subvec g (+ ins-off 2) (+ ins-off 2 ins-len))
                flags-start (+ ins-off 2 ins-len)
                ;; flags, expanding the repeat mechanism
                [flags coord-start]
                (loop [p flags-start acc []]
                  (if (>= (count acc) n-points)
                    [acc p]
                    (let [f (u8 g p)]
                      (if (pos? (bit-and f 0x08))
                        (let [r (u8 g (inc p))]
                          (recur (+ p 2) (into acc (repeat (inc r) f))))
                        (recur (inc p) (conj acc f))))))
                flags (vec (take n-points flags))
                ;; x deltas
                [xs p]
                (loop [i 0 p coord-start x 0 acc []]
                  (if (= i n-points)
                    [acc p]
                    (let [f (nth flags i)
                          short? (pos? (bit-and f 0x02))
                          same?  (pos? (bit-and f 0x10))
                          [d p'] (cond
                                   short? [(let [b (u8 g p)] (if same? b (- b))) (inc p)]
                                   same?  [0 p]
                                   :else  [(i16 g p) (+ p 2)])
                          x (+ x d)]
                      (recur (inc i) p' x (conj acc x)))))
                [ys _]
                (loop [i 0 p p y 0 acc []]
                  (if (= i n-points)
                    [acc p]
                    (let [f (nth flags i)
                          short? (pos? (bit-and f 0x04))
                          same?  (pos? (bit-and f 0x20))
                          [d p'] (cond
                                   short? [(let [b (u8 g p)] (if same? b (- b))) (inc p)]
                                   same?  [0 p]
                                   :else  [(i16 g p) (+ p 2)])
                          y (+ y d)]
                      (recur (inc i) p' y (conj acc y)))))]
            {:contours n-contours
             :bbox bbox
             :end-pts end-pts
             :instructions instructions
             :points (mapv (fn [f x y] [(pos? (bit-and f 0x01)) x y]) flags xs ys)}))))))

(defn glyph-count [font] (u16 (table font "maxp") 4))

(defn outlines
  "Every glyph, decoded — the comparable form of a font's `glyf` table."
  [font]
  (mapv #(glyph font %) (range (glyph-count font))))
