(ns opus.support.celt-encoder
  "Test-support-only CELT frame ENCODER, used to build genuine, decodable
   bitstreams for opus.celt's round-trip tests. This is *not* a general
   Opus/CELT encoder (this repo implements CELT decode only, see
   opus.celt's ns docstring) -- it only needs to produce streams inside
   this decoder's declared scope:

   - silence=0, post-filter=0, transient=0, intra=1 (mandatory);
   - coarse energy: always encodes qi=0 for every band (RFC SS4.3.2.1's
     Laplace symbol '0', the single most probable value), so the decoded
     per-band gain is exactly 2^eMeans[i] -- a real, non-flat spectral
     envelope (eMeans ranges 3.75-6.44 across bands), not degenerate;
   - band boost: always 0 (mirrors opus.celt/decode-band-boost's exact
     gating logic to know how many 'stop' bits to emit, so encoder and
     decoder read the identical number of boost bits);
   - allocation trim: mirrors opus.celt/decode-frame's exact gating
     condition to decide whether a trim symbol is present at all; encodes
     `trim` (default 5) when present;
   - per-band pulse counts come directly from
     `opus.celt/compute-band-allocations` (the same function the decoder
     calls), so the two sides can never disagree about K;
   - per-band PVQ vectors are caller-supplied (any valid integer vector
     with sum(abs)=K for that band -- see `pulse-vector-all-on-first-bin`
     for a simple default)."
  (:require [opus.celt :as celt]
            [opus.pvq :as pvq]
            [opus.support.range-encoder :as re]))

(defn pulse-vector-all-on-first-bin
  "A trivial, always-valid PVQ pulse vector for (n,k): the k pulses are
   distributed round-robin (one +1 at a time, wrapping) across the n bins,
   so it's well-formed even when k>n (multiple pulses stack on the same
   bin, which is legal PVQ, RFC SS4.3.4.2). Always length n, always
   sum(abs(x))=k exactly."
  [n k]
  (loop [remaining k idx 0 v (vec (repeat n 0))]
    (if (zero? remaining)
      v
      (recur (dec remaining) (mod (inc idx) n) (update v idx inc)))))

(defn- encode-band-boost
  "Mirrors opus.celt/decode-band-boost's gating exactly, but always emits
   boost=0 (writes the single 'stop' bit whenever the loop would have
   entered at all)."
  [st i dynalloc-logp total-bits total-boost]
  (let [cap (nth celt/cap-lm3-mono i)
        tell (re/ec-tell-frac st)]
    (if (and (< (+ (* dynalloc-logp 8) tell) (+ total-bits total-boost)) (< 0 cap))
      [0 (re/ec-enc-bit-logp st 0 dynalloc-logp) total-bits total-boost]
      [0 st total-bits total-boost])))

(defn- encode-boosts [st frame-bits-1-8th]
  (loop [i 0 st st dynalloc-logp 6 total-bits frame-bits-1-8th total-boost 0]
    (if (= i celt/nb-ebands)
      st
      (let [[_boost st' total-bits' total-boost'] (encode-band-boost st i dynalloc-logp total-bits total-boost)]
        (recur (inc i) st' dynalloc-logp total-bits' total-boost')))))

(defn encode-frame
  "Build a decodable CELT frame of exactly `frame-bytes` bytes. `trim`
   defaults to 5 (no bias). `pulse-vector-fn` (n,k)->vector defaults to
   `pulse-vector-all-on-first-bin`. Returns the byte vector."
  ([frame-bytes] (encode-frame frame-bytes {}))
  ([frame-bytes {:keys [trim pulse-vector-fn]
                 :or {trim 5 pulse-vector-fn pulse-vector-all-on-first-bin}}]
   (let [budget-bits (* frame-bytes 8)
         frame-bits-1-8th (* budget-bits 8)
         st0 (re/init)
         st1 (re/ec-enc-bit-logp st0 0 15)   ; silence=0
         st2 (re/ec-enc-bit-logp st1 0 1)    ; post-filter=0
         st3 (re/ec-enc-bit-logp st2 0 3)    ; transient=0
         st4 (re/ec-enc-bit-logp st3 1 3)    ; intra=1
         ;; coarse energy: qi=0 for every band -> ec_encode_bin(0, fs0, 15)
         st5 (reduce (fn [st i]
                       (let [pi (* 2 i)
                             fs0 (bit-shift-left (nth celt/e-prob-model-intra pi) 7)]
                         (re/ec-encode-bin st 0 fs0 15)))
                     st4 (range celt/nb-ebands))
         ;; tf_change = 0 for every band
         st6 (reduce (fn [st i] (re/ec-enc-bit-logp st 0 (if (zero? i) 4 5)))
                     st5 (range celt/nb-ebands))
         spread-param 0
         st7 (re/ec-enc-icdf st6 spread-param celt/spread-icdf 5)
         st8 (encode-boosts st7 frame-bits-1-8th)
         total-boost 0
         tell-frac-8 (re/ec-tell-frac st8)
         st9 (if (<= (+ tell-frac-8 48) (- frame-bits-1-8th total-boost))
               (re/ec-enc-icdf st8 trim celt/trim-icdf 7)
               st8)
         budget0 (max 0 (- (- frame-bits-1-8th (re/ec-tell-frac st9)) 1))
         skip-rsv (if (> budget0 8) 8 0)
         budget1 (- budget0 skip-rsv)
         {:keys [pulses bits1_8 thresh]} (celt/compute-band-allocations trim (vec (repeat celt/nb-ebands 0)) budget1)
         _ (doseq [i (range celt/nb-ebands)]
             (when (< (nth bits1_8 i) (nth thresh i))
               (throw (ex-info "opus.support.celt-encoder: band below threshold, choose a bigger frame-bytes"
                                {:band i}))))
         st10 (re/ec-enc-bit-logp st9 1 1) ; mandatory 'keep, no skip' bit
         st11 (reduce (fn [st i]
                        (let [n (celt/band-n i) k (nth pulses i)]
                          (if (zero? k)
                            st
                            (let [x (pulse-vector-fn n k)
                                  idx (pvq/encode-pulses n k x)
                                  ft (pvq/v-n-k n k)]
                              (re/ec-enc-uint st idx ft)))))
                      st10 (range celt/nb-ebands))]
     (re/finish st11 frame-bytes))))
