(ns kotobase.server.security.credential-test
  (:require [cljs.test :refer-macros [deftest is testing]]
            [kotobase.server.security.credential :as cred]))

(def opts {:graph "acme" :biscuit-enabled-graphs #{"acme"}})

(deftest a-request-names-its-wire
  (is (= {:wire :cacao} (cred/select {:delegations_b64 ["x"]} opts)))
  (is (= {:wire :biscuit} (cred/select {:biscuit_b64 [1 2 3]} opts))))

(deftest presenting-both-is-refused-not-resolved
  (testing "preferring one silently makes the other decorative"
    (let [r (cred/select {:delegations_b64 ["x"] :biscuit_b64 [1]} opts)]
      (is (= :ambiguous-credential (:refused r)))
      (is (= #{:cacao :biscuit} (:presented r))))))

(deftest presenting-nothing-is-distinct-from-being-rejected
  (let [r (cred/select {} opts)]
    (is (nil? (:wire r)))
    (is (= :no-delegation-presented (:reason r)))
    (is (nil? (:refused r)))))

(deftest an-empty-field-is-not-a-presentation
  (testing "an empty list is what a client sends when it means none"
    (is (= :no-delegation-presented (:reason (cred/select {:delegations_b64 []} opts))))))

(deftest the-new-wire-is-off-unless-the-graph-is-listed
  (is (= :biscuit-not-enabled-for-graph
         (:refused (cred/select {:biscuit_b64 [1]} {:graph "other"
                                                    :biscuit-enabled-graphs #{"acme"}}))))
  (testing "and an absent allowlist means no graph, not every graph"
    (is (= :biscuit-not-enabled-for-graph
           (:refused (cred/select {:biscuit_b64 [1]} {:graph "acme"}))))))

(deftest a-failed-verification-does-not-become-a-retry
  (testing "the tempting cond that falls through to the other wire"
    (let [calls (atom [])
          verifiers {:biscuit (fn [_ _] (swap! calls conj :biscuit) nil)
                     :cacao (fn [_ _] (swap! calls conj :cacao)
                              {:effective-caps #{"kotoba://graph/acme"}})}
          r (cred/verify-with {:biscuit_b64 [1]} opts verifiers)]
      (is (= :verification-failed (:refused r)))
      (is (= :biscuit (:wire r)))
      (testing "and the other verifier was never reached"
        (is (= [:biscuit] @calls))))))

(deftest exactly-one-verifier-runs
  (let [calls (atom [])
        verifiers {:biscuit (fn [_ _] (swap! calls conj :biscuit)
                              {:effective-caps #{"kotoba://graph/acme"}})
                   :cacao (fn [_ _] (swap! calls conj :cacao) {:effective-caps #{"x"}})}
        r (cred/verify-with {:biscuit_b64 [1]} opts verifiers)]
    (is (= :biscuit (:wire r)))
    (is (= [:biscuit] @calls))))

(deftest a-wire-with-no-verifier-is-refused-rather-than-skipped
  (is (= :no-verifier-for-wire
         (:refused (cred/verify-with {:biscuit_b64 [1]} opts {:cacao (fn [_ _] nil)})))))

(deftest delegation-may-only-narrow
  (let [held #{"kotoba://graph/acme" "kotoba://can/read" "kotoba://can/admin"}]
    (is (= #{"kotoba://graph/acme" "kotoba://can/read"}
           (cred/effective-caps held {:effective-caps #{"kotoba://graph/acme"
                                                        "kotoba://can/read"}})))
    (testing "a delegation naming something never held confers nothing extra"
      (is (= #{"kotoba://graph/acme"}
             (cred/effective-caps held {:effective-caps #{"kotoba://graph/acme"
                                                          "kotoba://can/everything"}}))))
    (testing "and a refusal confers nothing at all"
      (is (= #{} (cred/effective-caps held {:refused :verification-failed}))))))
