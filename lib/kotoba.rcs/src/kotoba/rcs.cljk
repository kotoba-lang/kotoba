(ns kotoba.rcs
  "GSMA RCS Universal Profile (RCC.07) message, session and capability
  records — pure data contracts.

  A kotoba-lang capability library modeling the application-layer records an
  RCS client/server exchanges under the GSMA Rich Communication Services
  Universal Profile: 1-to-1 chat messages, group chat, is-composing presence
  (RFC 3994-shaped), delivery/read receipts (IMDN, RFC 5438-shaped), file
  transfer descriptors and capability-discovery results (the outcome of a
  SIP OPTIONS exchange, not the exchange itself). No network, no I/O.

  Scope, stated plainly: this models *records*, not wire format — the same
  posture as kotoba-lang/webrtc, kotoba-lang/card and kotoba-lang/swift take
  toward the protocols they model. Explicitly out of scope and not
  implemented here: actual SIP/MSRP/CPIM transport framing, GSMA IR.92/IR.94
  network registration and provisioning, and TLS/IPsec transport security.
  Endpoints are E.164 numbers, validated by delegating to
  [[kotoba.phone/e164-valid?]] rather than re-implementing E.164 parsing —
  this library reuses kotoba-lang/phone as its numbering-plan authority.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.phone :as phone]))

;; ---------------------------------------------------------------------------
;; 1-to-1 chat message
;; ---------------------------------------------------------------------------

(defn chat-message
  "Construct a 1-to-1 RCS chat message record. from and to are E.164
  numbers. content-type defaults to \"text/plain\"."
  [id from to body & {:keys [content-type sent thread-id]}]
  {:rcs/message-id   id
   :rcs/from         from
   :rcs/to           to
   :rcs/body         body
   :rcs/content-type (or content-type "text/plain")
   :rcs/sent         sent
   :rcs/thread-id    thread-id})

;; ---------------------------------------------------------------------------
;; Group chat
;; ---------------------------------------------------------------------------

(defn group-chat
  "Construct a group chat (conversation) record. participants is a
  collection of E.164 strings, stored as a set."
  [id participants subject & {:keys [created]}]
  {:rcs/conversation-id id
   :rcs/participants    (set participants)
   :rcs/subject         subject
   :rcs/created         created})

(defn group-message
  "Construct an RCS chat message scoped to a group conversation-id. from is
  an E.164 number of the sending participant."
  [conversation-id id from body & {:keys [content-type sent]}]
  {:rcs/message-id      id
   :rcs/conversation-id conversation-id
   :rcs/from            from
   :rcs/body            body
   :rcs/content-type    (or content-type "text/plain")
   :rcs/sent            sent})

;; ---------------------------------------------------------------------------
;; Is-composing indicator (RFC 3994-shaped)
;; ---------------------------------------------------------------------------

(def composing-states
  "Valid is-composing states (RFC 3994 <state> element)."
  #{:idle :active})

(defn is-composing
  "Construct an is-composing presence record for thread-id. state must be
  :idle or :active. Returns nil when state is not a recognized value."
  [from thread-id state & {:keys [refresh]}]
  (when (contains? composing-states state)
    {:rcs/from      from
     :rcs/thread-id thread-id
     :rcs/state     state
     :rcs/refresh   refresh}))

;; ---------------------------------------------------------------------------
;; Delivery / read receipt (IMDN, RFC 5438-shaped)
;; ---------------------------------------------------------------------------

(def dispositions
  "Valid IMDN disposition notification types (RFC 5438 <status> element)."
  #{:delivered :displayed :error})

(defn receipt
  "Construct a delivery/read receipt (IMDN) for message-id. disposition
  must be one of :delivered, :displayed or :error. Returns nil when
  disposition is not a recognized value."
  [message-id disposition & {:keys [timestamp]}]
  (when (contains? dispositions disposition)
    {:rcs/message-id  message-id
     :rcs/disposition disposition
     :rcs/timestamp   timestamp}))

;; ---------------------------------------------------------------------------
;; File transfer descriptor
;; ---------------------------------------------------------------------------

(defn file-transfer
  "Construct a file transfer descriptor. from and to are E.164 numbers.
  file-size is bytes."
  [id from to file-name file-size mime-type & {:keys [thumbnail? sent]}]
  {:rcs/transfer-id  id
   :rcs/from         from
   :rcs/to           to
   :rcs/file-name    file-name
   :rcs/file-size    file-size
   :rcs/mime-type    mime-type
   :rcs/thumbnail?   (boolean thumbnail?)
   :rcs/sent         sent})

;; ---------------------------------------------------------------------------
;; Capability discovery result
;;   (normally exchanged via SIP OPTIONS — this models the result record
;;    only; no SIP transport is implemented here)
;; ---------------------------------------------------------------------------

(def capability-features
  "Feature tags a capability-discovery result may report support for."
  #{:chat :group-chat :file-transfer :is-composing :geolocation-push
    :standalone-messaging})

(defn capabilities
  "Construct a capability-discovery result for e164 reporting the given set
  of supported features (subset of [[capability-features]]). Returns nil
  when e164 is not a valid E.164 number."
  [e164 features & {:keys [checked-at]}]
  (when (phone/e164-valid? e164)
    {:rcs/endpoint    e164
     :rcs/features    (set features)
     :rcs/checked-at  checked-at}))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn valid-chat-message?
  "True when m has the required chat-message keys and from/to are valid
  E.164 endpoints."
  [m]
  (boolean
    (and (map? m)
         (:rcs/message-id m)
         (:rcs/body m)
         (phone/e164-valid? (:rcs/from m))
         (phone/e164-valid? (:rcs/to m)))))

(defn valid-receipt?
  "True when m has the required receipt keys and a recognized disposition."
  [m]
  (boolean
    (and (map? m)
         (:rcs/message-id m)
         (contains? dispositions (:rcs/disposition m)))))

(defn valid-capabilities?
  "True when m has the required capability-record keys, a valid E.164
  endpoint and a features set drawn from [[capability-features]]."
  [m]
  (boolean
    (and (map? m)
         (phone/e164-valid? (:rcs/endpoint m))
         (set? (:rcs/features m))
         (every? capability-features (:rcs/features m)))))
