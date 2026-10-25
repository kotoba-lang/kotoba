(ns h264.bitstream
  "H.264 (ITU-T H.264 / ISO/IEC 14496-10 AVC) Annex B byte-stream framing.
   Splits the byte stream into NAL units at start codes and reads the
   1-byte NAL header. Pure cljc, zero dependencies. This is framing only —
   entropy-coded slice data (CABAC/CAVLC) is not decoded; that stays a
   capability-gated native concern per kotoba-lang/utsushi's design.

   New implementation (not an extraction — utsushi.bitstream's split-annexb
   was an unimplemented TODO stub) as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  (:require [h264.rbsp :as rbsp]))

(defn- start-code-len
  "Length of the start code beginning exactly at index `i` (3 or 4), or nil
   if none begins there."
  [b n i]
  (cond
    (and (<= (+ i 4) n) (= 0 (nth b i)) (= 0 (nth b (+ i 1)))
         (= 0 (nth b (+ i 2))) (= 1 (nth b (+ i 3)))) 4
    (and (<= (+ i 3) n) (= 0 (nth b i)) (= 0 (nth b (+ i 1)))
         (= 1 (nth b (+ i 2)))) 3
    :else nil))

(defn split-annexb
  "Split an H.264/H.265 Annex B byte stream (vector of unsigned bytes) into
   NAL unit [start end) byte ranges, start codes (0x000001 / 0x00000001)
   excluded. Returns a vector of {:start :end}."
  [b]
  (let [n (count b)
        ;; positions where a start code BEGINS (not where NAL content begins)
        sc-starts (loop [i 0 acc []]
                    (if (>= i n)
                      acc
                      (if-let [sc (start-code-len b n i)]
                        (recur (+ i sc) (conj acc i))
                        (recur (inc i) acc))))
        content-starts (mapv #(+ % (start-code-len b n %)) sc-starts)
        content-ends   (vec (concat (rest sc-starts) [n]))]
    (vec (map (fn [s e] {:start s :end e}) content-starts content-ends))))

(defn nal-header
  "Parse an H.264 NAL unit's 1-byte header (the byte at `nal-range`'s :start).
   {:forbidden-zero-bit :nal-ref-idc :nal-unit-type}."
  [b nal-range]
  (let [h (nth b (:start nal-range))]
    {:forbidden-zero-bit (bit-and (bit-shift-right h 7) 1)
     :nal-ref-idc        (bit-and (bit-shift-right h 5) 3)
     :nal-unit-type       (bit-and h 0x1f)}))

(def nal-unit-types
  "H.264 Table 7-1 nal_unit_type semantics (the subset this repo cares
   about; unlisted values are still valid NAL types, just unnamed here)."
  {0 :unspecified 1 :slice-non-idr 5 :slice-idr 6 :sei 7 :sps 8 :pps
   9 :access-unit-delimiter 10 :end-of-sequence 11 :end-of-stream 12 :filler-data
   13 :sps-extension 14 :prefix-nal 15 :subset-sps 19 :slice-aux 20 :slice-extension})

(defn nal-units
  "Split `b` into NAL units and attach the parsed header (+ :kind, the
   nal-unit-types lookup) and a raw byte subvec of the NAL (including the
   header byte). Convenience wrapper over split-annexb + nal-header."
  [b]
  (mapv (fn [r] (let [h (nal-header b r)]
                  (assoc h :start (:start r) :end (:end r)
                         :kind (nal-unit-types (:nal-unit-type h) :unspecified)
                         :bytes (subvec b (:start r) (:end r)))))
        (split-annexb b)))

;; --- encode side (Wave 2 addition, kotoba-lang/root ADR-2607121400) ---

(defn write-nal-unit
  "Wrap `rbsp-with-header` (a byte vector with the 1-byte NAL header at
   index 0 followed by the RBSP payload — the shape `h264.sps/encode` and
   `h264.pps/encode` produce) with emulation-prevention escaping
   (`h264.rbsp/escape`) and an Annex B start code, ready to concatenate
   into a byte stream `nal-units`/`split-annexb` can split back apart.
   `long-start-code?` (default true) selects the 4-byte `00 00 00 01`
   start code over the 3-byte `00 00 01` form — both are spec-legal;
   real encoders commonly use the long form for the first NAL of an
   access unit."
  ([rbsp-with-header] (write-nal-unit rbsp-with-header true))
  ([rbsp-with-header long-start-code?]
   (into (if long-start-code? [0 0 0 1] [0 0 1])
         (rbsp/escape rbsp-with-header))))

(defn write-annexb-stream
  "Concatenate multiple `write-nal-unit`-wrapped NAL byte sequences into a
   single Annex B stream."
  [nal-unit-byte-seqs]
  (vec (apply concat nal-unit-byte-seqs)))
