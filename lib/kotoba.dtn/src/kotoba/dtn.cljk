(ns kotoba.dtn
  "RFC 9171 Bundle Protocol Version 7 (Delay/Disruption-Tolerant Networking)
  primary-block fields as pure data — no network, no I/O.

  A kotoba-lang capability library modeling the records a DTN store-and-carry
  node keeps: endpoint identifiers (EIDs) built on kotoba.phone's E.164
  numbering, and RFC 9171 §4.3.1 primary-block fields (version, source,
  destination, report-to, creation timestamp, lifetime, flags, payload) as
  plain EDN suitable for routing / store-and-forward decisions.

  This models primary-block *fields*, not the wire format. It explicitly
  does NOT implement: CBOR wire encoding (RFC 9171 §4.1), block CRC,
  bundle fragmentation/reassembly, or BPSec (RFC 9172) security blocks —
  all out of scope. Same 'records not wire format' discipline as
  kotoba-lang/webrtc and kotoba-lang/card: this library gives you the
  contract a routing/governor layer reasons over, not a codec.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]
            [kotoba.phone :as phone]))

;; ---------------------------------------------------------------------------
;; Endpoint identifier (EID) — dtn:<e164>
;; ---------------------------------------------------------------------------

(defn eid
  "Build a dtn: endpoint identifier from an E.164 number, e.g.
  (eid \"+819012345678\") => \"dtn:+819012345678\". Returns nil when e164
  is not a valid E.164 number (kotoba.phone/e164-valid?)."
  [e164]
  (when (phone/e164-valid? e164)
    (str "dtn:" e164)))

(defn eid->e164
  "Reverse of eid: strip the dtn: scheme prefix and return the E.164 number.
  Returns nil when eid is not a string with the dtn: prefix."
  [eid]
  (when (and (string? eid) (str/starts-with? eid "dtn:"))
    (subs eid 4)))

;; ---------------------------------------------------------------------------
;; Primary block (RFC 9171 §4.3.1)
;; ---------------------------------------------------------------------------

(defn bundle
  "Construct a Bundle Protocol Version 7 primary block (RFC 9171 §4.3.1) as
  plain EDN. source-e164 and dest-e164 are E.164 numbers wrapped into dtn:
  EIDs. payload is arbitrary caller data (opaque to this namespace — see
  kotoba.dtn.gateway for SMS/RCS-shaped payload interop).

  Optional: :report-to-e164 (EID to report bundle status to), :lifetime-ms
  (defaults to 86400000, i.e. 24h), :creation-ts (defaults to 0 — the
  caller's own clock; this namespace does not read wall-clock time),
  :seq-num (defaults to 0), :flags (a set, defaults to #{}).

  Returns nil when source-e164 or dest-e164 is not a valid E.164 number."
  [source-e164 dest-e164 payload & {:keys [report-to-e164 lifetime-ms creation-ts seq-num flags]}]
  (when-let [source (eid source-e164)]
    (when-let [destination (eid dest-e164)]
      {:dtn/version 7
       :dtn/source source
       :dtn/destination destination
       :dtn/report-to (when report-to-e164 (eid report-to-e164))
       :dtn/creation-timestamp (or creation-ts 0)
       :dtn/sequence-number (or seq-num 0)
       :dtn/lifetime-ms (or lifetime-ms 86400000)
       :dtn/flags (or flags #{})
       :dtn/payload payload
       :dtn/bundle-id (str (or creation-ts 0) "-" (or seq-num 0) "-" source-e164)})))

(defn expired?
  "True when now-ms is past bundle's creation-timestamp + lifetime-ms (RFC
  9171 §5.4.6.1's expiration test — a bundle whose retention constraint has
  elapsed and is a store-and-forward removal candidate)."
  [bundle now-ms]
  (> now-ms (+ (:dtn/creation-timestamp bundle) (:dtn/lifetime-ms bundle))))
