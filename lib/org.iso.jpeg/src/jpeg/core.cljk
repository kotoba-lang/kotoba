(ns jpeg.core
  "JPEG/JFIF metadata reader (ISO/IEC 10918-1 / ITU-T T.81). Walks marker
   segments to recover dimensions/components/progressive flag cheaply,
   without decoding the entropy-coded DCT scan (see jpeg.decode for
   baseline pixel decode). Pure cljc. Extracted from kotoba-lang/kasane
   (kasane.jpeg, ADR-2606280010) as `org-iso-jpeg`."
  (:require [jpeg.bytes :as b]))

(defn parse
  "Scan JPEG marker segments → {:width :height :components :progressive?
   :markers}. Does not decode pixels."
  [data]
  (let [bv (vec data)
        n  (count bv)]
    (when-not (and (= (nth bv 0) 0xFF) (= (nth bv 1) 0xD8))
      (throw (ex-info "jpeg: missing SOI" {})))
    (loop [i 2 acc {:markers []}]
      (if (>= (inc i) n)
        acc
        (if (not= (nth bv i) 0xFF)
          (recur (inc i) acc)
          (let [m   (nth bv (inc i))
                acc (update acc :markers conj m)]
            (cond
              ;; standalone markers (no length): RSTn, SOI, EOI, TEM
              (or (= m 0xD8) (= m 0xD9) (<= 0xD0 m 0xD7) (= m 0x01))
              (recur (+ i 2) acc)
              ;; SOF0/1 (baseline/extended) or SOF2 (progressive) carry geometry
              (or (= m 0xC0) (= m 0xC1) (= m 0xC2))
              (let [seg (+ i 4)
                    h   (b/uint! (b/cursor (subvec bv (+ seg 1) (+ seg 3))) 2 true)
                    w   (b/uint! (b/cursor (subvec bv (+ seg 3) (+ seg 5))) 2 true)
                    len (b/uint! (b/cursor (subvec bv (+ i 2) (+ i 4))) 2 true)]
                (recur (+ i 2 len)
                       (assoc acc :width w :height h
                              :components (nth bv (+ seg 5)) :progressive? (= m 0xC2))))
              ;; SOS = start of scan; metadata before this point is enough
              (= m 0xDA) (assoc acc :scan-start (+ i 2))
              ;; everything else: length-prefixed segment, skip
              :else
              (let [len (b/uint! (b/cursor (subvec bv (+ i 2) (+ i 4))) 2 true)]
                (recur (+ i 2 len) acc)))))))))
