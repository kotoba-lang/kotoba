(ns gif.codec
  "GIF's own LZW decoder (LSB-first bit order, non-early code-width change —
   widens at next-free-code == 2^width, unlike TIFF/PDF's early-change
   variant). Locked against real Pillow-encoded fixtures. Duplicated
   deliberately from kasane.codec/lzw, kept minimal.")

(defn- lzw-reader [data]
  {:data (vec data) :len (count data) :bp (atom 0) :bi (atom 0)})

(defn- lzw-bits [r n]
  (loop [i 0 acc 0]
    (if (= i n) acc
        (let [bp @(:bp r) bi @(:bi r)]
          (if (>= bp (:len r))
            nil
            (let [byte (nth (:data r) bp)
                  bit  (bit-and (bit-shift-right byte bi) 1)]
              (if (= bi 7) (do (reset! (:bi r) 0) (swap! (:bp r) inc)) (reset! (:bi r) (inc bi)))
              (recur (inc i) (bit-or acc (bit-shift-left bit i)))))))))

(defn lzw
  "Decode a GIF LZW stream (LSB, non-early, given `min-code-size` from the
   image data descriptor) → vector of unsigned bytes."
  [data min-code-size]
  (let [clear (bit-shift-left 1 min-code-size)
        eoi   (inc clear)
        fw    (inc min-code-size)
        base  (mapv vector (range clear))
        fresh (-> base (conj nil) (conj nil))
        r     (lzw-reader data)]
    (loop [width fw, dict fresh, nextc (+ clear 2), prev nil, out (transient [])]
      (let [code (lzw-bits r width)]
        (cond
          (nil? code)    (persistent! out)
          (= code clear) (recur fw fresh (+ clear 2) nil out)
          (= code eoi)   (persistent! out)
          :else
          (let [entry (cond
                        (and (< code (count dict)) (some? (nth dict code))) (nth dict code)
                        (= code nextc) (conj prev (nth prev 0))
                        :else (throw (ex-info "gif.codec/lzw: bad code" {:code code :nextc nextc})))
                out2  (reduce conj! out entry)]
            (if (nil? prev)
              (recur width dict nextc entry out2)
              (let [nextc2 (inc nextc)
                    width2 (if (and (< width 12)
                                    (= nextc2 (bit-shift-left 1 width)))    ; non-early: widen at 2^width exactly
                             (inc width) width)]
                (recur width2 (conj dict (conj prev (nth entry 0))) nextc2 entry out2)))))))))
