(ns kotoba.dtn.gateway
  "Structural (shape-only, duck-typed) translation between a DTN bundle
  payload and carrier-wire-compatible SMS/RCS payloads — the gateway
  interop seam where a DTN-delivered message becomes (or came from) a real
  carrier message.

  For SMS this namespace takes a real, direct dependency on
  kotoba-lang/phone: phone is a stable prerequisite this library already
  builds on (kotoba.dtn/eid is built on kotoba.phone/e164-valid?).

  For RCS this namespace deliberately does NOT :require kotoba-lang/rcs.
  rcs is a sibling capability library being built independently and in
  parallel with this one; taking a hard dependency here would create a
  build-order coupling between two libraries that should stay
  independently buildable and testable. Instead the RCS message shape is
  checked structurally (duck-typed on its well-known :rcs/* keys) — any
  map with that shape round-trips through bundle->rcs-shaped /
  rcs-shaped->bundle regardless of which library (if any) produced it.
  This is a deliberate decoupling decision, not an oversight.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.dtn :as dtn]
            [kotoba.phone :as phone]))

;; ---------------------------------------------------------------------------
;; SMS — real dependency on kotoba-lang/phone
;; ---------------------------------------------------------------------------

(defn bundle->sms
  "Unwrap a DTN bundle's payload as a kotoba.phone/sms record when it has
  that shape (a map with key :phone/sms-id whose :phone/from is a valid
  E.164 number, per kotoba.phone/e164-valid?). This is the interop seam:
  any host adapter that already knows how to serialize a kotoba.phone/sms
  record to a real carrier SMS PDU works unmodified against DTN-delivered
  payloads too, because the payload IS that record shape — no DTN-specific
  SMS translation step. Returns nil when the payload isn't SMS-shaped."
  [bundle]
  (let [payload (:dtn/payload bundle)]
    (when (and (map? payload)
               (contains? payload :phone/sms-id)
               (phone/e164-valid? (:phone/from payload)))
      payload)))

(defn sms->bundle
  "Wrap a kotoba.phone/sms record into a DTN bundle addressed to
  dest-e164, sourced from the SMS record's own :phone/from."
  [sms-record dest-e164]
  (dtn/bundle (:phone/from sms-record) dest-e164 sms-record))

;; ---------------------------------------------------------------------------
;; RCS — structural / duck-typed only, no :require of kotoba-lang/rcs
;; ---------------------------------------------------------------------------

(defn rcs-shaped?
  "Structural (duck-typed) check for the kotoba-lang/rcs message record
  shape — a map carrying :rcs/message-id (plus, by convention, :rcs/from
  :rcs/to :rcs/body) — WITHOUT requiring that library. See namespace
  docstring: this is a deliberate decoupling, not a stand-in for a real
  schema check."
  [m]
  (and (map? m) (contains? m :rcs/message-id)))

(defn bundle->rcs-shaped
  "Unwrap a DTN bundle's payload when it is RCS-shaped (see rcs-shaped?).
  Same interop-seam pattern as bundle->sms, purely structural: this
  namespace never requires kotoba-lang/rcs. Returns nil when the payload
  isn't RCS-shaped."
  [bundle]
  (let [payload (:dtn/payload bundle)]
    (when (rcs-shaped? payload) payload)))

(defn rcs-shaped->bundle
  "Wrap an RCS-shaped message map (:rcs/message-id :rcs/from :rcs/to
  :rcs/body — the kotoba-lang/rcs record shape, checked structurally, no
  :require of that library) into a DTN bundle from source-e164 to
  dest-e164."
  [msg-map dest-e164 source-e164]
  (dtn/bundle source-e164 dest-e164 msg-map))
