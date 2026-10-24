(ns diameter.types
  "RFC 6733 §4.2 Basic AVP Data Formats and §4.3.1 the common Derived AVP
  Data Formats — codecs from a domain value to/from the raw Data bytes of
  an AVP (`diameter.avp/encode-avp`'s `:diameter.avp/data`, not a whole
  AVP: these compose with `diameter.avp`, they don't replace it).

  Implemented: OctetString, Integer32, Integer64, Unsigned32, Unsigned64,
  Float32, UTF8String, DiameterIdentity, Enumerated, Grouped.

  Scoped out (RFC 6733 §4.3.1 defines these too, but they cost correctness
  under time pressure and this repo would rather be narrow and right than
  broad and guessed):

  - **Address** — a discriminated union (§4.3.1: \"first two octets ...
    represent the AddressType\") over the IANA Address Family Numbers
    registry, which this repo does not vendor a copy of. `Host-IP-Address`
    (RFC 6733 §5.3.5), the one base-protocol AVP that needs it, is left as
    a raw `diameter.avp/data` OctetString in `diameter.avps` — encodable
    and decodable as bytes, just not decoded into a semantic address.
  - **Time** (NTP-epoch seconds, with the 2036 rollover procedure) and
    **DiameterURI** (a URI grammar with its own default-port rules) — pull
    in more spec surface than this repo covers.
  - **Float64** — Float32 alone already needs `Float/floatToIntBits`
    (JVM) / `DataView` (JS) to get the IEEE-754 bit pattern exactly right;
    doubling the width doubles the chance of a subtle bit-order mistake
    with no independent RFC 6733 test vector to catch it against, so it's
    left out rather than shipped unverified.
  - **IPFilterRule** — its own grammar (RFC 6733 §4.3.1 refers out to
    RFC 6733's own IPFilterRule ABNF), unrelated to AVP framing.

  None of these are needed for anything this repo actually builds (see
  `diameter.avps`)."
  (:require [diameter.bytes :as b]
            [diameter.avp :as avp]))

;; ── OctetString / DiameterIdentity (RFC 6733 §4.2, §4.3.1) ──────────────
;;
;; OctetString is just \"arbitrary data of variable length\" — already the
;; working representation (`diameter.bytes/->ints`), so there is nothing to
;; convert. DiameterIdentity (§4.3.1) \"is derived from the OctetString
;; Basic AVP Format\" and is specified to be ASCII (an FQDN or realm), which
;; is a byte-identical subset of UTF-8, so it is implemented as an alias of
;; `encode-utf8`/`decode-utf8` below rather than a second string codec.

(defn encode-octet-string [data] (b/->ints data))
(defn decode-octet-string [data] (vec data))

;; ── UTF8String (RFC 6733 §4.3.1) ─────────────────────────────────────────
;;
;; \"This is a human-readable string represented using the ISO/IEC IS
;; 10646-1 character set, encoded as an OctetString using the UTF-8
;; transformation format.\" `TextEncoder`/`TextDecoder` (ClojureScript) and
;; `String.getBytes/new String` with an explicit UTF-8 `Charset`
;; (Clojure/JVM) are each the platform's own UTF-8 implementation, not a
;; hand-rolled one — there is no independent second implementation to
;; cross-check this against, unlike the CRC-style \"definition + optimized
;; form\" pattern used elsewhere in this workspace's sibling codecs, because
;; there is no smaller definition of UTF-8 to write by hand that wouldn't
;; just be a worse copy of the one the platform already ships.

(defn encode-utf8 [s]
  #?(:clj (vec (.getBytes (str s) "UTF-8"))
     :cljs (vec (.encode (js/TextEncoder.) (str s)))))

(defn decode-utf8 [data]
  #?(:clj (String. (byte-array (map unchecked-byte (b/->ints data))) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js (b/->ints data))))))

(def encode-diameter-identity encode-utf8)
(def decode-diameter-identity decode-utf8)

;; ── Integer32 / Unsigned32 (RFC 6733 §4.2) ───────────────────────────────
;;
;; \"AVP Length field MUST be set to 12 (16 if the 'V' bit is enabled)\" —
;; that's this repo's `diameter.avp/encode-avp` computing AVP Length from
;; the 4-octet Data it's given, automatically satisfying this whenever the
;; Data is exactly these 4 bytes; these functions don't need to know
;; anything about AVP Length themselves.

(defn encode-int32 [n] (b/int32->bytes n))
(defn decode-int32 [data] (b/bytes->int32 (vec data)))

(defn encode-uint32 [n] (b/uint32->bytes n))
(defn decode-uint32 [data] (b/bytes->uint32 (vec data)))

;; ── Integer64 / Unsigned64 (RFC 6733 §4.2) ───────────────────────────────
;;
;; See `diameter.bytes`'s namespace-level comment on the `{:hi :lo}` pair
;; these use instead of a single 64-bit scalar.

(defn encode-int64 [hilo] (b/hilo->bytes hilo))
(defn decode-int64 [data] (b/bytes->hilo (vec data)))

(defn encode-uint64 [hilo] (b/hilo->bytes hilo))
(defn decode-uint64 [data] (b/bytes->hilo (vec data)))

;; ── Float32 (RFC 6733 §4.2) ───────────────────────────────────────────────
;;
;; \"floating point values of single precision ... transmitted in network
;; byte order.\" Two independent routes to the same IEEE-754 bit pattern,
;; cross-checked in the test suite the way `modbus.crc` cross-checks its
;; bitwise CRC against its table form: `Float/floatToIntBits` (JVM,
;; :clj) reads the bits the platform itself would use for this exact
;; `float`, and `DataView.setFloat32`/`getFloat32` (:cljs) does the
;; equivalent through the standard typed-array API rather than through
;; hand-rolled sign/exponent/mantissa bit-twiddling — both are the
;; platform's own IEEE-754, not a reimplementation of it, for the same
;; reason `encode-utf8` above doesn't hand-roll UTF-8.

(defn encode-float32 [f]
  #?(:clj (b/uint32->bytes (bit-and (Float/floatToIntBits (float f)) 0xffffffff))
     :cljs (let [buf (js/ArrayBuffer. 4)
                 view (js/DataView. buf)]
             (.setFloat32 view 0 f false)
             (vec (for [i (range 4)] (.getUint8 view i))))))

(defn decode-float32 [data]
  (let [data (vec data)]
    #?(:clj (Float/intBitsToFloat (unchecked-int (b/bytes->uint32 data)))
       :cljs (let [buf (js/ArrayBuffer. 4)
                   view (js/DataView. buf)]
               (dotimes [i 4] (.setUint8 view i (nth data i)))
               (.getFloat32 view 0 false)))))

;; ── Enumerated (RFC 6733 §4.3.1) ─────────────────────────────────────────
;;
;; \"Derived from the Integer32 Basic AVP Format. The definition contains a
;; list of valid values and their interpretation ... described in the
;; Diameter application introducing the AVP.\" Wire form is plain
;; Integer32 — the name<->code table is supplied by the caller per AVP
;; (see `diameter.avps/disconnect-cause-name->code` for RFC 6733's own
;; example, §5.4.3). An unrecognized code on decode is returned as the raw
;; integer rather than failing: a future/vendor value an older decoder
;; doesn't know the name for is not the same thing as malformed wire data.

(defn encode-enumerated [value name->code]
  (encode-int32 (if (keyword? value) (get name->code value) value)))

(defn decode-enumerated [data code->name]
  (let [n (decode-int32 data)]
    (get code->name n n)))

;; ── Grouped (RFC 6733 §4.4) ───────────────────────────────────────────────
;;
;; \"The Data field is specified as a sequence of AVPs ... concatenated --
;; including their headers and padding.\" That's exactly
;; `diameter.avp/encode-avps`/`decode-avps`; recursion into nested Grouped
;; AVPs happens for free because a member AVP's own Data is decoded the
;; same way by whatever reads it.

(def encode-grouped avp/encode-avps)
(def decode-grouped avp/decode-avps)
