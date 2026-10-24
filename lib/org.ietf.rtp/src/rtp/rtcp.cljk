(ns rtp.rtcp
  "RTCP — RFC 3550 §6: the common header, the five packet types (SR 200,
  RR 201, SDES 202, BYE 203, APP 204) and compound-packet framing.

  RTCP packets are essentially always sent as a *compound* packet — several
  of these back to back inside one transport datagram, e.g. `SR SDES` or
  `RR RR SDES BYE` — never alone (§6.1 makes an SDES CNAME item mandatory
  in every compound packet a session member sends). `decode-all`/
  `encode-compound` are the entry points that match the wire; `decode-one`/
  the per-type `encode-*` operate on a single sub-packet, for callers
  building or inspecting compound packets piece by piece.

  Common header (all five types share this 4-byte prefix, RFC 3550 §6.1):

      0                   1                   2                   3
      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
     |V=2|P|   RC    |      PT       |             length            |
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

  `length` is the packet's total size in 32-bit words *minus one*,
  including this 4-byte header and any padding — never the body length,
  and never in bytes. Reading it as a byte count is the single most common
  RTCP decoding bug; every function here computes
  `(* 4 (inc length-field))` and nothing else.

  Bytes are `Sequential` collections of ints in 0..255, same convention as
  `rtp.header`/`modbus.pdu`."
  (:require [clojure.string :as str]))

;; ---------------------------------------------------------------------
;; shared byte-level helpers
;; ---------------------------------------------------------------------

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

(defn- s24
  "The 24-bit two's-complement cumulative-lost field, sign-extended to a
  normal integer. RFC 3550 §6.4.1 calls this out explicitly: a source that
  has received more packets than it expected (heavy duplication) reports a
  *negative* cumulative loss, and a naive unsigned 24-bit read turns
  `-1` into `16777215`."
  [bs i]
  (let [v (bit-or (bit-shift-left (byte-at bs i) 16)
                  (bit-shift-left (byte-at bs (inc i)) 8)
                  (byte-at bs (+ i 2)))]
    (if (>= v 0x800000) (- v 0x1000000) v)))

(defn- push-u16 [out v]
  (-> out (conj (bit-and (unsigned-bit-shift-right v 8) 0xFF)) (conj (bit-and v 0xFF))))

(defn- push-u32 [out v]
  (-> out
      (conj (bit-and (unsigned-bit-shift-right v 24) 0xFF))
      (conj (bit-and (unsigned-bit-shift-right v 16) 0xFF))
      (conj (bit-and (unsigned-bit-shift-right v 8) 0xFF))
      (conj (bit-and v 0xFF))))

(defn- push-s24 [out v]
  (let [u (bit-and v 0xFFFFFF)]
    (-> out
        (conj (bit-and (unsigned-bit-shift-right u 16) 0xFF))
        (conj (bit-and (unsigned-bit-shift-right u 8) 0xFF))
        (conj (bit-and u 0xFF)))))

(defn- str->bytes [s]
  #?(:clj (mapv #(bit-and (int %) 0xFF) (.getBytes ^String s "UTF-8"))
     :cljs (vec (js/Array.from (.encode (js/TextEncoder.) s)))))

(defn- bytes->str [bs]
  #?(:clj (String. (byte-array (map #(unchecked-byte %) bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder.) (js/Uint8Array.from (clj->js bs)))))

(defn- pad4
  "Bytes needed to bring `n` up to the next multiple of 4 — SDES items and
  BYE reasons are both padded to a 32-bit boundary (§6.5, §6.6)."
  [n]
  (mod (- 4 (mod n 4)) 4))

;; ---------------------------------------------------------------------
;; report blocks (§6.4.1)
;; ---------------------------------------------------------------------

(def report-block-size 24)

(defn encode-report-block
  "One 24-byte reception report block: SSRC, fraction lost (byte),
  cumulative lost (signed 24-bit), extended highest sequence number,
  jitter, LSR, DLSR — RFC 3550 §6.4.1 Fig. 2."
  [{:keys [ssrc fraction-lost cumulative-lost highest-seq jitter lsr dlsr]}]
  (-> []
      (push-u32 ssrc)
      (conj (bit-and fraction-lost 0xFF))
      (push-s24 cumulative-lost)
      (push-u32 highest-seq)
      (push-u32 jitter)
      (push-u32 lsr)
      (push-u32 dlsr)
      vec))

(defn decode-report-block [bs off]
  {:ssrc (u32 bs off)
   :fraction-lost (byte-at bs (+ off 4))
   :cumulative-lost (s24 bs (+ off 5))
   :highest-seq (u32 bs (+ off 8))
   :jitter (u32 bs (+ off 12))
   :lsr (u32 bs (+ off 16))
   :dlsr (u32 bs (+ off 20))})

(defn decode-report-blocks [bs off rc]
  (mapv #(decode-report-block bs (+ off (* % report-block-size))) (range rc)))

;; ---------------------------------------------------------------------
;; per-type constants
;; ---------------------------------------------------------------------

(def pt->keyword {200 :sr 201 :rr 202 :sdes 203 :bye 204 :app})
(def keyword->pt {:sr 200 :rr 201 :sdes 202 :bye 203 :app 204})
(def sdes-type->keyword {1 :cname 2 :name 3 :email 4 :phone 5 :loc 6 :tool 7 :note 8 :priv})
(def keyword->sdes-type {:cname 1 :name 2 :email 3 :phone 4 :loc 5 :tool 6 :note 7 :priv 8})

;; ---------------------------------------------------------------------
;; whole-packet framing shared by every type: header + body + optional pad
;; ---------------------------------------------------------------------

(defn- frame
  "Wrap a body byte-vector in the 4-byte common header (V=2, `rc` in the
  low 5 bits, `pt`, and the computed word-count-minus-one length), plus
  RFC 3550 §5.1-style padding (last octet = count, counting itself)."
  [rc pt body padding]
  (let [b0 (bit-or (bit-shift-left 2 6) (if (pos? padding) 0x20 0) (bit-and rc 0x1F))
        total (+ 4 (count body) padding)]
    (-> []
        (conj b0 pt)
        (push-u16 (dec (quot total 4)))
        (into body)
        (into (when (pos? padding) (concat (repeat (dec padding) 0) [padding])))
        vec)))

;; ---------------------------------------------------------------------
;; SR / RR (§6.4)
;; ---------------------------------------------------------------------

(defn encode-sr
  "Sender Report (PT 200): sender info (NTP timestamp as separate
  `:ntp-sec`/`:ntp-frac` 32-bit halves, RTP timestamp, packet/octet
  counts) followed by zero or more reception report blocks — RFC 3550
  §6.4.1 Fig. 2."
  [{:keys [ssrc ntp-sec ntp-frac rtp-timestamp packet-count octet-count
           reports padding]
    :or {reports [] padding 0}}]
  (let [body (-> []
                 (push-u32 ssrc)
                 (push-u32 ntp-sec) (push-u32 ntp-frac)
                 (push-u32 rtp-timestamp)
                 (push-u32 packet-count) (push-u32 octet-count)
                 (into (mapcat encode-report-block reports)))]
    (frame (count reports) 200 body padding)))

(defn encode-rr
  "Receiver Report (PT 201): same reception report blocks as SR, without
  sender info — sent by session members that are not themselves an active
  sender, RFC 3550 §6.4.2."
  [{:keys [ssrc reports padding] :or {reports [] padding 0}}]
  (let [body (-> [] (push-u32 ssrc) (into (mapcat encode-report-block reports)))]
    (frame (count reports) 201 body padding)))

(defn- decode-sr-body [bs rc]
  {:type :sr
   :ssrc (u32 bs 0)
   :ntp-sec (u32 bs 4) :ntp-frac (u32 bs 8)
   :rtp-timestamp (u32 bs 12)
   :packet-count (u32 bs 16) :octet-count (u32 bs 20)
   :reports (decode-report-blocks bs 24 rc)})

(defn- decode-rr-body [bs rc]
  {:type :rr :ssrc (u32 bs 0) :reports (decode-report-blocks bs 4 rc)})

;; ---------------------------------------------------------------------
;; SDES (§6.5)
;; ---------------------------------------------------------------------

(defn encode-sdes
  "Source Description (PT 202): one chunk per SSRC/CSRC, each chunk a
  4-byte identifier followed by `type(1) length(1) text(length)` items
  terminated by a zero type octet and padded to a 32-bit boundary — RFC
  3550 §6.5. `chunks` is `[{:ssrc int :items [{:type kw :text str} ...]}
  ...]`; item `:type` is one of `#{:cname :name :email :phone :loc :tool
  :note :priv}` (§6.5.1-8)."
  [{:keys [chunks padding] :or {chunks [] padding 0}}]
  (let [encode-chunk
        (fn [{:keys [ssrc items]}]
          (let [item-bytes (mapcat (fn [{:keys [type text]}]
                                      (let [tb (str->bytes text)]
                                        (into [(keyword->sdes-type type) (count tb)] tb)))
                                    items)
                unpadded (-> [] (push-u32 ssrc) (into item-bytes) (conj 0))]
            (into unpadded (repeat (pad4 (count unpadded)) 0))))
        body (mapcat encode-chunk chunks)]
    (frame (count chunks) 202 (vec body) padding)))

(defn- decode-sdes-chunk
  "Returns `[chunk bytes-consumed]`, or `[[:error reason] nil]`."
  [bs off]
  (let [ssrc (u32 bs off)]
    (loop [i (+ off 4) items []]
      (if (>= i (count bs))
        [[:error :rtcp/short-sdes] nil]
        (let [item-type (byte-at bs i)]
          (if (zero? item-type)
            (let [consumed (- (inc i) off)
                  padded (+ consumed (pad4 consumed))]
              (if (> (+ off padded) (count bs))
                [[:error :rtcp/short-sdes] nil]
                [{:ssrc ssrc :items items} padded]))
            (if (>= (inc i) (count bs))
              [[:error :rtcp/short-sdes] nil]
              (let [len (byte-at bs (inc i))
                    text-start (+ i 2)
                    text-end (+ text-start len)]
                (if (> text-end (count bs))
                  [[:error :rtcp/short-sdes] nil]
                  (recur text-end
                         (conj items {:type (get sdes-type->keyword item-type item-type)
                                      :text (bytes->str (subvec (vec bs) text-start text-end))})))))))))))

(defn- decode-sdes-body [bs sc]
  (loop [off 0 n sc chunks []]
    (if (zero? n)
      {:type :sdes :chunks chunks}
      (let [[result consumed] (decode-sdes-chunk bs off)]
        (if (and (vector? result) (= :error (first result)))
          result
          (recur (+ off consumed) (dec n) (conj chunks result)))))))

;; ---------------------------------------------------------------------
;; BYE (§6.6)
;; ---------------------------------------------------------------------

(defn encode-bye
  "Goodbye (PT 203): a list of leaving SSRC/CSRC identifiers, optionally
  followed by a `length(1) reason(length)` text padded to a 32-bit
  boundary — RFC 3550 §6.6."
  [{:keys [sources reason padding] :or {sources [] padding 0}}]
  (let [ids (reduce push-u32 [] sources)
        with-reason (if reason
                      (let [rb (str->bytes reason)
                            unpadded (into (conj ids (count rb)) rb)]
                        (into unpadded (repeat (pad4 (count unpadded)) 0)))
                      ids)]
    (frame (count sources) 203 with-reason padding)))

(defn- decode-bye-body [bs sc]
  (let [ids-end (* sc 4)
        sources (mapv #(u32 bs (* % 4)) (range sc))]
    (if (>= ids-end (count bs))
      {:type :bye :sources sources}
      (let [len (byte-at bs ids-end)
            text-start (inc ids-end)
            text-end (+ text-start len)]
        (if (> text-end (count bs))
          [:error :rtcp/short-bye]
          {:type :bye :sources sources
           :reason (bytes->str (subvec (vec bs) text-start text-end))})))))

;; ---------------------------------------------------------------------
;; APP (§6.7)
;; ---------------------------------------------------------------------

(defn encode-app
  "Application-defined (PT 204): a 4-byte ASCII name registered by the
  application, followed by arbitrary application data — RFC 3550 §6.7.
  `:subtype` reuses the 5-bit RC/SC field position for an
  application-defined subtype, per the RFC.

  Unlike SR/RR (always a multiple of 4 bytes by construction) and SDES/BYE
  (which pad their variable-length text fields themselves, §6.5/§6.6),
  `:data` is caller-supplied and RFC 3550 does not define an APP-specific
  padding rule for it — only the general packet-level P-bit padding
  (§5.1) applies. So any bytes needed to bring the packet up to a 32-bit
  boundary are folded into that same padding mechanism (added to whatever
  `:padding` the caller asked for), rather than truncated by `frame`'s
  word-count arithmetic — the classic way this goes wrong is computing
  `(quot total-bytes 4)` on a body that was never a multiple of 4 and
  silently dropping the last 1-3 bytes of application data."
  [{:keys [subtype ssrc name data padding] :or {data [] padding 0}}]
  (let [name-bytes (take 4 (concat (str->bytes name) (repeat 0)))
        raw-body (-> [] (push-u32 ssrc) (into name-bytes) (into data))
        align-pad (pad4 (count raw-body))]
    (frame subtype 204 (vec raw-body) (+ padding align-pad))))

(defn- decode-app-body [bs subtype]
  {:type :app :subtype subtype :ssrc (u32 bs 0)
   :name (str/replace (bytes->str (subvec (vec bs) 4 8)) " " "")
   :data (subvec (vec bs) 8 (count bs))})

;; ---------------------------------------------------------------------
;; single-packet decode/encode dispatch
;; ---------------------------------------------------------------------

(defn encode-one
  "Dispatch to the right `encode-*` by `(:type packet)`."
  [{:keys [type] :as packet}]
  (case type
    :sr (encode-sr packet)
    :rr (encode-rr packet)
    :sdes (encode-sdes packet)
    :bye (encode-bye packet)
    :app (encode-app packet)))

(defn decode-one
  "Decode a single RTCP sub-packet starting at the front of `bs`. Returns
  `[packet rest-bytes]` on success (`rest-bytes` is whatever followed this
  sub-packet — the next one in a compound packet, or `[]`), or
  `[[:error reason] nil]`.

  Reasons: `:rtcp/short-header` (fewer than 4 bytes), `:rtcp/bad-version`
  (V != 2), `:rtcp/short-packet` (the `length` field claims more bytes
  than `bs` has), `:rtcp/bad-padding` (P set but the trailing count octet
  is 0 or exceeds this packet's own body — same reasoning as
  `rtp.header/decode`), `:rtcp/unknown-type` (PT outside 200..204),
  `:rtcp/short-sdes`/`:rtcp/short-bye` (a type-specific sub-field runs
  past this packet's declared length)."
  [bs]
  (let [n (count bs)]
    (if (< n 4)
      [[:error :rtcp/short-header] nil]
      (let [b0 (byte-at bs 0)
            v (unsigned-bit-shift-right b0 6)
            p? (not (zero? (bit-and b0 0x20)))
            rc (bit-and b0 0x1F)
            pt (byte-at bs 1)
            len-words (u16 bs 2)
            total (* 4 (inc len-words))]
        (cond
          (not= v 2) [[:error :rtcp/bad-version] nil]
          (> total n) [[:error :rtcp/short-packet] nil]
          (not (contains? pt->keyword pt)) [[:error :rtcp/unknown-type] nil]
          :else
          (let [whole (subvec (vec bs) 0 total)
                rest-bytes (subvec (vec bs) total n)]
            (if-not p?
              (let [body (subvec whole 4 total)
                    result (case (get pt->keyword pt)
                             :sr (decode-sr-body body rc)
                             :rr (decode-rr-body body rc)
                             :sdes (decode-sdes-body body rc)
                             :bye (decode-bye-body body rc)
                             :app (decode-app-body body rc))]
                (if (and (vector? result) (= :error (first result)))
                  [result nil]
                  [result rest-bytes]))
              (let [pad (byte-at whole (dec total))]
                (if (or (zero? pad) (> pad (- total 4)))
                  [[:error :rtcp/bad-padding] nil]
                  (let [body (subvec whole 4 (- total pad))
                        result (case (get pt->keyword pt)
                                 :sr (decode-sr-body body rc)
                                 :rr (decode-rr-body body rc)
                                 :sdes (decode-sdes-body body rc)
                                 :bye (decode-bye-body body rc)
                                 :app (decode-app-body body rc))]
                    (if (and (vector? result) (= :error (first result)))
                      [result nil]
                      [(assoc result :padding pad) rest-bytes])))))))))))

;; ---------------------------------------------------------------------
;; compound-packet framing (§6.1)
;; ---------------------------------------------------------------------

(defn encode-compound
  "Concatenate `(encode-one p)` for each `p` in `packets` — a compound
  RTCP packet, RFC 3550 §6.1. No length prefix of its own: compound
  packets are delimited by the transport (one UDP datagram), not by
  anything inside the RTCP bytes themselves."
  [packets]
  (vec (mapcat encode-one packets)))

(defn decode-all
  "Decode every RTCP sub-packet in a compound packet. Returns a vector of
  packets on success, or `[:error reason]` (the reason from whichever
  sub-packet `decode-one` failed on) if any sub-packet fails to parse —
  a compound packet is all-or-nothing, since a corrupt sub-packet also
  corrupts the byte offset of everything after it."
  [bs]
  (loop [rest-bytes (vec bs) acc []]
    (if (empty? rest-bytes)
      acc
      (let [[result more] (decode-one rest-bytes)]
        (if (and (vector? result) (= :error (first result)))
          result
          (recur more (conj acc result)))))))
