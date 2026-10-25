(ns aozora.pds.prekeys-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotoba.lang.text :as str]
            [kotobase.client :as kc]
            [aozora.appview.prekeys :as appview-prekeys]
            [aozora.pds.prekeys :as prekeys]))

(defn- stub-transact [sink]
  (fn ([_ _ tx] (reset! sink tx) (js/Promise.resolve #js {}))
      ([_ _ tx _] (reset! sink tx) (js/Promise.resolve #js {}))))

(defn- tx-record-json
  "Decode the :atproto.record/jsonB64 payload out of a captured tx_edn string
  (record JSON is base64 on the wire — kotobase tx_edn brace-split
  workaround), same helper aozora.pds.convo-test uses."
  [tx]
  (some->> (re-find #":atproto\.record/jsonB64 \"([^\"]+)\"" (or tx ""))
           second
           (#(.toString (js/Buffer.from % "base64") "utf-8"))))

;; register-prekeys' conflict check only runs when `_env` is non-nil (see
;; aozora.pds.prekeys/existing-bundle) — fake env is just a marker object,
;; the stubbed get-prekey-bundle below ignores the real client/db it'd derive.
(def ^:private fake-env #js {})

(deftest register-prekeys-persists-bundle-under-fixed-rkey
  (async done
    (let [tx (atom nil)
          orig kc/transact]
      (set! kc/transact (stub-transact tx))
      (-> (prekeys/register-prekeys nil "yoro-social"
                                    {:_auth-did "did:web:alice"
                                     :identityKey "aWs"
                                     :signedPreKey "c3Br"
                                     :signedPreKeySig "c2ln"
                                     :signedPreKeyId 1})
          (.then (fn [res]
                   (is (= "did:web:alice" (:did res)))
                   (is (str/starts-with? (:uri res) "at://did:web:alice/app.aozora.convo.prekeyBundle/self"))
                   (is (str/includes? @tx ":atproto.record/collection \"app.aozora.convo.prekeyBundle\""))
                   (is (str/includes? @tx "self"))))
          (.finally (fn [] (set! kc/transact orig) (done)))))))

(deftest register-prekeys-persists-one-time-prekey-pool
  (async done
    (let [tx (atom nil)
          orig kc/transact]
      (set! kc/transact (stub-transact tx))
      (-> (prekeys/register-prekeys nil "yoro-social"
                                    {:_auth-did "did:web:alice"
                                     :identityKey "aWs"
                                     :signedPreKey "c3Br"
                                     :signedPreKeySig "c2ln"
                                     :signedPreKeyId 1
                                     :oneTimePreKeys ["b3BrMQ" "b3BrMg" "b3BrMw"]})
          (.then (fn [res]
                   (is (= "did:web:alice" (:did res)))
                   (is (str/includes? (tx-record-json @tx) "oneTimePreKeys"))
                   (is (str/includes? (tx-record-json @tx) "b3BrMQ"))))
          (.finally (fn [] (set! kc/transact orig) (done)))))))

(deftest register-prekeys-omits-empty-one-time-prekey-pool
  (async done
    (let [tx (atom nil)
          orig kc/transact]
      (set! kc/transact (stub-transact tx))
      (-> (prekeys/register-prekeys nil "yoro-social"
                                    {:_auth-did "did:web:alice"
                                     :identityKey "aWs"
                                     :signedPreKey "c3Br"
                                     :signedPreKeySig "c2ln"
                                     :signedPreKeyId 1
                                     :oneTimePreKeys []})
          (.then (fn [_]
                   (is (not (str/includes? (tx-record-json @tx) "oneTimePreKeys"))
                       "an empty pool is omitted, not stored as []")))
          (.finally (fn [] (set! kc/transact orig) (done)))))))

(deftest register-prekeys-rejects-without-auth
  (async done
    (-> (prekeys/register-prekeys nil "yoro-social"
                                  {:identityKey "aWs" :signedPreKey "c3Br"
                                   :signedPreKeySig "c2ln" :signedPreKeyId 1})
        (.then (fn [res]
                 (is (= "InvalidRequest" (:error res)))
                 (done))))))

(deftest register-prekeys-rejects-incomplete-bundle
  (async done
    (-> (prekeys/register-prekeys nil "yoro-social"
                                  {:_auth-did "did:web:alice" :identityKey "aWs"})
        (.then (fn [res]
                 (is (= "InvalidRequest" (:error res)))
                 (done))))))

(deftest register-prekeys-rejects-different-identity-without-force
  (async done
    (let [orig-transact kc/transact
          orig-lookup appview-prekeys/get-prekey-bundle]
      (set! kc/transact (stub-transact (atom nil)))
      (set! appview-prekeys/get-prekey-bundle
            (fn [_ _ _] (js/Promise.resolve {:found true :identityKey "OLD-DEVICE-IK"})))
      (-> (prekeys/register-prekeys nil "yoro-social"
                                    {:_auth-did "did:web:alice" :_env fake-env
                                     :identityKey "NEW-DEVICE-IK" :signedPreKey "c3Br"
                                     :signedPreKeySig "c2ln" :signedPreKeyId 1})
          (.then (fn [res] (is (= "IdentityConflict" (:error res)))))
          (.finally (fn [] (set! kc/transact orig-transact)
                      (set! appview-prekeys/get-prekey-bundle orig-lookup)
                      (done)))))))

(deftest register-prekeys-allows-same-identity-rotation
  (async done
    (let [tx (atom nil)
          orig-transact kc/transact
          orig-lookup appview-prekeys/get-prekey-bundle]
      (set! kc/transact (stub-transact tx))
      (set! appview-prekeys/get-prekey-bundle
            (fn [_ _ _] (js/Promise.resolve {:found true :identityKey "SAME-IK"})))
      (-> (prekeys/register-prekeys nil "yoro-social"
                                    {:_auth-did "did:web:alice" :_env fake-env
                                     :identityKey "SAME-IK" :signedPreKey "new-spk"
                                     :signedPreKeySig "c2ln" :signedPreKeyId 2})
          (.then (fn [res] (is (nil? (:error res))) (is (= "did:web:alice" (:did res)))))
          (.finally (fn [] (set! kc/transact orig-transact)
                      (set! appview-prekeys/get-prekey-bundle orig-lookup)
                      (done)))))))

(deftest register-prekeys-force-overwrites-different-identity
  (async done
    (let [tx (atom nil)
          orig-transact kc/transact
          orig-lookup appview-prekeys/get-prekey-bundle]
      (set! kc/transact (stub-transact tx))
      (set! appview-prekeys/get-prekey-bundle
            (fn [_ _ _] (js/Promise.resolve {:found true :identityKey "OLD-DEVICE-IK"})))
      (-> (prekeys/register-prekeys nil "yoro-social"
                                    {:_auth-did "did:web:alice" :_env fake-env :force true
                                     :identityKey "NEW-DEVICE-IK" :signedPreKey "c3Br"
                                     :signedPreKeySig "c2ln" :signedPreKeyId 1})
          (.then (fn [res] (is (nil? (:error res))) (is (= "did:web:alice" (:did res)))))
          (.finally (fn [] (set! kc/transact orig-transact)
                      (set! appview-prekeys/get-prekey-bundle orig-lookup)
                      (done)))))))
