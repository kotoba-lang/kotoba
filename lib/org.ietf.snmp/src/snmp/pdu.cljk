(ns snmp.pdu
  "The PDU layer: RFC 1157 §4.1's `PDU`/`Trap-PDU` and RFC 3416 §3's `PDU`/
  `BulkPDU`, plus the `VarBind`/`VarBindList` both share.

  Every PDU is `[n] IMPLICIT <SEQUENCE ...>` — the CHOICE tag from RFC 1157
  §4.1 / RFC 3416 §3 replaces the ordinary SEQUENCE tag but keeps the
  constructed bit, which is exactly `asn1.core/implicit`. Trap-PDU (v1) and
  BulkPDU (v2c GetBulk) are the two shapes that are NOT `request-id/
  error-status/error-index/variable-bindings`; everything else is."
  (:require [asn1.core :as asn1]
            [snmp.types :as types]))

;; ── PDU type ↔ CHOICE tag (RFC 1157 §4.1, RFC 3416 §3) ─────────────────────
;;
;; v1 defines 0–4. v2c reuses 0/1/2/3 and adds 5–8; v2c's tag 2 is named
;; "response" (formerly get-response) and tag 4 does not exist in v2c —
;; trap moved to 7 as `snmpv2-trap`, which is why `trap` (v1) and
;; `snmpv2-trap` (v2c) are different keywords even though a v1 Trap-PDU and
;; an SNMPv2-Trap-PDU carry different fields (the former has enterprise/
;; agent-addr/generic-trap/specific-trap/time-stamp; the latter is an
;; ordinary PDU whose first two varbinds are conventionally sysUpTime.0 and
;; snmpTrapOID.0 — RFC 3416 §4.2.6 — but that convention is not enforced by
;; the wire shape, so this codec does not enforce it either).

(def ^:private pdu-tag
  {:get-request 0 :get-next-request 1 :get-response 2 :set-request 3
   :trap 4 :get-bulk-request 5 :inform-request 6 :snmpv2-trap 7 :report 8})

(def ^:private tag->pdu-type (into {} (map (fn [[k v]] [v k])) pdu-tag))

;; response (v2c) is the same wire shape and tag as get-response (v1) — one
;; codec, two names a caller might reasonably send in.
(def ^:private pdu-type-alias {:response :get-response})

;; ── error-status (RFC 1157 §4.1.1 has 0–5; RFC 3416 §3 extends to 0–18) ────

(def error-status-name
  {0 :no-error 1 :too-big 2 :no-such-name 3 :bad-value 4 :read-only 5 :gen-err
   6 :no-access 7 :wrong-type 8 :wrong-length 9 :wrong-encoding 10 :wrong-value
   11 :no-creation 12 :inconsistent-value 13 :resource-unavailable
   14 :commit-failed 15 :undo-failed 16 :authorization-error 17 :not-writable
   18 :inconsistent-name})

(def error-status-code (into {} (map (fn [[k v]] [v k])) error-status-name))

(defn- status->code
  "`:snmp/error-status` as the wire integer. Accepts a known keyword, a raw
  integer (so an unrecognized future error-status round-trips as itself
  instead of being silently normalized to `no-error`), or `nil` (→ 0)."
  [v]
  (cond (nil? v) 0 (integer? v) v :else (get error-status-code v 0)))

;; ── generic-trap (RFC 1157 §4.1.6, v1 Trap-PDU only) ────────────────────────

(def generic-trap-name
  {0 :cold-start 1 :warm-start 2 :link-down 3 :link-up
   4 :authentication-failure 5 :egp-neighbor-loss 6 :enterprise-specific})

(def generic-trap-code (into {} (map (fn [[k v]] [v k])) generic-trap-name))

(defn- generic-trap->code
  [v]
  (cond (nil? v) 6 (integer? v) v :else (get generic-trap-code v 6)))

;; ── VarBind / VarBindList ────────────────────────────────────────────────

(defn encode-varbind
  "`{:snmp/oid \"1.3.6.1.2.1.1.1.0\" :snmp/value {...}}` → a VarBind
  SEQUENCE element."
  [{:snmp/keys [oid value]}]
  (asn1/sequence* [(asn1/oid oid) (types/encode-value value)]))

(defn decode-varbind
  "One VarBind SEQUENCE element → `[:ok {:snmp/oid s :snmp/value v}]` or
  `[:error kw]`. Structural checks (right count of children, both are
  present) happen before either child is interpreted, so a two-element
  VarBind with a broken OID reports `:snmp/bad-oid`, not
  `:snmp/truncated-varbind` — the shape was fine; a leaf was not."
  [{:asn1/keys [elements] :as element}]
  (cond
    (not (:asn1/constructed? element)) [:error :snmp/truncated-varbind]
    (not= 2 (count elements)) [:error :snmp/truncated-varbind]
    :else
    (let [[name-el value-el] elements]
      ;; `asn1/oid-value` decodes whatever content bytes it is given as OID
      ;; arcs regardless of the element's own tag — it trusts the caller to
      ;; have already picked the right child. ObjectName IS an OBJECT
      ;; IDENTIFIER (RFC 1157 §3.2), so a `name` field that is not tagged as
      ;; one is a malformed VarBind, checked here rather than left to
      ;; silently decode the wrong bytes as arcs.
      (if-not (and (= :universal (:asn1/class name-el)) (= 6 (:asn1/tag name-el)))
        [:error :snmp/bad-oid]
        (try
          (let [oid (asn1/oid-value name-el)
                [status v] (types/decode-value value-el)]
            (if (= :error status)
              [:error v]
              [:ok {:snmp/oid oid :snmp/value v}]))
          (catch #?(:clj Exception :cljs :default) _
            [:error :snmp/bad-oid]))))))

(defn encode-varbind-list [varbinds]
  (asn1/sequence* (mapv encode-varbind varbinds)))

(defn decode-varbind-list
  "A VarBindList SEQUENCE → `[:ok [varbind ...]]` or the first `[:error kw]`
  encountered, fail-fast rather than collecting partial results — a PDU with
  one bad varbind is a bad PDU, not a PDU with 4 good bindings and a hole."
  [{:asn1/keys [elements] :as element}]
  (if-not (:asn1/constructed? element)
    [:error :snmp/truncated-pdu]
    (loop [els elements out []]
      (if (empty? els)
        [:ok out]
        (let [[status v] (decode-varbind (first els))]
          (if (= :error status)
            [:error v]
            (recur (rest els) (conj out v))))))))

;; ── ordinary PDU (get/get-next/response/set/inform/snmpv2-trap/report) ─────

(defn- encode-ordinary-pdu [pdu-type {:snmp/keys [request-id error-status error-index varbinds]}]
  (asn1/implicit
   (get pdu-tag (get pdu-type-alias pdu-type pdu-type))
   (asn1/sequence*
    [(asn1/integer request-id)
     (asn1/integer (status->code error-status))
     (asn1/integer (or error-index 0))
     (encode-varbind-list varbinds)])))

(defn- decode-ordinary-pdu [pdu-type {:asn1/keys [elements] :as element}]
  (cond
    (not (:asn1/constructed? element)) [:error :snmp/truncated-pdu]
    (not= 4 (count elements)) [:error :snmp/truncated-pdu]
    :else
    (try
      (let [[req-el err-el idx-el vbl-el] elements
            request-id (asn1/integer-value req-el)
            error-status-n (asn1/integer-value err-el)
            error-index (asn1/integer-value idx-el)]
        (let [[status varbinds] (decode-varbind-list vbl-el)]
          (if (= :error status)
            [:error varbinds]
            [:ok {:snmp/pdu-type pdu-type
                  :snmp/request-id request-id
                  :snmp/error-status (get error-status-name error-status-n error-status-n)
                  :snmp/error-index error-index
                  :snmp/varbinds varbinds}])))
      (catch #?(:clj Exception :cljs :default) _
        [:error :snmp/truncated-pdu]))))

;; ── BulkPDU (RFC 3416 §3, GetBulkRequest-PDU only) ──────────────────────────

(defn- encode-bulk-pdu [{:snmp/keys [request-id non-repeaters max-repetitions varbinds]}]
  (asn1/implicit
   (:get-bulk-request pdu-tag)
   (asn1/sequence*
    [(asn1/integer request-id)
     (asn1/integer (or non-repeaters 0))
     (asn1/integer (or max-repetitions 0))
     (encode-varbind-list varbinds)])))

(defn- decode-bulk-pdu [{:asn1/keys [elements] :as element}]
  (cond
    (not (:asn1/constructed? element)) [:error :snmp/truncated-pdu]
    (not= 4 (count elements)) [:error :snmp/truncated-pdu]
    :else
    (try
      (let [[req-el nr-el mr-el vbl-el] elements
            request-id (asn1/integer-value req-el)
            non-repeaters (asn1/integer-value nr-el)
            max-repetitions (asn1/integer-value mr-el)]
        (let [[status varbinds] (decode-varbind-list vbl-el)]
          (if (= :error status)
            [:error varbinds]
            [:ok {:snmp/pdu-type :get-bulk-request
                  :snmp/request-id request-id
                  :snmp/non-repeaters non-repeaters
                  :snmp/max-repetitions max-repetitions
                  :snmp/varbinds varbinds}])))
      (catch #?(:clj Exception :cljs :default) _
        [:error :snmp/truncated-pdu]))))

;; ── Trap-PDU (RFC 1157 §4.1.6, v1 only — a different shape entirely) ────────

(defn- encode-trap-pdu [{:snmp/keys [enterprise agent-addr generic-trap specific-trap
                                     time-stamp varbinds]}]
  (asn1/implicit
   (:trap pdu-tag)
   (asn1/sequence*
    [(asn1/oid enterprise)
     (types/ip-address agent-addr)
     (asn1/integer (generic-trap->code generic-trap))
     (asn1/integer (or specific-trap 0))
     (types/time-ticks time-stamp)
     (encode-varbind-list varbinds)])))

(defn- decode-trap-pdu [{:asn1/keys [elements] :as element}]
  (cond
    (not (:asn1/constructed? element)) [:error :snmp/truncated-trap-pdu]
    (not= 6 (count elements)) [:error :snmp/truncated-trap-pdu]
    :else
    (try
      (let [[ent-el addr-el gt-el st-el ts-el vbl-el] elements
            enterprise (asn1/oid-value ent-el)]
        (let [[addr-status addr] (types/decode-value addr-el)]
          (if (or (= :error addr-status) (not= :ip-address (:snmp/type addr)))
            [:error :snmp/bad-ip-address]
            (let [generic-trap-n (asn1/integer-value gt-el)
                  specific-trap (asn1/integer-value st-el)
                  [ts-status ts] (types/decode-value ts-el)]
              (if (or (= :error ts-status) (not= :time-ticks (:snmp/type ts)))
                [:error :snmp/truncated-trap-pdu]
                (let [[vbl-status varbinds] (decode-varbind-list vbl-el)]
                  (if (= :error vbl-status)
                    [:error varbinds]
                    [:ok {:snmp/pdu-type :trap
                          :snmp/enterprise enterprise
                          :snmp/agent-addr (:snmp/bytes addr)
                          :snmp/generic-trap (get generic-trap-name generic-trap-n generic-trap-n)
                          :snmp/specific-trap specific-trap
                          :snmp/time-stamp (:snmp/int ts)
                          :snmp/varbinds varbinds}])))))))
      (catch #?(:clj Exception :cljs :default) _
        [:error :snmp/truncated-trap-pdu]))))

;; ── dispatch ─────────────────────────────────────────────────────────────

(defn encode-pdu
  "`pdu-map` → the `[n] IMPLICIT` element for its `:snmp/pdu-type`. Throws on
  an unrecognized `:snmp/pdu-type` — this builds a trusted local value, see
  `snmp.types/encode-value`'s docstring for the same distinction."
  [{:snmp/keys [pdu-type] :as pdu-map}]
  (case pdu-type
    :trap (encode-trap-pdu pdu-map)
    :get-bulk-request (encode-bulk-pdu pdu-map)
    (:get-request :get-next-request :get-response :response :set-request
     :inform-request :snmpv2-trap :report)
    (encode-ordinary-pdu pdu-type pdu-map)
    (asn1/fail! :snmp/unknown-pdu-type "no encoder for this :snmp/pdu-type"
                {:snmp/pdu-type pdu-type})))

(defn decode-pdu
  "The `data` field of an SNMP Message → `[:ok pdu-map]` or `[:error kw]`,
  dispatched on the CONTEXT tag that names which PDU shape follows."
  [{:asn1/keys [class tag] :as element}]
  (if (not= :context class)
    [:error :snmp/unknown-pdu-type]
    (let [pdu-type (get tag->pdu-type tag)]
      (cond
        (nil? pdu-type) [:error :snmp/unknown-pdu-type]
        (= :trap pdu-type) (decode-trap-pdu element)
        (= :get-bulk-request pdu-type) (decode-bulk-pdu element)
        :else (decode-ordinary-pdu pdu-type element)))))
