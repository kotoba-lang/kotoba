(ns aozora.pds.actor-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotoba.lang.text :as str]
            [kotobase.client :as kc]
            [aozora.pds.actor :as actor]))

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

(deftest block-persists-under-callers-own-repo-with-deterministic-rkey
  (async done
    (let [tx (atom nil)
          orig kc/transact]
      (set! kc/transact (stub-transact tx))
      (-> (actor/block nil "yoro-social"
                       {:_auth-did "did:web:alice" :blockedDid "did:web:mallory"})
          (.then (fn [res]
                   (is (= "did:web:alice" (:did res)))
                   (is (= "did:web:mallory" (:blockedDid res)))
                   (is (str/starts-with? (:uri res) "at://did:web:alice/app.aozora.actor.block/did:web:mallory")
                       "rkey is the blockedDid itself — re-blocking replaces, not accumulates")
                   (is (str/includes? @tx ":atproto.record/collection \"app.aozora.actor.block\""))
                   (is (str/includes? (tx-record-json @tx) "\"blockedDid\":\"did:web:mallory\""))))
          (.finally (fn [] (set! kc/transact orig) (done)))))))

(deftest block-rejects-without-auth
  (async done
    (-> (actor/block nil "yoro-social" {:blockedDid "did:web:mallory"})
        (.then (fn [res]
                 (is (= "InvalidRequest" (:error res)))
                 (done))))))

(deftest block-rejects-without-blocked-did
  (async done
    (-> (actor/block nil "yoro-social" {:_auth-did "did:web:alice"})
        (.then (fn [res]
                 (is (= "InvalidRequest" (:error res)))
                 (done))))))

(deftest unblock-deletes-the-record-under-the-same-deterministic-rkey
  (async done
    (let [tx (atom nil)
          orig kc/transact]
      (set! kc/transact (stub-transact tx))
      (-> (actor/unblock nil "yoro-social"
                         {:_auth-did "did:web:alice" :blockedDid "did:web:mallory"})
          (.then (fn [res]
                   (is (= "did:web:alice" (:did res)))
                   (is (= "did:web:mallory" (:blockedDid res)))))
          (.finally (fn [] (set! kc/transact orig) (done)))))))

(deftest unblock-rejects-without-auth
  (async done
    (-> (actor/unblock nil "yoro-social" {:blockedDid "did:web:mallory"})
        (.then (fn [res]
                 (is (= "InvalidRequest" (:error res)))
                 (done))))))
