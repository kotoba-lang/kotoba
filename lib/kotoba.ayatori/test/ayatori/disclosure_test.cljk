(ns ayatori.disclosure-test
  "Cross-repository contract test against the pinned public Kotobase API."
  (:require [cljs.test :refer [deftest is async]]
            [ayatori.disclosure :as a]
            [ayatori.remote :as remote]
            [arrangement.core :as arr]
            [kotobase.disclosure-grant :as d]
            [ayatori.disclosure-fixture :as f]
            ["node:crypto" :as crypto]))

(defn ports [service open!]
  {:crypto-policy f/policy
   :context! (fn [resource] (assoc f/context :resource resource))
   :request! (fn [_] (:request service))
   :deliver! (fn [request] (d/release-async! (assoc service :request request)))
   :verify! (fn [check] (js/Promise.resolve (f/verify check)))
   :open! open!})

(deftest synchronous-decryptor-refuses-promise-from-final-crypto-port
  (let [service (f/options)
        opts (assoc (ports service (fn [_] (js/Promise.resolve [9])))
                    :deliver! (fn [request] (d/release! (assoc service :request request)))
                    :verify! f/verify)]
    (is (thrown? js/Error ((a/recipient-decryptor opts) [1 2 3])))))

(deftest delivery-precedes-decryption-and-is-not-cached
  (async done
    (let [opened (atom 0) service (f/options)
          decrypt (a/recipient-decryptor-async
                   (ports service (fn [_] (swap! opened inc) (js/Promise.resolve [9]))))]
      (-> (decrypt [1 2 3])
          (.then (fn [result]
                   (is (= [9] result))
                   (is (= 1 @opened))
                   ;; Same ciphertext, but same nonce is not fresh authority.
                   (decrypt [1 2 3])))
          (.then (fn [_] (is false "replayed delivery decrypted")))
          (.catch (fn [_] (is (= 1 @opened))))
          (.finally done)))))

(deftest persistence-failure-prevents-open
  (async done
    (let [opened (atom 0)
          service (assoc (f/options) :read! (constantly nil))
          decrypt (a/recipient-decryptor-async
                   (ports service (fn [_] (swap! opened inc))))]
      (-> (decrypt [1 2 3])
          (.then (fn [_] (is false "opened without receipt")))
          (.catch (fn [_] (is (zero? @opened))))
          (.finally done)))))

(deftest changed-authority-during-delivery-prevents-open
  (async done
    (let [opened (atom 0) calls (atom 0)
          opts (assoc (ports (f/options) (fn [_] (swap! opened inc)))
                      :context! (fn [_] (if (= 1 (swap! calls inc)) f/context
                                          (assoc f/context :epoch 3))))]
      (-> ((a/recipient-decryptor-async opts) [1 2 3])
          (.then (fn [_] (is false "opened at a stale epoch")))
          (.catch (fn [_] (is (zero? @opened))))
          (.finally done)))))

(deftest substituted-recipient-envelope-prevents-open
  (async done
    (let [opened (atom 0) service (f/options)
          opts (assoc (ports service (fn [_] (swap! opened inc)))
                      :deliver! (fn [_] (-> (d/release-async! service)
                                           (.then #(assoc-in % [:key-envelope :sealed/ciphertext] [99])))))]
      (-> ((a/recipient-decryptor-async opts) [1 2 3])
          (.then (fn [_] (is false "opened a substituted key")))
          (.catch (fn [_] (is (zero? @opened))))
          (.finally done)))))

(deftest encrypted-arrangement-through-verified-remote-cursor
  (async done
    ;; Real AES-GCM content encryption. Envelope/authority ports use explicit
    ;; service fixtures; this does NOT qualify a hybrid KEM provider.
    (let [blocks (atom {}) services (atom {}) receipts (atom 0)
          key (crypto/randomBytes 32)
          encrypt (fn [bytes]
                    (let [iv (crypto/randomBytes 12)
                          cipher (crypto/createCipheriv "aes-256-gcm" key iv)
                          body (js/Buffer.concat #js [(.update cipher (js/Buffer.from bytes)) (.final cipher)])
                          ciphertext (js/Buffer.concat #js [iv (.getAuthTag cipher) body])
                          resource (d/ciphertext-cid ciphertext)
                          ctx (assoc f/context :resource resource)
                          service (f/options [(f/grant {:resource resource})] ctx)]
                      (swap! services assoc resource service)
                      (js/Promise.resolve ciphertext)))
          open! (fn [{:keys [ciphertext]}]
                  (let [b (js/Buffer.from ciphertext)
                        decipher (crypto/createDecipheriv "aes-256-gcm" key (.subarray b 0 12))]
                    (.setAuthTag decipher (.subarray b 12 28))
                    (js/Buffer.concat #js [(.update decipher (.subarray b 28)) (.final decipher)])))
          decrypt (a/recipient-decryptor-async
                   {:crypto-policy f/policy
                    :context! #(assoc f/context :resource %)
                    :request! (fn [ctx]
                                (let [s (get @services (:resource ctx))]
                                  (f/sign :disclosure-request "alice"
                                          (assoc (:request s) :nonce (str (random-uuid))))))
                    :deliver! (fn [request]
                                (-> (d/release-async! (assoc (get @services (:resource request)) :request request))
                                    (.then (fn [result] (swap! receipts inc) result))))
                    :verify! f/verify
                    :open! open!})
          put! (fn [cid bytes] (swap! blocks assoc cid bytes) (js/Promise.resolve cid))
          blind #(js/Promise.resolve (pr-str %))
          db (reduce arr/assert-quad (arr/empty-db)
                     [{:s "s1" :p "kind" :o "rare"}
                      {:s "s2" :p "kind" :o "common"}])]
      (-> (arr/commit! put! db nil arr/current-schema-version blind encrypt nil)
          (.then (fn [cid]
                   (remote/open-snapshot-async
                    {:snapshot-cid cid :blind-fn blind :decrypt-fn decrypt
                     :discover-fn (fn [wanted] {:ok? true :cid wanted :providers [{:peer "fixture"}]})
                     :fetch-fn (fn [_ wanted] (js/Promise.resolve (get @blocks wanted)))})))
          (.then (fn [opened]
                   (remote/q-async opened '{:find [?s] :where [[?s "kind" "rare"]]}
                                   (constantly true))))
          (.then (fn [rows]
                   (is (= #{["s1"]} rows))
                   (is (pos? @receipts))))
          (.catch #(is false (str %)))
          (.finally done)))))
