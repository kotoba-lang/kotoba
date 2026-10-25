(ns diameter.avp
  "RFC 6733 §4.1 AVP header, §4.1.1 the optional Vendor-ID, and the padding
  rule stated just above §4.1 (in §4 itself):

  ```
       0                   1                   2                   3
       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |                           AVP Code                            |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |V M P r r r r r|                  AVP Length                   |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |                        Vendor-ID (opt)                        |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |    Data ...
      +-+-+-+-+-+-+-+-+
  ```

  §4: \"Each AVP of type OctetString MUST be padded to align on a 32-bit
  boundary, while other AVP types align naturally. A number of zero-valued
  bytes are added to the end of the AVP Data field until a word boundary is
  reached. The length of the padding is not reflected in the AVP Length
  field.\"

  §4.1: \"AVP Length ... indicates the number of octets in this AVP
  including the AVP Code field, AVP Length field, AVP Flags field,
  Vendor-ID field (if present), and the AVP Data field.\" So AVP Length
  covers everything except the padding, and the padding exists to get the
  *next* AVP onto a 4-octet boundary — the single most common place a
  hand-rolled Diameter codec goes wrong, in either direction: an encoder
  that forgets it desynchronizes every AVP after the first one whose data
  isn't already a multiple of 4 octets long, and a decoder that reads
  `AVP Length` bytes and then just carries on (instead of skipping to the
  next 4-octet boundary) does the same.

  §4.1.1: the Vendor-ID field \"is present if the 'V' bit is set\" — here
  that's not a separate flag the caller sets independently of a value:
  whether an AVP carries `:diameter.avp/vendor-id` *is* what sets the V
  bit, so the two can't be told to disagree."
  (:require [diameter.bytes :as b]))

;; ── AVP Flags (RFC 6733 §4.1) ────────────────────────────────────────────
;;
;; `V M P r r r r r` — V is bit 0 (0x80), M is bit 1 (0x40), P is bit 2
;; (0x20, \"reserved for future usage of end-to-end security ... SHOULD be
;; set to 0\" but still a real flag bit, decoded out rather than dropped),
;; and bits 3-7 are reserved. §4.1: \"The sender of the AVP MUST set 'R'
;; (reserved) bits to 0 and the receiver SHOULD ignore all 'R' (reserved)
;; bits\" — so a decode that finds them set does not fail, but the value is
;; still handed back (`:diameter.avp/reserved-flags`, 0..31) rather than
;; silently discarded, on the same reasoning the message header applies to
;; its own reserved bits (see `diameter.message`).

(def ^:private v-bit 2r10000000)
(def ^:private m-bit 2r01000000)
(def ^:private p-bit 2r00100000)
(def ^:private reserved-mask 2r00011111)

(defn- flags-byte [v? m? p? reserved]
  (bit-or (if v? v-bit 0)
          (if m? m-bit 0)
          (if p? p-bit 0)
          (bit-and reserved reserved-mask)))

(defn fail!
  [code message data]
  (throw (ex-info message (assoc data :type code))))

;; ── padding ──────────────────────────────────────────────────────────────

(defn pad-length
  "How many zero bytes must follow `n` octets of AVP (header + Vendor-ID +
  data, i.e. AVP Length) so the next AVP starts on a 4-octet boundary. 0
  when `n` is already a multiple of 4 — most non-OctetString AVPs, whose
  fixed-width data plus the 8- or 12-octet header is already aligned, never
  pay this at all."
  [n]
  (mod (- 4 (mod n 4)) 4))

;; ── encode ───────────────────────────────────────────────────────────────

(defn encode-avp
  "`{:diameter.avp/code c :diameter.avp/data bytes
     :diameter.avp/vendor-id (optional) :diameter.avp/m? bool
     :diameter.avp/p? bool}` -> the AVP as a vector of ints, header +
  Vendor-ID (if any) + data + zero-padding to the next 4-octet boundary.
  `data` for a Grouped AVP is the already-concatenated encoding of its
  member AVPs (`encode-avps` below, called on the members) — see
  `diameter.types/encode-grouped`.

  Throws (not `[:error ...]`) on a value this side controls being
  malformed — same split as `radius.packet/encode-packet` and
  `snmp.pdu/encode-pdu` in the sibling libraries: encode fails loud because
  the caller built the input, decode never throws because the network
  built it."
  [{:diameter.avp/keys [code data vendor-id m? p? reserved]
    :or {m? false p? false reserved 0}}]
  (when (or (nil? code) (neg? code) (> code 0xffffffff))
    (fail! :diameter/bad-avp-code "AVP Code is a 32-bit unsigned integer" {:code code}))
  (let [data (b/->ints data)
        v? (some? vendor-id)
        header-len (if v? 12 8)
        avp-length (+ header-len (count data))
        pad (pad-length avp-length)]
    (when (> avp-length 0xffffff)
      (fail! :diameter/avp-too-long "AVP Length is a 24-bit field" {:length avp-length}))
    (into
     (into (into [] (b/uint32->bytes code))
           (into [(flags-byte v? m? p? reserved)] (b/uint24->bytes avp-length)))
     (concat (when v? (b/uint32->bytes vendor-id))
             data
             (repeat pad 0)))))

(defn encode-avps
  "Every AVP in `avps`, concatenated in order — each one already carrying
  its own padding, so this is also the correct way to build the Data field
  of a Grouped AVP (RFC 6733 §4.4: member AVPs are concatenated \"including
  their headers and padding\")."
  [avps]
  (vec (mapcat encode-avp avps)))

;; ── decode ───────────────────────────────────────────────────────────────

(defn decode-avp-at
  "One AVP at `pos` in `bs` -> `[:ok avp next-pos]` or `[:error kw]`. Never
  throws. `next-pos` is past this AVP's padding, i.e. where the next AVP
  (if any) begins."
  [bs pos]
  (let [bs (vec bs)
        n (count bs)]
    (cond
      ;; Not even the fixed 8-octet Code+Flags+Length header fits.
      (> (+ pos 8) n) [:error :diameter/avp-truncated-header]
      :else
      (let [code (b/bytes->uint32 (subvec bs pos (+ pos 4)))
            flags (nth bs (+ pos 4))
            v? (not (zero? (bit-and flags v-bit)))
            m? (not (zero? (bit-and flags m-bit)))
            p? (not (zero? (bit-and flags p-bit)))
            reserved (bit-and flags reserved-mask)
            avp-length (b/bytes->uint24 (subvec bs (+ pos 5) (+ pos 8)))
            header-len (if v? 12 8)]
        (cond
          (< avp-length header-len)
          [:error :diameter/avp-length-too-short]

          (> (+ pos header-len) n)
          [:error :diameter/avp-truncated-header]

          (> (+ pos avp-length) n)
          [:error :diameter/avp-truncated-data]

          :else
          (let [vendor-id (when v? (b/bytes->uint32 (subvec bs (+ pos 8) (+ pos 12))))
                data (subvec bs (+ pos header-len) (+ pos avp-length))
                pad (pad-length avp-length)
                pad-end (+ pos avp-length pad)]
            (cond
              (> pad-end n)
              [:error :diameter/avp-padding-truncated]

              (not (every? zero? (subvec bs (+ pos avp-length) pad-end)))
              [:error :diameter/avp-padding-invalid]

              :else
              [:ok
               (cond-> {:diameter.avp/code code
                        :diameter.avp/m? m?
                        :diameter.avp/p? p?
                        :diameter.avp/reserved reserved
                        :diameter.avp/data data}
                 v? (assoc :diameter.avp/vendor-id vendor-id))
               pad-end])))))))

(defn decode-avps
  "Every AVP in `bs`, in order -> `[:ok [avp ...]]` or the first
  `[:error kw]` — fail-fast: an AVP list with one malformed member is a
  malformed list, not N-1 good AVPs and a hole (same rationale as
  `radius.attribute/decode-attributes` in the sibling library)."
  [bs]
  (let [bs (vec bs)
        n (count bs)]
    (loop [pos 0 out []]
      (if (>= pos n)
        [:ok out]
        (let [[status a next-pos] (decode-avp-at bs pos)]
          (if (= :error status)
            [:error a]
            (recur next-pos (conj out a))))))))
