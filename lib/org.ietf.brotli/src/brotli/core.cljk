(ns brotli.core
  "Brotli decompression (RFC 7932), portable `.cljc`.

   A brotli stream is a window size and then a series of meta-blocks. Each
   meta-block carries its own entropy machinery, which is where brotli's
   complexity lives compared with DEFLATE or even zstd:

   - **three block categories** (literals, insert-and-copy commands, distances),
     each switching between up to 256 *block types* on its own schedule, driven by
     their own prefix codes;
   - **context modelling** for literals: the previous two output bytes pick one of
     64 context IDs, which a context map then maps to one of up to 256 prefix
     codes — so a literal's code depends on what came before it;
   - **a static dictionary** (`brotli.dictionary`): a distance beyond the window
     is a reference into 122,784 bytes of stock words, in any of 121 transformed
     forms;
   - **recent-distance reuse**: sixteen of the distance symbols mean \"the last
     distance, ±1, ±2, ±3\" and friends, and dictionary or reused distances are
     *not* pushed back into the ring buffer.

   Decoding only. There is no brotli encoder here, and there is unlikely to ever
   be one: the format's whole point is expensive-encode/cheap-decode, and this
   workspace's compressing path is `org-ietf-deflate`."
  (:require [brotli.bits :as bits]
            [brotli.data :as data]
            [brotli.dictionary :as dict]
            [brotli.prefix :as prefix]))

;; ---------------------------------------------------------------------------
;; Code tables (RFC 7932 §5, §6) — [extra-bits base]
;; ---------------------------------------------------------------------------

(def ^:private insert-length-code
  [[0 0] [0 1] [0 2] [0 3] [0 4] [0 5] [1 6] [1 8]
   [2 10] [2 14] [3 18] [3 26] [4 34] [4 50] [5 66] [5 98]
   [6 130] [7 194] [8 322] [9 578] [10 1090] [12 2114] [14 6210] [24 22594]])

(def ^:private copy-length-code
  [[0 2] [0 3] [0 4] [0 5] [0 6] [0 7] [0 8] [0 9]
   [1 10] [1 12] [2 14] [2 18] [3 22] [3 30] [4 38] [4 54]
   [5 70] [5 102] [6 134] [7 198] [8 326] [9 582] [10 1094] [24 2118]])

(def ^:private block-length-code
  [[2 1] [2 5] [2 9] [2 13] [3 17] [3 25] [3 33] [3 41]
   [4 49] [4 65] [4 81] [4 97] [5 113] [5 145] [5 177] [5 209]
   [6 241] [6 305] [7 369] [8 497] [9 753] [10 1265] [11 2289] [12 4337]
   [13 8433] [24 16625]])

(def ^:private insert-and-copy-cells
  "§5: which insert/copy code ranges each 64-symbol cell selects, and whether the
   distance is an implicit zero."
  [[0 0 true] [0 8 true] [0 0 false] [0 8 false] [8 0 false] [8 8 false]
   [0 16 false] [16 0 false] [8 16 false] [16 8 false] [16 16 false]])

(def ^:private num-block-length-codes 26)
(def ^:private num-insert-and-copy-codes 704)
(def ^:private num-literal-codes 256)

;; ---------------------------------------------------------------------------
;; Variable-length header fields (§9.1, §9.2, §7.3)
;; ---------------------------------------------------------------------------

(defn- read-wbits [r]
  (if (zero? (bits/read-bit r))
    16
    (let [n (bits/read-bits r 3)]
      (if (pos? n)
        (+ 17 n)                                            ; 1..7 → 18..24
        (let [m (bits/read-bits r 3)]
          (case m
            0 17
            1 (throw (ex-info "brotli: invalid window size code"
                              {:reason :bad-window-size}))
            (+ 8 m)))))))                                   ; 2..7 → 10..15

(defn- read-count
  "§9.2: the 1..11-bit code used for NBLTYPES* and NTREES*."
  [r]
  (if (zero? (bits/read-bit r))
    1
    (let [n (bits/read-bits r 3)]
      (if (zero? n)
        2
        (+ (bit-shift-left 1 n) 1 (bits/read-bits r n))))))

(defn- read-mnibbles [r]
  (case (bits/read-bits r 2)
    0 4, 1 5, 2 6, 3 0))

(defn- read-value
  "A `[extra base]` code plus its extra bits."
  [r table sym]
  (let [[extra base] (nth table sym)]
    (+ base (bits/read-bits r extra))))

(defn- inverse-mtf
  "§7.3 inverse move-to-front."
  [v]
  (loop [i 0 mtf (vec (range 256)) out v]
    (if (>= i (count v))
      out
      (let [index (nth out i)
            value (nth mtf index)]
        (recur (inc i)
               (into [value] (into (subvec mtf 0 index) (subvec mtf (inc index))))
               (assoc out i value))))))

(defn- read-context-map
  "§7.3: RLEMAX, a prefix code, run-length-coded values, then an optional IMTF."
  [r size ntrees]
  (if (< ntrees 2)
    (vec (repeat size 0))
    (let [rlemax (if (zero? (bits/read-bit r)) 0 (inc (bits/read-bits r 4)))
          table  (prefix/read-code r (+ ntrees rlemax))
          values (loop [out []]
                   (if (>= (count out) size)
                     out
                     (let [sym (prefix/read-sym r table)]
                       (cond
                         (zero? sym) (recur (conj out 0))
                         (<= sym rlemax)
                         (let [n (+ (bit-shift-left 1 sym) (bits/read-bits r sym))]
                           (when (> (+ (count out) n) size)
                             (throw (ex-info "brotli: context map run runs past its size"
                                             {:reason :bad-context-map})))
                           (recur (into out (repeat n 0))))
                         :else (recur (conj out (- sym rlemax)))))))
          values (if (pos? (bits/read-bit r)) (inverse-mtf values) values)]
      (when (some #(>= % ntrees) values)
        (throw (ex-info "brotli: context map names a tree that does not exist"
                        {:reason :bad-context-map})))
      values)))

(defn- literal-context-id [mode p1 p2]
  (case mode
    0 (bit-and p1 0x3f)                                     ; LSB6
    1 (unsigned-bit-shift-right p1 2)                       ; MSB6
    2 (bit-or (nth data/lut0 p1) (nth data/lut1 p2))         ; UTF8
    3 (bit-or (bit-shift-left (nth data/lut2 p1) 3) (nth data/lut2 p2))  ; Signed
    (throw (ex-info "brotli: unknown context mode" {:reason :bad-context-mode :mode mode}))))

;; ---------------------------------------------------------------------------
;; Output buffer
;; ---------------------------------------------------------------------------

#?(:clj  (defn- mk-buf [n] (byte-array n))
   :cljs (defn- mk-buf [n] (js/Uint8Array. n)))
#?(:clj  (defn- bget [a i] (bit-and (aget ^bytes a i) 0xff))
   :cljs (defn- bget [a i] (aget a i)))
#?(:clj  (defn- bset! [a i v] (aset-byte a i (unchecked-byte v)))
   :cljs (defn- bset! [a i v] (aset a i v)))
#?(:clj  (defn- bcap [a] (alength ^bytes a))
   :cljs (defn- bcap [a] (.-length a)))

(defn- out-buffer [] {:arr (volatile! (mk-buf 65536)) :len (volatile! 0)})

(defn- out-push! [b v]
  (let [n @(:len b)
        a @(:arr b)]
    (when (>= n (bcap a))
      (let [bigger (mk-buf (* 2 (bcap a)))]
        #?(:clj (System/arraycopy a 0 bigger 0 n)
           :cljs (.set bigger (.subarray a 0 n) 0))
        (vreset! (:arr b) bigger)))
    (bset! @(:arr b) n v)
    (vreset! (:len b) (inc n))
    v))

(defn- out-size [b] @(:len b))
(defn- out-at [b i] (bget @(:arr b) i))

(defn- out->vector [b]
  (let [a @(:arr b) n @(:len b)]
    (persistent! (loop [i 0 acc (transient [])]
                   (if (>= i n) acc (recur (inc i) (conj! acc (bget a i))))))))

;; ---------------------------------------------------------------------------
;; Block-switch state per category
;; ---------------------------------------------------------------------------

(defn- read-block-switch
  "A block-switch command: the new type (relative or absolute) and a new count."
  [r {:keys [type-table count-table ntypes cur prev]}]
  (let [sym (prefix/read-sym r type-table)
        new-type (case sym
                   0 prev
                   1 (mod (inc cur) ntypes)
                   (- sym 2))]
    (when (>= new-type ntypes)
      (throw (ex-info "brotli: block type out of range"
                      {:reason :bad-block-type :type new-type})))
    {:type new-type
     :prev cur
     :count (read-value r block-length-code (prefix/read-sym r count-table))}))

(defn- category
  "Read the per-category header: type code, count code, first count (§9.2)."
  [r ntypes]
  (if (< ntypes 2)
    {:ntypes ntypes :cur 0 :prev 1 :count 16777216}          ; never switches
    (let [type-table  (prefix/read-code r (+ ntypes 2))
          count-table (prefix/read-code r num-block-length-codes)
          cnt         (read-value r block-length-code (prefix/read-sym r count-table))]
      {:ntypes ntypes :cur 0 :prev 1 :count cnt
       :type-table type-table :count-table count-table})))

(defn- maybe-switch!
  "Consume a block-switch command when this category's count has run out."
  [r st]
  (if (pos? (:count st))
    st
    (let [{:keys [type prev count]} (read-block-switch r st)]
      (assoc st :cur type :prev prev :count count))))

;; ---------------------------------------------------------------------------
;; Distances (§4)
;; ---------------------------------------------------------------------------

(def ^:private special-distance
  "Symbols 0..15: which recent distance, and the offset applied to it."
  [[0 0] [1 0] [2 0] [3 0]
   [0 -1] [0 1] [0 -2] [0 2] [0 -3] [0 3]
   [1 -1] [1 1] [1 -2] [1 2] [1 -3] [1 3]])

(defn- decode-distance
  "Turn a distance symbol into a backward distance, given the recent-distance
   ring buffer `dists` (index 0 = most recent)."
  [r sym dists npostfix ndirect]
  (cond
    (< sym 16)
    (let [[which delta] (nth special-distance sym)]
      [(+ (nth dists which) delta) (zero? sym)])

    (< sym (+ 16 ndirect))
    [(- sym 15) false]

    :else
    (let [postfix-mask (dec (bit-shift-left 1 npostfix))
          base         (- sym ndirect 16)
          ndistbits    (inc (unsigned-bit-shift-right base (inc npostfix)))
          hcode        (unsigned-bit-shift-right base npostfix)
          lcode        (bit-and base postfix-mask)
          dextra       (bits/read-bits r ndistbits)
          offset       (- (* (+ 2 (bit-and hcode 1)) (bit-shift-left 1 ndistbits)) 4)]
      [(+ (* (+ offset dextra) (bit-shift-left 1 npostfix)) lcode ndirect 1) false])))

;; ---------------------------------------------------------------------------
;; The decoder
;; ---------------------------------------------------------------------------

(defn- copy-match! [out distance length]
  (let [n (out-size out)]
    (dotimes [i length]
      (out-push! out (out-at out (- (+ n i) distance))))))

(defn decompress
  "Decompress a brotli stream → vector of unsigned bytes.

   Options: `:max-output` (ceiling on produced bytes)."
  ([data] (decompress data nil))
  ([data {:keys [max-output]}]
   (let [r      (bits/reader data)
         wbits  (read-wbits r)
         window (- (bit-shift-left 1 wbits) 16)
         out    (out-buffer)
         dists  (volatile! [4 11 15 16])]                    ; §4: last, 2nd, 3rd, 4th
     (loop []
       (let [islast (pos? (bits/read-bit r))
             empty? (and islast (pos? (bits/read-bit r)))]
         (if empty?
           (out->vector out)
           (let [mnibbles (read-mnibbles r)]
             (if (zero? mnibbles)
               ;; A metadata meta-block: skipped entirely.
               (do
                 (when (pos? (bits/read-bit r))
                   (throw (ex-info "brotli: reserved bit set in a metadata meta-block"
                                   {:reason :bad-metablock})))
                 (let [mskipbytes (bits/read-bits r 2)
                       mskiplen   (if (zero? mskipbytes) 0 (inc (bits/read-bits r (* 8 mskipbytes))))]
                   (when-not (bits/align! r)
                     (throw (ex-info "brotli: non-zero fill bits before metadata"
                                     {:reason :bad-metablock})))
                   (bits/read-bytes! r mskiplen))
                 (if islast (out->vector out) (recur)))
               (let [mlen (inc (bits/read-bits r (* 4 mnibbles)))
                     uncompressed? (and (not islast) (pos? (bits/read-bit r)))]
                 (when (and max-output (> (+ (out-size out) mlen) max-output))
                   (throw (ex-info "brotli: output exceeds limit"
                                   {:reason :output-limit :limit max-output})))
                 (if uncompressed?
                   (do
                     (when-not (bits/align! r)
                       (throw (ex-info "brotli: non-zero fill bits before uncompressed data"
                                       {:reason :bad-metablock})))
                     (doseq [b (bits/read-bytes! r mlen)] (out-push! out b))
                     (if islast (out->vector out) (recur)))

                   ;; A compressed meta-block: read its whole entropy setup.
                   (let [nbltypesl (read-count r)
                         cat-l     (category r nbltypesl)
                         nbltypesi (read-count r)
                         cat-i     (category r nbltypesi)
                         nbltypesd (read-count r)
                         cat-d     (category r nbltypesd)
                         npostfix  (bits/read-bits r 2)
                         ndirect   (bit-shift-left (bits/read-bits r 4) npostfix)
                         ctx-modes (vec (repeatedly nbltypesl #(bits/read-bits r 2)))
                         ntreesl   (read-count r)
                         cmapl     (read-context-map r (* 64 nbltypesl) ntreesl)
                         ntreesd   (read-count r)
                         cmapd     (read-context-map r (* 4 nbltypesd) ntreesd)
                         lit-codes (vec (repeatedly ntreesl #(prefix/read-code r num-literal-codes)))
                         ic-codes  (vec (repeatedly nbltypesi
                                                    #(prefix/read-code r num-insert-and-copy-codes)))
                         dist-alpha (+ 16 ndirect (bit-shift-left 48 npostfix))
                         dist-codes (vec (repeatedly ntreesd #(prefix/read-code r dist-alpha)))
                         start      (out-size out)]
                     (loop [cl cat-l ci cat-i cd cat-d p1 (if (pos? start) (out-at out (dec start)) 0)
                            p2 (if (> start 1) (out-at out (- start 2)) 0)]
                       (if (>= (- (out-size out) start) mlen)
                         nil
                         (let [ci (maybe-switch! r ci)
                               ci (update ci :count dec)
                               sym (prefix/read-sym r (nth ic-codes (:cur ci)))
                               [ins-base copy-base dist0?] (nth insert-and-copy-cells
                                                                (unsigned-bit-shift-right sym 6))
                               ins-code  (+ ins-base (bit-and (unsigned-bit-shift-right sym 3) 7))
                               copy-code (+ copy-base (bit-and sym 7))
                               ins-len   (read-value r insert-length-code ins-code)
                               copy-len  (read-value r copy-length-code copy-code)
                               ;; literals
                               ;; p1/p2 are recomputed from the output below, so
                               ;; only the block-switch state is threaded out.
                               [cl _ _]
                               (loop [k 0 cl cl p1 p1 p2 p2]
                                 (if (= k ins-len)
                                   [cl p1 p2]
                                   (let [cl (maybe-switch! r cl)
                                         cl (update cl :count dec)
                                         cid (literal-context-id (nth ctx-modes (:cur cl)) p1 p2)
                                         tree (nth cmapl (+ (* 64 (:cur cl)) cid))
                                         b (prefix/read-sym r (nth lit-codes tree))]
                                     (out-push! out b)
                                     (recur (inc k) cl b p1))))
                               produced (- (out-size out) start)]
                           (when (> produced mlen)
                             (throw (ex-info "brotli: insert runs past the meta-block length"
                                             {:reason :bad-metablock})))
                           (if (= produced mlen)
                             ;; §9.3: the last command's copy is ignored.
                             nil
                             (let [[cd distance from-ring?]
                                   (if dist0?
                                     [cd (nth @dists 0) true]
                                     (let [cd (maybe-switch! r cd)
                                           cd (update cd :count dec)
                                           cid (min 3 (- copy-len 2))
                                           tree (nth cmapd (+ (* 4 (:cur cd)) cid))
                                           sym (prefix/read-sym r (nth dist-codes tree))
                                           [d zero?] (decode-distance r sym @dists npostfix ndirect)]
                                       [cd d zero?]))
                                   max-dist (min window (out-size out))]
                               (when (<= distance 0)
                                 (throw (ex-info "brotli: distance resolves to zero or negative"
                                                 {:reason :bad-distance :distance distance})))
                               (if (> distance max-dist)
                                 ;; A static dictionary reference.
                                 (let [w (dict/word-for-distance copy-len distance max-dist)]
                                   (when (> (+ produced (count w)) mlen)
                                     (throw (ex-info "brotli: dictionary word runs past the meta-block"
                                                     {:reason :bad-metablock})))
                                   (doseq [b w] (out-push! out b)))
                                 (do
                                   (when (> (+ produced copy-len) mlen)
                                     (throw (ex-info "brotli: copy runs past the meta-block length"
                                                     {:reason :bad-metablock})))
                                   (copy-match! out distance copy-len)
                                   ;; Reused and dictionary distances are not pushed.
                                   (when-not (or from-ring? (> distance max-dist))
                                     (vreset! dists (into [distance] (subvec @dists 0 3))))))
                               (let [n (out-size out)]
                                 (recur cl ci cd
                                        (out-at out (dec n))
                                        (if (> n 1) (out-at out (- n 2)) 0))))))))
                     (when (and max-output (> (out-size out) max-output))
                       (throw (ex-info "brotli: output exceeds limit"
                                       {:reason :output-limit :limit max-output})))
                     (if islast (out->vector out) (recur)))))))))))))
