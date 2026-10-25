(ns kotoba.signal.x3dh-test
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [kotoba.signal.x3dh :as x3dh]))

(deftest bundle-signature-verifies
  (let [bob (x3dh/generate-identity)
        [bundle _bob'] (x3dh/publish-bundle bob)]
    (is (true? (x3dh/verify-bundle bundle)))))

(deftest tampered-bundle-signature-is-rejected
  (let [bob (x3dh/generate-identity)
        [bundle _] (x3dh/publish-bundle bob)
        other (x3dh/generate-identity)
        forged (assoc bundle :spk (:pub (:spk other)))] ; swap in an unsigned spk
    (is (false? (x3dh/verify-bundle forged)))))

(defn- run-session
  "Promise<{:alice-secret :bob-secret :opk-id}> — both sides of one X3DH
  session against `bundle` (already published from `bob`)."
  [alice bob bundle]
  (-> (x3dh/x3dh-initiate alice bundle)
      (.then (fn [{:keys [shared-secret ek-pub opk-id]}]
               (-> (x3dh/x3dh-respond bob (:pub (:ik alice)) ek-pub opk-id)
                   (.then (fn [bob-sk]
                            {:alice-secret shared-secret :bob-secret bob-sk :opk-id opk-id})))))))

(deftest x3dh-roundtrip-with-opk
  (async done
    (let [alice (x3dh/generate-identity)
          bob (x3dh/generate-identity)
          [bundle _bob'] (x3dh/publish-bundle bob)]
      (is (true? (x3dh/verify-bundle bundle)))
      (-> (run-session alice bob bundle)
          (.then (fn [{:keys [alice-secret bob-secret opk-id]}]
                   (is (some? opk-id) "bob published an opk, so alice should have consumed one")
                   (is (= 32 (.-length alice-secret)))
                   ;; = on (seq typed-array) is unreliable across two DIFFERENT
                   ;; Uint8Array instances in this cljs runtime even with equal
                   ;; content (confirmed empirically — vec gives real structural
                   ;; equality; do not revert to seq here or in the other
                   ;; secret-comparison assertions in this file).
                   (is (= (vec alice-secret) (vec bob-secret))
                       "alice's x3dh-initiate and bob's x3dh-respond must derive the identical secret")
                   (done)))))))

(deftest x3dh-roundtrip-without-opk
  (async done
    (let [alice (x3dh/generate-identity)
          bob (x3dh/generate-identity 0) ; no one-time prekeys
          [bundle _] (x3dh/publish-bundle bob)]
      (is (nil? (:opk bundle)))
      (-> (run-session alice bob bundle)
          (.then (fn [{:keys [alice-secret bob-secret opk-id]}]
                   (is (nil? opk-id))
                   (is (= (vec alice-secret) (vec bob-secret)))
                   (done)))))))

(deftest different-sessions-produce-different-secrets
  (async done
    (let [alice (x3dh/generate-identity)
          bob (x3dh/generate-identity)
          [bundle bob'] (x3dh/publish-bundle bob)
          [bundle2 _] (x3dh/publish-bundle bob')]
      (-> (js/Promise.all #js [(run-session alice bob bundle) (run-session alice bob' bundle2)])
          (.then (fn [^js pair]
                   (let [s1 (:alice-secret (aget pair 0))
                         s2 (:alice-secret (aget pair 1))]
                     (is (not= (vec s1) (vec s2))
                         "fresh ephemeral key + fresh opk per session => independent secrets")
                     (done))))))))

(deftest opk-pool-is-consumed-one-at-a-time
  (testing "publish-bundle pops exactly one opk and doesn't repeat it"
    (let [bob (x3dh/generate-identity 3)
          [b1 bob1] (x3dh/publish-bundle bob)
          [b2 bob2] (x3dh/publish-bundle bob1)
          [b3 bob3] (x3dh/publish-bundle bob2)]
      (is (= [0 1 2] [(:opk-id b1) (:opk-id b2) (:opk-id b3)]))
      (is (empty? (:opks bob3))))))
