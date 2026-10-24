(ns rtp.header
  "The 12-byte RTP fixed header, plus the CSRC list, header extension and
  padding it can carry — RFC 3550 §5.1.

      0                   1                   2                   3
      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
     |V=2|P|X|  CC   |M|     PT      |       sequence number        |
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
     |                           timestamp                          |
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
     |           synchronization source (SSRC) identifier            |
     +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
     |            contributing source (CSRC) identifiers             |
     |                             ....                               |
     +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+

  The classic wrong way to write this in a language without real bitfields
  is to reach for a byte-array `DataView`/`ByteBuffer` and let it do the
  packing. That hides the actual bit layout — `V`, `P`, `X` and `CC` are
  four fields sharing one octet — behind a library call, which is exactly
  the kind of protocol code an audit can't tell apart from a stub. Here
  every field is placed with `bit-and`/`bit-or`/`bit-shift-left`/
  `unsigned-bit-shift-right` so the layout is legible from the code.

  Bytes are `Sequential` collections of ints in 0..255, in and out — same
  convention as `modbus.pdu`.")

(def ^:const version
  "RTP version this codec speaks. RFC 3550 fixes it at 2 — version 1 and 0
  belong to the vat/vnp audio tools RTP superseded, never appeared on the
  wire as RTP, and are rejected here rather than silently accepted."
  2)

(defn- byte-at [bs i] (bit-and (nth bs i) 0xFF))

(defn- u16 [bs i]
  (bit-or (bit-shift-left (byte-at bs i) 8) (byte-at bs (inc i))))

(defn- u32
  "Combine 4 bytes big-endian into an unsigned 32-bit integer. Plain
  `bit-or`/`bit-shift-left` builds this up through JS's *signed* 32-bit
  bitwise semantics in ClojureScript (`>>>` and `|` both coerce through
  Int32) — so once the top byte's high bit is set, the intermediate result
  goes negative, and e.g. SSRC `0xdeadbeef` decodes as `-559038737`
  instead of `3735928559`. On the JVM this never happens (`bit-or` works
  on 64-bit longs, so a 32-bit value never overflows into the sign bit),
  which is exactly the kind of platform-specific bug that survives a
  `clj`-only test run and only shows up once the same `.cljc` is loaded in
  cljs. `unsigned-bit-shift-right x 0` forces the JS-side reinterpretation
  back to unsigned (`>>> 0`) and is a no-op on the JVM (a non-negative long
  shifted right by 0 bits is unchanged)."
  [bs i]
  (unsigned-bit-shift-right
    (bit-or (bit-shift-left (byte-at bs i) 24)
            (bit-shift-left (byte-at bs (inc i)) 16)
            (bit-shift-left (byte-at bs (+ i 2)) 8)
            (byte-at bs (+ i 3)))
    0))

(defn- push-u16 [out v]
  (-> out
      (conj (bit-and (unsigned-bit-shift-right v 8) 0xFF))
      (conj (bit-and v 0xFF))))

(defn- push-u32 [out v]
  (-> out
      (conj (bit-and (unsigned-bit-shift-right v 24) 0xFF))
      (conj (bit-and (unsigned-bit-shift-right v 16) 0xFF))
      (conj (bit-and (unsigned-bit-shift-right v 8) 0xFF))
      (conj (bit-and v 0xFF))))

(defn encode
  "Encode an RTP packet map to a byte vector.

  Required keys: `:payload-type` (0..127), `:sequence-number` (0..65535),
  `:timestamp` (0..2^32-1), `:ssrc` (0..2^32-1), `:payload` (byte seq).
  Optional: `:marker?` (default false), `:csrc` (0..15 SSRC ints — CC is
  derived from `(count csrc)`, never passed separately, so it cannot
  disagree with the list), `:extension` `{:profile int :data byte-seq}`
  (data length in 32-bit words is derived, must be a multiple of 4 bytes
  per RFC 3550 §5.3.1), `:padding` (0..255 extra zero bytes appended, with
  the RFC-mandated final octet holding `1 + padding`, since the count
  octet includes itself)."
  [{:keys [marker? payload-type sequence-number timestamp ssrc csrc
           extension padding payload]
    :or {marker? false csrc [] padding 0 payload []}}]
  (let [cc (count csrc)
        x? (some? extension)
        p? (pos? padding)
        b0 (bit-or (bit-shift-left version 6)
                    (if p? 0x20 0)
                    (if x? 0x10 0)
                    (bit-and cc 0x0F))
        b1 (bit-or (if marker? 0x80 0) (bit-and payload-type 0x7F))]
    (as-> [] out
      (conj out b0 b1)
      (push-u16 out sequence-number)
      (push-u32 out timestamp)
      (push-u32 out ssrc)
      (reduce push-u32 out csrc)
      (if x?
        (let [{:keys [profile data]} extension
              words (quot (count data) 4)]
          (-> out (push-u16 profile) (push-u16 words) (into data)))
        out)
      (into out payload)
      (if p?
        (into out (concat (repeat (dec padding) 0) [padding]))
        out)
      (vec out))))

(defn- extract-body
  "Slice the payload out of `bs[start,end)`, stripping and validating
  padding if `p?`. Returns `{:payload [...] :padding N}` on success, or
  `[:error :rtp/bad-padding]` — the RFC's padding-count octet includes
  itself, so `0` is never a legal count, and a count larger than the
  region it is supposed to be inside of means the packet is truncated or
  lying."
  [bs start end p?]
  (let [raw (subvec (vec bs) start end)]
    (if p?
      (let [pad (byte-at bs (dec end))]
        (if (or (zero? pad) (> pad (count raw)))
          [:error :rtp/bad-padding]
          {:payload (subvec raw 0 (- (count raw) pad)) :padding pad}))
      {:payload raw :padding 0})))

(defn decode
  "Decode a byte vector into an RTP packet map, or `[:error reason]`.

  Reasons: `:rtp/short-header` (fewer than 12 bytes), `:rtp/bad-version`
  (V != 2), `:rtp/short-csrc` (CC list runs past the end),
  `:rtp/short-extension` (X set but the 4-byte extension header or its
  declared word count don't fit), `:rtp/bad-padding` (P set but the
  trailing count octet is 0, or claims more bytes than remain)."
  [bs]
  (let [n (count bs)]
    (if (< n 12)
      [:error :rtp/short-header]
      (let [b0 (byte-at bs 0)
            b1 (byte-at bs 1)
            v (unsigned-bit-shift-right b0 6)
            p? (not (zero? (bit-and b0 0x20)))
            x? (not (zero? (bit-and b0 0x10)))
            cc (bit-and b0 0x0F)
            marker? (not (zero? (bit-and b1 0x80)))
            pt (bit-and b1 0x7F)
            seq-num (u16 bs 2)
            ts (u32 bs 4)
            ssrc-id (u32 bs 8)
            csrc-end (+ 12 (* 4 cc))
            base {:version v :marker? marker? :payload-type pt
                  :sequence-number seq-num :timestamp ts :ssrc ssrc-id}]
        (cond
          (not= v version) [:error :rtp/bad-version]
          (> csrc-end n) [:error :rtp/short-csrc]

          (not x?)
          (let [csrc (mapv #(u32 bs (+ 12 (* 4 %))) (range cc))
                result (extract-body bs csrc-end n p?)]
            (if (vector? result)
              result
              (merge base {:extension? false :padding? p? :csrc csrc
                           :padding (:padding result) :payload (:payload result)})))

          (< n (+ csrc-end 4))
          [:error :rtp/short-extension]

          :else
          (let [profile (u16 bs csrc-end)
                words (u16 bs (+ csrc-end 2))
                ext-data-start (+ csrc-end 4)
                ext-data-end (+ ext-data-start (* 4 words))]
            (if (> ext-data-end n)
              [:error :rtp/short-extension]
              (let [csrc (mapv #(u32 bs (+ 12 (* 4 %))) (range cc))
                    ext-data (subvec (vec bs) ext-data-start ext-data-end)
                    result (extract-body bs ext-data-end n p?)]
                (if (vector? result)
                  result
                  (merge base {:extension? true :padding? p? :csrc csrc
                               :extension {:profile profile :data ext-data}
                               :padding (:padding result)
                               :payload (:payload result)}))))))))))
