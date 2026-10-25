(ns bzip2.encode
  "bzip2 compression.

   This is the first *real* entropy-coding encoder in this workspace's
   compression plane — deflate aside, the other formats here write stored or
   uncompressed containers and say so. bzip2 is the one where writing is
   tractable, because there is no match finder to price: the pipeline is
   RLE1 → BWT → MTF → RLE2 → multi-table Huffman, and every stage is decided by
   counting rather than by searching.

   The multi-table stage follows the reference: pick 2-6 tables by symbol count,
   seed them by splitting the alphabet into equal-frequency chunks, then iterate
   four times, assigning each group of 50 symbols to whichever table codes it
   most cheaply and rebuilding the tables from the resulting counts. Skipping
   that iteration is what separates a conformant-but-pointless encoder from one
   whose output is the size bzip2 users expect.

   Block CRCs are computed over the bytes *before* RLE1, which is easy to get
   wrong: the CRC in the stream covers the user's data, not the run-coded form."
  (:require [bzip2.bits :as bits]
            [bzip2.bwt :as bwt]
            [bzip2.crc :as crc]
            [bzip2.huffman :as huff]))

(def ^:private encoder-max-code-len 17)
(def ^:private group-size 50)
(def ^:private n-iters 4)

;; ---------------------------------------------------------------------------
;; RLE1, and the block split that must respect it
;; ---------------------------------------------------------------------------

(defn- rle1-groups
  "Run-length code `data` into indivisible groups.

   Each group is `[orig-count rle1-bytes]`. A run of four or more equal bytes
   becomes four copies plus a count byte, and that five-byte group must never be
   split across a block boundary — a decoder reading the count byte from the
   next block would corrupt silently rather than fail."
  [data]
  (let [n (count data)]
    (loop [i 0 out (transient [])]
      (if (>= i n)
        (persistent! out)
        (let [b (nth data i)
              run (loop [j i] (if (and (< j n) (= b (nth data j))) (recur (inc j)) (- j i)))
              out' (loop [left run acc out]
                     (if (zero? left)
                       acc
                       (let [t (min left 255)]
                         (recur (- left t)
                                (conj! acc (if (>= t 4)
                                             [t (into [b b b b] [(- t 4)])]
                                             [t (vec (repeat t b))]))))))]
          (recur (+ i run) out'))))))

(defn- split-blocks
  "Pack RLE1 groups into blocks of at most `limit` coded bytes →
   seq of `{:rle1 [...] :orig [...]}`, where `:orig` is the pre-RLE1 form the
  block CRC is computed over."
  [data limit]
  (let [groups (rle1-groups data)]
    (loop [gs (seq groups) cur [] cur-orig [] out []]
      (if-not gs
        (if (seq cur) (conj out {:rle1 cur :orig cur-orig}) out)
        (let [[cnt bs] (first gs)
              b (first bs)]
          (if (and (seq cur) (> (+ (count cur) (count bs)) limit))
            (recur gs [] [] (conj out {:rle1 cur :orig cur-orig}))
            (recur (next gs)
                   (into cur bs)
                   (into cur-orig (repeat cnt b))
                   out)))))))

;; ---------------------------------------------------------------------------
;; MTF + RLE2
;; ---------------------------------------------------------------------------

(defn- mtf-rle2
  "Move-to-front and run-code the BWT output.

   Returns `{:symbols [...] :used [...] :freqs [...]}` where `symbols` ends with
   EOB. Runs of MTF position 0 — by far the most common symbol after a BWT —
   are coded as RUNA/RUNB in bijective base 2, so a run of length 1 costs one
   symbol and a run of 1000 costs ten."
  [last-column]
  (let [used (vec (sort (distinct last-column)))
        alpha (+ (count used) 2)
        eob (dec alpha)]
    (letfn [(emit-zeros [out z]
              (if (zero? z)
                out
                (loop [z (dec z) out out]
                  (let [out (conj! out (if (odd? z) 1 0))]
                    (if (< z 2) out (recur (quot (- z 2) 2) out))))))]
      (let [[syms _ z]
            (reduce (fn [[out mtf z] b]
                      (let [idx (loop [i 0] (if (= b (nth mtf i)) i (recur (inc i))))]
                        (if (zero? idx)
                          [out mtf (inc z)]
                          [(conj! (emit-zeros out z) (inc idx))
                           (into [b] (concat (subvec mtf 0 idx) (subvec mtf (inc idx))))
                           0])))
                    [(transient []) used 0]
                    last-column)
            syms (persistent! (conj! (emit-zeros syms z) eob))
            freqs (reduce (fn [f s] (assoc f s (inc (nth f s))))
                          (vec (repeat alpha 0))
                          syms)]
        {:symbols syms :used used :freqs freqs :alpha alpha}))))

;; ---------------------------------------------------------------------------
;; Table selection — the reference's four-iteration assignment
;; ---------------------------------------------------------------------------

(defn- table-count [n-mtf]
  (cond (< n-mtf 200) 2
        (< n-mtf 600) 3
        (< n-mtf 1200) 4
        (< n-mtf 2400) 5
        :else 6))

(defn- seed-tables
  "Seed `n-groups` tables by cutting the alphabet into chunks of roughly equal
   cumulative frequency; symbols inside a table's chunk cost 0, outside 15."
  [freqs alpha n-groups n-mtf]
  (loop [part n-groups gs 0 rem-f n-mtf out []]
    (if (zero? part)
      (vec (reverse out))
      (let [t-freq (quot rem-f part)
            [ge a-freq] (loop [ge (dec gs) a 0]
                          (if (and (< a t-freq) (< ge (dec alpha)))
                            (recur (inc ge) (+ a (nth freqs (inc ge))))
                            [ge a]))
            [ge a-freq] (if (and (> ge gs) (not= part n-groups) (not= part 1)
                                 (odd? (- n-groups part)))
                          [(dec ge) (- a-freq (nth freqs ge))]
                          [ge a-freq])
            lens (mapv (fn [v] (if (and (>= v gs) (<= v ge)) 0 15)) (range alpha))]
        (recur (dec part) (inc ge) (- rem-f a-freq) (conj out lens))))))

(defn- assign-tables
  "Iterate table assignment: cost every 50-symbol group against every table,
   take the cheapest, then rebuild each table from the counts it accumulated."
  [symbols freqs alpha n-groups]
  (let [n-mtf (count symbols)
        groups (vec (partition-all group-size symbols))]
    (loop [lens (seed-tables freqs alpha n-groups n-mtf)
           iter 0]
      (let [{:keys [sel rfreq]}
            (reduce (fn [{:keys [sel rfreq]} g]
                      (let [costs (mapv (fn [l] (reduce + (map #(nth l %) g))) lens)
                            best (loop [t 1 best 0]
                                   (if (= t n-groups)
                                     best
                                     (recur (inc t)
                                            (if (< (nth costs t) (nth costs best)) t best))))
                            rf (update rfreq best
                                       (fn [f] (reduce (fn [f s] (assoc f s (inc (nth f s)))) f g)))]
                        {:sel (conj sel best) :rfreq rf}))
                    {:sel [] :rfreq (vec (repeat n-groups (vec (repeat alpha 0))))}
                    groups)
            lens' (mapv #(huff/code-lengths % encoder-max-code-len) rfreq)]
        (if (= (inc iter) n-iters)
          {:lens lens' :selectors sel}
          (recur lens' (inc iter)))))))

;; ---------------------------------------------------------------------------
;; Block and stream emission
;; ---------------------------------------------------------------------------

(defn- write-symbol-map! [w used]
  (let [used-set (set used)
        ranges (vec (for [i (range 16)]
                      (some #(contains? used-set (+ (* 16 i) %)) (range 16))))]
    (bits/write-bits! w 16 (reduce (fn [acc i]
                                     (+ (* 2 acc) (if (nth ranges i) 1 0)))
                                   0 (range 16)))
    (doseq [i (range 16) :when (nth ranges i)]
      (bits/write-bits! w 16 (reduce (fn [acc j]
                                       (+ (* 2 acc)
                                          (if (contains? used-set (+ (* 16 i) j)) 1 0)))
                                     0 (range 16))))))

(defn- write-selectors! [w selectors n-groups]
  (bits/write-bits! w 15 (count selectors))
  ;; move-to-front code them, then write each in unary
  (loop [s (seq selectors) order (vec (range n-groups))]
    (when s
      (let [v (first s)
            j (loop [i 0] (if (= v (nth order i)) i (recur (inc i))))]
        (dotimes [_ j] (bits/write-bit! w 1))
        (bits/write-bit! w 0)
        (recur (next s)
               (into [v] (concat (subvec order 0 j) (subvec order (inc j)))))))))

(defn- write-block! [w {:keys [rle1 orig]}]
  (let [block-crc (crc/crc32 orig)
        {:keys [last-column orig-ptr]} (bwt/forward (vec rle1))
        {:keys [symbols used freqs alpha]} (mtf-rle2 last-column)
        n-groups (table-count (count symbols))
        {:keys [lens selectors]} (assign-tables symbols freqs alpha n-groups)
        codes (mapv huff/codes lens)]
    (bits/write-u48! w 0x314159265359)
    (bits/write-u32! w block-crc)
    (bits/write-bit! w 0)                                   ; never randomised
    (bits/write-bits! w 24 orig-ptr)
    (write-symbol-map! w used)
    (bits/write-bits! w 3 n-groups)
    (write-selectors! w selectors n-groups)
    (doseq [l lens] (huff/write-lengths! w l))
    ;; the symbols themselves, switching table every 50
    (loop [ss (seq symbols) gi 0 pos 0]
      (when ss
        (let [t (nth selectors gi)
              len (nth (nth lens t) (first ss))
              code (nth (nth codes t) (first ss))]
          (bits/write-bits! w len code)
          (if (= (inc pos) group-size)
            (recur (next ss) (inc gi) 0)
            (recur (next ss) gi (inc pos))))))
    block-crc))

(defn compress
  "Compress `data` (unsigned bytes) into a bzip2 stream → a vector of unsigned
   bytes.

   `:level` 1-9 (default 9) sets the block size to level x 100,000 bytes, as
   `bzip2 -1` .. `bzip2 -9` do."
  ([data] (compress data {}))
  ([data {:keys [level] :or {level 9}}]
   (when (or (< level 1) (> level 9))
     (throw (ex-info "bzip2: level outside 1..9" {:reason :bad-level :level level})))
   (let [w (bits/writer)
         limit (- (* level 100000) 20)
         blocks (split-blocks (vec data) limit)]
     (bits/write-bits! w 8 0x42)
     (bits/write-bits! w 8 0x5a)
     (bits/write-bits! w 8 0x68)
     (bits/write-bits! w 8 (+ 0x30 level))
     (let [combined (reduce (fn [acc blk] (crc/combine acc (write-block! w blk))) 0 blocks)]
       (bits/write-u48! w 0x177245385090)
       (bits/write-u32! w combined)
       (bits/finish! w)))))
