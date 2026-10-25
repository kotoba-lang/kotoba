(ns kasane.codec
  "PackBits RLE — the one codec kasane's own native formats (PSD) still use
   directly. DEFLATE/LZW moved out with the extracted formats that needed
   them (see org-ietf-deflate/org-adobe-tiff/org-compuserve-gif/org-iso-pdf)
   as part of the kotoba-lang reverse-domain media/graphics
   standards-substrate split (com-junkawasaki/root)."
  )

(defn packbits
  "Decode PackBits RLE (used by PSD :rle channels).
   `data` = seq of unsigned bytes. Returns a vector of unsigned bytes."
  [data]
  (let [v (vec data) n (count v)]
    (loop [i 0 out []]
      (if (>= i n)
        out
        (let [h (nth v i)]
          (cond
            (= h 128) (recur (inc i) out)                          ; no-op
            (< h 128) (let [cnt (inc h)]                           ; literal run
                        (recur (+ i 1 cnt) (into out (subvec v (inc i) (+ i 1 cnt)))))
            :else     (let [cnt (- 257 h) b (nth v (inc i))]       ; replicate run
                        (recur (+ i 2) (into out (repeat cnt b))))))))))
