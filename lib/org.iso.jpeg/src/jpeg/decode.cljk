(ns jpeg.decode
  "Baseline JPEG (SOF0) pixel decoder. Pure cljc: marker parse
   (DQT/DHT/SOF0/SOS/DRI) → Huffman entropy decode → dequantize → 8×8 IDCT →
   chroma upsample → YCbCr→RGB. Float IDCT, so output is bit-close (not
   bit-exact) to libjpeg/Pillow. Baseline only; progressive (SOF2) and
   restart-heavy streams are best-effort. Extracted from kotoba-lang/kasane
   (kasane.jpeg.decode, ADR-2606280010) as part of `org-iso-jpeg`."
  (:require [jpeg.bytes :as b]))

(def ^:private zigzag
  [0 1 8 16 9 2 3 10 17 24 32 25 18 11 4 5 12 19 26 33 40 48 41 34 27 20 13 6 7 14 21 28
   35 42 49 56 57 50 43 36 29 22 15 23 30 37 44 51 58 59 52 45 38 31 39 46 53 60 61 54 47 55 62 63])

(defn- cosv [a] #?(:clj (Math/cos a) :cljs (js/Math.cos a)))
(defn- sqrt [a] #?(:clj (Math/sqrt a) :cljs (js/Math.sqrt a)))
(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))

(def ^:private idct-cos
  (vec (for [f (range 8)] (vec (for [x (range 8)] (cosv (/ (* (+ (* 2 x) 1) f PI) 16.0)))))))
(def ^:private c0 (/ 1.0 (sqrt 2.0)))

;; ---- Huffman ----
(defn- build-huff [counts symbols]
  (loop [len 1 k 0 code 0 t {}]
    (if (> len 16)
      t
      (let [c (nth counts (dec len))
            [t2 k2 code2] (loop [i 0 t t k k code code]
                            (if (= i c) [t k code]
                                (recur (inc i) (assoc t [len code] (nth symbols k)) (inc k) (inc code))))]
        (recur (inc len) k2 (bit-shift-left code2 1) t2)))))

;; ---- entropy bit reader (FF00 unstuffing; RST markers skipped) ----
(defn- mk-br [data] {:data (vec data) :len (count data) :p (atom 0) :buf (atom 0) :cnt (atom 0)})

(defn- next-byte [br]
  (let [p @(:p br)]
    (if (>= p (:len br))
      0
      (let [bte (nth (:data br) p)]
        (if (= bte 0xFF)
          (let [n (if (< (inc p) (:len br)) (nth (:data br) (inc p)) 0)]
            (cond
              (= n 0x00)        (do (reset! (:p br) (+ p 2)) 0xFF)
              (<= 0xD0 n 0xD7)  (do (reset! (:p br) (+ p 2)) (next-byte br))   ; RST
              :else             (do (reset! (:p br) (:len br)) 0)))            ; marker → stop
          (do (reset! (:p br) (inc p)) bte))))))

(defn- get-bit [br]
  (when (zero? @(:cnt br)) (reset! (:buf br) (next-byte br)) (reset! (:cnt br) 8))
  (swap! (:cnt br) dec)
  (bit-and (bit-shift-right @(:buf br) @(:cnt br)) 1))

(defn- get-bits [br n] (loop [i 0 v 0] (if (= i n) v (recur (inc i) (bit-or (bit-shift-left v 1) (get-bit br))))))

(defn- align! [br] (reset! (:cnt br) 0))

(defn- extend [v t] (if (and (pos? t) (< v (bit-shift-left 1 (dec t)))) (+ v 1 (- (bit-shift-left 1 t))) v))

(defn- decode-huff [br table]
  (loop [len 1 code 0]
    (let [code (bit-or (bit-shift-left code 1) (get-bit br))]
      (if-let [s (get table [len code])]
        s
        (if (>= len 16) (throw (ex-info "jpeg: bad huffman code" {})) (recur (inc len) code))))))

;; ---- decode one 8×8 block → dequantized natural-order coefficients ----
(defn- decode-block [br dc-tbl ac-tbl qt pred]
  (let [coef (double-array 64)
        t    (decode-huff br dc-tbl)
        diff (extend (get-bits br t) t)
        dc   (+ pred diff)]
    (aset coef 0 (double (* dc (nth qt 0))))
    (loop [k 1]
      (when (<= k 63)
        (let [rs (decode-huff br ac-tbl) r (bit-shift-right rs 4) s (bit-and rs 15)]
          (if (zero? s)
            (when (= r 15) (recur (+ k 16)))                  ; ZRL (else EOB → stop)
            (let [k (+ k r)]
              (when (<= k 63)
                (aset coef (nth zigzag k) (double (* (extend (get-bits br s) s) (nth qt k))))
                (recur (inc k))))))))
    [coef dc]))

(defn- idct->bytes [coef]
  (let [out (int-array 64)]
    (dotimes [y 8]
      (dotimes [x 8]
        (let [s (loop [u 0 acc 0.0]
                  (if (= u 8) acc
                      (recur (inc u)
                             (loop [v 0 a acc]
                               (if (= v 8) a
                                   (let [cu (if (zero? u) c0 1.0)
                                         cv (if (zero? v) c0 1.0)]
                                     (recur (inc v)
                                            (+ a (* cu cv (aget ^doubles coef (+ (* v 8) u))
                                                    (double (get-in idct-cos [u x]))
                                                    (double (get-in idct-cos [v y])))))))))))
              val (+ (Math/round (* 0.25 s)) 128)]
          (aset out (+ (* y 8) x) (min 255 (max 0 val))))))
    out))

(defn- clamp [v] (min 255 (max 0 (int (Math/round (double v))))))

(defn decode-rgb
  "Decode baseline JPEG `data` → {:width :height :rgb [r g b ...]} (row-major)."
  [data]
  (let [bv (vec data) n (count bv)
        u16 (fn [o] (b/uint! (b/cursor (subvec bv o (+ o 2))) 2 true))]
    ;; --- parse markers ---
    (loop [i 2 qt {} huff {} frame nil dri 0]
      (if (>= (inc i) n)
        (throw (ex-info "jpeg: no scan" {}))
        (if (not= (nth bv i) 0xFF)
          (recur (inc i) qt huff frame dri)
          (let [m (nth bv (inc i))]
            (cond
              (= m 0xDB)                                       ; DQT
              (let [len (u16 (+ i 2)) end (+ i 2 len)]
                (recur end
                       (loop [p (+ i 4) qt qt]
                         (if (>= p end) qt
                             (let [pq (bit-shift-right (nth bv p) 4) tq (bit-and (nth bv p) 15)
                                   vals (if (zero? pq)
                                          (mapv #(nth bv (+ p 1 %)) (range 64))
                                          (mapv #(u16 (+ p 1 (* 2 %))) (range 64)))
                                   adv (if (zero? pq) 65 129)]
                               (recur (+ p adv) (assoc qt tq vals)))))
                       huff frame dri))
              (= m 0xC4)                                       ; DHT
              (let [len (u16 (+ i 2)) end (+ i 2 len)]
                (recur end qt
                       (loop [p (+ i 4) huff huff]
                         (if (>= p end) huff
                             (let [tc (bit-shift-right (nth bv p) 4) th (bit-and (nth bv p) 15)
                                   counts (mapv #(nth bv (+ p 1 %)) (range 16))
                                   total (reduce + counts)
                                   syms (mapv #(nth bv (+ p 17 %)) (range total))]
                               (recur (+ p 17 total) (assoc huff [tc th] (build-huff counts syms))))))
                       frame dri))
              (or (= m 0xC0) (= m 0xC1))                       ; SOF0/1 baseline
              (let [seg (+ i 4)
                    h (u16 (+ seg 1)) w (u16 (+ seg 3)) nc (nth bv (+ seg 5))
                    comps (mapv (fn [c] (let [o (+ seg 6 (* c 3))]
                                          {:id (nth bv o)
                                           :h (bit-shift-right (nth bv (+ o 1)) 4)
                                           :v (bit-and (nth bv (+ o 1)) 15)
                                           :tq (nth bv (+ o 2))})) (range nc))]
                (recur (+ i 2 (u16 (+ i 2))) qt huff {:w w :h h :comps comps} dri))
              (= m 0xDD)                                       ; DRI
              (recur (+ i 2 (u16 (+ i 2))) qt huff frame (u16 (+ i 4)))
              (= m 0xDA)                                       ; SOS → decode
              (let [len (u16 (+ i 2)) ns (nth bv (+ i 4))
                    sel (into {} (map (fn [s] (let [o (+ i 5 (* s 2))]
                                                [(nth bv o) {:td (bit-shift-right (nth bv (+ o 1)) 4)
                                                             :ta (bit-and (nth bv (+ o 1)) 15)}]))
                                      (range ns)))
                    scan-start (+ i 2 len)
                    br (mk-br (subvec bv scan-start))
                    {:keys [w h comps]} frame
                    maxh (reduce max (map :h comps)) maxv (reduce max (map :v comps))
                    mcux (quot (+ w (- (* 8 maxh) 1)) (* 8 maxh))
                    mcuy (quot (+ h (- (* 8 maxv) 1)) (* 8 maxv))
                    ;; per-component sample plane
                    planes (atom (into {} (map (fn [c] [(:id c) (int-array (* mcux (:h c) 8 mcuy (:v c) 8))]) comps)))
                    cw (into {} (map (fn [c] [(:id c) (* mcux (:h c) 8)]) comps))
                    dri-int dri]
                (loop [my 0 mx 0 preds (zipmap (map :id comps) (repeat 0)) mcu-count 0]
                  (if (>= my mcuy)
                    nil
                    (let [preds
                          (reduce
                           (fn [preds c]
                             (let [dct (get huff [0 (:td (sel (:id c)))])
                                   act (get huff [1 (:ta (sel (:id c)))])
                                   qt  (get qt (:tq c))
                                   plane (get @planes (:id c))
                                   pw    (get cw (:id c))]
                               (loop [by 0 preds preds]
                                 (if (>= by (:v c)) preds
                                     (recur (inc by)
                                            (loop [bx 0 preds preds]
                                              (if (>= bx (:h c)) preds
                                                  (let [[coef dc] (decode-block br dct act qt (get preds (:id c)))
                                                        px (idct->bytes coef)
                                                        ox (+ (* mx (:h c) 8) (* bx 8))
                                                        oy (+ (* my (:v c) 8) (* by 8))]
                                                    (dotimes [yy 8]
                                                      (dotimes [xx 8]
                                                        (aset ^ints plane (+ (* (+ oy yy) pw) ox xx)
                                                              (aget ^ints px (+ (* yy 8) xx)))))
                                                    (recur (inc bx) (assoc preds (:id c) dc))))))))))
                           preds comps)
                          mcu-count (inc mcu-count)
                          restart? (and (pos? dri-int) (zero? (mod mcu-count dri-int)))]
                      (when restart? (align! br))
                      (let [preds (if restart? (zipmap (map :id comps) (repeat 0)) preds)
                            nx (inc mx)]
                        (if (>= nx mcux) (recur (inc my) 0 preds mcu-count)
                            (recur my nx preds mcu-count))))))
                ;; --- upsample + color convert ---
                (let [comp-by-idx comps
                      get-sample (fn [c x y]
                                   (let [pw (get cw (:id c))
                                         sx (quot (* x (:h c)) maxh)
                                         sy (quot (* y (:v c)) maxv)]
                                     (aget ^ints (get @planes (:id c)) (+ (* sy pw) sx))))
                      rgb (int-array (* w h 3))]
                  (dotimes [y h]
                    (dotimes [x w]
                      (let [yc (get-sample (nth comp-by-idx 0) x y)
                            [r g bl]
                            (if (= (count comps) 1)
                              [yc yc yc]
                              (let [cb (- (get-sample (nth comp-by-idx 1) x y) 128)
                                    cr (- (get-sample (nth comp-by-idx 2) x y) 128)]
                                [(clamp (+ yc (* 1.402 cr)))
                                 (clamp (- yc (* 0.344136 cb) (* 0.714136 cr)))
                                 (clamp (+ yc (* 1.772 cb)))]))
                            o (* (+ (* y w) x) 3)]
                        (aset ^ints rgb o r) (aset ^ints rgb (+ o 1) g) (aset ^ints rgb (+ o 2) bl))))
                  {:width w :height h :rgb (vec rgb)}))
              :else (recur (+ i 2 (u16 (+ i 2))) qt huff frame dri))))))))
