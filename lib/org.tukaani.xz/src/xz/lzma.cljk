(ns xz.lzma
  "LZMA1 and LZMA2 decompression, portable `.cljc`.

   LZMA is a binary range coder over a context-modelled LZ77: every bit of every
   symbol is coded against an adaptive probability chosen by (state machine
   position, recent bytes, match length, distance slot). There is no Huffman
   table and no byte alignment anywhere in the stream, which is why the decoder
   must mirror the reference bit-for-bit — a single probability index off by one
   still decodes plausible-looking output for a while and then diverges.

   Structure follows Igor Pavlov's `LzmaSpec.cpp` (the normative description in
   the LZMA SDK) deliberately closely, including the state-transition tables and
   the distance-slot layout, so the two can be diffed by eye.

   LZMA2 (`decompress-lzma2`) is the chunked framing .xz and .7z use: a control
   byte per chunk selects uncompressed data or an LZMA chunk, and says whether to
   reset the probability model, the properties and/or the dictionary. Chunk sizes
   bound everything, so no end-of-stream marker is needed.

   Not implemented: encoding. Writing LZMA would need the optimal-parse price
   model to be worth anything, and `xz.core` writes valid .xz using LZMA2's
   uncompressed chunks instead — see that namespace."
  (:require [xz.buffer :as buf]))

;; ---------------------------------------------------------------------------
;; Constants (LzmaSpec.cpp names kept)
;; ---------------------------------------------------------------------------

(def ^:private num-states 12)
(def ^:private num-pos-bits-max 4)
(def ^:private num-len-to-pos-states 4)
(def ^:private num-align-bits 4)
(def ^:private end-pos-model-index 14)
(def ^:private num-full-distances 128)                     ; 1 << (14 >> 1)
(def ^:private match-min-len 2)
(def ^:private prob-init 1024)                             ; (1 << 11) / 2
(def ^:private top-value 16777216)                         ; 1 << 24

;; ---------------------------------------------------------------------------
;; Probability arrays
;; ---------------------------------------------------------------------------

#?(:clj  (defn- probs [n] (let [a (int-array n)] (java.util.Arrays/fill a prob-init) a))
   :cljs (defn- probs [n] (.fill (js/Int32Array. n) prob-init)))

#?(:clj  (defn- pget [a i] (aget ^ints a i))
   :cljs (defn- pget [a i] (aget a i)))

#?(:clj  (defn- pset! [a i v] (aset-int a i v))
   :cljs (defn- pset! [a i v] (aset a i v)))

#?(:clj  (defn- pfill! [a] (java.util.Arrays/fill ^ints a prob-init) a)
   :cljs (defn- pfill! [a] (.fill a prob-init) a))

;; ---------------------------------------------------------------------------
;; Range decoder
;; ---------------------------------------------------------------------------

(defn- next-byte! [rc]
  (let [p @(:pos rc)]
    (when (>= p (:len rc))
      (throw (ex-info "lzma: range coder ran out of input"
                      {:reason :truncated :pos p})))
    (vreset! (:pos rc) (inc p))
    (nth (:data rc) p)))

(defn- range-decoder
  "A range decoder over `data` starting at `from`. The first byte must be zero
   and the next four are the initial code, big-endian (LZMA has no other framing:
   this five-byte preamble is the whole header of a range-coded stream)."
  [data from]
  (let [v  (vec data)
        rc {:data v :len (count v) :pos (volatile! from)
            :range (volatile! 4294967295) :code (volatile! 0)}
        b0 (next-byte! rc)]
    (when-not (zero? b0)
      (throw (ex-info "lzma: range coder preamble is not zero"
                      {:reason :bad-range-coder :byte b0})))
    (vreset! (:code rc)
             (loop [i 0 c 0]
               (if (= i 4) c (recur (inc i) (+ (* c 256) (next-byte! rc))))))
    rc))

(defn- normalize! [rc]
  (when (< @(:range rc) top-value)
    (vreset! (:range rc) (* @(:range rc) 256))
    ;; Arithmetic rather than shifts: `code` reaches 2^32 and int32 shifts would
    ;; wrap on a JavaScript runtime.
    (vreset! (:code rc) (mod (+ (* @(:code rc) 256) (next-byte! rc)) 4294967296))))

(defn- decode-bit! [rc a i]
  (let [v     (pget a i)
        bound (* (quot @(:range rc) 2048) v)]
    (if (< @(:code rc) bound)
      (do (pset! a i (+ v (unsigned-bit-shift-right (- 2048 v) 5)))
          (vreset! (:range rc) bound)
          (normalize! rc)
          0)
      (do (pset! a i (- v (unsigned-bit-shift-right v 5)))
          (vreset! (:code rc) (- @(:code rc) bound))
          (vreset! (:range rc) (- @(:range rc) bound))
          (normalize! rc)
          1))))

(defn- decode-direct! [rc num-bits]
  (loop [i 0 res 0]
    (if (= i num-bits)
      res
      (let [r (quot @(:range rc) 2)
            _ (vreset! (:range rc) r)
            bit (if (>= @(:code rc) r)
                  (do (vreset! (:code rc) (- @(:code rc) r)) 1)
                  0)]
        (normalize! rc)
        (recur (inc i) (+ (* res 2) bit))))))

(defn- bit-tree! [rc a base num-bits]
  (loop [i 0 m 1]
    (if (= i num-bits)
      (- m (bit-shift-left 1 num-bits))
      (recur (inc i) (+ (* m 2) (decode-bit! rc a (+ base m)))))))

(defn- bit-tree-reverse! [rc a base num-bits]
  (loop [i 0 m 1 sym 0]
    (if (= i num-bits)
      sym
      (let [b (decode-bit! rc a (+ base m))]
        (recur (inc i) (+ (* m 2) b) (bit-or sym (bit-shift-left b i)))))))

(defn- finished?
  "A well-formed stream ends with the range coder's code at zero."
  [rc]
  (zero? @(:code rc)))

;; ---------------------------------------------------------------------------
;; Length coder
;; ---------------------------------------------------------------------------

(defn- len-coder []
  {:choice (probs 1) :choice2 (probs 1)
   :low (probs (* 16 8)) :mid (probs (* 16 8)) :high (probs 256)})

(defn- reset-len-coder! [lc]
  (doseq [k [:choice :choice2 :low :mid :high]] (pfill! (get lc k)))
  lc)

(defn- decode-len! [rc lc pos-state]
  (if (zero? (decode-bit! rc (:choice lc) 0))
    (bit-tree! rc (:low lc) (* pos-state 8) 3)
    (if (zero? (decode-bit! rc (:choice2 lc) 0))
      (+ 8 (bit-tree! rc (:mid lc) (* pos-state 8) 3))
      (+ 16 (bit-tree! rc (:high lc) 0 8)))))

;; ---------------------------------------------------------------------------
;; Decoder state
;; ---------------------------------------------------------------------------

(defn decoder
  "Probability model + LZ state for one LZMA stream. `lc`/`lp`/`pb` come from the
   properties byte (`lc + 9*(lp + 5*pb)`)."
  [lc lp pb]
  {:lc           lc
   :lp           lp
   :pb           pb
   :is-match     (probs (* num-states (bit-shift-left 1 num-pos-bits-max)))
   :is-rep       (probs num-states)
   :is-rep-g0    (probs num-states)
   :is-rep-g1    (probs num-states)
   :is-rep-g2    (probs num-states)
   :is-rep0-long (probs (* num-states (bit-shift-left 1 num-pos-bits-max)))
   :pos-slot     (probs (* num-len-to-pos-states 64))
   :spec-pos     (probs (inc (- num-full-distances end-pos-model-index)))
   :align        (probs (bit-shift-left 1 num-align-bits))
   :literal      (probs (bit-shift-left 0x300 (+ lc lp)))
   :len          (len-coder)
   :rep-len      (len-coder)
   :state        (volatile! 0)
   :reps         (volatile! [0 0 0 0])})

(defn reset-state!
  "LZMA2's 'reset state': every probability back to 0.5, LZ state and the four
   recent distances cleared. Properties and dictionary are untouched."
  [d]
  (doseq [k [:is-match :is-rep :is-rep-g0 :is-rep-g1 :is-rep-g2 :is-rep0-long
             :pos-slot :spec-pos :align :literal]]
    (pfill! (get d k)))
  (reset-len-coder! (:len d))
  (reset-len-coder! (:rep-len d))
  (vreset! (:state d) 0)
  (vreset! (:reps d) [0 0 0 0])
  d)

(defn props->lclppb
  "Unpack the properties byte. `lc + lp` is bounded because the literal
   probability array is `0x300 << (lc + lp)` entries."
  [p]
  (when (>= p (* 9 5 5))
    (throw (ex-info "lzma: invalid properties byte" {:reason :bad-properties :byte p})))
  (let [lc (mod p 9)
        r  (quot p 9)
        lp (mod r 5)
        pb (quot r 5)]
    (when (> (+ lc lp) 4)
      (throw (ex-info "lzma: lc + lp is larger than this decoder supports"
                      {:reason :bad-properties :lc lc :lp lp})))
    [lc lp pb]))

;; ---------------------------------------------------------------------------
;; State transitions (LzmaSpec.cpp UpdateState_*)
;; ---------------------------------------------------------------------------

(defn- state-literal [s] (cond (< s 4) 0 (< s 10) (- s 3) :else (- s 6)))
(defn- state-match [s] (if (< s 7) 7 10))
(defn- state-rep [s] (if (< s 7) 8 11))
(defn- state-short-rep [s] (if (< s 7) 9 11))

;; ---------------------------------------------------------------------------
;; Symbol decoding
;; ---------------------------------------------------------------------------

(defn- decode-literal! [rc d buf dict-start]
  (let [pos       (- (buf/size buf) dict-start)
        prev      (if (pos? (buf/size buf)) (buf/back buf 1) 0)
        lit-state (+ (* (bit-and pos (dec (bit-shift-left 1 (:lp d))))
                        (bit-shift-left 1 (:lc d)))
                     (unsigned-bit-shift-right prev (- 8 (:lc d))))
        base      (* 0x300 lit-state)
        a         (:literal d)
        state     @(:state d)]
    (if (>= state 7)
      ;; After a match, literals are coded against the byte that *would* have
      ;; come next at the last distance — the single most confusing part of LZMA.
      (let [rep0 (nth @(:reps d) 0)]
        (loop [sym 1 mb (buf/back buf (inc rep0))]
          (if (>= sym 0x100)
            (bit-and sym 0xff)
            (let [mbit (bit-and (unsigned-bit-shift-right mb 7) 1)
                  bit  (decode-bit! rc a (+ base (bit-shift-left (inc mbit) 8) sym))
                  sym' (+ (* sym 2) bit)]
              (if (not= mbit bit)
                ;; Once they disagree the match byte is useless; finish plainly.
                (loop [sym sym']
                  (if (>= sym 0x100)
                    (bit-and sym 0xff)
                    (recur (+ (* sym 2) (decode-bit! rc a (+ base sym))))))
                (recur sym' (bit-and (* mb 2) 0xff)))))))
      (loop [sym 1]
        (if (>= sym 0x100)
          (bit-and sym 0xff)
          (recur (+ (* sym 2) (decode-bit! rc a (+ base sym)))))))))

(defn- decode-distance! [rc d len]
  (let [len-state (min len (dec num-len-to-pos-states))
        slot      (bit-tree! rc (:pos-slot d) (* len-state 64) 6)]
    (if (< slot 4)
      slot
      (let [direct (dec (unsigned-bit-shift-right slot 1))
            ;; Multiplication, not `bit-shift-left`: slot 63 gives 3 << 30, which
            ;; is negative in int32 and would silently corrupt every long
            ;; distance on a JavaScript runtime.
            dist   (* (bit-or 2 (bit-and slot 1)) (bit-shift-left 1 direct))]
        (if (< slot end-pos-model-index)
          (+ dist (bit-tree-reverse! rc (:spec-pos d) (- dist slot) direct))
          (+ dist
             (* (decode-direct! rc (- direct num-align-bits)) 16)
             (bit-tree-reverse! rc (:align d) 0 num-align-bits)))))))

(defn- emit-rep!
  "A rep match: the length is coded, the distance is whichever of the four recent
   distances the caller already rotated to the front."
  [rc d buf pos-state state produced limit]
  (let [l  (+ match-min-len (decode-len! rc (:rep-len d) pos-state))
        r0 (nth @(:reps d) 0)]
    (vreset! (:state d) (state-rep state))
    (when (> (+ produced l) limit)
      (throw (ex-info "lzma: match runs past the declared size"
                      {:reason :size-mismatch :limit limit})))
    (buf/copy-match! buf (inc r0) l)
    nil))

(defn- emit-match!
  "A new match: length, then distance. Returns `:end-marker` for the
   0xFFFFFFFF distance that ends a stream of unknown length."
  [rc d buf pos-state state produced limit dict-start dict-size]
  (let [raw  (decode-len! rc (:len d) pos-state)
        dist (decode-distance! rc d raw)
        l    (+ match-min-len raw)]
    (vreset! (:state d) (state-match state))
    (if (= dist 4294967295)
      :end-marker
      (do
        (when (or (>= dist dict-size)
                  (> (inc dist) (- (buf/size buf) dict-start)))
          (throw (ex-info "lzma: distance outside the dictionary"
                          {:reason :bad-distance :distance dist :dict-size dict-size})))
        (vreset! (:reps d) (into [dist] (subvec @(:reps d) 0 3)))
        (when (> (+ produced l) limit)
          (throw (ex-info "lzma: match runs past the declared size"
                          {:reason :size-mismatch :limit limit})))
        (buf/copy-match! buf (inc dist) l)
        nil))))

(defn decode-into!
  "Decode LZMA1 symbols into `buf` until `limit` bytes have been produced since
   `start`, or the end-of-stream marker appears.

   `dict-start` is where the current dictionary began (LZMA2 resets it); it fixes
   both the position used for `pb`/`lp` contexts and how far back a distance may
   legally reach.

   Returns `:end-marker` or `:limit`."
  [rc d buf {:keys [limit dict-start dict-size]}]
  (let [start   (buf/size buf)
        pb-mask (dec (bit-shift-left 1 (:pb d)))]
    (loop []
      (let [produced (- (buf/size buf) start)]
        (cond
          (> produced limit)
          (throw (ex-info "lzma: produced more than the declared size"
                          {:reason :size-mismatch :limit limit :produced produced}))

          (= produced limit) :limit

          :else
          (let [pos-state (bit-and (- (buf/size buf) dict-start) pb-mask)
                state     @(:state d)
                state-pos (+ (* state 16) pos-state)]
            (if (zero? (decode-bit! rc (:is-match d) state-pos))
              (do (buf/push! buf (decode-literal! rc d buf dict-start))
                  (vreset! (:state d) (state-literal state))
                  (recur))

              (if (pos? (decode-bit! rc (:is-rep d) state))
                ;; One of the four recent distances.
                (do
                  (when (zero? (- (buf/size buf) dict-start))
                    (throw (ex-info "lzma: rep match with an empty dictionary"
                                    {:reason :bad-distance})))
                  (if (zero? (decode-bit! rc (:is-rep-g0 d) state))
                    (if (zero? (decode-bit! rc (:is-rep0-long d) state-pos))
                      ;; short rep: a single byte at the most recent distance
                      (do (vreset! (:state d) (state-short-rep state))
                          (buf/push! buf (buf/back buf (inc (nth @(:reps d) 0))))
                          (recur))
                      (do (emit-rep! rc d buf pos-state state produced limit)
                          (recur)))
                    ;; Rotate by *which* slot was selected, never by comparing
                    ;; distances: two slots legitimately hold the same value
                    ;; (they all start at 0) and value-matching then rotates the
                    ;; wrong one, which diverges only later and only sometimes.
                    (let [[r0 r1 r2 r3] @(:reps d)
                          reps' (if (zero? (decode-bit! rc (:is-rep-g1 d) state))
                                  [r1 r0 r2 r3]
                                  (if (zero? (decode-bit! rc (:is-rep-g2 d) state))
                                    [r2 r0 r1 r3]
                                    [r3 r0 r1 r2]))]
                      (vreset! (:reps d) reps')
                      (emit-rep! rc d buf pos-state state produced limit)
                      (recur))))

                ;; A new distance.
                (if (= :end-marker (emit-match! rc d buf pos-state state produced limit
                                                dict-start dict-size))
                  :end-marker
                  (recur))))))))))

;; ---------------------------------------------------------------------------
;; LZMA1 (.lzma "alone" payload)
;; ---------------------------------------------------------------------------

(defn decompress-lzma1
  "Decode a raw LZMA1 stream that starts at `from`.

   `:unpacked-size` nil means 'until the end-of-stream marker', which is what the
   .lzma container writes when it does not know the size up front."
  [data from {:keys [props unpacked-size dict-size]
              :or   {dict-size 0x4000000}}]
  (let [[lc lp pb] (props->lclppb props)
        d   (decoder lc lp pb)
        rc  (range-decoder data from)
        buf (buf/buffer (min (or unpacked-size 65536) (* 4 1024 1024)))
        how (decode-into! rc d buf {:limit (or unpacked-size 9007199254740991)
                                    :dict-start 0
                                    :dict-size dict-size})]
    (when (and unpacked-size (not= (buf/size buf) unpacked-size))
      (throw (ex-info "lzma: decoded size does not match the header"
                      {:reason :size-mismatch
                       :expected unpacked-size :actual (buf/size buf)})))
    {:bytes (buf/->vector buf)
     :end @(:pos rc)
     :terminated-by how
     :range-coder-clean? (finished? rc)}))

;; ---------------------------------------------------------------------------
;; LZMA2 (the chunked framing .xz and .7z use)
;; ---------------------------------------------------------------------------

(defn decompress-lzma2
  "Decode an LZMA2 stream: a sequence of chunks, each either uncompressed or
   LZMA-coded, with the control byte saying what to reset.

   Returns `{:bytes ... :end <offset past the terminating 0x00>}`."
  [data from {:keys [dict-size max-output]
              :or   {dict-size 0x4000000}}]
  (let [v   (vec data)
        n   (count v)
        buf (buf/buffer 65536)]
    (loop [pos from d nil dict-start 0]
      (when (>= pos n)
        (throw (ex-info "lzma2: stream ends without a terminator"
                        {:reason :truncated :pos pos})))
      (let [control (nth v pos)]
        (cond
          (zero? control)
          {:bytes (buf/->vector buf) :end (inc pos)}

          ;; 0x01 = uncompressed chunk + dictionary reset, 0x02 = uncompressed
          (or (= control 1) (= control 2))
          (let [size (inc (+ (* 256 (nth v (+ pos 1))) (nth v (+ pos 2))))
                from (+ pos 3)]
            (when (> (+ from size) n)
              (throw (ex-info "lzma2: uncompressed chunk runs past the end"
                              {:reason :truncated :pos from})))
            (when (and max-output (> (+ (buf/size buf) size) max-output))
              (throw (ex-info "lzma2: output exceeds limit"
                              {:reason :output-limit :limit max-output})))
            (buf/append! buf (subvec v from (+ from size)))
            ;; An uncompressed chunk always invalidates the probability model.
            ;; An uncompressed chunk always invalidates the probability model,
            ;; which the next LZMA chunk's control byte must therefore admit to
            ;; resetting — so nothing needs to be remembered here.
            (when d (reset-state! d))
            (recur (+ from size) d
                   (if (= control 1) (- (buf/size buf) size) dict-start)))

          (>= control 0x80)
          (let [unpacked (inc (+ (bit-shift-left (bit-and control 0x1f) 16)
                                 (* 256 (nth v (+ pos 1)))
                                 (nth v (+ pos 2))))
                packed   (inc (+ (* 256 (nth v (+ pos 3))) (nth v (+ pos 4))))
                reset    (bit-and (unsigned-bit-shift-right control 5) 0x3)
                props?   (>= reset 2)
                props    (when props? (nth v (+ pos 5)))
                from     (+ pos 5 (if props? 1 0))
                d        (cond
                           props? (let [[lc lp pb] (props->lclppb props)] (decoder lc lp pb))
                           (nil? d) (throw (ex-info "lzma2: chunk needs properties that were never sent"
                                                    {:reason :bad-chunk :pos pos}))
                           :else d)
                _        (when (and (>= reset 1) (not props?)) (reset-state! d))
                dict-start (if (= reset 3) (buf/size buf) dict-start)]
            (when (> (+ from packed) n)
              (throw (ex-info "lzma2: chunk runs past the end of the stream"
                              {:reason :truncated :pos from})))
            (when (and max-output (> (+ (buf/size buf) unpacked) max-output))
              (throw (ex-info "lzma2: output exceeds limit"
                              {:reason :output-limit :limit max-output})))
            (let [rc (range-decoder (subvec v from (+ from packed)) 0)]
              (decode-into! rc d buf {:limit unpacked
                                      :dict-start dict-start
                                      :dict-size dict-size}))
            (recur (+ from packed) d dict-start))

          :else
          (throw (ex-info "lzma2: invalid control byte"
                          {:reason :bad-chunk :control control :pos pos})))))))
