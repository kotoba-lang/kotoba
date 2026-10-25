(ns snmp.message
  "The outermost SNMP envelope: RFC 1157 §4's v1 `Message` and RFC 1901 §3's
  community-based v2c `Message` — the same three-field SEQUENCE in both,
  differing only in the `version` integer (0 for v1, 1 for v2c — RFC 1901
  §3 names it `version(1)`, \"modified from [RFC 1157]\" while keeping the
  same numeric value) and in which PDU shapes RFC 3416 §3 allows in `data`
  for v2c.  SNMPv3 (RFC 3412's `msgVersion`/USM header) is out of scope —
  see the README's \"what this is not\"."
  (:require [asn1.core :as asn1]
            [snmp.pdu :as pdu]))

(def ^:private version-code {:v1 0 :v2c 1})
(def ^:private code->version {0 :v1 1 :v2c})

(defn- string->octets
  "A community string as octets — Latin-1 byte-per-char, matching
  `asn1.core`'s own `octet-string`/`ia5-string` treatment of a plain string
  (community names are conventionally ASCII, RFC 3584 §3.3)."
  [s]
  (mapv int s))

(defn encode-message
  "`{:snmp/version :v1 :snmp/community \"public\" :snmp/pdu {...}}` → the
  complete message as bytes. Throws on a bad `:snmp/version` or a PDU
  `encode-pdu` itself refuses — see its docstring for why encode does not
  wrap those in `[:error ...]`."
  [{:snmp/keys [version community pdu]}]
  (when-not (contains? version-code version)
    (asn1/fail! :snmp/unknown-version "version must be :v1 or :v2c" {:version version}))
  (asn1/encode
   (asn1/sequence*
    [(asn1/integer (get version-code version))
     (asn1/octet-string (string->octets community))
     (pdu/encode-pdu pdu)])))

(defn decode-message
  "The bytes of one SNMP message → `[:ok message-map]` or `[:error kw]`.
  Every failure mode — truncated bytes, a bad BER length, an unrecognized
  version, a malformed PDU — comes back as a named keyword rather than a
  thrown exception, per the negative-test contract in the README."
  [data]
  (try
    (let [top (asn1/decode data)]
      (if (or (not (:asn1/constructed? top)) (not= 3 (count (:asn1/elements top))))
        [:error :snmp/truncated-message]
        (let [[version-el community-el pdu-el] (:asn1/elements top)
              version-n (asn1/integer-value version-el)]
          (if-not (contains? code->version version-n)
            [:error :snmp/unknown-version]
            ;; `community-el`'s type is already `:octet-string` (asn1.core
            ;; names universal tag 4 on decode), so `string-value` takes the
            ;; Latin-1 char-per-byte branch — the exact inverse of
            ;; `string->octets` above, byte for byte.
            (let [community (asn1/string-value community-el)
                  [status pdu-map] (pdu/decode-pdu pdu-el)]
              (if (= :error status)
                [:error pdu-map]
                [:ok {:snmp/version (get code->version version-n)
                      :snmp/community community
                      :snmp/pdu pdu-map}]))))))
    (catch #?(:clj Exception :cljs :default) e
      (let [asn1-kw (:type (ex-data e))]
        [:error (case asn1-kw
                  :asn1/truncated :snmp/truncated-message
                  :asn1/trailing-bytes :snmp/trailing-bytes
                  :snmp/truncated-message)]))))
