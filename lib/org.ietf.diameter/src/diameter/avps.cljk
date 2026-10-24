(ns diameter.avps
  "The base-protocol AVP codes and command codes this repo actually uses,
  plus Capabilities-Exchange-Request/Answer (RFC 6733 §5.3.1/§5.3.2) built
  from them as full command messages.

  Every AVP Code, Command Code, and result value below is cited to its RFC
  6733 section next to it — none are remembered/guessed, all were read out
  of the fetched RFC text (rfc-editor.org/rfc/rfc6733.txt) while writing
  this file."
  (:require [diameter.avp :as avp]
            [diameter.types :as t]
            [diameter.message :as msg]))

;; ── AVP codes used here (all Vendor-ID 0, i.e. the IETF AVP space) ──────

(def session-id-code            263) ; §8.8,  UTF8String
(def origin-host-code           264) ; §6.3,  DiameterIdentity
(def destination-realm-code     283) ; §6.6,  DiameterIdentity
(def destination-host-code      293) ; §6.5,  DiameterIdentity
(def origin-realm-code          296) ; §6.4,  DiameterIdentity
(def result-code-code           268) ; §7.1,  Unsigned32
(def auth-application-id-code   258) ; §6.8,  Unsigned32
(def acct-application-id-code   259) ; §6.9,  Unsigned32
(def inband-security-id-code    299) ; §6.10, Unsigned32
(def vendor-id-code             266) ; §5.3.3, Unsigned32
(def firmware-revision-code     267) ; §5.3.4, Unsigned32
(def host-ip-address-code       257) ; §5.3.5, Address (scoped out — see diameter.types; carried as raw OctetString here)
(def supported-vendor-id-code   265) ; §5.3.6, Unsigned32
(def product-name-code          269) ; §5.3.7, UTF8String
(def origin-state-id-code       278) ; §8.16,  Unsigned32
(def disconnect-cause-code      273) ; §5.4.3, Enumerated

;; ── Command codes ─────────────────────────────────────────────────────

(def cer-cea-command-code 257)  ; §5.3.1/§5.3.2
(def base-application-id  0)    ; the Diameter base protocol's own application

;; ── Result-Code values used in tests (RFC 6733 §7.1) ─────────────────

(def diameter-success 2001)     ; §7.1: "2001 DIAMETER_SUCCESS"

;; ── Disconnect-Cause (RFC 6733 §5.4.3, an Enumerated AVP) ────────────

(def disconnect-cause-name->code
  {:rebooting 0 :busy 1 :do-not-want-to-talk-to-you 2})
(def disconnect-cause-code->name
  (into {} (map (fn [[k v]] [v k])) disconnect-cause-name->code))

;; ── typed AVP constructors ────────────────────────────────────────────
;;
;; Small helpers over `diameter.avp/encode-avp` — not a second framing
;; layer, just "AVP code N always carries value type T" spelled out once
;; per AVP instead of at every call site.

(defn utf8-avp [code s & {:keys [m?] :or {m? false}}]
  {:diameter.avp/code code :diameter.avp/m? m? :diameter.avp/data (t/encode-utf8 s)})

(defn diameter-identity-avp [code s & {:keys [m?] :or {m? false}}]
  {:diameter.avp/code code :diameter.avp/m? m? :diameter.avp/data (t/encode-diameter-identity s)})

(defn uint32-avp [code n & {:keys [m?] :or {m? false}}]
  {:diameter.avp/code code :diameter.avp/m? m? :diameter.avp/data (t/encode-uint32 n)})

(defn octet-string-avp [code bs & {:keys [m?] :or {m? false}}]
  {:diameter.avp/code code :diameter.avp/m? m? :diameter.avp/data (t/encode-octet-string bs)})

(defn grouped-avp [code member-avps & {:keys [m?] :or {m? false}}]
  {:diameter.avp/code code :diameter.avp/m? m? :diameter.avp/data (t/encode-grouped member-avps)})

;; ── find/decode helpers ───────────────────────────────────────────────

(defn find-avp
  "The first AVP with this code in `avps`, or nil."
  [avps code]
  (first (filter #(= code (:diameter.avp/code %)) avps)))

(defn find-avps [avps code]
  (filterv #(= code (:diameter.avp/code %)) avps))

(defn avp-utf8 [avp] (when avp (t/decode-utf8 (:diameter.avp/data avp))))
(defn avp-diameter-identity [avp] (when avp (t/decode-diameter-identity (:diameter.avp/data avp))))
(defn avp-uint32 [avp] (when avp (t/decode-uint32 (:diameter.avp/data avp))))

;; ── Capabilities-Exchange-Request (RFC 6733 §5.3.1) ──────────────────
;;
;; ```
;;       <CER> ::= < Diameter Header: 257, REQ >
;;                 { Origin-Host }
;;                 { Origin-Realm }
;;              1* { Host-IP-Address }
;;                 { Vendor-Id }
;;                 { Product-Name }
;;                 [ Origin-State-Id ]
;;               * [ Supported-Vendor-Id ]
;;               * [ Auth-Application-Id ]
;;               * [ Inband-Security-Id ]
;;               * [ Acct-Application-Id ]
;;               * [ Vendor-Specific-Application-Id ]
;;                 [ Firmware-Revision ]
;;               * [ AVP ]
;; ```
;;
;; `{}` is required-exactly-once, `[]` optional-at-most-once, `*[]`
;; zero-or-more. Vendor-Specific-Application-Id (a Grouped AVP) is not
;; built here — nothing in this repo's scoped-in AVP set needs it, and a
;; caller who does can pass it through `extra-avps`. Host-IP-Address is
;; carried as a raw OctetString (its Address encoding is scoped out — see
;; `diameter.types`); this repo's CER/CEA fixtures pass IPv4 bytes built by
;; hand per §4.3.1's own AddressType-then-address layout for realism, with
;; that layout NOT decoded back out by this repo (comment on the fixture
;; itself says so — see the test suite).

(defn encode-cer
  "`{:origin-host s :origin-realm s :host-ip-address bytes :vendor-id n
     :product-name s :origin-state-id n? :firmware-revision n?
     :hop-by-hop n :end-to-end n :extra-avps [...]}` -> the full CER
  message, as a vector of ints."
  [{:keys [origin-host origin-realm host-ip-address vendor-id product-name
           origin-state-id firmware-revision hop-by-hop end-to-end extra-avps]
    :or {extra-avps []}}]
  (msg/encode-message
   {:diameter.message/command-code cer-cea-command-code
    :diameter.message/application-id base-application-id
    :diameter.message/request? true
    :diameter.message/hop-by-hop hop-by-hop
    :diameter.message/end-to-end end-to-end
    :diameter.message/avps
    (into
     (cond-> [(diameter-identity-avp origin-host-code origin-host :m? true)
              (diameter-identity-avp origin-realm-code origin-realm :m? true)
              (octet-string-avp host-ip-address-code host-ip-address :m? true)
              (uint32-avp vendor-id-code vendor-id :m? true)
              (utf8-avp product-name-code product-name :m? true)]
       origin-state-id (conj (uint32-avp origin-state-id-code origin-state-id :m? true))
       firmware-revision (conj (uint32-avp firmware-revision-code firmware-revision :m? true)))
     extra-avps)}))

(defn decode-cer
  "The inverse of `encode-cer`, over an already-decoded
  `diameter.message/decode-message` result's `:diameter.message/avps`.
  Returns a plain map of the fields this repo knows how to pull out; AVPs
  it doesn't recognize are left in `:diameter.avps/avps` for the caller."
  [avps]
  {:origin-host (avp-diameter-identity (find-avp avps origin-host-code))
   :origin-realm (avp-diameter-identity (find-avp avps origin-realm-code))
   :host-ip-address (:diameter.avp/data (find-avp avps host-ip-address-code))
   :vendor-id (avp-uint32 (find-avp avps vendor-id-code))
   :product-name (avp-utf8 (find-avp avps product-name-code))
   :origin-state-id (avp-uint32 (find-avp avps origin-state-id-code))
   :firmware-revision (avp-uint32 (find-avp avps firmware-revision-code))
   :diameter.avps/avps avps})

;; ── Capabilities-Exchange-Answer (RFC 6733 §5.3.2) ───────────────────
;;
;; ```
;;       <CEA> ::= < Diameter Header: 257 >
;;                 { Result-Code }
;;                 { Origin-Host }
;;                 { Origin-Realm }
;;              1* { Host-IP-Address }
;;                 { Vendor-Id }
;;                 { Product-Name }
;;                 [ Origin-State-Id ]
;;                 [ Error-Message ]
;;                 [ Failed-AVP ]
;;               * [ Supported-Vendor-Id ]
;;               * [ Auth-Application-Id ]
;;               * [ Inband-Security-Id ]
;;               * [ Acct-Application-Id ]
;;               * [ Vendor-Specific-Application-Id ]
;;                 [ Firmware-Revision ]
;;               * [ AVP ]
;; ```

(defn encode-cea
  "`{:result-code n :origin-host s :origin-realm s :host-ip-address bytes
     :vendor-id n :product-name s :origin-state-id n? :firmware-revision n?
     :hop-by-hop n :end-to-end n :extra-avps [...]}` -> the full CEA
  message (Command Flags' R bit cleared — §5.3.2: \"Command Flags' 'R' bit
  cleared\")."
  [{:keys [result-code origin-host origin-realm host-ip-address vendor-id
           product-name origin-state-id firmware-revision hop-by-hop end-to-end
           extra-avps]
    :or {extra-avps []}}]
  (msg/encode-message
   {:diameter.message/command-code cer-cea-command-code
    :diameter.message/application-id base-application-id
    :diameter.message/request? false
    :diameter.message/hop-by-hop hop-by-hop
    :diameter.message/end-to-end end-to-end
    :diameter.message/avps
    (into
     (cond-> [(uint32-avp result-code-code result-code :m? true)
              (diameter-identity-avp origin-host-code origin-host :m? true)
              (diameter-identity-avp origin-realm-code origin-realm :m? true)
              (octet-string-avp host-ip-address-code host-ip-address :m? true)
              (uint32-avp vendor-id-code vendor-id :m? true)
              (utf8-avp product-name-code product-name :m? true)]
       origin-state-id (conj (uint32-avp origin-state-id-code origin-state-id :m? true))
       firmware-revision (conj (uint32-avp firmware-revision-code firmware-revision :m? true)))
     extra-avps)}))

(defn decode-cea [avps]
  {:result-code (avp-uint32 (find-avp avps result-code-code))
   :origin-host (avp-diameter-identity (find-avp avps origin-host-code))
   :origin-realm (avp-diameter-identity (find-avp avps origin-realm-code))
   :host-ip-address (:diameter.avp/data (find-avp avps host-ip-address-code))
   :vendor-id (avp-uint32 (find-avp avps vendor-id-code))
   :product-name (avp-utf8 (find-avp avps product-name-code))
   :origin-state-id (avp-uint32 (find-avp avps origin-state-id-code))
   :firmware-revision (avp-uint32 (find-avp avps firmware-revision-code))
   :diameter.avps/avps avps})
