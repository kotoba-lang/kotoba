(ns fleet.kcm-receipt
  "Self-contained Ed25519 signatures for customer KCM pilot evidence. The
  signer id is the SHA-256 of the public SPKI bytes; the public key travels in
  the receipt so verification needs no fleet account or network service."
  (:require ["node:crypto" :as crypto]
            ["node:fs" :as fs]
            [fleet.kcm :as kcm]))

(def signed-format :kotoba-kcm-signed-pilot-receipt/v1)

(defn- public-material [private-key]
  (let [public-key (crypto/createPublicKey private-key)
        pem (.export public-key #js {:format "pem" :type "spki"})
        der (.export public-key #js {:format "der" :type "spki"})]
    {:key public-key
     :pem (str pem)
     :id (str "sha256:" (kcm/sha256-bytes der))}))

(defn sign [receipt private-key-path]
  (let [private-key (crypto/createPrivateKey (fs/readFileSync private-key-path "utf8"))
        {:keys [pem id]} (public-material private-key)
        cid (str "sha256:" (kcm/sha256 receipt))
        signature (-> (crypto/sign nil (js/Buffer.from cid "utf8") private-key)
                      (.toString "hex"))]
    {:format signed-format
     :receipt receipt
     :cid cid
     :signature {:algorithm :ed25519
                 :signer id
                 :public-key-pem pem
                 :value signature}}))

(defn verification-reasons [signed]
  (let [{:keys [receipt cid signature]} signed
        {:keys [algorithm signer public-key-pem value]} signature]
    (cond-> []
      (not= signed-format (:format signed))
      (conj "unsupported signed KCM pilot receipt format")

      (not= cid (str "sha256:" (kcm/sha256 receipt)))
      (conj "pilot receipt CID does not match its EDN body")

      (not= :ed25519 algorithm)
      (conj "pilot receipt signature is not Ed25519")

      (not (and (string? value) (boolean (re-matches #"[0-9a-f]{128}" value))))
      (conj "pilot receipt signature encoding is invalid")

      (not (string? public-key-pem))
      (conj "pilot receipt has no public verification key")

      (and (string? public-key-pem)
           (try
             (not= "ed25519" (.-asymmetricKeyType
                               (crypto/createPublicKey public-key-pem)))
             (catch :default _ true)))
      (conj "pilot receipt public key is not Ed25519")

      (and (string? public-key-pem)
           (try
             (let [public-key (crypto/createPublicKey public-key-pem)
                   der (.export public-key #js {:format "der" :type "spki"})]
               (not= signer (str "sha256:" (kcm/sha256-bytes der))))
             (catch :default _ true)))
      (conj "pilot receipt signer does not match its public key")

      (and (string? public-key-pem)
           (string? value)
           (boolean (re-matches #"[0-9a-f]{128}" value))
           (try
             (not (crypto/verify nil (js/Buffer.from (str cid) "utf8")
                                 (crypto/createPublicKey public-key-pem)
                                 (js/Buffer.from value "hex")))
             (catch :default _ true)))
      (conj "pilot receipt signature verification failed"))))

(defn verify! [signed]
  (when-let [reasons (seq (verification-reasons signed))]
    (throw (ex-info (str "invalid signed KCM pilot receipt: " (pr-str reasons))
                    {:reasons reasons})))
  signed)
