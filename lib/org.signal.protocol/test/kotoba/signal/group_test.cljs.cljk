(ns kotoba.signal.group-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotoba.signal.ratchet :as ratchet]
            [kotoba.signal.group :as group]))

(defn- utf8 [^string s] (.encode (js/TextEncoder.) s))
(defn- utf8-decode [^js b] (.decode (js/TextDecoder.) b))

(deftest distribution-message-verifies
  (let [sk (group/create-sender-key)
        dist (group/distribution-message sk 0)]
    (is (true? (group/verify-distribution dist)))))

(deftest forged-distribution-is-rejected
  (let [sk (group/create-sender-key)
        other (group/create-sender-key)
        dist (group/distribution-message sk 0)
        forged (assoc dist :chain-key (:chain-key other))] ; swap in a different chain-key, keep old sig
    (is (false? (group/verify-distribution forged)))))

(deftest sender-and-member-derive-identical-message-keys-in-lockstep
  (async done
    (let [sk (group/create-sender-key)
          dist (group/distribution-message sk 0)]
      (-> (group/sender-advance sk)
          (.then (fn [[sk1 sender-mk1]]
                   (-> (group/sender-advance sk1)
                       (.then (fn [[sk2 sender-mk2]]
                                (-> (group/sender-advance sk2)
                                    (.then (fn [[sk3 _sender-mk3]]
                                             (-> (group/member-derive (:chain-key dist))
                                                 (.then (fn [[ck1 member-mk1]]
                                                          (-> (group/member-derive ck1)
                                                              (.then (fn [[_ck2 member-mk2]]
                                                                       (is (ratchet/bytes= sender-mk1 member-mk1) "step 1 message keys agree")
                                                                       (is (ratchet/bytes= sender-mk2 member-mk2) "step 2 message keys agree")
                                                                       (is (some? sk3))
                                                                       (done)))))))))))))))))))

(deftest segment-encrypt-decrypt-roundtrip
  (async done
    (let [sk (group/create-sender-key)
          dist (group/distribution-message sk 0)
          segment (utf8 "aozora private segment #42")]
      (-> (js/Promise.all #js [(group/sender-advance sk) (group/member-derive (:chain-key dist))])
          (.then (fn [^js pair]
                   (let [[_sk1 sender-mk] (aget pair 0)
                         [_ck1 member-mk] (aget pair 1)]
                     (-> (group/encrypt-segment sender-mk segment)
                         (.then (fn [env] (group/decrypt-segment member-mk env)))
                         (.then (fn [pt] (is (= "aozora private segment #42" (utf8-decode pt))) (done)))))))))))

(deftest chain-forward-secrecy-distinct-keys-per-segment
  (async done
    (let [n 50]
      (letfn [(step [sk i acc]
                (if (= i n)
                  (do (is (= n (count (into #{} (map js/JSON.stringify) (map vec acc)))) "no two segment keys collide across 50 chain steps")
                      (done))
                  (-> (group/sender-advance sk)
                      (.then (fn [[sk' mk]] (step sk' (inc i) (conj acc mk)))))))]
        (step (group/create-sender-key) 0 [])))))

(deftest members-cannot-derive-without-a-valid-distribution
  (async done
    (let [sk (group/create-sender-key)
          bogus-chain-key (js/Uint8Array. 32)]
      ;; a member that never got a real distribution has no way to reach the
      ;; sender's actual chain position; its derived keys diverge immediately.
      (-> (js/Promise.all #js [(group/sender-advance sk) (group/member-derive bogus-chain-key)])
          (.then (fn [^js pair]
                   (let [[_sk1 real-mk] (aget pair 0)
                         [_ck bogus-mk] (aget pair 1)]
                     (is (not (ratchet/bytes= real-mk bogus-mk)))
                     (done))))))))
