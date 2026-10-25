(ns ayatori.disclosure-custody-test
  "The `:keys!` port with a custodian behind it.

  `ayatori.disclosure-open` makes custody a named seam, and a named seam with
  nothing behind it is still nothing behind it. Here the seam is
  `envelope.keystore`: records that hold public material and two wraps, a
  fingerprint derived from the keys rather than assigned to them, and an
  unlock secret supplied per call. What that buys is not the round trip --
  the previous test already had one -- but the refusals a store can make that
  a closure over a key cannot: an unknown recipient, a revoked one, and a
  device that is not unlocked."
  (:require [cljs.test :refer [deftest is testing async]]
            [ayatori.disclosure :as a]
            [ayatori.disclosure-fixture :as f]
            [ayatori.disclosure-open :as open]
            [envelope.keystore :as keystore]
            [envelope.sealed-key :as sealed-key]
            [kotobase.disclosure-grant :as d]
            [kotobase.execution-identity :as id]
            ["node:crypto" :as crypto]))

(def ^:private plaintext "the arrangement bytes nobody else may read")
(def ^:private unlock (js/Uint8Array.from (clj->js (repeat 32 3))))
(def ^:private locked (js/Uint8Array.from (clj->js (repeat 32 4))))

(defn- encrypt-content [^js content-key text]
  (let [iv (crypto/randomBytes 12)
        cipher (crypto/createCipheriv "aes-256-gcm" content-key iv)
        body (js/Buffer.concat #js [(.update cipher (js/Buffer.from text "utf8")) (.final cipher)])]
    (js/Buffer.concat #js [iv (.getAuthTag cipher) body])))

(defn- open-content! [{:keys [ciphertext key]}]
  (let [b (js/Buffer.from ciphertext)
        decipher (crypto/createDecipheriv "aes-256-gcm" (js/Buffer.from key) (.subarray b 0 12))]
    (.setAuthTag decipher (.subarray b 12 28))
    (js/Buffer.concat #js [(.update decipher (.subarray b 28)) (.final decipher)])))

(defn- issue
  "Issue a grant to IDENTITY over a freshly encrypted object, with the
  recipient's DERIVED fingerprint as :recipient-key -- which is what the
  protocol asks for and what the keystore can check.
  -> Promise<{:ciphertext :ctx :entry}>."
  [identity]
  (let [content-key (crypto/randomBytes 32)
        ciphertext (encrypt-content content-key plaintext)
        resource (d/ciphertext-cid ciphertext)
        fingerprint (:recipient-key identity)
        ctx (assoc f/context :resource resource :recipient-key fingerprint)
        g {:disclosure/version 1 :tenant "t" :owner "owner" :issuer "owner"
           :recipient "alice" :recipient-key fingerprint
           :resource resource :policy (:policy ctx)
           :operations #{:decrypt} :delegation-depth 2 :parent nil
           :not-before "2026-09-06T11:00:00Z"
           :expires-at "2026-09-06T13:00:00Z" :epoch 2}
        binding (d/binding g)]
    (-> (sealed-key/seal-key content-key identity binding)
        (.then (fn [frame]
                 (let [envelope {:envelope/provider {:provider/id :noble/ml-kem-768
                                                     :provider/fips-validated false}
                                 :envelope/algorithms [:x25519 :ml-kem-768 :aes-256-gcm]
                                 :envelope/kem? true :envelope/hybrid? true
                                 :envelope/epoch 2
                                 :envelope/binding binding
                                 :sealed/ciphertext (sealed-key/octets frame)}]
                   {:ciphertext ciphertext :ctx ctx
                    :entry {:grant (f/sign :disclosure-grant "owner"
                                           (assoc g :key-envelope-cid (id/value-cid envelope)))
                            :envelope envelope}}))))))

(defn- decryptor [{:keys [ctx entry]} keys!]
  (let [service (f/options [entry] ctx)]
    (a/recipient-decryptor-async
     {:crypto-policy f/policy
      :context! (fn [resource] (assoc ctx :resource resource))
      :request! (fn [_] (:request service))
      :deliver! (fn [request] (d/release-async! (assoc service :request request)))
      :verify! (fn [check] (js/Promise.resolve (f/verify check)))
      :open! (open/recipient-opener {:keys! keys! :open-content! open-content!})})))

(defn- reason [p]
  (letfn [(named [e] (when e (or (:ayatori.disclosure-open/reason (ex-data e))
                                 (:envelope.keystore/reason (ex-data e))
                                 (named (ex-cause e)))))]
    (-> (js/Promise.resolve p)
        (.then (fn [_] :no-rejection))
        (.catch (fn [e] (or (named e) :other))))))

(defn- enrolled
  "An identity, its stored record, and the issued grant over one object."
  []
  (-> (keystore/generate-identity)
      (.then (fn [identity]
               (js/Promise.all #js [identity
                                    (keystore/seal-record identity unlock nil)
                                    (issue identity)])))))

;; ── the round trip, through a real custodian ─────────────────────────────

(deftest an-unlocked-custodian-opens-the-object
  (async done
    (-> (enrolled)
        (.then (fn [[_ record issued]]
                 (let [keys! (keystore/unlocker {(:recipient-key record) record} unlock)]
                   ((decryptor issued keys!) (:ciphertext issued)))))
        (.then (fn [opened]
                 (is (= plaintext (.toString (js/Buffer.from opened) "utf8")))
                 (done)))
        (.catch (fn [e] (is false (str e)) (done))))))

(deftest the-grants-recipient-key-is-the-derived-fingerprint
  (testing "so the issuer and the custodian name the recipient the same way,
            from the same bytes, rather than agreeing to use the same label"
    (async done
      (-> (enrolled)
          (.then (fn [[identity record issued]]
                   (-> (keystore/fingerprint identity)
                       (.then (fn [fp]
                                (is (= fp (:recipient-key record)))
                                (is (= fp (get-in issued [:entry :grant :recipient-key])))
                                (is (= fp (:recipient-key (:ctx issued))))
                                (done))))))))))

;; ── what a custodian can refuse that a closure cannot ────────────────────

(deftest an-unknown-recipient-is-not-a-key
  (async done
    (-> (enrolled)
        (.then (fn [[_ _ issued]]
                 (reason ((decryptor issued (keystore/unlocker {} unlock))
                          (:ciphertext issued)))))
        (.then (fn [r] (is (= :no-key-for-recipient r)) (done))))))

(deftest a-revoked-recipient-is-refused-and-says-so
  (testing "and does not arrive as :no-key-for-recipient -- a revoked key is
            not an absent one, and an audit that cannot tell them apart
            cannot see a revocation take effect"
    (async done
      (-> (enrolled)
          (.then (fn [[_ record issued]]
                   (let [revoked (assoc record :key/status :revoked)
                         keys! (keystore/unlocker {(:recipient-key record) revoked} unlock)]
                     (reason ((decryptor issued keys!) (:ciphertext issued))))))
          (.then (fn [r] (is (= :key-not-active r)) (done)))))))

(deftest a-locked-device-opens-nothing
  (testing "the record is present and active; only the unlock secret is wrong"
    (async done
      (-> (enrolled)
          (.then (fn [[_ record issued]]
                   (let [keys! (keystore/unlocker {(:recipient-key record) record} locked)]
                     (-> ((decryptor issued keys!) (:ciphertext issued))
                         (.then (constantly false))
                         (.catch (constantly true))))))
          (.then (fn [rejected] (is (true? rejected)) (done)))))))

(deftest another-recipients-record-does-not-open-this-grant
  (testing "two enrolments, each valid, and the wrong one is still wrong"
    (async done
      (-> (js/Promise.all #js [(enrolled) (enrolled)])
          (.then (fn [[[_ _ issued] [_ bobs-record _]]]
                   ;; look bob's record up under alice's fingerprint: the
                   ;; keystore refuses on the derived name before any unwrap
                   (let [keys! (keystore/unlocker (constantly bobs-record) unlock)]
                     (reason ((decryptor issued keys!) (:ciphertext issued))))))
          (.then (fn [r]
                   ;; Named exactly. Accepting either this or the keystore's
                   ;; own :fingerprint-mismatch was measured 2026-09-06 to
                   ;; make the test insensitive: removing the keystore check
                   ;; left it green, because the opener's check caught it
                   ;; instead. Each check is asserted where it lives --
                   ;; :fingerprint-mismatch has its own tests in
                   ;; kotoba-lang/envelope.
                   (is (= :custody-returned-another-key r) (str "got " r))
                   (done)))))))
