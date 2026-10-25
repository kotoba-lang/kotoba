(ns snmp.types
  "The SNMP-specific ASN.1 types: RFC 1157 §3.2 / RFC 1155-SMI's
  `NetworkAddress`/`Counter`/`Gauge`/`TimeTicks`/`Opaque`, RFC 2578 §7.1.6's
  `Counter64`, and the RFC 3416 §3 varbind exception markers
  (`noSuchObject`/`noSuchInstance`/`endOfMibView`).

  Every one of these is an ordinary ASN.1 element with an unusual tag: the
  five SMI application types are `[APPLICATION n] IMPLICIT` re-tags of a
  primitive that already exists (INTEGER or OCTET STRING), and the three
  exception markers are `[n] IMPLICIT NULL` under the CONTEXT class. Both
  reuses go through `asn1.core/retag`, which is exactly the seam it was
  built for: build the universal element with the existing constructor, then
  swap the tag. No second BER/length/OID codec lives here — see the
  `deps.edn` comment and the README for why.

  `ObjectSyntax` (RFC 1157 §3.2 / RFC 1902 §7) is the CHOICE of all of the
  above plus a bare OID; `encode-value`/`decode-value` are that CHOICE's
  encoder and decoder, keyed on a `:snmp/type` keyword rather than on the
  wire tag, because the tag alone does not distinguish e.g. `Counter32` from
  `Gauge32` (RFC 1155-SMI gives them different APPLICATION numbers, 1 and 2,
  so the tag *does* distinguish those two — but nothing on the wire says
  \"this INTEGER is a plain SNMPv2 `Integer32`\" versus \"this INTEGER is a
  MIB value with no SMI type at all\"; both are simply the universal INTEGER
  tag.  The keyword is the caller's declared intent, not a wire artifact.)"
  (:require [asn1.core :as asn1]
            [kotoba.lang.text :as str]))

;; ── IP address bytes — real bit ops, not delegated to asn1 ────────────────
;;
;; asn1.core has no notion of an address; packing/unpacking one from a
;; 32-bit integer is genuinely SNMP's own bit-twiddling, done the way a
;; NIC's own address register is actually laid out: four octets, high byte
;; first, extracted with `unsigned-bit-shift-right` + `bit-and` and rebuilt
;; with `bit-shift-left` + `bit-or`. Getting the shift amounts backwards is
;; the classic way to turn 192.168.1.1 into 1.1.168.192.

(defn ip-int->bytes
  "A 32-bit unsigned int as 4 big-endian octets."
  [n]
  [(bit-and (unsigned-bit-shift-right n 24) 0xff)
   (bit-and (unsigned-bit-shift-right n 16) 0xff)
   (bit-and (unsigned-bit-shift-right n 8) 0xff)
   (bit-and n 0xff)])

(defn bytes->ip-int
  "4 big-endian octets as a 32-bit unsigned int."
  [[a b c d]]
  (bit-or (bit-shift-left (bit-and a 0xff) 24)
          (bit-shift-left (bit-and b 0xff) 16)
          (bit-shift-left (bit-and c 0xff) 8)
          (bit-and d 0xff)))

(defn- parse-octet
  "A decimal string as an int 0–255, or `nil` — never throws, so a caller
  scanning four of these can just check for `nil` rather than catch."
  [s]
  (when (re-matches #"\d{1,3}" s)
    (let [n #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))]
      (when (<= 0 n 255) n))))

(defn dotted->bytes
  "\"192.168.1.1\" → `[192 168 1 1]`, or `nil` if it is not four 0–255
  octets. `nil` rather than throwing: this is a string parse of untrusted
  input, same contract as the decode side of this namespace."
  [s]
  (let [parts (str/split (str s) #"\." -1)]
    (when (= 4 (count parts))
      (let [ns (mapv parse-octet parts)]
        (when (every? some? ns)
          ns)))))

(defn bytes->dotted
  "`[192 168 1 1]` → \"192.168.1.1\"."
  [bs]
  (str/join "." bs))

;; ── the five RFC 1155-SMI / RFC 2578 application types ─────────────────────
;;
;; IpAddress ::= [APPLICATION 0] IMPLICIT OCTET STRING (SIZE (4))
;; Counter32 ::= [APPLICATION 1] IMPLICIT INTEGER (0..4294967295)
;; Gauge32   ::= [APPLICATION 2] IMPLICIT INTEGER (0..4294967295)
;; TimeTicks ::= [APPLICATION 3] IMPLICIT INTEGER (0..4294967295)
;; Opaque    ::= [APPLICATION 4] IMPLICIT OCTET STRING
;; Counter64 ::= [APPLICATION 6] IMPLICIT INTEGER (0..18446744073709551615)
;;               (RFC 2578 §7.1.6 — not in RFC 1157/v1)

(def ^:private application-tag
  {:ip-address 0 :counter32 1 :gauge32 2 :time-ticks 3 :opaque 4 :counter64 6})

(defn ip-address
  "IpAddress from 4 octets (a vector, not a dotted string — see
  `dotted->bytes` for the string form)."
  [octets]
  (when (not= 4 (count octets))
    (asn1/fail! :snmp/bad-ip-address "IpAddress is exactly 4 octets"
                {:octets octets}))
  (asn1/retag (asn1/octet-string octets) :application (:ip-address application-tag)))

(defn- unsigned32
  "Counter32/Gauge32/TimeTicks share one encoding: a 32-bit unsigned value
  written as a DER-minimal INTEGER (leading `0x00` added when the top bit of
  the top octet would otherwise flip the sign — `asn1/integer` already does
  exactly this) and then re-tagged onto its APPLICATION number."
  [kind n]
  (when-not (<= 0 n 4294967295)
    (asn1/fail! :snmp/out-of-range (str kind " is a 32-bit unsigned value")
                {:value n}))
  (asn1/retag (asn1/integer n) :application (get application-tag kind)))

(defn counter32 [n] (unsigned32 :counter32 n))
(defn gauge32 [n] (unsigned32 :gauge32 n))
(defn time-ticks [n] (unsigned32 :time-ticks n))

(defn opaque [octets] (asn1/retag (asn1/octet-string octets) :application (:opaque application-tag)))

;; Counter64 needs its own content encoder rather than `asn1/integer`,
;; because that function refuses anything past `asn1/safe-integer-limit`
;; (2^53 - 1) — correctly, for the reason its own docstring gives — and a
;; 64-bit counter can legitimately be as large as 2^64 - 1. For values that
;; DO fit in the exactly-representable range we still go through
;; `asn1/integer` (one codepath, one thing to get right); for values that
;; don't, the caller supplies the two's-complement content octets as hex —
;; the same split `asn1.core` itself uses (`integer` / `integer-from-hex`).

(defn counter64
  "Counter64 from a number ≤ `asn1/safe-integer-limit` (2^53 - 1, NOT the
  32-bit range `unsigned32` enforces — Counter64's whole reason to exist is
  values `Counter32` cannot hold). For a value that can exceed even that,
  use `counter64-from-hex`."
  [n]
  (when-not (<= 0 n asn1/safe-integer-limit)
    (asn1/fail! :snmp/out-of-range "Counter64 is unsigned and ≤ safe-integer-limit"
                {:value n}))
  (asn1/retag (asn1/integer n) :application (:counter64 application-tag)))

(defn counter64-from-hex
  "Counter64 from the hex of its unsigned big-endian value, e.g. from a
  128-bit counter formatted by the caller's own bignum library. Adds the
  leading `0x00` DER requires when the top bit is set, the same rule
  `asn1/unsigned-integer-from-hex` implements — reused rather than
  duplicated."
  [hex-string]
  (asn1/retag (asn1/unsigned-integer-from-hex hex-string) :application 6))

;; ── exception markers (RFC 3416 §3 — SNMPv2 varbind CHOICE) ────────────────
;;
;; noSuchObject   [0] IMPLICIT NULL
;; noSuchInstance [1] IMPLICIT NULL
;; endOfMibView   [2] IMPLICIT NULL
;;
;; CONTEXT class, primitive, zero-length content — i.e. NULL's content with
;; a context tag standing in for its universal one, via the same `retag`
;; seam as the application types above.

(def ^:private exception-tag {:no-such-object 0 :no-such-instance 1 :end-of-mib-view 2})
(def ^:private tag->exception (into {} (map (fn [[k v]] [v k])) exception-tag))

(defn exception-marker [kind]
  (asn1/retag (asn1/null*) :context (get exception-tag kind)))

;; ── ObjectSyntax: the CHOICE of everything above, keyed by `:snmp/type` ────

(defn encode-value
  "`{:snmp/type k ...}` → an `asn1.core` element. Throws (via `asn1/fail!`)
  on a value this workspace's ASN.1 layer would also throw on — an
  out-of-range counter, a malformed OID — because this side of the codec
  builds trusted local values, not untrusted wire bytes; see the README for
  why encode and decode have different failure contracts."
  [{:snmp/keys [type] :as v}]
  (case type
    :integer (asn1/integer (:snmp/int v))
    :octet-string (asn1/octet-string (:snmp/bytes v))
    :null (asn1/null*)
    :oid (asn1/oid (:snmp/oid v))
    :ip-address (ip-address (:snmp/bytes v))
    :counter32 (counter32 (:snmp/int v))
    :gauge32 (gauge32 (:snmp/int v))
    :time-ticks (time-ticks (:snmp/int v))
    :opaque (opaque (:snmp/bytes v))
    :counter64 (if (:snmp/hex v)
                 (counter64-from-hex (:snmp/hex v))
                 (counter64 (:snmp/int v)))
    :no-such-object (exception-marker :no-such-object)
    :no-such-instance (exception-marker :no-such-instance)
    :end-of-mib-view (exception-marker :end-of-mib-view)
    (asn1/fail! :snmp/unknown-value-type "no encoder for this :snmp/type"
                {:snmp/type type})))

(defn- unsigned32-value
  "`asn1/integer-value` on an APPLICATION-tagged unsigned 32-bit element,
  refusing a negative result — which is what you get when the encoder
  omitted the leading `0x00` DER (and this counter's own unsignedness)
  requires. A negative Counter32 is not a smaller counter; it is a
  malformed one."
  [element err-kw]
  (let [n (asn1/integer-value element)]
    (if (neg? n) [:error err-kw] [:ok n])))

(defn decode-value
  "The one ObjectSyntax element at `element` → `[:ok value-map]` or
  `[:error kw]`. Never throws — every `asn1.core` read that can throw on
  malformed content (`integer-value`, `oid-value`) is guarded here, because
  the caller is decoding wire bytes from a UDP datagram, not a value it
  built itself."
  [{:asn1/keys [class tag constructed? content] :as element}]
  (try
    (cond
      (and (= :universal class) (= 2 tag) (not constructed?))
      (let [n (asn1/integer-value element)] [:ok {:snmp/type :integer :snmp/int n}])

      (and (= :universal class) (= 4 tag) (not constructed?))
      [:ok {:snmp/type :octet-string :snmp/bytes (asn1/->ints content)}]

      (and (= :universal class) (= 5 tag) (not constructed?))
      [:ok {:snmp/type :null}]

      (and (= :universal class) (= 6 tag) (not constructed?))
      [:ok {:snmp/type :oid :snmp/oid (asn1/oid-value element)}]

      (and (= :application class) (= 0 tag) (not constructed?))
      (if (= 4 (count content))
        [:ok {:snmp/type :ip-address :snmp/bytes (asn1/->ints content)}]
        [:error :snmp/bad-ip-address])

      (and (= :application class) (= 1 tag) (not constructed?))
      (let [[status n] (unsigned32-value element :snmp/negative-counter)]
        (if (= :error status) [:error n] [:ok {:snmp/type :counter32 :snmp/int n}]))

      (and (= :application class) (= 2 tag) (not constructed?))
      (let [[status n] (unsigned32-value element :snmp/negative-counter)]
        (if (= :error status) [:error n] [:ok {:snmp/type :gauge32 :snmp/int n}]))

      (and (= :application class) (= 3 tag) (not constructed?))
      (let [[status n] (unsigned32-value element :snmp/negative-counter)]
        (if (= :error status) [:error n] [:ok {:snmp/type :time-ticks :snmp/int n}]))

      (and (= :application class) (= 4 tag) (not constructed?))
      [:ok {:snmp/type :opaque :snmp/bytes (asn1/->ints content)}]

      (and (= :application class) (= 6 tag) (not constructed?))
      ;; `asn1/integer-value` throws :asn1/integer-too-large past
      ;; safe-integer-limit — expected for a real 64-bit counter, not an
      ;; error, so it is caught here (not by the outer guard) and answered
      ;; with the hex form instead of being flattened to :snmp/malformed-value.
      (try
        (let [n (asn1/integer-value element)]
          (if (neg? n)
            [:error :snmp/negative-counter]
            [:ok {:snmp/type :counter64 :snmp/int n}]))
        (catch #?(:clj Exception :cljs :default) e
          (if (= :asn1/integer-too-large (:type (ex-data e)))
            [:ok {:snmp/type :counter64 :snmp/hex (asn1/integer-hex element)}]
            [:error :snmp/malformed-value])))

      (and (= :context class) (contains? tag->exception tag) (not constructed?))
      [:ok {:snmp/type (get tag->exception tag)}]

      :else [:error :snmp/unknown-value-type])
    (catch #?(:clj Exception :cljs :default) _
      [:error :snmp/malformed-value])))
