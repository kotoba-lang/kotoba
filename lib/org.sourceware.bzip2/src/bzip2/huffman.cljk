(ns bzip2.huffman
  "Canonical Huffman coding as bzip2 uses it, in both directions.

   bzip2 does not transmit codes or a code-length alphabet; it transmits each
   table as a **5-bit starting length followed by a delta walk** (`+1`/`-1`
   steps, one terminator bit per symbol), and the decoder rebuilds the codes
   canonically. Lengths are limited to 20 bits, which is why length generation
   here is the reference's weight-scaling loop rather than package-merge: on
   overflow the weights are halved and the tree rebuilt, exactly as bzip2 does,
   so a pathological block cannot produce a code the format cannot express.

   The decoder side uses bzip2's own `limit`/`base`/`perm` formulation rather
   than a generic canonical decoder, because that is what makes the
   'read one more bit and compare' loop terminate on a corrupt stream."
  (:require [bzip2.bits :as bits]))

(def max-code-len 20)

;; ---------------------------------------------------------------------------
;; Decoding
;; ---------------------------------------------------------------------------

(defn decode-table
  "Build bzip2's decode tables from `lens` (a vector of code lengths, one per
   symbol). Mirrors `hbCreateDecodeTables`."
  [lens]
  (let [alpha (count lens)
        min-len (reduce min lens)
        max-len (reduce max lens)
        perm (vec (for [l (range min-len (inc max-len))
                        s (range alpha)
                        :when (= l (nth lens s))]
                    s))
        ;; base[len+1]++ then prefix-sum
        counts (reduce (fn [acc l] (update acc (inc l) (fnil inc 0)))
                       (vec (repeat (+ max-code-len 2) 0))
                       lens)
        base0 (reduce (fn [acc i] (assoc acc i (+ (nth acc i) (nth acc (dec i)))))
                      counts
                      (range 1 (+ max-code-len 2)))
        [limit base]
        (loop [l min-len v 0 limit (vec (repeat (+ max-code-len 2) 0)) base base0]
          (if (> l max-len)
            [limit base]
            (let [v (+ v (- (nth base0 (inc l)) (nth base0 l)))]
              (recur (inc l) (* 2 v) (assoc limit l (dec v)) base))))
        base (loop [l (inc min-len) base base]
               (if (> l max-len)
                 base
                 (recur (inc l)
                        (assoc base l (- (* 2 (inc (nth limit (dec l))))
                                         (nth base l))))))]
    {:min-len min-len :max-len max-len :limit limit :base base :perm perm}))

(defn read-symbol
  "Decode one symbol from bit reader `r` using `table`."
  [r {:keys [min-len max-len limit base perm]}]
  (loop [l min-len v (bits/read-bits r min-len)]
    (cond
      (> l max-len)
      (throw (ex-info "bzip2: no Huffman code matches" {:reason :bad-huffman-code}))

      (<= v (nth limit l))
      (let [i (- v (nth base l))]
        (when (or (neg? i) (>= i (count perm)))
          (throw (ex-info "bzip2: Huffman code out of range"
                          {:reason :bad-huffman-code :index i})))
        (nth perm i))

      :else
      (recur (inc l) (+ (* 2 v) (bits/read-bit r))))))

;; ---------------------------------------------------------------------------
;; Encoding
;; ---------------------------------------------------------------------------

(defn- tree-lengths
  "Code lengths for `weights` (all >= 1) by repeated merge of the two smallest.
   Alphabets here are at most 258 symbols, so a linear scan for the minimum is
   cheaper than maintaining a heap."
  [weights]
  (let [n (count weights)]
    (if (= n 1)
      [1]
      (loop [nodes (vec (map-indexed (fn [i w] {:w w :leaves #{i}}) weights))
             depths (vec (repeat n 0))]
        (if (= 1 (count nodes))
          depths
          (let [;; two smallest weights
                idx (vec (range (count nodes)))
                [a b] (take 2 (sort-by #(:w (nth nodes %)) idx))
                na (nth nodes a) nb (nth nodes b)
                merged {:w (+ (:w na) (:w nb))
                        :leaves (into (:leaves na) (:leaves nb))}
                rest' (vec (keep-indexed (fn [i v] (when-not (or (= i a) (= i b)) v)) nodes))
                depths (reduce (fn [d l] (assoc d l (inc (nth d l))))
                               depths
                               (:leaves merged))]
            (recur (conj rest' merged) depths)))))))

(defn code-lengths
  "Code lengths for symbol frequencies `freqs`, capped at `max-code-len`.

   Zero-frequency symbols get weight 1 rather than being dropped: bzip2's table
   format has no way to say 'unused', every symbol needs a length of at least 1,
   and the decoder would reject a zero. On overflow the weights are halved and
   the tree rebuilt — the reference's approach, and the reason a block of
   near-uniform noise still produces a legal table. `limit` defaults to the
   format ceiling of 20; the reference encoder uses 17, leaving headroom."
  ([freqs] (code-lengths freqs max-code-len))
  ([freqs limit]
   (loop [w (mapv #(if (zero? %) 1 %) freqs)
          guard 0]
     (let [lens (tree-lengths w)]
       (if (or (<= (reduce max lens) limit) (> guard 20))
         (mapv #(max 1 (min limit %)) lens)
         (recur (mapv #(inc (quot % 2)) w) (inc guard)))))))

(defn codes
  "Canonical codes for `lens` → vector of integers (`hbAssignCodes`)."
  [lens]
  (let [alpha (count lens)
        min-len (reduce min lens)
        max-len (reduce max lens)]
    (loop [l min-len v 0 out (vec (repeat alpha 0))]
      (if (> l max-len)
        out
        (let [[v out] (reduce (fn [[v out] s]
                                (if (= l (nth lens s))
                                  [(inc v) (assoc out s v)]
                                  [v out]))
                              [v out]
                              (range alpha))]
          (recur (inc l) (* 2 v) out))))))

(defn write-lengths!
  "Emit one table as bzip2 does: a 5-bit starting length, then per symbol a
   delta walk of `1 0` (increment) / `1 1` (decrement) pairs terminated by `0`."
  [w lens]
  (bits/write-bits! w 5 (first lens))
  (loop [curr (first lens) s 0]
    (if (= s (count lens))
      w
      (let [target (nth lens s)]
        (cond
          (< curr target) (do (bits/write-bits! w 2 2) (recur (inc curr) s))
          (> curr target) (do (bits/write-bits! w 2 3) (recur (dec curr) s))
          :else (do (bits/write-bit! w 0) (recur curr (inc s))))))))

(defn read-lengths
  "Read one table's code lengths for `alpha` symbols."
  [r alpha]
  (loop [curr (bits/read-bits r 5) s 0 out []]
    (if (= s alpha)
      out
      (if (zero? (bits/read-bit r))
        (do (when (or (< curr 1) (> curr max-code-len))
              (throw (ex-info "bzip2: code length out of range"
                              {:reason :bad-code-length :length curr})))
            (recur curr (inc s) (conj out curr)))
        (let [curr (if (zero? (bits/read-bit r)) (inc curr) (dec curr))]
          (when (or (< curr 1) (> curr max-code-len))
            (throw (ex-info "bzip2: code length out of range"
                            {:reason :bad-code-length :length curr})))
          (recur curr s out))))))
