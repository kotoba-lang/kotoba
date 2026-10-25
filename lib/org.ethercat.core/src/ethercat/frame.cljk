(ns ethercat.frame
  "The EtherCAT frame header (ETG.1000/ETG.1500, 'EtherCAT frame'; also
  called the 'Ethernet frame header' in the specification family since it
  is the first thing after the Ethernet header) — a single 2-byte field
  that precedes one or more datagrams (see `ethercat.datagram`).

  Bit layout, **little-endian on the wire**, 16 bits total:

    bit 15      Type (see below — actually 4 bits, 15..12; written this
                way because the field packs LSB-first and it is easy to
                get the bit direction backwards, see the note below)
    bits 15..12 Type      4 bits — `1` = 'EtherCAT command' (the only
                          value any real network uses; other values were
                          reserved for a since-abandoned 'Network
                          Variables' protocol)
    bit 11      Reserved  1 bit, must be 0
    bits 10..0  Length    11 bits — the length in bytes of everything
                          that follows this header (all datagrams,
                          header+data+WKC each), NOT including this
                          2-byte header itself

  Restated without the bit-position ambiguity: `header = (Length & 0x7FF)
  | ((Reserved & 0x1) << 11) | ((Type & 0xF) << 12)`, and because EtherCAT
  is little-endian, that 16-bit value's LOW byte goes on the wire FIRST —
  the mirror image of PROFINET, which is big-endian throughout (see
  `com-profibus-profinet`), and the same direction as CANopen's SDO
  multi-byte fields (see `org-can-cia-canopen`).

  Source: this exact bit layout (11/1/4 split, little-endian) is
  reproduced identically in the open-source EtherCAT master stacks SOEM
  (github.com/OpenEtherCATsociety/SOEM, `soem/ethercattype.h`
  `ec_comt`/`EC_ETHERCATTYPE`) and IgH EtherCAT Master
  (etherlab.org, `master/ethernet.h`), and in Wireshark's
  `epan/dissectors/packet-ecatmb.c`. ETG.1000 itself is a paywalled
  EtherCAT Technology Group membership document not quoted here from
  memory.")

(def ethertype 0x88A4)
(def ecat-command-type "The only Type value used in practice." 1)
(def max-length "2^11 - 1: the 11-bit Length field's ceiling." 0x7FF)

(defn- u16le [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd-u16le [bs off] (bit-or (bit-and (nth bs off) 0xFF)
                                  (bit-shift-left (bit-and (nth bs (inc off)) 0xFF) 8)))

(defn encode-header
  "`{:length 0..2047 :type (default 1) :reserved (default 0)}` -> `[:ok
  [lo hi]]`, the 2-byte EtherCAT frame header, little-endian."
  [{:keys [length type reserved] :or {type ecat-command-type reserved 0}}]
  (cond
    (not (<= 0 length max-length)) [:error :ethercat/length-out-of-range length]
    (not (<= 0 type 0xF)) [:error :ethercat/type-out-of-range type]
    (not (#{0 1} reserved)) [:error :ethercat/reserved-not-a-bit reserved]
    :else
    (let [word (bit-or (bit-and length 0x7FF)
                        (bit-shift-left (bit-and reserved 0x1) 11)
                        (bit-shift-left (bit-and type 0xF) 12))]
      [:ok (u16le word)])))

(defn decode-header
  "2 bytes -> `[:ok {:length :type :reserved}]`."
  [bytes]
  (let [bs (vec bytes)]
    (if (not= 2 (count bs))
      [:error :ethercat/header-wrong-length (count bs)]
      (let [word (rd-u16le bs 0)]
        [:ok {:length (bit-and word 0x7FF)
              :reserved (bit-and (unsigned-bit-shift-right word 11) 0x1)
              :type (bit-and (unsigned-bit-shift-right word 12) 0xF)}]))))

;; ── composing multiple datagrams into one frame ─────────────────────────
;; A frame's own Length field, and each datagram's own More (M) bit, are
;; both derivable from the list of datagrams — the caller should not have
;; to keep them consistent by hand. `encode-frame` does that: given
;; already-built datagram byte-vectors (see `ethercat.datagram`), it stamps
;; M correctly on all but the last and computes the header Length as the
;; sum of every datagram's own length (10-byte header + Data + 2-byte
;; WKC each).

(defn- set-more-bit
  "Datagram bytes -> the same bytes with the Len/flags word's M bit (byte
  7, bit 7 — see `ethercat.datagram`'s Len/flags layout) forced to
  `more?`. Kept private and byte-level (not round-tripped through
  `ethercat.datagram/decode-datagram`+`encode-datagram`) so composing a
  frame cannot silently perturb any other field."
  [datagram-bytes more?]
  (update (vec datagram-bytes) 7
          (fn [hi] (if more? (bit-or hi 0x80) (bit-and hi 0x7F)))))

(defn encode-frame
  "`datagrams` (a non-empty seq of already-encoded datagram byte-vectors,
  e.g. from `ethercat.datagram/encode-datagram` — their own `:more?` bit
  is IGNORED and recomputed here) -> `[:ok bytes]`, the header followed
  by every datagram back-to-back with M stamped correctly."
  [datagrams]
  (let [datagrams (vec datagrams)
        n (count datagrams)]
    (cond
      (zero? n) [:error :ethercat/frame-has-no-datagrams nil]
      :else
      (let [total-length (reduce + (map count datagrams))
            [hst header] (encode-header {:length total-length})]
        (if (= :error hst)
          [:error header]
          [:ok (reduce (fn [acc [i dg]]
                         (into acc (set-more-bit dg (< i (dec n)))))
                       (vec header)
                       (map-indexed vector datagrams))])))))

(defn- walk-datagrams
  "pos into `bs` + accumulated datagram byte-vectors -> `[:ok datagrams]`
  or `[:error kw data]`. Separated from `decode-frame` so each step's
  `cond` stays flat instead of nesting deeper with every check."
  [bs pos out]
  (cond
    (>= pos (count bs))
    [:error :ethercat/frame-truncated {:consumed pos :total (count bs)}]

    (< (- (count bs) pos) 12)
    [:error :ethercat/datagram-header-truncated {:remaining (- (count bs) pos)}]

    :else
    (let [len-flags (rd-u16le bs (+ pos 6))
          length (bit-and len-flags 0x7FF)
          more? (pos? (bit-and len-flags 0x8000))
          dg-total (+ 10 length 2)]
      (cond
        (> (+ pos dg-total) (count bs))
        [:error :ethercat/datagram-truncated {:need dg-total :remaining (- (count bs) pos)}]

        more?
        (recur bs (+ pos dg-total) (conj out (subvec bs pos (+ pos dg-total))))

        :else
        [:ok (conj out (subvec bs pos (+ pos dg-total)))]))))

(defn decode-frame
  "bytes -> `[:ok {:length :type :datagrams [raw byte-vectors]}]`. Walks
  the datagram chain using each datagram's OWN Len/M fields (it does not
  trust the header's `:length` for anything beyond validating the total
  at the end) — a caller decodes each returned byte-vector with
  `ethercat.datagram/decode-datagram`. Splitting frame-walking from
  datagram-field-decoding keeps each function's error cases narrow."
  [bytes]
  (let [bs (vec bytes)]
    (if (< (count bs) 2)
      [:error :ethercat/frame-too-short (count bs)]
      (let [[hst header] (decode-header (subvec bs 0 2))]
        (if (= :error hst)
          [:error header]
          (let [[wst datagrams] (walk-datagrams bs 2 [])]
            (if (= :error wst)
              [:error datagrams]
              [:ok {:length (:length header) :type (:type header) :datagrams datagrams}])))))))

(defn header-round-trip?
  "Convenience predicate the test suite leans on for the exhaustive sweep
  — packs then unpacks and reports whether the fields survived."
  [fields]
  (let [[pst bytes] (encode-header fields)]
    (and (= :ok pst)
         (let [[ust back] (decode-header bytes)]
           (and (= :ok ust)
                (= (:length fields) (:length back))
                (= (get fields :type ecat-command-type) (:type back))
                (= (get fields :reserved 0) (:reserved back)))))))
