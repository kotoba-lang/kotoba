;; kotoba.signal.sealed — CLJS sibling of sealed.clj (ADR-2608161600).
;; Same maps, same file-key-in-plaintext rule. Every X3DH/ratchet step that
;; touches Web Crypto returns a Promise — do not collapse this into .cljc.
;;
;; :sign-pub on the cljs X3DH bundle is raw Ed25519 bytes (group.cljs
;; precedent), not a did:key string. The sealed public bundle therefore
;; base64url-encodes it. JVM and CLJS sealed wires are not interchangeable
;; for that reason; PQXDH remains a named gap on both backends.
(ns kotoba.signal.sealed
  (:require [cljs.reader :as reader]
            [kotoba.lang.text :as str]
            [kotoba.protocol.sealed :as sealed]
            [kotoba.signal.ratchet :as ratchet]
            [kotoba.signal.x3dh :as x3dh]))

(def in-session-wrap "in-session")

(defn- b64 [^js u8]
  (-> (js/btoa (apply str (map #(js/String.fromCharCode %) (array-seq u8))))
      (.replace (js/RegExp. "\\+" "g") "-")
      (.replace (js/RegExp. "/" "g") "_")))

(defn- unb64 [^string s]
  (let [std (-> s
                (.replace (js/RegExp. "-" "g") "+")
                (.replace (js/RegExp. "_" "g") "/"))
        bin (js/atob std)
        n (.-length bin)
        out (js/Uint8Array. n)]
    (dotimes [i n] (aset out i (.charCodeAt bin i)))
    out))

(defn- utf8 [^string s] (.encode (js/TextEncoder.) s))
(defn- utf8-decode [^js b] (.decode (js/TextDecoder.) b))
(defn- err [e] {:error e})
(defn- resolved [x] (js/Promise.resolve x))

(defn bundle->public
  "X3DH bundle (Uint8Arrays) → sealed prekey-bundle (strings). Public."
  [bundle]
  (sealed/prekey-bundle
   {:identity-pub (b64 (:ik bundle))
    :signed-prekey (cond-> {:pub (b64 (:spk bundle))
                            :sign-pub (b64 (:sign-pub bundle))}
                     (some? (:opk bundle)) (assoc :opk (b64 (:opk bundle)))
                     (some? (:opk-id bundle)) (assoc :opk-id (:opk-id bundle)))
    :signature (b64 (:spk-sig bundle))}))

(defn public->x3dh
  "Inverse of bundle->public."
  [public]
  (when (and (map? public) (not (:error public)))
    (let [spk (:signed-prekey public)]
      {:ik (unb64 (:identity-pub public))
       :sign-pub (unb64 (:sign-pub spk))
       :spk (unb64 (:pub spk))
       :spk-sig (unb64 (:signature public))
       :opk (when (:opk spk) (unb64 (:opk spk)))
       :opk-id (:opk-id spk)})))

(defn check-roles
  [roles]
  (sealed/key-roles roles))

(defn publish
  "Sync, like x3dh/publish-bundle. Optional `roles` runs sealed/key-roles first.
   `accept` must use the identity that still holds the issued OPK, not
   :remaining — IPFS cannot enforce once-only fetch."
  ([identity] (publish identity nil))
  ([identity roles]
   (if-let [role-err (when roles
                       (let [checked (check-roles roles)]
                         (when (:error checked) checked)))]
     role-err
     (let [[bundle remaining] (x3dh/publish-bundle identity)]
       (if-not (x3dh/verify-bundle bundle)
         (err :unverified-bundle)
         (let [public (bundle->public bundle)]
           (if (:error public)
             public
             {:public public :remaining remaining})))))))

(defn initiate
  "-> Promise<session | {:error …}>."
  ([alice-identity public] (initiate alice-identity public nil))
  ([alice-identity public roles]
   (if-let [role-err (when roles
                       (let [checked (check-roles roles)]
                         (when (:error checked) checked)))]
     (resolved role-err)
     (let [raw (public->x3dh public)]
       (cond
         (nil? raw) (resolved (err :invalid-bundle))
         (not (x3dh/verify-bundle raw)) (resolved (err :unverified-bundle))
         :else
         (-> (x3dh/x3dh-initiate alice-identity raw)
             (.then (fn [{:keys [shared-secret ek-pub opk-id]}]
                      (-> (ratchet/init-sender shared-secret (:spk raw))
                          (.then (fn [r]
                                   {:ok? true
                                    :role :initiator
                                    :identity alice-identity
                                    :ratchet r
                                    :handshake {:ik-pub (:pub (:ik alice-identity))
                                                :ek-pub ek-pub
                                                :opk-id opk-id}})))))))))))

(defn- outer-attachment
  [{:keys [cid size digest] :as a}]
  (if (contains? a :plaintext)
    (err :plaintext-in-attachment)
    (sealed/attachment (cond-> {:cid cid :wrapped-key in-session-wrap :alg :in-session}
                         (some? size) (assoc :size size)
                         (some? digest) (assoc :digest digest)))))

(defn- inner-body
  [{:keys [text attachments]}]
  {:text text
   :attachments (mapv #(select-keys % [:cid :file-key :size :digest :alg])
                      (or attachments []))})

(defn- wire-header
  [session env]
  (let [h (:header env)
        header {:dh-pub (b64 (:dh-pub h)) :n (:n h)}]
    (if-let [hs (:handshake session)]
      (cond-> (assoc header
                     :ik-pub (b64 (:ik-pub hs))
                     :ek-pub (b64 (:ek-pub hs)))
        (contains? hs :opk-id) (assoc :opk-id (:opk-id hs)))
      header)))

(defn- wire-ciphertext
  [env]
  (str (b64 (:iv env)) "." (b64 (:ciphertext env))))

(defn- unwire
  [msg]
  (let [h (:header msg)
        parts (str/split (:ciphertext msg) #"\." 2)]
    (when (and (= 2 (count parts)) (map? h) (:dh-pub h))
      {:header {:dh-pub (unb64 (:dh-pub h)) :n (:n h)}
       :iv (unb64 (nth parts 0))
       :ciphertext (unb64 (nth parts 1))})))

(defn encrypt
  "-> Promise<[session' sealed-message]>."
  [session plaintext]
  (cond
    (:error session) (resolved [session session])
    (not (:ratchet session)) (resolved [session (err :not-a-session)])
    (some #(contains? % :plaintext) (or (:attachments plaintext) []))
    (resolved [session (err :plaintext-in-attachment)])
    ;; Receiver send-chain-key is nil until encrypt-message DH-ratchets on
    ;; first send after decrypt. Only refuse when nothing has been received
    ;; (dh-remote still nil) — same moment the JVM ratchet throws.
    (and (nil? (get-in session [:ratchet :send-chain-key]))
         (nil? (get-in session [:ratchet :dh-remote])))
    (resolved [session (err :cannot-send-before-receive)])
    :else
    (let [outers (mapv outer-attachment (or (:attachments plaintext) []))]
      (if-let [att-err (first (filter :error outers))]
        (resolved [session att-err])
        (-> (ratchet/encrypt-message (:ratchet session) (utf8 (pr-str (inner-body plaintext))))
            (.then (fn [[r' env]]
                     (let [msg (sealed/message {:construction :session
                                                :header (wire-header session env)
                                                :ciphertext (wire-ciphertext env)
                                                :attachments outers})
                           session' (-> session
                                        (assoc :ratchet r')
                                        (dissoc :handshake))]
                       [session' msg]))))))))

(defn decrypt
  "-> Promise<[session' plaintext-map]>. Tamper rejects the Promise
   (crypto failure, not a composition error)."
  [session msg]
  (cond
    (:error session) (resolved [session session])
    (:error msg) (resolved [session msg])
    (not (sealed/message? msg)) (resolved [session (err :not-a-sealed-message)])
    :else
    (let [env (unwire msg)]
      (if (nil? env)
        (resolved [session (err :invalid-wire)])
        (-> (ratchet/decrypt-message (:ratchet session) env)
            (.then (fn [[r' pt]]
                     [(assoc session :ratchet r')
                      (reader/read-string (utf8-decode pt))])))))))

(defn accept
  "-> Promise<[session' plaintext-map] | {:error …}>."
  [bob-identity msg]
  (cond
    (:error msg) (resolved msg)
    (not (sealed/message? msg)) (resolved (err :not-a-sealed-message))
    (not (string? (get-in msg [:header :ek-pub]))) (resolved (err :missing-handshake))
    :else
    (let [h (:header msg)]
      (-> (x3dh/x3dh-respond bob-identity
                             (unb64 (:ik-pub h))
                             (unb64 (:ek-pub h))
                             (:opk-id h))
          (.then (fn [sk]
                   (-> (ratchet/init-receiver sk (:spk bob-identity))
                       (.then (fn [r]
                                (decrypt {:ok? true
                                          :role :responder
                                          :identity bob-identity
                                          :ratchet r}
                                         msg))))))))))

(defn store-msg
  [msg hash-fn]
  (cond
    (:error msg) msg
    (not (ifn? hash-fn)) (err :hash-fn-required)
    :else (sealed/store msg (hash-fn msg))))

(defn put-in-mailbox
  [mb stored head-fn]
  (cond
    (:error mb) mb
    (:error stored) stored
    (not= :stored-ciphertext (:kind stored)) (err :not-stored-ciphertext)
    :else
    (-> mb
        (sealed/append (:cid stored))
        (sealed/commit-head head-fn))))

(defn publish-head
  [name head-cid]
  (sealed/publish-head name head-cid))
