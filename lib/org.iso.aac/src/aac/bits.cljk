(ns aac.bits
  "MSB-first bit reader AND writer over a byte vector, for the AAC
   raw_data_block payload (ISO/IEC 14496-3 §4.4 syntax tables read every
   field this way — `uimsbf`/`bslbf`/`vlclbf`). Pure cljc, zero dependencies.
   Mirrors `kotoba-lang/org-iso-h264`'s `h264.expgolomb` reader/writer shape
   (same `reader`/`bit!`/`bits!` + `writer`/`write-bit!`/`write-bits!`/
   `bytes!` names and atom-based state) for consistency across this org's
   bitstream-format repos, minus the Exp-Golomb-specific `ue!`/`se!`/
   `write-ue!`/`write-se!` (AAC has no Exp-Golomb codes — its variable-length
   fields are all Huffman, see `aac.huffman`)."
  )

(defn reader [data]
  {:data (vec data) :len (count data) :bytepos (atom 0) :bitpos (atom 0)})

(defn bit! [r]
  (let [bp @(:bytepos r) bi @(:bitpos r)]
    (when (>= bp (:len r)) (throw (ex-info "aac.bits: bit EOF" {})))
    (let [byte (nth (:data r) bp)
          v    (bit-and (bit-shift-right byte (- 7 bi)) 1)]
      (if (= bi 7) (do (reset! (:bitpos r) 0) (swap! (:bytepos r) inc))
          (reset! (:bitpos r) (inc bi)))
      v)))

(defn bits! [r n]
  (loop [i 0 acc 0] (if (= i n) acc (recur (inc i) (bit-or (bit-shift-left acc 1) (bit! r))))))

(defn byte-aligned? [r] (zero? @(:bitpos r)))

(defn align-to-byte!
  "Advance `r` to the next byte boundary if not already aligned (no-op if
   already aligned). Used by e.g. `data_stream_element()`'s
   `data_byte_align_flag`."
  [r]
  (when-not (byte-aligned? r)
    (reset! (:bitpos r) 0)
    (swap! (:bytepos r) inc)))

(defn bit-position
  "Total bits consumed so far (bytepos*8 + bitpos) — for diagnostics/tests."
  [r]
  (+ (* 8 @(:bytepos r)) @(:bitpos r)))

;; --- encode side (`aac.encode`, com-junkawasaki/root ADR-2800002800) -----
;; Bit writer mirroring `reader`/`bit!`/`bits!` above (and h264.expgolomb's
;; own writer, same names): accumulates bits MSB-first into whole bytes.
;; `bytes!` finalizes, flushing a partial byte zero-padded — which is
;; exactly `byte_alignment()` (§4.4.2.1's `id_syn_ele == ID_END` trailer),
;; so a raw_data_block needs no separate padding call.

(defn writer []
  {:out (atom []) :cur (atom 0) :nbits (atom 0) :written (atom 0)})

(defn write-bit! [w bit]
  (swap! (:cur w) #(bit-or (bit-shift-left % 1) (bit-and bit 1)))
  (swap! (:nbits w) inc)
  (swap! (:written w) inc)
  (when (= 8 @(:nbits w))
    (swap! (:out w) conj @(:cur w))
    (reset! (:cur w) 0)
    (reset! (:nbits w) 0))
  nil)

(defn write-bits!
  "Write the low `n` bits of `v`, MSB first."
  [w n v]
  (dotimes [i n] (write-bit! w (bit-and (bit-shift-right v (- n i 1)) 1))))

(defn bits-written
  "Total bits written so far (NOT rounded up to a byte) — lets the encoder
   assert its own predicted bit count against the real one (see
   `aac.encode/frame-bits`)."
  [w]
  @(:written w))

(defn bytes!
  "Finalize `w` into a plain byte vector, flushing any partial byte
   zero-padded (= `byte_alignment()`, see the comment above)."
  [w]
  (when (pos? @(:nbits w))
    (swap! (:out w) conj (bit-shift-left @(:cur w) (- 8 @(:nbits w))))
    (reset! (:cur w) 0)
    (reset! (:nbits w) 0))
  @(:out w))
