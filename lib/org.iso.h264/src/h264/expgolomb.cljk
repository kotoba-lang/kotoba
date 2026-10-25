(ns h264.expgolomb
  "MSB-first bit reader + Exp-Golomb ue(v)/se(v) decode (H.264 §9.1), the
   entropy code SPS/PPS/slice-header fields use. Pure cljc.

   New implementation as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  )

(defn reader [data]
  {:data (vec data) :len (count data) :bytepos (atom 0) :bitpos (atom 0)})

(defn bit! [r]
  (let [bp @(:bytepos r) bi @(:bitpos r)]
    (when (>= bp (:len r)) (throw (ex-info "expgolomb: bit EOF" {})))
    (let [byte (nth (:data r) bp)
          v    (bit-and (bit-shift-right byte (- 7 bi)) 1)]
      (if (= bi 7) (do (reset! (:bitpos r) 0) (swap! (:bytepos r) inc))
          (reset! (:bitpos r) (inc bi)))
      v)))

(defn bits! [r n]
  (loop [i 0 acc 0] (if (= i n) acc (recur (inc i) (bit-or (bit-shift-left acc 1) (bit! r))))))

(defn ue!
  "Unsigned Exp-Golomb: count leading zero bits, then read that many more
   bits as the low-order part. 2^leadingZeroBits - 1 + readBits."
  [r]
  (let [lz (loop [n 0] (if (zero? (bit! r)) (recur (inc n)) n))]
    (if (zero? lz) 0 (+ (dec (bit-shift-left 1 lz)) (bits! r lz)))))

(defn se!
  "Signed Exp-Golomb, mapped from ue(v) per H.264 §9.1.1: codeNum k → value
   (-1)^(k+1) * ceil(k/2)."
  [r]
  (let [k (ue! r)
        m (bit-shift-right (inc k) 1)]
    (if (odd? k) m (- m))))

(defn flag! [r] (bit! r))

(defn byte-aligned?
  "True iff `r` is currently positioned at a byte boundary (bitpos 0) —
   H.264 §7.2's `byte_aligned()`, needed by CABAC's `slice_data()`
   `cabac_alignment_one_bit` (see `h264.cabac/byte-align!`)."
  [r]
  (zero? @(:bitpos r)))

;; --- encode side (Wave 2 addition, kotoba-lang/root ADR-2607121400) ---
;; Bit writer mirroring `reader`/`bit!`/`bits!` above: accumulates bits
;; MSB-first into whole bytes. `bytes!` finalizes (flushes a partial byte,
;; zero-padded) and returns the accumulated byte vector.

(defn writer []
  {:out (atom []) :cur (atom 0) :nbits (atom 0)})

(defn write-bit! [w bit]
  (swap! (:cur w) #(bit-or (bit-shift-left % 1) (bit-and bit 1)))
  (swap! (:nbits w) inc)
  (when (= 8 @(:nbits w))
    (swap! (:out w) conj @(:cur w))
    (reset! (:cur w) 0)
    (reset! (:nbits w) 0))
  nil)

(defn write-bits!
  "Write the low `n` bits of `v`, MSB first."
  [w n v]
  (dotimes [i n] (write-bit! w (bit-and (bit-shift-right v (- n i 1)) 1))))

(defn- bit-length [v] (loop [v v n 0] (if (zero? v) n (recur (bit-shift-right v 1) (inc n)))))

(defn write-ue!
  "Unsigned Exp-Golomb encode of non-negative `v` — inverse of `ue!`.
   codeNum = v; write (bit-length(codeNum+1) - 1) leading zero bits, then
   codeNum+1 itself in bit-length(codeNum+1) bits (MSB first) — the leading
   `1` of that value is the Exp-Golomb stop bit, matching `ue!`'s read
   order exactly."
  [w v]
  (let [code (inc v)
        nbits (bit-length code)
        leading-zeros (dec nbits)]
    (dotimes [_ leading-zeros] (write-bit! w 0))
    (write-bits! w nbits code)))

(defn write-se!
  "Signed Exp-Golomb encode — inverse of `se!` (H.264 §9.1.1 codeNum mapping)."
  [w v]
  (write-ue! w (if (<= v 0) (* -2 v) (dec (* 2 v)))))

(defn write-flag! [w b] (write-bit! w (if b 1 0)))

(defn rbsp-trailing-bits!
  "Append rbsp_trailing_bits() (H.264 §7.3.2.11): a single stop bit `1`
   then zero-pad to the next byte boundary. Must be called once, last,
   before `bytes!`."
  [w]
  (write-bit! w 1)
  (while (pos? @(:nbits w)) (write-bit! w 0)))

(defn bytes!
  "Finalize `w` into a plain byte vector. Flushes any partial byte
   (zero-padded) if `rbsp-trailing-bits!` wasn't called first."
  [w]
  (when (pos? @(:nbits w))
    (swap! (:out w) conj (bit-shift-left @(:cur w) (- 8 @(:nbits w))))
    (reset! (:cur w) 0)
    (reset! (:nbits w) 0))
  @(:out w))
