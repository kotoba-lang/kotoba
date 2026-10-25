(ns gif.core
  "GIF (CompuServe GIF89a) decode: header/LSD via the grammar engine, then a
   byte scan for image separators (0x2C) to count frames, plus first-frame
   LZW pixel decode. Extracted from kotoba-lang/kasane (kasane.gif,
   ADR-2606272100) as `org-compuserve-gif`."
  (:require [gif.decode :as d]
            [gif.codec :as codec]))

(defn parse
  "Parse GIF `data` with `grammar` (resources/gif/grammar.edn). Returns
   {:width :height :frames :version :global-color-table?}."
  [grammar data]
  (let [bv  (vec data)
        hdr (d/decode grammar bv)]
    (when-not (= "GIF8" (subs (:magic hdr) 0 4))
      (throw (ex-info "gif: bad signature" {:magic (:magic hdr)})))
    {:version              (:magic hdr)
     :width                (:width hdr)
     :height               (:height hdr)
     :global-color-table?  (bit-test (:flags hdr) 7)
     :frames               (count (filter #(= % 0x2C) bv))}))   ; 0x2C = Image Separator

(defn- skip-subblocks [bv i]
  (loop [j i] (let [len (nth bv j)] (if (zero? len) (inc j) (recur (+ j 1 len))))))

(defn- u16le [bv o] (+ (nth bv o) (* 256 (nth bv (inc o)))))

(defn- deinterlace
  "Reorder interlaced GIF rows (4-pass scheme) into row-major."
  [linear w h]
  (let [rows   (vec (partition w linear))
        order  (vec (concat (range 0 h 8) (range 4 h 8) (range 2 h 4) (range 1 h 2)))
        placed (reduce (fn [m k] (assoc m (nth order k) (nth rows k))) {} (range (count rows)))]
    (vec (mapcat #(get placed %) (range h)))))

(defn first-frame-indices
  "Decode the first frame's palette indices (LZW, LSB, non-early) → row-major
   color-table indices. Handles the GIF interlace flag (4-pass de-ordering).
   R0: first frame only."
  [data]
  (let [bv       (vec data)
        w        (u16le bv 6)
        h        (u16le bv 8)
        flags    (nth bv 10)
        gct-size (if (bit-test flags 7) (* 3 (bit-shift-left 1 (inc (bit-and flags 7)))) 0)
        imgsep   (loop [i (+ 13 gct-size)]
                   (let [b (nth bv i)]
                     (cond (= b 0x2C) i
                           (= b 0x21) (recur (skip-subblocks bv (+ i 2)))   ; extension block
                           :else (throw (ex-info "gif: no image descriptor" {:byte b})))))
        dflags   (nth bv (+ imgsep 9))
        interlace? (bit-test dflags 6)
        lct-size (if (bit-test dflags 7) (* 3 (bit-shift-left 1 (inc (bit-and dflags 7)))) 0)
        mcs-pos  (+ imgsep 10 lct-size)
        mcs      (nth bv mcs-pos)
        lzwdata  (loop [j (inc mcs-pos) acc []]
                   (let [len (nth bv j)]
                     (if (zero? len) acc (recur (+ j 1 len) (into acc (subvec bv (inc j) (+ j 1 len)))))))
        linear   (codec/lzw lzwdata mcs)]
    (if interlace? (deinterlace linear w h) linear)))
