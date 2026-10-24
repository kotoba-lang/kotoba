(ns opus.support.range-encoder
  "Test-support-only range ENCODER, mirroring opus.range-decoder, so tests
   can build genuine, decodable Opus/CELT bitstreams for round-trip
   assertions (RFC 6716 Section 5.1 'Range Encoder'). Transcribed from the
   RFC text, same status as opus.range-decoder.

   Not shipped as part of this repo's public decode surface (see
   opus.celt's ns docstring: this repo implements CELT *decode* only) --
   lives under test/ deliberately. Finalization (`finish`) uses a
   deliberately simple safe strategy rather than the reference's optimal
   'maximum trailing zero bits' choice (RFC SS5.1.5): it just flushes `val`
   through the normal carry mechanism and pads/space-checks against a
   caller-supplied target frame length. This is sufficient (proven by the
   round-trip tests that consume it) but is not a byte-minimal encoder."
  (:require [opus.range-decoder :as rd]))

(defn init []
  {:val 0 :rng (bit-shift-left 1 31) :rem -1 :ext 0 :out []
   :end-window 0 :nend-bits 0 :end-bytes []
   :nbits-total 33})

(defn- carry-out [{:keys [rem ext out] :as st} c]
  (if (= c 255)
    (assoc st :ext (inc ext))
    (let [b (bit-shift-right c 8)
          out1 (if (not= rem -1) (conj out (bit-and (+ rem b) 0xff)) out)
          out2 (if (pos? ext) (into out1 (repeat ext (if (= b 1) 0 255))) out1)]
      (assoc st :out out2 :ext 0 :rem (bit-and c 0xff)))))

(defn- normalize [st]
  (loop [st st]
    (if (> (:rng st) (bit-shift-left 1 23))
      st
      (let [c (bit-shift-right (:val st) 23)
            st' (carry-out st c)]
        (recur (assoc st'
                      :val (bit-and (bit-shift-left (:val st) 8) 0x7FFFFFFF)
                      :rng (bit-shift-left (:rng st) 8)
                      :nbits-total (+ (:nbits-total st) 8)))))))

(defn ec-encode
  "RFC 6716 SS5.1.1: encode symbol tuple (fl,fh,ft)."
  [{:keys [val rng] :as st} fl fh ft]
  (let [q (quot rng ft)
        st' (if (pos? fl)
              (assoc st :val (+ val (- rng (* q (- ft fl)))) :rng (* q (- fh fl)))
              (assoc st :rng (- rng (* q (- ft fh)))))]
    (normalize st')))

(defn ec-encode-bin [st fl fh ftb] (ec-encode st fl fh (bit-shift-left 1 ftb)))

(defn ec-enc-bit-logp [st bit logp]
  (let [ft (bit-shift-left 1 logp)]
    (if (zero? bit) (ec-encode st 0 (dec ft) ft) (ec-encode st (dec ft) ft ft))))

(defn ec-enc-icdf [st k icdf ftb]
  (let [ft (bit-shift-left 1 ftb)
        fl (if (zero? k) 0 (- ft (nth icdf (dec k))))
        fh (- ft (nth icdf k))]
    (ec-encode st fl fh ft)))

(defn ec-enc-bits
  "RFC SS5.1.3: pack `nbits` raw bits (LSB-first) into the end-of-frame
   side channel."
  [{:keys [end-window nend-bits end-bytes] :as st} value nbits]
  (loop [window (bit-or end-window (bit-shift-left (bit-and value (dec (bit-shift-left 1 nbits))) nend-bits))
         nbits' (+ nend-bits nbits)
         bytes end-bytes]
    (if (>= nbits' 8)
      (recur (bit-shift-right window 8) (- nbits' 8) (conj bytes (bit-and window 0xff)))
      (assoc st :end-window window :nend-bits nbits' :end-bytes bytes
             :nbits-total (+ (:nbits-total st) nbits)))))

(defn ec-enc-uint
  "RFC SS5.1.4."
  [st t ft]
  (let [ftb (rd/ilog (dec ft))]
    (if (<= ftb 8)
      (ec-encode st t (inc t) ft)
      (let [shift (- ftb 8)
            top (bit-shift-right t shift)
            ft-top (inc (bit-shift-right (dec ft) shift))
            st1 (ec-encode st top (inc top) ft-top)
            low (bit-and t (dec (bit-shift-left 1 shift)))]
        (ec-enc-bits st1 low shift)))))

(defn ec-tell [{:keys [rng nbits-total]}] (- nbits-total (rd/ilog rng)))
(defn ec-tell-frac [st] (rd/ec-tell-frac st))

(defn finish
  "RFC SS5.1.5, simplified (see ns docstring): flush the encoder and return
   a byte vector of exactly `frame-bytes` length. Throws if the encoded
   content (range-coder prefix + raw-bit suffix) doesn't fit."
  [st frame-bytes]
  ;; Flush any still-buffered partial raw-bits byte (RFC SS5.1.3: "the
  ;; encoder must be prepared to merge these values into a single byte" --
  ;; here, simply zero-pad the remaining high bits of the last partial byte
  ;; and flush it; opus.range-decoder's ec-dec-bits treats missing/padding
  ;; bits as zero either way, per RFC SS4.1.2.1/SS4.1.4).
  (let [st0 (if (pos? (:nend-bits st))
              (-> st
                  (update :end-bytes conj (bit-and (:end-window st) 0xff))
                  (assoc :end-window 0 :nend-bits 0))
              st)
        st1 (loop [end (:val st0) st st0]
              (if (zero? end)
                st
                (let [c (bit-shift-right end 23)
                      st' (carry-out st c)]
                  (recur (bit-and (bit-shift-left end 8) 0x7FFFFFFF) st'))))
        st2 (if (or (and (not= (:rem st1) -1) (not= (:rem st1) 0)) (pos? (:ext st1)))
              (carry-out st1 0)
              st1)
        out (:out st2)
        ;; end-bytes were flushed in the order encountered, i.e. index 0 =
        ;; the frame's *last* byte, index 1 = second-to-last, etc.
        end-bytes (:end-bytes st2)
        n-out (count out)
        n-end (count end-bytes)]
    (when (> (+ n-out n-end) frame-bytes)
      (throw (ex-info "opus.support.range-encoder/finish: content doesn't fit target frame size"
                       {:n-out n-out :n-end n-end :frame-bytes frame-bytes})))
    (vec (concat out
                 (repeat (- frame-bytes n-out n-end) 0)
                 (reverse end-bytes)))))
