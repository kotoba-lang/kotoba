(ns kotobase.server.security.audit
  "Signed, encrypted, content-addressed security receipts."
  (:require [ipld.core :as ipld]
            [kotobase.cacao :as cacao]
            [kotobase.cid :as cid]
            ["@noble/curves/ed25519.js" :refer [ed25519]]))

(def receipt-version 1)

(defn signer [seed-b64]
  (when-not (seq seed-b64)
    (throw (ex-info "audit signing seed is required" {:type :audit-key-missing})))
  (let [seed (cacao/base64->bytes seed-b64)]
    (when-not (= 32 (.-length seed))
      (throw (ex-info "audit seed must decode to 32 bytes"
                      {:type :audit-key-invalid :length (.-length seed)})))
    (let [pub (.getPublicKey ed25519 seed)]
      {:seed seed :public-key pub :did (cid/did-key-from-ed25519-pub pub)})))

(defn create-receipt [{:keys [seed did]} encrypt-fn event]
  (let [unsigned (assoc event "receipt-version" receipt-version "signer" did)
        signature (.sign ed25519 (ipld/encode unsigned) seed)
        signed (assoc unsigned "signature" (cacao/bytes->base64url signature))]
    (-> (encrypt-fn (ipld/encode signed))
        (.then (fn [ciphertext]
                 (let [{:keys [cid bytes]}
                       (ipld/node->block {"type" "kotobase/audit-encrypted/v1"
                                         "ciphertext" ciphertext})]
                   {:cid cid :bytes bytes :signed signed}))))))

(defn verify-receipt
  [expected-cid wrapper-bytes decrypt-fn expected-signer-did]
  (when-not (seq expected-signer-did)
    (throw (ex-info "expected audit signer DID is required"
                    {:type :audit-signer-required})))
  (when-not (= expected-cid (ipld/cid wrapper-bytes))
    (throw (ex-info "audit receipt CID mismatch" {:type :audit-cid-mismatch})))
  (let [wrapper (ipld/decode wrapper-bytes)]
    (when-not (= "kotobase/audit-encrypted/v1" (get wrapper "type"))
      (throw (ex-info "unsupported audit wrapper" {:type :audit-wrapper-invalid})))
    (-> (decrypt-fn (get wrapper "ciphertext"))
        (.then
         (fn [plain]
           (let [signed (ipld/decode plain)
                 signature (cacao/base64url->bytes (get signed "signature"))
                 unsigned (dissoc signed "signature")
                 signer-did (get signed "signer")]
             (when-not (= expected-signer-did signer-did)
               (throw (ex-info "untrusted audit receipt signer"
                               {:type :audit-signer-mismatch
                                :expected expected-signer-did :actual signer-did})))
             (let [pub (cid/did-key->ed25519-pub signer-did)]
               (when-not (and pub (.verify ed25519 signature (ipld/encode unsigned) pub))
                 (throw (ex-info "audit receipt signature invalid"
                                 {:type :audit-signature-invalid})))
               signed)))))))
