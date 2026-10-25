(ns webauthn.virtual-authenticator
  "A virtual WebAuthn authenticator, for testing `webauthn.adapters.edge`
  against real ceremonies instead of hand-frozen fixtures.

  It does what a real platform authenticator does: holds a P-256 credential
  keypair, emits an attestationObject at registration, and signs
  `authenticatorData || SHA-256(clientDataJSON)` at login. Everything it
  produces is genuinely signed, so a break in the verifier's parsing, its
  rpIdHash check, its flag checks or its DER handling fails a test rather
  than passing against a fixture that was frozen alongside the bug.

  It can also misbehave on demand -- wrong origin, wrong RP, user-present
  clear, a tampered signature -- which is the half a fixture cannot do at
  all.

  The CBOR and DER *encoders* here are test-only and intentionally separate
  from the production decoders they feed: an encoder written by reading the
  decoder would agree with the decoder's bugs.

  CLJS-only."
  (:require [webauthn.adapters.edge :as edge]))

;; ── minimal CBOR encoder (test-only) ────────────────────────────────────────

(defn- header [major n]
  (cond
    (< n 24) #js [(bit-or (bit-shift-left major 5) n)]
    (< n 256) #js [(bit-or (bit-shift-left major 5) 24) n]
    (< n 65536) #js [(bit-or (bit-shift-left major 5) 25)
                     (bit-and (bit-shift-right n 8) 0xff) (bit-and n 0xff)]
    :else #js [(bit-or (bit-shift-left major 5) 26)
               (bit-and (bit-shift-right n 24) 0xff) (bit-and (bit-shift-right n 16) 0xff)
               (bit-and (bit-shift-right n 8) 0xff) (bit-and n 0xff)]))

(defn- cat-arrays [arrays]
  (let [total (reduce + 0 (map #(aget % "length") arrays))
        out (js/Uint8Array. total)]
    (loop [[a & more] arrays offset 0]
      (if (nil? a)
        out
        (do (.set out (js/Uint8Array.from a) offset)
            (recur more (+ offset (aget a "length"))))))))

(declare cbor-encode)

(defn- cbor-text [s]
  (let [bytes (.encode (js/TextEncoder.) s)]
    (cat-arrays [(header 3 (aget bytes "length")) bytes])))

(defn- cbor-bytes [b]
  (cat-arrays [(header 2 (aget b "length")) b]))

(defn- cbor-int [n]
  (if (neg? n) (header 1 (dec (- n))) (header 0 n)))

(defn- cbor-map
  "`pairs` is a seq of [key value] where key is a string or an int."
  [pairs]
  (cat-arrays
   (into [(header 5 (count pairs))]
         (mapcat (fn [[k v]]
                   [(if (string? k) (cbor-text k) (cbor-int k))
                    (cbor-encode v)])
                 pairs))))

(defn- cbor-encode [v]
  (cond
    (string? v) (cbor-text v)
    (number? v) (cbor-int v)
    (vector? v) (cbor-map v)
    :else (cbor-bytes v)))

;; ── minimal DER encoder for an ECDSA signature (test-only) ──────────────────

(defn- der-integer [bytes]
  (let [trimmed (loop [i 0]
                  (if (and (< i (dec (aget bytes "length"))) (zero? (aget bytes i)))
                    (recur (inc i))
                    (.slice bytes i)))
        needs-pad? (>= (aget trimmed 0) 0x80)
        body (if needs-pad?
               (cat-arrays [#js [0x00] trimmed])
               trimmed)]
    (cat-arrays [#js [0x02 (aget body "length")] body])))

(defn raw->der
  "Raw IEEE-P1363 r||s -> DER SEQUENCE{INTEGER r, INTEGER s}. The inverse of
  `webauthn.der/raw`, which is what the verifier runs."
  [raw]
  (let [r (der-integer (.slice raw 0 32))
        s (der-integer (.slice raw 32 64))
        body (cat-arrays [r s])]
    (cat-arrays [#js [0x30 (aget body "length")] body])))

;; ── bytes/base64url ─────────────────────────────────────────────────────────

(defn b64url [bytes]
  (-> (edge/bytes->b64 bytes)
      (.replace (js/RegExp. "\\+" "g") "-")
      (.replace (js/RegExp. "/" "g") "_")
      (.replace (js/RegExp. "=+$" "") "")))

(defn- sha256 [bytes]
  (.then (js/crypto.subtle.digest "SHA-256" bytes) #(js/Uint8Array. %)))

(defn- text-bytes [s] (.encode (js/TextEncoder.) s))

(defn client-data
  "The clientDataJSON a browser builds. `overrides` can bend any field, which
  is how the negative cases are produced."
  [type origin challenge & [overrides]]
  (b64url (text-bytes (js/JSON.stringify
                       (js/Object.assign #js {:type type :origin origin :challenge challenge
                                              :crossOrigin false}
                                         (or overrides #js {}))))))

;; ── the authenticator ───────────────────────────────────────────────────────

(defn- auth-data
  "rpIdHash | flags | signCount [| aaguid | credIdLen | credId | coseKey]"
  [rp-id-hash {:keys [user-present? user-verified? backup-eligible? backed-up?
                      sign-count attested]}]
  (let [flags (cond-> 0
                user-present? (bit-or 0x01)
                user-verified? (bit-or 0x04)
                backup-eligible? (bit-or 0x08)
                backed-up? (bit-or 0x10)
                attested (bit-or 0x40))
        head (cat-arrays [rp-id-hash
                          #js [flags]
                          #js [(bit-and (bit-shift-right sign-count 24) 0xff)
                               (bit-and (bit-shift-right sign-count 16) 0xff)
                               (bit-and (bit-shift-right sign-count 8) 0xff)
                               (bit-and sign-count 0xff)]])]
    (if-not attested
      head
      (let [{:keys [aaguid credential-id cose-key]} attested]
        (cat-arrays [head aaguid
                     #js [(bit-and (bit-shift-right (aget credential-id "length") 8) 0xff)
                          (bit-and (aget credential-id "length") 0xff)]
                     credential-id cose-key])))))

(defn create!
  "Mint a virtual authenticator holding one P-256 credential for `rp-id`.
  Returns a Promise of a map with `:credential-id`, `:register!` and
  `:assert!`."
  [rp-id]
  (-> (js/Promise.all
       #js [(js/crypto.subtle.generateKey #js {:name "ECDSA" :namedCurve "P-256"}
                                          true #js ["sign" "verify"])
            (sha256 (text-bytes rp-id))])
      (.then
       (fn [[kp rp-id-hash]]
         (-> (.exportKey js/crypto.subtle "raw" (.-publicKey kp))
             (.then
              (fn [raw-pub]
                (let [pub (js/Uint8Array. raw-pub)
                      cose (cbor-map [[1 2] [3 -7] [-1 1]
                                      [-2 (.slice pub 1 33)]
                                      [-3 (.slice pub 33 65)]])
                      credential-id (js/crypto.getRandomValues (js/Uint8Array. 20))
                      aaguid (js/Uint8Array. 16)]
                  {:credential-id (b64url credential-id)
                   :public-key pub

                   :register!
                   (fn [{:keys [origin challenge sign-count user-present? user-verified?
                                backup-eligible? backed-up? rp-hash]
                         :or {sign-count 0 user-present? true user-verified? true}}]
                     (let [ad (auth-data (or rp-hash rp-id-hash)
                                         {:user-present? user-present?
                                          :user-verified? user-verified?
                                          :backup-eligible? backup-eligible?
                                          :backed-up? backed-up?
                                          :sign-count sign-count
                                          :attested {:aaguid aaguid
                                                     :credential-id credential-id
                                                     :cose-key cose}})]
                       {:client-data-json-b64url (client-data "webauthn.create" origin challenge)
                        :attestation-object-b64url
                        (b64url (cbor-map [["fmt" "none"] ["attStmt" []] ["authData" ad]]))}))

                   :assert!
                   (fn [{:keys [origin challenge sign-count user-present? user-verified?
                                backup-eligible? backed-up? rp-hash tamper-signature?
                                client-data-type]
                         :or {sign-count 1 user-present? true user-verified? true}}]
                     (let [cd-b64url (client-data (or client-data-type "webauthn.get") origin challenge)
                           cd-bytes (edge/b64url->bytes cd-b64url)
                           ad (auth-data (or rp-hash rp-id-hash)
                                         {:user-present? user-present?
                                          :user-verified? user-verified?
                                          :backup-eligible? backup-eligible?
                                          :backed-up? backed-up?
                                          :sign-count sign-count})]
                       (-> (sha256 cd-bytes)
                           (.then (fn [cd-hash]
                                    (let [signed (cat-arrays [ad cd-hash])]
                                      (.sign js/crypto.subtle
                                             #js {:name "ECDSA" :hash "SHA-256"}
                                             (.-privateKey kp) signed))))
                           (.then (fn [sig]
                                    (let [raw (js/Uint8Array. sig)]
                                      (when tamper-signature?
                                        (aset raw 10 (bit-xor (aget raw 10) 0xff)))
                                      {:credential-id-b64url (b64url credential-id)
                                       :client-data-json-b64url cd-b64url
                                       :authenticator-data-b64url (b64url ad)
                                       :signature-b64url (b64url (raw->der raw))}))))))}))))))))
