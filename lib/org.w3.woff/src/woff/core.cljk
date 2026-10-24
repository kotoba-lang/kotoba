(ns woff.core
  "WOFF 1.0 web font decode (W3C Recommendation). WOFF wraps an SFNT
   (TTF/OTF) with per-table zlib compression, so this reassembles a plain
   SFNT (decompressing each table via org-ietf-deflate) and delegates to
   org-iso-opentype. WOFF2 (Brotli + transforms) is a separate larger
   effort. Extracted from kotoba-lang/kasane (kasane.woff, ADR-2606272100)
   as `org-w3-woff`."
  (:require [woff.bytes :as b]
            [deflate.core :as deflate]
            [opentype.core :as opentype]))

(defn- be   [bv o n] (b/uint! (b/cursor (subvec bv o (+ o n))) n true))
(defn- u16e [n] [(bit-and (bit-shift-right n 8) 0xff) (bit-and n 0xff)])
(defn- u32e [n] [(bit-and (bit-shift-right n 24) 0xff) (bit-and (bit-shift-right n 16) 0xff)
                 (bit-and (bit-shift-right n 8) 0xff) (bit-and n 0xff)])
(defn- pad4 [v] (into (vec v) (repeat (mod (- (count v)) 4) 0)))

(defn ->sfnt
  "Reassemble the wrapped SFNT byte vector from a WOFF1 file."
  [data]
  (let [bv  (vec data)
        sig (b/bytes->ascii (subvec bv 0 4))]
    (when (not= sig "wOFF") (throw (ex-info "woff: bad signature" {:sig sig})))
    (let [flavor (be bv 4 4)
          num    (be bv 12 2)
          tables (->> (range num)
                      (mapv (fn [i]
                              (let [o   (+ 44 (* i 20))
                                    off (be bv (+ o 4) 4)
                                    clen (be bv (+ o 8) 4)
                                    olen (be bv (+ o 12) 4)
                                    raw (subvec bv off (+ off clen))]
                                {:tag  (b/bytes->ascii (subvec bv o (+ o 4)))
                                 :csum (be bv (+ o 16) 4)
                                 :olen olen
                                 :data (if (= clen olen) raw (deflate/inflate raw))})))
                      (sort-by :tag)
                      vec)
          es  (loop [e 0] (if (<= (bit-shift-left 1 (inc e)) num) (recur (inc e)) e))
          sr  (* 16 (bit-shift-left 1 es))
          rs  (- (* num 16) sr)
          placed (first (reduce (fn [[ts off] t]
                                  [(conj ts (assoc t :off off))
                                   (+ off (count (pad4 (:data t))))])
                                [[] (+ 12 (* num 16))] tables))
          header (vec (concat (u32e flavor) (u16e num) (u16e sr) (u16e es) (u16e rs)))
          dir    (vec (mapcat (fn [t] (concat (mapv int (:tag t)) (u32e (:csum t))
                                              (u32e (:off t)) (u32e (:olen t)))) placed))
          body   (vec (mapcat (fn [t] (pad4 (:data t))) placed))]
      (vec (concat header dir body)))))

(defn parse
  "Decode WOFF1 `data` → SFNT metadata (same shape as opentype.core/parse)."
  [data]
  (assoc (opentype/parse (->sfnt data)) :woff true))
