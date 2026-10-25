(ns zstd.huff
  "Huffman decoding for zstd's literals section (RFC 8878 §4.2).

   Two things distinguish it from DEFLATE's Huffman:

   - **The table is described by *weights*, not code lengths.** A weight `w`
     means the symbol's code is `maxBits + 1 - w` bits long and occupies
     `2^(w-1)` table slots. The weight of the *last* symbol is never transmitted:
     it is whatever makes the total a power of two, which is also the integrity
     check on the description.
   - **The weights themselves may be FSE-compressed**, with two interleaved FSE
     states, so decoding a literals block can mean running one entropy coder to
     build the table for another.

   Decoding a symbol peeks `maxBits` bits, indexes the table, and consumes only
   the bits that symbol actually used."
  (:require [zstd.bits :as bits]
            [zstd.fse :as fse]))

(defn- highbit [x]
  (loop [i 31]
    (cond (neg? i) 0
          (pos? (bit-and x (bit-shift-left 1 i))) i
          :else (recur (dec i)))))

(def ^:private pow2 (vec (reductions * 1 (repeat 32 2))))

(defn- decode-weights
  "FSE-coded weights, two interleaved states. The stream ends when the bits run
   out; both states then still hold one symbol each, which are the final two
   weights."
  [r table accuracy-log]
  (let [s1 (fse/init-state r accuracy-log)
        s2 (fse/init-state r accuracy-log)]
    (loop [s1 s1 s2 s2 out [] turn 0]
      (when (> (count out) 255)
        (throw (ex-info "zstd: Huffman weight stream does not terminate"
                        {:reason :bad-huffman-table})))
      ;; Mirror the reference's order: emit, *then* update (which consumes the
      ;; bits), and only then test for exhaustion. Testing before the update
      ;; stops one weight early — and one missing weight makes the total fail the
      ;; power-of-two check with no hint as to why.
      (let [st   (if (zero? turn) s1 s2)
            out  (conj out (fse/symbol-at table st))
            st'  (fse/next-state r table st)]
        (if (bits/rev-overflow? r)
          (conj out (fse/symbol-at table (if (zero? turn) s2 s1)))
          (if (zero? turn)
            (recur st' s2 out 1)
            (recur s1 st' out 0)))))))

(defn- build
  "Weights → `{:table [...] :max-bits n}`. The table is indexed by `max-bits`
   peeked bits."
  [weights]
  (let [total (reduce + (map #(if (pos? %) (nth pow2 (dec %)) 0) weights))]
    (when (zero? total)
      (throw (ex-info "zstd: Huffman table has no symbols"
                      {:reason :bad-huffman-table})))
    (let [max-bits (inc (highbit total))
          left     (- (nth pow2 max-bits) total)]
      (when (or (<= left 0) (not= left (nth pow2 (highbit left))))
        (throw (ex-info "zstd: Huffman weights do not sum to a power of two"
                        {:reason :bad-huffman-table :total total :left left})))
      (let [ws         (conj (vec weights) (inc (highbit left)))
            table-size (nth pow2 max-bits)
            table
            (first
             (reduce
              (fn [[t pos] w]
                (reduce (fn [[t pos] s]
                          (let [nb    (- (inc max-bits) w)
                                slots (nth pow2 (dec w))]
                            [(reduce (fn [t i] (assoc t (+ pos i) {:symbol s :nb-bits nb}))
                                     t (range slots))
                             (+ pos slots)]))
                        [t pos]
                        ;; symbols with this weight, in increasing symbol order
                        (keep-indexed (fn [i x] (when (= x w) i)) ws)))
              [(vec (repeat table-size nil)) 0]
              ;; RFC 8878 §4.2.1.3: "starting from the *lowest* Weight, prefix
              ;; codes are distributed in sequential order" — longest codes
              ;; first. Filling from the highest weight instead still produces a
              ;; valid prefix code, just a different one, so the table looks
              ;; healthy and decodes confident nonsense.
              (range 1 (inc max-bits))))]
        (when (some nil? table)
          (throw (ex-info "zstd: Huffman table is not fully populated"
                          {:reason :bad-huffman-table})))
        {:table table :max-bits max-bits :weights ws}))))

(defn read-table
  "Parse a Huffman table description starting at byte `from`.

   Returns `{:table ... :max-bits ... :end <byte offset past the description>}`."
  [data from]
  (let [v      (vec data)
        header (nth v from)]
    (if (>= header 128)
      ;; Direct representation: (header - 127) weights, four bits each.
      (let [n      (- header 127)
            nbytes (quot (inc n) 2)
            ws     (vec (for [i (range n)]
                          (let [b (nth v (+ from 1 (quot i 2)))]
                            (if (even? i)
                              (unsigned-bit-shift-right b 4)
                              (bit-and b 0x0f)))))]
        (assoc (build ws) :end (+ from 1 nbytes)))
      ;; FSE-compressed weights; `header` is the compressed size in bytes.
      (let [{:keys [counts accuracy-log end]} (fse/read-ncount v (inc from) 255)
            table (fse/build-table counts accuracy-log)
            stop  (+ from 1 header)
            r     (bits/rev-reader v end stop)
            ws    (decode-weights r table accuracy-log)]
        (assoc (build ws) :end stop)))))

(defn decode-symbol
  "One literal from a backward bitstream."
  [r {:keys [table max-bits]}]
  (let [idx (bits/rev-peek r max-bits)
        e   (nth table idx)]
    (bits/rev-skip! r (:nb-bits e))
    (:symbol e)))
