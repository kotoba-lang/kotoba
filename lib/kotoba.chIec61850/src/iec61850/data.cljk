(ns iec61850.data
  "The MMS-style `Data` CHOICE that fills GOOSE's `allData` (IEC 61850-8-1)
  and, unmapped here, MMS `Read`/`Write`/`InformationReport` (ISO 9506-2).

  This is BER wearing IEC 61850's context tags, so every element is built
  and read through `asn1.core` — `asn1/implicit` for the tag-and-keep-content
  cases (boolean, bit-string, integer, unsigned, octet-string, floating-point)
  and `asn1/boolean-value` / `asn1/bit-string-value` / `asn1/integer-value` /
  `asn1/string-value` to read them back, since IMPLICIT tagging changes the
  wire tag but not the content encoding those functions already validate.
  Nothing here re-derives DER integer minimality, BIT STRING unused-bit
  handling, or BER tag/length framing — that is exactly the point of wiring
  to `org-ietf-asn1` instead of writing a second BER codec.

  ## Provenance of the tag numbers — read before trusting them

  IEC 61850-8-1 (and the ISO 9506-2 `Data` type it extends) are paywalled
  standards; the tag table below is reconstructed from public, widely-used
  open-source implementations that ship their own copy of this ASN.1 —
  libiec61850's `mms_common.h` `MmsType` enum and Wireshark's BSD-licensed
  `epan/dissectors/asn1/mms`/`goose` modules — not transcribed from the
  standard text itself. Tags 1-16 (the base MMS `Data` CHOICE) are the ones
  seen consistently across those sources. Tag 17 for the IEC 61850-7-2
  `utc-time` extension to `Data` (not present in base MMS) is the value
  seen most often in that literature, but it could not be independently
  verified against standard text from memory, so treat it as best-effort
  rather than certified. What this namespace can actually promise is an
  internal property: `decode-data` inverts `encode-data` exactly, which the
  round-trip test asserts over every variant below — that holds regardless
  of whether tag 17 matches the standard's own choice.

  | tag | name | ASN.1 shape | scope here |
  |---|---|---|---|
  | 2 | structure | `[2] IMPLICIT SEQUENCE OF Data` | yes |
  | 3 | boolean | `[3] IMPLICIT BOOLEAN` | yes |
  | 4 | bit-string | `[4] IMPLICIT BIT STRING` | yes |
  | 5 | integer | `[5] IMPLICIT INTEGER` | yes |
  | 6 | unsigned | `[6] IMPLICIT INTEGER` (non-negative) | yes |
  | 7 | floating-point | `[7] IMPLICIT OCTET STRING` (MMS FloatingPoint) | yes, 32-bit only |
  | 9 | octet-string | `[9] IMPLICIT OCTET STRING` | yes |
  | 10 | visible-string | `[10] IMPLICIT VisibleString` | yes |
  | 17 | utc-time | `[17] IMPLICIT UtcTime` (61850 binary form, see `iec61850.utctime`) | yes |
  | 1, 8, 11-16 | array, real, binary-time, bcd, booleanArray, objId, mMSString | — | **not implemented** |"
  (:require [asn1.core :as asn1]
            [iec61850.utctime :as utctime]))

;; ── tag table ────────────────────────────────────────────────────────────────

(def tags
  "Choice name <-> context tag number. A single map both directions are
  derived from, so the encoder and decoder cannot silently disagree with
  each other about a number."
  {:structure 2 :boolean 3 :bit-string 4 :integer 5 :unsigned 6
   :floating-point 7 :octet-string 9 :visible-string 10 :utc-time 17})

(def ^:private tag->name (into {} (map (fn [[k v]] [v k])) tags))

;; ── FloatingPoint (ISO 9506-2 §6.6, "FloatingPoint" — 32-bit profile only) ────
;;
;; Content = 1 octet exponent-width (8, for IEEE 754 binary32) followed by
;; the 4 IEEE 754 binary32 octets, big-endian. The bit *pattern* conversion
;; is done with each platform's own float representation (`Float/floatToIntBits`
;; on the JVM, `DataView` on JS) rather than a hand-rolled IEEE 754 rounding
;; routine — re-deriving correctly-rounded float encode/decode by hand is a
;; well-known place to introduce a bug that only shows up at specific
;; mantissa boundaries, and both platforms already have a byte-correct
;; implementation. The part that touches the wire — splitting/assembling the
;; 32-bit pattern into big-endian octets — is plain `bit-and`/`bit-shift`.

(defn- float32-bits [n]
  #?(:clj (bit-and (Float/floatToIntBits (float n)) 0xFFFFFFFF)
     :cljs (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
             (.setFloat32 dv 0 n false)
             (.getUint32 dv 0 false))))

(defn- bits->float32 [bits]
  #?(:clj (Float/intBitsToFloat (unchecked-int bits))
     :cljs (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
             (.setUint32 dv 0 bits false)
             (.getFloat32 dv 0 false))))

(defn- encode-float32-content [n]
  (let [b (float32-bits n)]
    [8
     (bit-and (unsigned-bit-shift-right b 24) 0xFF)
     (bit-and (unsigned-bit-shift-right b 16) 0xFF)
     (bit-and (unsigned-bit-shift-right b 8) 0xFF)
     (bit-and b 0xFF)]))

(defn- decode-float32-content [content]
  (let [ints (asn1/->ints content)]
    (cond
      (not= 5 (count ints))
      [:error :iec61850.data/floating-point-wrong-length {:length (count ints)}]

      (not= 8 (first ints))
      [:error :iec61850.data/floating-point-unsupported-width {:exponent-width (first ints)}]

      :else
      (let [[_ b3 b2 b1 b0] ints
            bits (bit-or (bit-shift-left b3 24) (bit-shift-left b2 16)
                          (bit-shift-left b1 8) b0)]
        [:ok (bits->float32 bits)]))))

;; ── encode ───────────────────────────────────────────────────────────────────

(declare encode-data)

(defn- ctx [n element]
  (asn1/implicit n element))

(defn encode-data
  "`[choice value]` -> an `asn1.core` element ready for `asn1/encode-ints`.

  `choice` is one of the keys of `tags`. `:structure`'s value is a seq of
  further `[choice value]` pairs (Data is recursive: a structure holds
  Data, not just leaves)."
  [[choice value]]
  (case choice
    :boolean (ctx (:boolean tags) (asn1/boolean* (boolean value)))
    :bit-string (ctx (:bit-string tags)
                      (asn1/bit-string (:ints value) (:unused-bits value 0)))
    :integer (ctx (:integer tags) (asn1/integer value))
    :unsigned (if (neg? value)
                (throw (ex-info "unsigned Data value is negative"
                                 {:type :iec61850.data/negative-unsigned :value value}))
                (ctx (:unsigned tags) (asn1/integer value)))
    :floating-point (ctx (:floating-point tags)
                          (asn1/octet-string (encode-float32-content value)))
    :octet-string (ctx (:octet-string tags) (asn1/octet-string value))
    :visible-string (ctx (:visible-string tags) (asn1/ia5-string value))
    :utc-time {:asn1/class :context :asn1/tag (:utc-time tags) :asn1/constructed? false
               :asn1/content (utctime/encode value)}
    :structure {:asn1/class :context :asn1/tag (:structure tags) :asn1/constructed? true
                :asn1/elements (mapv encode-data value)}
    (throw (ex-info "unknown Data choice" {:type :iec61850.data/unknown-choice :choice choice}))))

;; ── decode ───────────────────────────────────────────────────────────────────

(defn decode-data
  "An `asn1.core` element (as returned by `asn1/decode-at`/`decode`) ->
  `[:ok [choice value]]` or `[:error kw data]`. Never throws — a malformed
  `Data` element inside a GOOSE frame someone else put on the wire is data,
  not a programmer error."
  [{:asn1/keys [class tag constructed? content elements] :as element}]
  (if (not= :context class)
    [:error :iec61850.data/not-context-tagged {:class class :tag tag}]
    (let [name (tag->name tag)]
      (case name
        :boolean
        (try [:ok [:boolean (asn1/boolean-value element)]]
             (catch #?(:clj Exception :cljs :default) e
               [:error :iec61850.data/bad-boolean {:message (ex-message e)}]))

        :bit-string
        [:ok [:bit-string (asn1/bit-string-value element)]]

        :integer
        (try [:ok [:integer (asn1/integer-value element)]]
             (catch #?(:clj Exception :cljs :default) e
               [:error :iec61850.data/bad-integer {:message (ex-message e)}]))

        :unsigned
        (try
          (let [v (asn1/integer-value element)]
            (if (neg? v)
              [:error :iec61850.data/negative-unsigned {:value v}]
              [:ok [:unsigned v]]))
          (catch #?(:clj Exception :cljs :default) e
            [:error :iec61850.data/bad-integer {:message (ex-message e)}]))

        :floating-point
        (let [result (decode-float32-content content)]
          (if (= :ok (first result))
            [:ok [:floating-point (second result)]]
            result))

        :octet-string
        [:ok [:octet-string (asn1/->ints content)]]

        :visible-string
        [:ok [:visible-string (asn1/string-value element)]]

        :utc-time
        (let [result (utctime/decode (asn1/->ints content))]
          (if (= :error (first result))
            result
            [:ok [:utc-time (second result)]]))

        :structure
        (if-not constructed?
          [:error :iec61850.data/structure-not-constructed {}]
          (let [decoded (mapv decode-data elements)
                bad (first (filter #(= :error (first %)) decoded))]
            (if bad
              bad
              [:ok [:structure (mapv second decoded)]])))

        [:error :iec61850.data/unknown-choice-tag {:tag tag}]))))
