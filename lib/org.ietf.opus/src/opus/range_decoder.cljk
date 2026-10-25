(ns opus.range-decoder
  "Opus (IETF RFC 6716) entropy decoder -- RFC 6716 Section 4.1 'Range
   Decoder'. This is the arithmetic-coding engine shared by the SILK and
   CELT layers (CELT additionally uses the 'raw bits' side channel packed
   from the end of the frame, Section 4.1.4). Pure cljc, zero dependencies.

   The decoder state is plain data (a map); every `ec-*` function is a pure
   function of that state, returning either a bare new state (for
   update/normalize) or a [value new-state] pair (for the decode
   procedures), so callers can thread state through `let`/`reduce` without
   mutation. This mirrors the reference `entdec.c` algorithm procedure for
   procedure (Section 4.1.1 through 4.1.6), transcribed from the RFC text,
   not lifted from the (separately licensed) reference C source.

   New implementation, part of the CELT-mode audio decode increment for
   kotoba-lang/org-ietf-opus (see opus.celt); no range decoder existed in
   this repo before (packet/toc are opaque-byte framing only)."
  )

(defn- byte-at
  "Unsigned byte at index `i` of frame `data` (a vector/seq of unsigned
   byte values), or 0 past the end of the frame (RFC 6716 SS4.1.2.1 / SS4.1.4:
   once input is exhausted the decoder MUST keep returning zero bits)."
  [data len i]
  (if (and (>= i 0) (< i len)) (bit-and (int (nth data i)) 0xff) 0))

;; ilog(x): number of bits to represent x in two's complement, i.e.
;; floor(log2(x))+1 for x>=1, and 0 for x<=0. Used by ec_tell()/ec_dec_uint().
(defn ilog [x]
  (loop [x (long x) n 0]
    (if (pos? x) (recur (bit-shift-right x 1) (inc n)) n)))

(defn- normalize-1
  "One iteration of the renormalization loop, RFC 6716 SS4.1.2.1."
  [{:keys [data len bptr rng val buf nbits-total] :as st}]
  (let [b    (byte-at data len bptr)
        sym  (bit-or (bit-shift-left buf 7) (bit-shift-right b 1))
        val' (bit-and (+ (bit-shift-left val 8) (- 255 sym)) 0x7FFFFFFF)]
    (assoc st
           :rng (bit-shift-left rng 8)
           :val val'
           :buf (bit-and b 1)
           :bptr (inc bptr)
           :nbits-total (+ nbits-total 8))))

(defn- normalize
  "Repeats `normalize-1` until rng > 2^23, RFC 6716 SS4.1.2.1."
  [st]
  (loop [st st]
    (if (> (:rng st) (bit-shift-left 1 23)) st (recur (normalize-1 st)))))

(defn init
  "Initialize a range decoder over `data` (vector of unsigned bytes, the
   Opus frame payload -- CELT frame bytes after the TOC/frame-header have
   already been stripped by opus.packet). RFC 6716 SS4.1.1."
  [data]
  (let [len (count data)
        b0  (byte-at data len 0)
        st  {:data data :len len
             :bptr 1                       ; next byte for range-coder normalize
             :end-off 0                    ; bytes consumed from the end (raw bits)
             :end-window 0 :nend-bits 0    ; raw-bits shift register (SS4.1.4)
             :rng 128
             :val (- 127 (bit-shift-right b0 1))
             :buf (bit-and b0 1)           ; leftover bit from b0, for normalize
             :nbits-total 9}]
    (normalize st)))

(defn ec-decode
  "Step 1 of decoding a symbol (RFC 6716 SS4.1.2): returns fs, the 16-bit
   value locating the symbol within the context's cumulative-frequency
   table (`ft` = total frequency of the context)."
  [{:keys [rng val]} ft]
  (let [ext (quot rng ft)
        s   (quot val ext)]
    (- ft (min (inc s) ft))))

(defn ec-dec-update
  "Step 2 (RFC 6716 SS4.1.2): given the (fl, fh, ft) tuple of the symbol
   identified via `ec-decode`'s fs, updates decoder state and normalizes."
  [{:keys [rng val] :as st} fl fh ft]
  (let [ext  (quot rng ft)
        val' (- val (* ext (- ft fh)))
        rng' (if (pos? fl) (* ext (- fh fl)) (- rng (* ext (- ft fh))))]
    (normalize (assoc st :val val' :rng rng'))))

(defn ec-decode-bin
  "RFC 6716 SS4.1.3.1: `ec_decode_bin(ftb)`, equivalent to `ec-decode` with
   ft=(1<<ftb) computed without a division."
  [{:keys [rng val]} ftb]
  (let [ext (bit-shift-right rng ftb)
        s   (quot val ext)
        ft  (bit-shift-left 1 ftb)]
    (- ft (min (inc s) ft))))

(defn ec-dec-bit-logp
  "RFC 6716 SS4.1.3.2: decode a single binary symbol whose probability of a
   '1' is 2^-logp. Returns [bit new-state]."
  [{:keys [rng val] :as st} logp]
  (let [ft  (bit-shift-left 1 logp)
        ext (bit-shift-right rng logp)
        s   (quot val ext)
        fs  (- ft (min (inc s) ft))]
    (if (< fs (dec ft))
      [0 (normalize (assoc st :val (- val ext) :rng (- rng ext)))]
      [1 (normalize (assoc st :rng ext))])))

(defn ec-dec-icdf
  "RFC 6716 SS4.1.3.3: decode a symbol from an inverse-CDF table `icdf`
   (terminated by a 0 entry) with `ft` = (1<<ftb). Returns [symbol new-state]."
  [{:keys [rng val] :as st} icdf ftb]
  (let [ext (bit-shift-right rng ftb)
        s   (quot val ext)
        ft  (bit-shift-left 1 ftb)
        fs  (- ft (min (inc s) ft))
        k   (loop [k 0] (if (< fs (- ft (nth icdf k))) k (recur (inc k))))
        fl  (if (zero? k) 0 (- ft (nth icdf (dec k))))
        fh  (- ft (nth icdf k))
        val' (- val (* ext (- ft fh)))
        rng' (if (pos? fl) (* ext (- fh fl)) (- rng (* ext (- ft fh))))]
    [k (normalize (assoc st :val val' :rng rng'))]))

(defn ec-dec-bits
  "RFC 6716 SS4.1.4: decode `nbits` raw bits packed from the *end* of the
   frame (LSB-first). Returns [value new-state]."
  [{:keys [data len end-off end-window nend-bits] :as st} nbits]
  (loop [end-off end-off end-window end-window nend-bits nend-bits]
    (if (< nend-bits nbits)
      (let [idx (- len end-off 1)
            b   (byte-at data len idx)]
        (recur (inc end-off) (bit-or end-window (bit-shift-left b nend-bits)) (+ nend-bits 8)))
      (let [mask (dec (bit-shift-left 1 nbits))
            v    (bit-and end-window mask)]
        [v (assoc st
                  :end-off end-off
                  :end-window (bit-shift-right end-window nbits)
                  :nend-bits (- nend-bits nbits)
                  :nbits-total (+ (:nbits-total st) nbits))]))))

(defn ec-dec-uint
  "RFC 6716 SS4.1.5: decode a uniformly distributed integer in [0, ft).
   `ft` may exceed 16 bits (e.g. PVQ codebook sizes); the top <=8 bits are
   range-coded and any remainder is packed as raw bits. Returns [t new-state]."
  [st ft]
  (let [ftb (ilog (dec ft))]
    (if (<= ftb 8)
      (let [t (ec-decode st ft)]
        [t (ec-dec-update st t (inc t) ft)])
      (let [ft-top (inc (bit-shift-right (dec ft) (- ftb 8)))
            t-top  (ec-decode st ft-top)
            st1    (ec-dec-update st t-top (inc t-top) ft-top)
            [lo st2] (ec-dec-bits st1 (- ftb 8))
            t (bit-or (bit-shift-left t-top (- ftb 8)) lo)]
        [t st2]))))

(defn ec-tell
  "RFC 6716 SS4.1.6.1: conservative upper bound, in whole bits, on the
   number of bits used so far."
  [{:keys [rng nbits-total]}]
  (- nbits-total (ilog rng)))

(defn ec-tell-frac
  "RFC 6716 SS4.1.6.2: `ec_tell()` to 1/8-bit precision."
  [{:keys [rng nbits-total]}]
  (let [lg0 (ilog rng)
        r0  (bit-shift-right rng (- lg0 16))]
    (loop [lg lg0 r r0 i 0]
      (if (= i 3)
        (- (* nbits-total 8) lg)
        (let [r2  (bit-shift-right (* r r) 15)
              bit (bit-shift-right r2 16)
              lg' (+ (* 2 lg) bit)
              r'  (if (pos? bit) (bit-shift-right r2 1) r2)]
          (recur lg' r' (inc i)))))))
