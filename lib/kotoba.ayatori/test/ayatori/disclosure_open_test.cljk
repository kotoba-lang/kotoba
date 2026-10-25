(ns ayatori.disclosure-open-test
  "Key delivery with a real key.

  Every disclosure test before this one handed `:open!` a closure that
  already held the content key. That proves the delivery protocol -- the
  chain, the nonce, the receipt -- and proves nothing about the delivery of
  a key, because there was no key in flight. Here the content key exists
  once, is wrapped to a hybrid recipient under `binding(grant)`, travels as
  the grant's `:sealed/ciphertext`, and is recovered through the qualified
  provider or not at all."
  (:require [cljs.test :refer [deftest is testing async]]
            [ayatori.disclosure :as a]
            [ayatori.disclosure-fixture :as f]
            [ayatori.disclosure-open :as open]
            [envelope.kem :as kem]
            [envelope.sealed-key :as sealed-key]
            [kotoba.signal.x25519 :as x25519]
            [kotobase.disclosure-grant :as d]
            [kotobase.execution-identity :as id]
            ["node:crypto" :as crypto]))

;; ── a real recipient, a real object ──────────────────────────────────────

(defn- recipient [fingerprint]
  (let [x (x25519/generate-keypair)
        pq (kem/generate-keypair)]
    {:recipient-key fingerprint
     :pub (:pub x) :priv (:priv x)
     :pq-pub (:pub pq) :pq-priv (:priv pq)}))

(def ^:private plaintext "the arrangement bytes nobody else may read")

(defn- encrypt-content
  "iv || tag || body, AES-256-GCM. The framing is the writer's, which is why
  `:open-content!` is a port and not something the opener decides."
  [^js content-key text]
  (let [iv (crypto/randomBytes 12)
        cipher (crypto/createCipheriv "aes-256-gcm" content-key iv)
        body (js/Buffer.concat #js [(.update cipher (js/Buffer.from text "utf8")) (.final cipher)])]
    (js/Buffer.concat #js [iv (.getAuthTag cipher) body])))

(defn- open-content! [{:keys [ciphertext key]}]
  (let [b (js/Buffer.from ciphertext)
        decipher (crypto/createDecipheriv "aes-256-gcm" (js/Buffer.from key) (.subarray b 0 12))]
    (.setAuthTag decipher (.subarray b 12 28))
    (js/Buffer.concat #js [(.update decipher (.subarray b 28)) (.final decipher)])))

(defn- entry-for
  "Build one grant and its envelope in the order docs/disclosure-grants.edn
  gives: fields, then binding, then seal, then the envelope CID, then the
  signature over a grant that names it. -> Promise<{:entry :ciphertext :ctx}>."
  ([who] (entry-for who who))
  ([sealed-to signed-for]
   (let [content-key (crypto/randomBytes 32)
         ciphertext (encrypt-content content-key plaintext)
         resource (d/ciphertext-cid ciphertext)
         ctx (assoc f/context :resource resource
                    :recipient-key (:recipient-key signed-for))
         g {:disclosure/version 1 :tenant "t" :owner "owner" :issuer "owner"
            :recipient "alice" :recipient-key (:recipient-key signed-for)
            :resource resource :policy (:policy ctx)
            :operations #{:decrypt} :delegation-depth 2 :parent nil
            :not-before "2026-09-06T11:00:00Z"
            :expires-at "2026-09-06T13:00:00Z" :epoch 2}
         binding (d/binding g)]
     (-> (sealed-key/seal-key content-key sealed-to binding)
         (.then (fn [frame]
                  (let [envelope {:envelope/provider {:provider/id :noble/ml-kem-768
                                                      :provider/fips-validated false}
                                  :envelope/algorithms [:x25519 :ml-kem-768 :aes-256-gcm]
                                  :envelope/kem? true :envelope/hybrid? true
                                  :envelope/epoch 2
                                  :envelope/binding binding
                                  :sealed/ciphertext (sealed-key/octets frame)}]
                    {:ciphertext ciphertext
                     :ctx ctx
                     :entry {:grant (f/sign :disclosure-grant "owner"
                                            (assoc g :key-envelope-cid (id/value-cid envelope)))
                             :envelope envelope}})))))))

(defn- decryptor [{:keys [ctx entry]} opener]
  (let [service (f/options [entry] ctx)]
    (a/recipient-decryptor-async
     {:crypto-policy f/policy
      :context! (fn [resource] (assoc ctx :resource resource))
      :request! (fn [_] (:request service))
      :deliver! (fn [request] (d/release-async! (assoc service :request request)))
      :verify! (fn [check] (js/Promise.resolve (f/verify check)))
      :open! opener})))

(defn- opener-for [& holders]
  (let [by-fingerprint (into {} (map (juxt :recipient-key identity)) holders)]
    (open/recipient-opener {:keys! (fn [fingerprint] (get by-fingerprint fingerprint))
                            :open-content! open-content!})))

(defn- fails [p]
  (-> (js/Promise.resolve p) (.then (fn [_] false)) (.catch (fn [_] true))))

(defn- reason
  "The refusal a rejection names, unwrapped.

  nbb evaluates this through SCI, which wraps a thrown ex-info in one of its
  own carrying `:type :sci/error` and puts the original in `ex-cause`. A test
  that read only the outer `ex-data` would see no reason on every refusal and
  report the same `:other` whether the code named its reason or not -- which
  is the difference these tests exist to check."
  [p]
  (letfn [(named [e]
            (when e
              (or (:ayatori.disclosure-open/reason (ex-data e))
                  (named (ex-cause e)))))]
    (-> (js/Promise.resolve p)
        (.then (fn [_] :no-rejection))
        (.catch (fn [e] (or (named e) :other))))))

;; ── the round trip ───────────────────────────────────────────────────────

(deftest a-wrapped-content-key-is-delivered-and-opens-the-object
  (async done
    (let [alice (recipient "alice-encryption-key")]
      (-> (entry-for alice)
          (.then (fn [{:keys [ciphertext] :as built}]
                   ((decryptor built (opener-for alice)) ciphertext)))
          (.then (fn [opened]
                   (is (= plaintext (.toString (js/Buffer.from opened) "utf8")))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest the-recovered-key-reaches-open-content-and-nothing-else
  (async done
    (let [alice (recipient "alice-encryption-key")
          seen (atom [])
          opener (open/recipient-opener
                  {:keys! (constantly alice)
                   :open-content! (fn [{:keys [ciphertext key]}]
                                    (swap! seen conj key)
                                    (open-content! {:ciphertext ciphertext :key key}))})]
      (-> (entry-for alice)
          (.then (fn [{:keys [ciphertext] :as built}]
                   ((decryptor built opener) ciphertext)))
          (.then (fn [opened]
                   (is (= plaintext (.toString (js/Buffer.from opened) "utf8")))
                   (is (= 1 (count @seen)) "the key is handed over exactly once")
                   (testing "and it is not the object's plaintext, nor returned"
                     (is (= 32 (.-length ^js (first @seen))))
                     (is (not= plaintext (.toString (js/Buffer.from opened) "utf8")
                               (str (first @seen)))))
                   (testing "wiped once the content is out -- best effort, but the
                             longest-lived copy is the one this can reach"
                     (is (every? zero? (array-seq (first @seen)))))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

;; ── the refusals ─────────────────────────────────────────────────────────

(deftest custody-with-no-key-for-the-fingerprint-refuses
  (async done
    (let [alice (recipient "alice-encryption-key")]
      (-> (entry-for alice)
          (.then (fn [{:keys [ciphertext] :as built}]
                   (reason ((decryptor built (opener-for)) ciphertext))))
          (.then (fn [r]
                   (is (= :no-key-for-recipient r))
                   (done)))))))

(deftest custody-that-returns-a-different-key-is-refused-by-name
  (testing "not four steps later as an AEAD failure that looks like forgery"
    (async done
      (let [alice (recipient "alice-encryption-key")
            bob (recipient "bob-encryption-key")
            opener (open/recipient-opener {:keys! (constantly bob)
                                           :open-content! open-content!})]
        (-> (entry-for alice)
            (.then (fn [{:keys [ciphertext] :as built}]
                     (reason ((decryptor built opener) ciphertext))))
            (.then (fn [r]
                     (is (= :custody-returned-another-key r))
                     (done))))))))

(deftest another-recipients-wrap-does-not-open
  (testing "the fingerprints agree; only the keys differ"
    (async done
      (let [alice (recipient "alice-encryption-key")
            impostor (assoc (recipient "x") :recipient-key "alice-encryption-key")]
        (-> (entry-for alice)
            (.then (fn [{:keys [ciphertext] :as built}]
                     (fails ((decryptor built (opener-for impostor)) ciphertext))))
            (.then (fn [rejected] (is (true? rejected)) (done))))))))

(deftest a-tampered-wrapped-key-does-not-open
  (async done
    (let [alice (recipient "alice-encryption-key")]
      (-> (entry-for alice)
          (.then (fn [{:keys [ciphertext ctx entry]}]
                   (let [broken (update-in entry [:envelope :sealed/ciphertext]
                                           (fn [octets]
                                             (update octets 40 #(bit-xor % 1))))
                         ;; the grant commits to the envelope CID, so a
                         ;; tampered envelope is refused before any crypto;
                         ;; re-sign it so the wrap itself is what is on trial
                         g (dissoc (:grant entry) :signature :key-envelope-cid)
                         regrant (f/sign :disclosure-grant "owner"
                                         (assoc g :key-envelope-cid
                                                (id/value-cid (:envelope broken))))]
                     (fails ((decryptor {:ctx ctx :entry {:grant regrant
                                                          :envelope (:envelope broken)}}
                                        (opener-for alice))
                             ciphertext)))))
          (.then (fn [rejected] (is (true? rejected)) (done)))))))

(deftest an-empty-binding-is-refused-rather-than-used
  (testing "an absent AAD is not a weaker binding, it is none"
    (async done
      (let [alice (recipient "alice-encryption-key")
            opener (opener-for alice)]
        (-> (entry-for alice)
            (.then (fn [{:keys [ciphertext entry]}]
                     (reason (opener {:ciphertext ciphertext
                                      :key-envelope (:envelope entry)
                                      :binding ""
                                      :recipient-key "alice-encryption-key"}))))
            (.then (fn [r] (is (= :missing-binding r)) (done))))))))

(deftest the-ports-are-required
  (is (thrown? js/Error (open/recipient-opener {})))
  (is (thrown? js/Error (open/recipient-opener {:keys! (constantly nil)})))
  (is (thrown? js/Error (open/recipient-opener {:keys! (constantly nil)
                                                :open-content! open-content!
                                                :extra :port})))
  (is (thrown? js/Error (open/recipient-opener {:keys! :not-a-fn
                                                :open-content! open-content!}))))
