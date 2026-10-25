(ns aac.huffman
  "AAC-LC noiseless-coding Huffman decode AND encode (ISO/IEC 14496-3:2005
   §4.6.3.3 \"Decoding process\" + Annex 4.A tables, `aac.huffman-tables`) —
   see the `encode side` section at the bottom of this file for the write
   direction (`tuple->idx`/`tuple-bits`/`write-spectral-tuple!`/
   `write-scalefactor-dpcm!`), which reuses the very same tables. Builds a
   canonical binary trie per codebook from the (length, codeword) table and
   walks it one bit at a time — a plain, literal transcription of the
   decoding process, not FAAD2's 2-step lookup-table optimization (deliberate:
   this repo is Apache-2.0, FAAD2 is GPL-2.0, and a byte-for-byte-optimized
   lookup-table ARRANGEMENT is a different (and copyrightable) artifact from
   the underlying spec-mandated codeword-to-value mapping the trie approach
   decodes directly from Annex 4.A's own published tables; see
   `aac.huffman-tables`'s namespace docstring for how those tables were
   sourced/verified).

   Scope: the scalefactor codebook (Table 4.A.1) and all eleven spectral
   codebooks (1-11, Table 4.132 / Tables 4.A.2-4.A.12) are implemented —
   more than this repo's original 'at least 1-2 codebooks actually used in
   real data' target, because empirically decoding a real ffmpeg/libavcodec
   AAC-LC ONLY_LONG_SEQUENCE frame with actual (non-silent) audio content
   requires MOST of codebooks 1-11 simultaneously (a single real frame's
   sections routinely span 5-9 distinct codebooks — verified by probing
   `section_data()` output against `ffmpeg -c:a aac`-encoded fixtures during
   development). Codebooks 12 (reserved), 13 (NOISE_HCB/PNS), 14
   (INTENSITY_HCB2) and 15 (INTENSITY_HCB) are pseudo-codebooks that carry NO
   Huffman-coded spectral data (§4.6.3.3) — `aac.ics` skips them structurally
   and never calls into this namespace for them; PNS/intensity-stereo
   themselves are out of scope and `aac.ics` throws if a scalefactor band is
   actually marked with one (see that namespace's docstring)."
  (:require [aac.bits :as bits]
            [aac.huffman-tables :as tabs]))

;; --- canonical trie construction --------------------------------------

(defn build-trie
  "Build a binary trie from a `cbN-huffman-table`-shaped vector (index i ->
   [length codeword]): each leaf is the codeword's table index `i` (NOT yet
   translated to spectral/scalefactor values — see `idx->tuple`/scalefactor
   `index_offset`). Internal nodes are maps {0 <child-or-leaf>, 1
   <child-or-leaf>}; a leaf is a bare integer (the index)."
  [table]
  (loop [trie {} i 0]
    (if (>= i (count table))
      trie
      (let [[length codeword] (nth table i)
            bits-str (map #(bit-and (bit-shift-right codeword %) 1)
                          (range (dec length) -1 -1))]
        (recur (update-in trie bits-str (fn [existing]
                                           (when (map? existing)
                                             (throw (ex-info "aac.huffman: codeword prefix collision building trie"
                                                              {:index i :length length :codeword codeword})))
                                           i))
               (inc i))))))

(def ^:private trie-cache (atom {}))

(defn- trie-for [key table]
  (or (get @trie-cache key)
      (let [t (build-trie table)]
        (swap! trie-cache assoc key t)
        t)))

(defn decode-index!
  "Walk `trie` one bit at a time from `r` until a leaf (integer) is found;
   returns the table index."
  [r trie]
  (loop [node trie]
    (if (integer? node)
      node
      (let [b (bits/bit! r)]
        (if-let [next (get node b)]
          (recur next)
          (throw (ex-info "aac.huffman: no codeword matches (bitstream desync or corrupt data)" {})))))))

;; --- scalefactor (Table 4.A.1 / Table 4.131) ---------------------------

(def ^:private sf-index-offset -60)

(defn decode-scalefactor-dpcm!
  "Decode one Huffman scalefactor/is_position/noise_nrg DPCM codeword ->
   differential value (index_offset + huffman index, Table 4.131)."
  [r]
  (+ sf-index-offset (decode-index! r (trie-for :sf tabs/sf-huffman-table))))

;; --- spectral codebooks 1-11 (Table 4.132 / Tables 4.A.2-4.A.12) -------

(def codebook-params
  "cb -> {:dim :unsigned? :lav}, Table 4.132."
  {1  {:dim 4 :unsigned? false :lav 1}
   2  {:dim 4 :unsigned? false :lav 1}
   3  {:dim 4 :unsigned? true  :lav 2}
   4  {:dim 4 :unsigned? true  :lav 2}
   5  {:dim 2 :unsigned? false :lav 4}
   6  {:dim 2 :unsigned? false :lav 4}
   7  {:dim 2 :unsigned? true  :lav 7}
   8  {:dim 2 :unsigned? true  :lav 7}
   9  {:dim 2 :unsigned? true  :lav 12}
   10 {:dim 2 :unsigned? true  :lav 12}
   11 {:dim 2 :unsigned? true  :lav 16}})

(def ^:private cb-table
  {1 tabs/cb1-huffman-table 2 tabs/cb2-huffman-table 3 tabs/cb3-huffman-table
   4 tabs/cb4-huffman-table 5 tabs/cb5-huffman-table 6 tabs/cb6-huffman-table
   7 tabs/cb7-huffman-table 8 tabs/cb8-huffman-table 9 tabs/cb9-huffman-table
   10 tabs/cb10-huffman-table 11 tabs/cb11-huffman-table})

(defn idx->tuple
  "Translate a decoded Huffman table index to its n-tuple of quantized
   spectral values, per the pseudo-C code in §4.6.3.3 ('The result of
   Huffman decoding each spectrum n-tuple is the codeword index ... This
   index is translated to the n-tuple spectral values ...')."
  [cb idx]
  (let [{:keys [dim unsigned? lav]} (get codebook-params cb)
        _ (when (nil? dim) (throw (ex-info "aac.huffman: unknown/unsupported spectral codebook" {:cb cb})))
        mod- (if unsigned? (inc lav) (inc (* 2 lav)))
        off (if unsigned? 0 lav)]
    (if (= dim 4)
      (let [w (- (quot idx (* mod- mod- mod-)) off)
            idx1 (- idx (* (+ w off) mod- mod- mod-))
            x (- (quot idx1 (* mod- mod-)) off)
            idx2 (- idx1 (* (+ x off) mod- mod-))
            y (- (quot idx2 mod-) off)
            idx3 (- idx2 (* (+ y off) mod-))
            z (- idx3 off)]
        [w x y z])
      (let [y (- (quot idx mod-) off)
            idx1 (- idx (* (+ y off) mod-))
            z (- idx1 off)]
        [y z]))))

(defn- read-sign-bits!
  "For unsigned codebooks: one sign bit ('1' = negative) per NON-ZERO
   coefficient, immediately following the Huffman codeword (§4.6.3.3)."
  [r tuple]
  (mapv (fn [v]
          (if (zero? v)
            v
            (if (= 1 (bits/bit! r)) (- v) v)))
        tuple))

(def ^:private escape-flag 16)

(defn- read-escape!
  "ESC_HCB (codebook 11) escape_sequence for a value of magnitude 16
   (`escape_flag`): N one-bits (prefix, N>=1) + one zero-bit (separator) +
   an (N+4)-bit unsigned integer word -> decoded magnitude
   2^(N+4) + escape_word (§4.6.3.3), sign already applied by the caller via
   the sign bit read for this coefficient's slot before the escape."
  [r]
  (loop [n 0]
    (if (= 1 (bits/bit! r))
      (recur (inc n))
      (let [word-bits (+ n 4)
            word (bits/bits! r word-bits)]
        (+ (bit-shift-left 1 word-bits) word)))))

(defn decode-spectral-tuple!
  "Decode one n-tuple (quad for cb<5, pair for cb>=5) of quantized spectral
   coefficients for spectral codebook `cb` (1-11). Handles sign bits
   (unsigned codebooks) and codebook 11's escape mechanism. Returns the
   signed quantized integer tuple (a vector of length 4 or 2)."
  [r cb]
  (let [table (or (get cb-table cb) (throw (ex-info "aac.huffman: unsupported spectral codebook" {:cb cb})))
        {:keys [unsigned?]} (get codebook-params cb)
        idx (decode-index! r (trie-for [:cb cb] table))
        tuple (idx->tuple cb idx)
        tuple (if unsigned? (read-sign-bits! r tuple) tuple)]
    (if (= cb 11)
      (mapv (fn [v]
              (if (= (if (neg? v) (- v) v) escape-flag)
                (let [mag (read-escape! r)]
                  (if (neg? v) (- mag) mag))
                v))
            tuple)
      tuple)))

;; --- encode side (`aac.encode`, com-junkawasaki/root ADR-2800002800) -----
;;
;; The SAME Annex 4.A tables serve both directions: decode walks a trie built
;; from them, encode indexes them directly, because `[length codeword]` at
;; index i is exactly what has to be written for the n-tuple that index i
;; denotes. `kotoba-lang/org-iso-h264`'s `h264.cavlc` established that
;; precedent in this org (one table, `residual-block!` and
;; `encode-residual-block!` on either side of it); doing the same here means a
;; transcription error in `aac.huffman-tables` cannot be right for one
;; direction and wrong for the other, and the round-trip tests exercise both.

(defn- abs- [v] (if (neg? v) (- v) v))

(defn- index-digit
  "The table digit for one tuple element `v` under codebook `cb`: the signed
   value offset by `lav` for signed codebooks, the magnitude for unsigned ones
   (sign is carried by a separate bit). For ESC_HCB (11) a magnitude at or
   above `escape-flag` collapses to `escape-flag` — the table entry says only
   `escaped`, the real magnitude follows in the escape sequence. Throws rather
   than silently clamping when a value does not fit the codebook, since a
   clamp would emit audio that is not what was quantized."
  [cb unsigned? lav v]
  (let [m (abs- v)]
    (cond
      (= cb 11) (min m escape-flag)
      (and unsigned? (<= m lav)) m
      (and (not unsigned?) (<= (- lav) v) (<= v lav)) (+ v lav)
      :else (throw (ex-info "aac.huffman: value out of range for this spectral codebook"
                             {:cb cb :value v :lav lav :unsigned? unsigned?})))))

(defn tuple->idx
  "Inverse of `idx->tuple`: the Annex 4.A table index for an n-tuple of
   quantized spectral values under codebook `cb`. Little more than reading
   §4.6.3.3's translation formula as the base-`mod` positional number it is."
  [cb tuple]
  (let [{:keys [dim unsigned? lav]} (get codebook-params cb)
        _ (when (nil? dim) (throw (ex-info "aac.huffman: unknown/unsupported spectral codebook" {:cb cb})))
        _ (when-not (= dim (count tuple))
            (throw (ex-info "aac.huffman: tuple length does not match codebook dimension"
                             {:cb cb :dim dim :tuple tuple})))
        mod- (if unsigned? (inc lav) (inc (* 2 lav)))]
    (reduce (fn [acc v] (+ (* acc mod-) (index-digit cb unsigned? lav v))) 0 tuple)))

(defn escape-bits
  "Bit cost of ESC_HCB's `escape_sequence` for magnitude `mag` (>= 16): the
   `N` one-bits, the zero separator, and the `N+4`-bit word — `2N+5` bits,
   where `N` is fixed by `2^(N+4) <= mag < 2^(N+5)` (inverse of `read-escape!`)."
  [mag]
  (loop [n 0]
    (if (< mag (bit-shift-left 1 (+ n 5)))
      (+ (* 2 n) 5)
      (recur (inc n)))))

(defn codebook-fits?
  "Can codebook `cb` code every value in `values`? Signed codebooks need
   `|v| <= lav` with the sign IN the table index; unsigned ones need
   `|v| <= lav` with a separate sign bit; ESC_HCB (11) takes anything up to the
   spec's 8191 via its escape sequence."
  [cb values]
  (let [{:keys [lav]} (get codebook-params cb)]
    (if (nil? lav)
      false
      (if (= cb 11)
        (every? (fn [v] (<= (abs- v) 8191)) values)
        (every? (fn [v] (<= (abs- v) lav)) values)))))

(defn tuple-bits
  "Exact bit cost of one n-tuple under codebook `cb`: the codeword, one sign
   bit per non-zero value for unsigned codebooks, and ESC_HCB's escape
   sequences. Exact rather than estimated because `aac.encode` compares its
   predicted frame size against the bits actually written."
  [cb tuple]
  (let [{:keys [unsigned?]} (get codebook-params cb)
        [length _] (nth (get cb-table cb) (tuple->idx cb tuple))]
    (+ length
       (if unsigned? (count (filter (complement zero?) tuple)) 0)
       (if (= cb 11)
         (reduce (fn [acc v] (let [m (abs- v)] (if (>= m escape-flag) (+ acc (escape-bits m)) acc)))
                 0 tuple)
         0))))

(defn- write-escape!
  "Write ESC_HCB's `escape_sequence` for magnitude `mag` — inverse of
   `read-escape!`."
  [w mag]
  (let [n (loop [n 0] (if (< mag (bit-shift-left 1 (+ n 5))) n (recur (inc n))))]
    (dotimes [_ n] (bits/write-bit! w 1))
    (bits/write-bit! w 0)
    (bits/write-bits! w (+ n 4) (- mag (bit-shift-left 1 (+ n 4))))))

(defn write-spectral-tuple!
  "Write one n-tuple of quantized spectral values under codebook `cb` — the
   inverse of `decode-spectral-tuple!`, in its exact field order: codeword,
   then ALL sign bits (unsigned codebooks, one per non-zero value), then ALL
   escape sequences (ESC_HCB). That ordering is not a guess — it is the order
   `decode-spectral-tuple!` reads, and that decoder is validated bit-exactly
   against real ffmpeg-encoded streams."
  [w cb tuple]
  (let [{:keys [unsigned?]} (get codebook-params cb)
        [length codeword] (nth (get cb-table cb) (tuple->idx cb tuple))]
    (bits/write-bits! w length codeword)
    (when unsigned?
      (doseq [v tuple] (when-not (zero? v) (bits/write-bit! w (if (neg? v) 1 0)))))
    (when (= cb 11)
      (doseq [v tuple] (let [m (abs- v)] (when (>= m escape-flag) (write-escape! w m)))))
    nil))

;; --- scalefactor DPCM, encode direction --------------------------------

(defn scalefactor-delta-bits
  "Bit cost of one differential scalefactor `delta` (Table 4.A.1). Throws
   outside the codebook's -60..60 range — `aac.quant/clamp-dpcm-chain` exists
   to make sure that never reaches here."
  [delta]
  (let [idx (- delta sf-index-offset)]
    (when (or (neg? idx) (>= idx (count tabs/sf-huffman-table)))
      (throw (ex-info "aac.huffman: differential scalefactor out of codebook range"
                       {:delta delta :limit 60})))
    (first (nth tabs/sf-huffman-table idx))))

(defn write-scalefactor-dpcm!
  "Write one differential scalefactor — inverse of `decode-scalefactor-dpcm!`."
  [w delta]
  (let [idx (- delta sf-index-offset)
        _ (when (or (neg? idx) (>= idx (count tabs/sf-huffman-table)))
            (throw (ex-info "aac.huffman: differential scalefactor out of codebook range"
                             {:delta delta :limit 60})))
        [length codeword] (nth tabs/sf-huffman-table idx)]
    (bits/write-bits! w length codeword)
    nil))
